"""Play the packaged ten-stop route through keyboard and button events in Chromium."""
import argparse
import functools
import hashlib
import http.server
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import threading
import time

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from build_courier_production import render

OUT = ROOT / 'test-results/courier-campaign'
KEY = 'isegye:playground:courier:v2'
PREFS = 'isegye:archive:prefs:v1'
LEGACY_THEME = 'isegye:theme:v1'

# Record the source actually painted into the scrolling field and its overview.
# Keep a few image names per stage instead of copying large data URIs or frames.
PAINT_OBSERVER = """() => {
  const names = new WeakMap(), drawImage = CanvasRenderingContext2D.prototype.drawImage;
  window.courierPaint = {};
  CanvasRenderingContext2D.prototype.drawImage = function(image, ...args) {
    const result = drawImage.call(this, image, ...args);
    if (this.canvas.id !== 'arena' || !(image instanceof HTMLImageElement)) return result;
    if (!names.has(image)) {
      names.set(image, Object.entries(COURIER_ART).find(([,uri]) => uri === image.src)?.[0]);
    }
    const name = names.get(image);
    if (name === 'walk' && args.length === 8 && window.courierWalkSample) {
      const frame = Math.round(args[0] * 4 / image.naturalWidth);
      const row = Math.round(args[1] * 6 / image.naturalHeight);
      window.courierWalkSample.add(row * 4 + frame);
    }
    if (name === 'standing' && args.length === 8 && window.courierStandingSample) {
      const col = Math.round(args[0] * 3 / image.naturalWidth);
      const row = Math.round(args[1] * 2 / image.naturalHeight);
      window.courierStandingSample.add(row * 3 + col);
    }
    if (name === 'plaza' || /^stage[0-9]+$/.test(name)) {
      const stage = CourierApp.state.stage, entry = courierPaint[stage] ??= {field:{}, overview:{}};
      if (args.length === 8) entry.field[name] = true;
      if (args.length === 4) entry.overview[name] = true;
    }
    return result;
  };
}"""

# Advance Chromium's clock and send the same keys as a player. Game state is
# observed only. Choosing equipment still goes through real, visible buttons.
DRIVER = """stopAfterFirstLetter => {
  const held = new Set();
  function key(code, down) {
    document.getElementById('arena').dispatchEvent(new KeyboardEvent(down ? 'keydown' : 'keyup', {code, bubbles:true}));
  }
  function steer(x, y) {
    const angle = Math.atan2(y,x), moving = Math.hypot(x,y) > 3;
    for (const [code, amount] of [['KeyD',Math.cos(angle)],['KeyA',-Math.cos(angle)],
                                  ['KeyS',Math.sin(angle)],['KeyW',-Math.sin(angle)]]) {
      const down = moving && amount > .38;
      if (down !== held.has(code)) { key(code,down); if(down) held.add(code); else held.delete(code); }
    }
  }
  function follow() {
    const s = CourierApp.state;
    if (stopAfterFirstLetter && s?.stats.letters > 0) { steer(0,0); return; }
    if (s?.mode === 'playing' && !CourierApp.paused && document.querySelector('#stage-arrival').hidden) {
      const dist = o => Math.hypot(o.x-s.x,o.y-s.y);
      const letters = s.stars.filter(o => o.availableAt <= s.elapsed).sort((a,b)=>dist(a)-dist(b));
      const point = s.cargo < s.required && letters.length ? letters[0] : s.beacon;
      const range = Math.max(dist(point),1);
      let x=(point.x-s.x)/range, y=(point.y-s.y)/range;
      let closest=Infinity, dodge=false;
      if (s.boss && (s.cargo >= s.required || dist(s.boss)<255)) {
        const bx=s.boss.x-s.x, by=s.boss.y-s.y, gap=dist(s.boss) || 1;
        const radial=Math.max(-1,Math.min(1,(gap-185)/65));
        x=(bx*radial-by*.55)/gap;
        y=(by*radial+bx*.55)/gap;
      }
      for (const enemy of s.enemies) {
        const gap = Math.max(1,dist(enemy));
        if (enemy.spawnTime>0 || enemy.stunTime>0) continue;
        closest=Math.min(closest,gap);
        if (gap<67) {
          x+=(s.x-enemy.x)/gap*(67-gap)/32;
          y+=(s.y-enemy.y)/gap*(67-gap)/32;
        }
      }
      for (const h of s.hazards) {
        const ex=s.x-h.x, ey=s.y-h.y, gap=dist(h) || 1;
        if (h.kind==='circle' && h.delay<.7 && gap<h.radius+38) {
          x+=ex/gap*2.2; y+=ey/gap*2.2;
        }
        if (h.kind==='ring' && h.delay<.3 && gap>=h.innerRadius-12 && gap<h.radius+65) {
          x=ex/gap; y=ey/gap; dodge=true;
        }
        if (h.kind==='line') {
          const cos=Math.cos(h.angle), sin=Math.sin(h.angle);
          const side=-ex*sin+ey*cos, ahead=ex*cos+ey*sin;
          if (ahead>0 && ahead<h.length && Math.abs(side)<h.width/2+30) {
            x-=sin*Math.sign(side||1)*2; y+=cos*Math.sign(side||1)*2;
          }
        }
      }
      steer(x*100, y*100);
      if (s.skillCooldown <= 0 && (dodge || closest<130 || s.hearts<3)) {
        key('KeyE',true); key('KeyE',false);
      }
      if (s.dashCooldown<=0 && (dodge || (!s.boss && (closest<85 || range>150)))) {
        key('Space',true); key('Space',false);
      }
    } else steer(0,0);
    requestAnimationFrame(follow);
  }
  follow();
}"""


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def painted_fonts(page, samples):
    """Ask Chromium which face supplied glyphs for visible Korean text."""
    page.evaluate('document.fonts.ready.then(() => true)')
    cdp = page.context.new_cdp_session(page)
    matches = {}
    try:
        cdp.send('DOM.enable')
        cdp.send('CSS.enable')
        root = cdp.send('DOM.getDocument')['root']['nodeId']
        for selector, expected in samples.items():
            element = page.locator(selector).first
            expect(element).to_be_visible()
            direct = element.evaluate("""el => [...el.childNodes].filter(c => c.nodeType===3)
                                       .map(c => c.textContent).join('')""")
            korean = len(re.findall(r'[가-힣]', direct))
            node = cdp.send('DOM.querySelector', {'nodeId': root, 'selector': selector})['nodeId']
            fonts = cdp.send('CSS.getPlatformFontsForNode', {'nodeId': node})['fonts']
            count = sum(face['glyphCount'] for face in fonts if face['isCustomFont'] and
                        expected.replace(' ', '').lower() in
                        (face['familyName'] + '/' + face.get('postScriptName', '')).replace(' ', '').lower())
            assert korean and count >= korean, (selector, direct, expected, fonts)
            matches[selector] = {'family': expected, 'paintedGlyphs': count}
    finally:
        cdp.detach()
    return matches


def check_appearance(page, touch):
    def press(selector):
        element = page.locator(selector)
        element.tap() if touch else element.click()

    def theme(value):
        expect(page.locator('html')).to_have_attribute('data-theme', value)
        expect(page.locator('#theme-button')).to_have_attribute('aria-pressed', str(value == 'dark').lower())
        return page.locator('body').evaluate("el => getComputedStyle(el).backgroundImage")

    # An existing site preference wins over both legacy storage and system theme.
    page.emulate_media(color_scheme='light')
    page.evaluate("""([prefs, legacy]) => {
      localStorage.setItem(prefs, JSON.stringify({theme:'dark', compact:true}));
      localStorage.setItem(legacy, 'light');
    }""", [PREFS, LEGACY_THEME])
    page.reload()
    expect(page.locator('#start-button')).to_be_enabled()
    dark = theme('dark')
    fonts = painted_fonts(page, {'.hero-copy h1': 'Jua', '.hero-copy .story': 'Gowun Dodum'})
    press('#theme-button')
    assert theme('light') != dark
    assert page.evaluate('k=>JSON.parse(localStorage.getItem(k))', PREFS) == {'theme': 'light', 'compact': True}
    page.reload()
    expect(page.locator('#start-button')).to_be_enabled()
    theme('light')
    press('#settings-button')
    expect(page.locator('#how-dialog')).to_be_visible()
    fonts.update(painted_fonts(page, {'#help-title': 'Jua', 'label[for=theme-setting]': 'Gowun Dodum'}))
    press('details.font-licenses summary')
    credits = page.locator('details.font-licenses')
    notices = credits.locator('pre').all_text_contents()
    assert len(notices) == 2 and credits.locator('h3').count() == 2
    for filename in ('GowunDodum-OFL.txt', 'Jua-OFL.txt'):
        original = (ROOT / 'rpg' / 'fonts' / filename).read_text(encoding='utf-8-sig').strip()
        assert original in [notice.strip() for notice in notices], filename
    page.locator('#theme-setting').select_option('system')
    assert page.evaluate('k=>JSON.parse(localStorage.getItem(k))', PREFS) == {'compact': True}
    assert page.evaluate('k=>localStorage.getItem(k)', LEGACY_THEME) is None
    page.emulate_media(color_scheme='dark')
    theme('dark')
    press('#close-how')
    # A legacy-only preference still overrides the system through a reload.
    page.evaluate("""([prefs,legacy]) => {
      localStorage.removeItem(prefs);
      localStorage.setItem(legacy,'light');
    }""", [PREFS, LEGACY_THEME])
    page.reload()
    expect(page.locator('#start-button')).to_be_enabled()
    theme('light')
    press('#theme-button')
    theme('dark')
    assert page.evaluate('k=>localStorage.getItem(k)', LEGACY_THEME) == 'dark'
    assert page.evaluate('k=>localStorage.getItem(k)', PREFS) is None
    page.reload()
    expect(page.locator('#start-button')).to_be_enabled()
    theme('dark')
    return fonts


def check_arrival(page, index, previous=None, chosen=None):
    expect(page.locator('#stage-arrival')).to_be_visible()
    state = page.evaluate("""() => {
      const s=CourierApp.state, r=CourierEngine.ROUTES[s.stage];
      return {stage:s.stage, entrance:[s.x,s.y], expected:[r.start.x,r.start.y],
        beacon:[s.beacon.x,s.beacon.y], expectedBox:[r.beacon.x,r.beacon.y],
        title:r.name, brief:r.brief, deliveries:s.deliveries, cargo:s.cargo, goal:s.required,
        required:r.goal, times:[s.stageElapsed,s.timeLeft,r.time], hearts:s.hearts, score:s.score,
        gear:s.upgrades, live:s.projectiles.length+s.hazards.length, paint:courierPaint[s.stage],
        effects:[s.shieldTime,s.slowTime,s.hasteTime,s.magnetTime,s.dashTime,s.combo],
        objects:[...s.stars,...s.enemies,...(s.boss?[s.boss]:[])].map(p=>p.id)};
    }""")
    assert state['stage'] == state['deliveries'] == index, state
    assert state['entrance'] == state['expected'] and state['beacon'] == state['expectedBox']
    assert state['cargo'] == state['live'] == state['times'][0] == 0 and not any(state['effects'])
    assert state['goal'] == state['required'] and state['times'][1] == state['times'][2]
    expect(page.locator('#arrival-title')).to_have_text(state['title'])
    expect(page.locator('#arrival-brief')).to_have_text(state['brief'])
    expect(page.locator('#stage-label')).to_contain_text(state['title'])
    art = 'plaza' if index == 0 else f'stage{index + 1:02d}'
    assert state['paint'] == {'field': {art: True}, 'overview': {art: True}}, state['paint']
    if previous:
        assert state['score'] == previous['score'] and state['gear'] == [*previous['gear'], chosen]
        assert state['hearts'] == previous['hearts'] + int(chosen == 'shield')
        assert set(state['objects']).isdisjoint(previous['objects'])
        assert state['entrance'] != previous['position'] and state['beacon'] != previous['beacon']
    return {'stop': index + 1, 'name': state['title'], 'entrance': state['entrance'],
            'beacon': state['beacon'], 'background': art, 'goal': state['goal']}


def check_cards(buttons, offered):
    cards = buttons.evaluate_all("""async buttons => Promise.all(buttons.map(async button => {
      const c=button.querySelector('canvas.gear-art'), g=c.getContext('2d');
      const px=new Uint32Array(g.getImageData(0,0,c.width,c.height).data.buffer);
      const colors=new Set(px), rect=c.getBoundingClientRect();
      const digest=await crypto.subtle.digest('SHA-256',px);
      return {id:button.dataset.upgrade, colors:colors.size, width:rect.width, height:rect.height,
        art:[...new Uint8Array(digest)].join(','), title:button.querySelector('strong').innerText,
        effect:button.querySelector('.gear-effect').innerText};
    }))""")
    assert [card['id'] for card in cards] == offered and len(cards) == 3
    assert len({card['art'] for card in cards}) == 3
    for card in cards:
        assert card['colors'] > 100 and min(card['width'], card['height']) > 24, card['id']
        assert card['title'] and 2 <= len(card['effect']) <= 25 and re.search('[0-9]', card['effect']), card['id']


def set_run_seed(page):
    # The low 32 bits supply the same starting seed as the engine regression.
    seed_date = 400 * 2**32 + 770
    page.clock.install(time=seed_date - 1000)
    page.clock.pause_at(seed_date)
    page.evaluate('() => { const random = Math.random; Math.random = () => { Math.random = random; return 0; }; }')


def check_difficulty_records(page, key, shot):
    legacy = {'version':2, 'best':2300, 'runs':3, 'lastDelivery':{'completed':2}, 'selected':'lilpa', 'sound':True}
    page.evaluate('([key,save])=>localStorage.setItem(key, JSON.stringify(save))', [key, legacy])
    page.emulate_media(reduced_motion='no-preference')
    page.reload()
    expect(page.locator('#start-button')).to_be_enabled()
    radios = page.get_by_role('group', name='배송 난이도').get_by_role('radio')
    assert radios.count() == 3
    easy, normal, hard = [page.get_by_role('radio', name=label, exact=True) for label in ('쉬움','보통','어려움')]
    expect(easy).to_be_checked()
    expect(page.locator('#best-label')).to_have_text('쉬움 · 최고 2,300점 · 최근 2곳 배송')
    expect(page.locator('#sound-button')).to_have_attribute('aria-pressed','true')
    expect(page.locator('#member-name')).to_have_text('릴파')
    easy.focus()
    page.keyboard.press('ArrowRight')
    expect(normal).to_be_checked()
    expect(page.locator('#difficulty-description')).to_contain_text('18%')
    page.keyboard.press('ArrowRight')
    expect(hard).to_be_checked()
    expect(page.locator('#difficulty-description')).to_contain_text('36%')
    expect(page.locator('#best-label')).to_have_text('어려움 · 첫 배달 전')
    page.reload()
    expect(hard).to_be_checked()
    expect(page.locator('#start-button')).to_have_text('릴파 · 어려움 출발')
    shot(page, 'hard-selection')
    page.evaluate(PAINT_OBSERVER)
    set_run_seed(page)
    page.locator('#start-button').click()
    expect(page.locator('#run-difficulty')).to_contain_text('어려움')
    assert page.evaluate("CourierApp.state.difficulty==='hard'")
    page.clock.run_for(2350)
    page.evaluate('window.courierWalkSample=new Set()')
    page.keyboard.down('ArrowRight')
    page.clock.run_for(650)
    page.keyboard.up('ArrowRight')
    walk = page.evaluate('[...window.courierWalkSample]')
    assert len(walk) >= 2 and all(8 <= cell < 12 for cell in walk), walk
    page.clock.run_for(250)
    page.evaluate('() => { window.courierWalkSample.clear(); window.courierStandingSample=new Set(); }')
    page.clock.run_for(300)
    idle = page.evaluate('[...window.courierWalkSample]')
    standing = page.evaluate('[...window.courierStandingSample]')
    assert not idle and standing == [2], (idle, standing)
    page.evaluate(DRIVER, True)
    page.clock.run_for(4500)
    assert page.evaluate('CourierApp.state.score') > 0
    # Let the run finish with its own enemies and deadline, then press the real retry.
    for _ in range(23):
        page.clock.run_for(3000)
        if page.evaluate("CourierApp.state.mode==='lost'"):
            break
    expect(page.locator('#retry-button')).to_have_text('어려움 난이도로 다시 출발')
    expect(page.locator('#game-overlay .eyebrow')).to_contain_text('어려움')
    score = page.evaluate('CourierApp.state.score')
    record = page.evaluate('k=>JSON.parse(localStorage.getItem(k))', key)
    assert record['best'] == 2300 and record['runs'] == 4
    assert record['recordsByDifficulty']['easy'] == {'best':2300,'lastDelivery':{'completed':2}}
    assert record['recordsByDifficulty']['hard'] == {'best':score,'lastDelivery':{'completed':0}}
    assert record['recordsByDifficulty']['normal'] == {'best':0,'lastDelivery':None}
    assert record['difficulty'] == 'hard' and record['selected'] == 'lilpa' and record['sound'] is True
    page.locator('#retry-button').click()
    assert page.evaluate("CourierApp.state.difficulty==='hard' && CourierApp.state.score===0 && CourierApp.state.stage===0")
    page.locator('#pause-button').click()
    page.locator('#pause-home').click()
    expect(page.locator('#best-label')).to_contain_text(f'어려움 · 최고 {score:,}점')
    easy.check()
    expect(page.locator('#best-label')).to_contain_text('쉬움 · 최고 2,300점')
    return {'legacyEasy':2300, 'hardScore':score, 'hardRetry':True, 'movingFrames':walk, 'standingPose':standing[0]}


def main(html_path=None):
    OUT.mkdir(parents=True, exist_ok=True)
    raw = html_path.read_bytes() if html_path is not None else render()[0]
    game_key = 'isegye:review:courier:v2' if b'isegye:review:courier:v2' in raw else KEY
    errors, violations, external = [], [], []
    report = {'htmlSha256': hashlib.sha256(raw).hexdigest(), 'deliveries': [], 'arrivals': [], 'bosses': [], 'fonts': {},
              'errors': errors, 'cspViolations': violations, 'externalRequests': external}
    with tempfile.TemporaryDirectory() as temp:
        (Path(temp) / 'index.html').write_bytes(raw)
        handler = functools.partial(QuietHandler, directory=temp)
        with http.server.ThreadingHTTPServer(('127.0.0.1', 0), handler) as server, sync_playwright() as pw:
            origin = f'http://127.0.0.1:{server.server_port}'
            browser = pw.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH'))
            threading.Thread(target=server.serve_forever, daemon=True).start()

            def open_game(width, height, touch=False):
                ctx = browser.new_context(viewport={'width': width, 'height': height}, has_touch=touch,
                                          is_mobile=touch, reduced_motion='reduce')
                page = ctx.new_page()
                page.on('pageerror', lambda err: errors.append(str(err)))
                page.on('request', lambda req: external.append(req.url) if req.url.startswith(('https:', 'http:')) and not req.url.startswith(origin + '/') else None)
                page.expose_function('recordCourierViolation', lambda directive: violations.append(directive))
                page.add_init_script("document.addEventListener('securitypolicyviolation', e=>recordCourierViolation(e.effectiveDirective));")
                page.goto(origin)
                expect(page.locator('#start-button')).to_be_enabled()
                assert page.locator('.member-card').count() == 6
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                return ctx, page

            def shot(page, name):
                page.screenshot(path=str(OUT / (name + '.png')), full_page=True, timeout=15000)

            try:
                ctx, page = open_game(1280, 800)
                report['difficulties'] = check_difficulty_records(page, game_key, shot)
                ctx.close()
                ctx, page = open_game(1280, 800)
                page.evaluate("(k)=>localStorage.setItem(k,JSON.stringify({version:2,best:2300,runs:3,selected:'ine',sound:false}))", game_key)
                report['fonts']['desktop lobby/settings'] = check_appearance(page, touch=False)
                page.locator('#theme-button').click()
                assert '2,300' in page.locator('#best-label').inner_text()
                shot(page, 'lobby')
                page.locator('[data-member=viichan]').click()
                page.evaluate(PAINT_OBSERVER)
                set_run_seed(page)
                page.locator('#start-button').click()
                report['arrivals'].append(check_arrival(page, 0))
                report['fonts']['desktop arrival'] = painted_fonts(page, {'#arrival-title':'Jua', '#arrival-brief':'Gowun Dodum'})
                page.clock.run_for(2300)
                expect(page.locator('#stage-arrival')).to_be_hidden()
                page.locator('#pause-button').click()
                before = page.evaluate('CourierApp.state.elapsed')
                page.clock.run_for(600)
                assert page.evaluate('CourierApp.state.elapsed') == before
                page.locator('#resume-button').click()
                x = page.evaluate('CourierApp.state.x')
                page.keyboard.down('ArrowRight')
                page.clock.run_for(250)
                page.keyboard.up('ArrowRight')
                assert page.evaluate('CourierApp.state.x') > x + 20
                page.evaluate(DRIVER)
                shot(page, 'route-01')
                closeups = set()
                for _ in range(350):
                    page.clock.run_for(1400)
                    snap = page.evaluate("""() => {const s=CourierApp.state; return {mode:s.mode,
                        stage:s.stage+1,cargo:s.cargo,required:s.required,boss:s.boss?.kind,stats:s.stats,
                        bossNearby:!!s.boss && Math.abs(s.boss.x-s.x)<410 && Math.abs(s.boss.y-s.y)<245,
                        draft:s.draft,hearts:s.hearts,maxHearts:s.maxHearts,deliveries:s.deliveries,elapsed:s.elapsed,loss:s.lossReason};}""")
                    boss = snap['boss']
                    if boss and boss not in report['bosses']:
                        report['bosses'].append(boss)
                        shot(page, f"boss-{snap['stage']:02d}")
                    if snap['bossNearby'] and boss not in closeups:
                        closeups.add(boss)
                        shot(page, f"boss-{snap['stage']:02d}")
                    if snap['mode'] == 'upgrade':
                        buttons = page.locator('#game-overlay [data-upgrade]')
                        assert buttons.first.is_visible() and snap['deliveries'] == snap['stage'] == len(report['arrivals'])
                        assert snap['cargo'] >= snap['required']
                        check_cards(buttons, snap['draft'])
                        if not report['deliveries']:
                            report['fonts']['reward'] = painted_fonts(page, {
                                '.upgrade-option strong':'Jua', '.upgrade-option .gear-effect':'Gowun Dodum'})
                            shot(page, 'first-draft')
                        draft = snap['draft']
                        priority = ['fan','quill','spool','magnet','speed','ribbon','shield']
                        if snap['maxHearts'] < 5 or snap['hearts'] <= 2:
                            priority.insert(0, 'shield')
                        choice = next(item for item in priority if item in draft)
                        cleared = page.evaluate("""() => {const s=CourierApp.state; return {
                          score:s.score, hearts:s.hearts, gear:s.upgrades, position:[s.x,s.y], beacon:[s.beacon.x,s.beacon.y],
                          objects:[...s.stars,...s.enemies,...s.hazards,...s.projectiles].map(p=>p.id)};}""")
                        page.clock.run_for(500)
                        assert page.evaluate('CourierApp.state.stage + 1') == snap['stage']
                        page.locator(f'#game-overlay [data-upgrade="{choice}"]').click()
                        report['arrivals'].append(check_arrival(page, snap['stage'], cleared, choice))
                        if snap['stage'] == 1:
                            shot(page, 'second-arrival')
                        report['deliveries'].append({'stop': snap['deliveries'], 'reward': choice})
                    if snap['mode'] in ('lost','won'):
                        assert snap['mode'] == 'won', snap
                        assert snap['deliveries'] == 10 and snap['stats']['bosses'] == 3
                        assert len(report['deliveries']) == 9 and len(report['bosses']) == 3
                        assert len({tuple(stage['entrance']) for stage in report['arrivals']}) == 10
                        assert len({tuple(stage['beacon']) for stage in report['arrivals']}) == 10
                        assert report['bosses'] == ['warden','siren','regent'] and snap['stats']['letters'] >= 172
                        assert '콤보' in page.locator('.result-grade').inner_text()
                        report['result'] = snap
                        shot(page, 'delivery-report')
                        page.locator('#retry-button').click()
                        assert page.evaluate("CourierApp.state.stage===0 && CourierApp.state.deliveries===0 && CourierApp.state.difficulty==='easy'")
                        break
                else:
                    raise AssertionError(f'Campaign did not finish: {snap}')
                ctx.close()
                for width in (320,390,768):
                    ctx, page = open_game(width, 844, touch=True)
                    if width == 390:
                        report['fonts']['mobile lobby/settings'] = check_appearance(page, touch=True)
                        page.get_by_role('radio',name='보통',exact=True).tap()
                        expect(page.get_by_role('radio',name='보통',exact=True)).to_be_checked()
                        expect(page.locator('#start-button')).to_contain_text('보통')
                        set_run_seed(page)
                        page.evaluate(PAINT_OBSERVER)
                    page.locator('#start-button').tap()
                    if width == 390:
                        assert page.evaluate("CourierApp.state.difficulty==='normal'")
                        expect(page.locator('#run-difficulty')).to_contain_text('보통')
                        report['fonts']['mobile arrival'] = painted_fonts(page, {'#arrival-title':'Jua', '#arrival-brief':'Gowun Dodum'})
                        header = page.locator('.masthead .wordmark,.masthead button').evaluate_all("""controls =>
                          controls.map(el => {
                            const range=document.createRange(), walker=document.createTreeWalker(el,NodeFilter.SHOW_TEXT);
                            const boxes=[], bounds=el.getBoundingClientRect();
                            while (walker.nextNode()) {
                              if (!walker.currentNode.textContent.trim()) continue;
                              range.selectNodeContents(walker.currentNode);
                              boxes.push(...range.getClientRects());
                            }
                            const centers=boxes.map(r=>r.top+r.height/2);
                            return {label:el.innerText, nowrap:getComputedStyle(el).whiteSpace==='nowrap',
                              oneLine:centers.length>0 && Math.max(...centers)-Math.min(...centers)<6,
                              fits:bounds.left>=0 && bounds.right<=innerWidth &&
                                boxes.every(r=>r.left>=bounds.left-1 && r.right<=bounds.right+1)};
                          })""")
                        assert len(header) == 4 and all(item['nowrap'] and item['oneLine'] and item['fits']
                                                        for item in header), header
                        report['mobileHeader'] = header
                        shot(page, 'touch-arrival')
                        page.clock.run_for(2400)
                    deadline = time.monotonic() + 10
                    while not page.evaluate('CourierApp.state?.elapsed>0'):
                        assert time.monotonic() < deadline, 'Touch start did not enter gameplay'
                        page.wait_for_timeout(100)
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                    page.locator('#dash-button').tap()
                    assert page.evaluate('CourierApp.state.stats.dashes') == 1
                    shot(page, f'touch-{width}')
                    if width == 390:
                        page.evaluate(DRIVER)
                        for _ in range(35):
                            page.clock.run_for(1200)
                            if page.evaluate("CourierApp.state.mode!=='playing'"):
                                break
                        assert page.evaluate("CourierApp.state.mode==='upgrade'")
                        expect(page.locator('html')).to_have_attribute('data-theme','dark')
                        offered = page.evaluate('CourierApp.state.draft')
                        cards = page.locator('#game-overlay [data-upgrade]')
                        check_cards(cards, offered)
                        report['fonts']['mobile reward'] = painted_fonts(page, {
                            '.upgrade-option strong':'Jua', '.upgrade-option .gear-effect':'Gowun Dodum'})
                        shot(page, 'touch-reward')
                        cards.last.tap()
                        check_arrival(page, 1)
                        assert page.evaluate('CourierApp.state.upgrades') == [offered[-1]]
                    ctx.close()
                assert not errors and not external and not violations, (errors, external, violations)
                report['passed'] = True
            finally:
                (OUT / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
                browser.close()
                server.shutdown()
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--html', type=Path, help='exercise the HTML from an existing playground build')
    main(parser.parse_args().html)
