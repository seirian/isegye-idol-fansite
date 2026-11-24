#!/usr/bin/env python3
"""Play the built RPG through public controls; game diagnostics are read-only.

This deliberately does not inject a completed save, call engine dispatch, create
accounts, or claim automated execution time represents a first human playthrough.
"""
from collections import deque
import argparse
import hashlib
import http.server
import json
import os
from pathlib import Path
import re
import signal
import socketserver
import subprocess
import sys
import threading
import time
import uuid
import shutil
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
DIST = Path(os.environ.get("RPG_TEST_DIST", str(ROOT / "rpg-dist")))
RESULTS = ROOT / "test-results/rpg"
WATCHDOG_SECONDS = 300
TERMINATION_GRACE_SECONDS = 5
BUILD_HASH = ''
RUN_ID = ''
OUT = None
CONTENT = {}
report = {}
started = None


def write_json(path, value):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    temporary.replace(path)


def checkpoint():
    if OUT is not None:
        write_json(OUT / 'progress.json', report)


def progress(phase):
    report['lastProgress'] = {
        'phase': phase,
        'checkedAt': datetime.now(timezone.utc).isoformat(),
        'elapsedSeconds': round(time.monotonic() - started, 2),
        'completedChecks': len(report['checks']),
    }
    checkpoint()
    print(json.dumps({'rpgProgress': report['lastProgress']}, ensure_ascii=False), flush=True)


def stop_process_group(process, grace=TERMINATION_GRACE_SECONDS):
    """Stop only this worker's isolated group, including a hung browser driver."""
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=grace)
    except subprocess.TimeoutExpired:
        pass
    # The group can still contain children after its leader has already exited.
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=grace)
    except subprocess.TimeoutExpired:
        pass


def run_guarded(command, timeout=WATCHDOG_SECONDS, grace=TERMINATION_GRACE_SECONDS, cwd=ROOT):
    """One worker attempt; timeout is failure, never permission to skip checks."""
    if os.name != 'posix':
        raise RuntimeError('The RPG browser watchdog requires POSIX process groups')
    began = time.monotonic()
    process = subprocess.Popen(command, cwd=cwd, start_new_session=True)
    try:
        code = process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        stop_process_group(process, grace)
        return {'exitCode': 124, 'timedOut': True,
                'elapsedSeconds': round(time.monotonic() - began, 2)}
    except BaseException:
        stop_process_group(process, grace)
        raise
    if code:
        stop_process_group(process, grace)
    return {'exitCode': code, 'timedOut': False,
            'elapsedSeconds': round(time.monotonic() - began, 2)}


def supervised_report(directory, outcome):
    """Preserve the last atomic checkpoint even if the worker cannot run finally."""
    value = {}
    for filename in ('report.json', 'progress.json'):
        try:
            candidate = json.loads((directory / filename).read_text())
        except (OSError, ValueError):
            continue
        if isinstance(candidate, dict):
            value = candidate
            break
    if outcome['timedOut']:
        value.update(status='failed', failure='RPG browser verification exceeded its 300-second watchdog',
                     failureCode='browser_watchdog_timeout')
    elif outcome['exitCode'] or value.get('status') != 'passed':
        value['status'] = 'failed'
        value.setdefault('failure', 'RPG browser worker did not finish with a passing report')
        value.setdefault('failureCode', 'browser_worker_failed')
    value['watchdog'] = {'limitSeconds': WATCHDOG_SECONDS, **outcome}
    return value


def initialize_worker(run_id):
    global BUILD_HASH, RUN_ID, OUT, CONTENT, report, started
    if not re.fullmatch(r'\d{8}T\d{6}\.\d{6}Z-[0-9a-f]{12}-[0-9a-f]{6}', run_id):
        raise ValueError('Invalid RPG browser run directory')
    RUN_ID = run_id
    OUT = RESULTS / 'runs' / RUN_ID
    if not OUT.is_dir() or OUT.is_symlink():
        raise ValueError('RPG browser supervisor directory required')
    started = time.monotonic()
    report = {
        'status': 'running', 'runDirectory': str(OUT.relative_to(ROOT)),
        'checks': [], 'errors': [], 'externalRequests': [], 'screenshots': [],
        'inputPolicy': 'Public keyboard, mouse and touch controls; snapshot only read. No engine dispatch or valid-save injection.',
        'storageFixtures': 'Corrupt game JSON, corrupt settings beside a UI-earned save, and simulated denied Storage API only.',
        'humanPlaytimeMeasured': False,
    }
    progress('worker:initialize')
    BUILD_HASH = hashlib.sha256((DIST / 'index.html').read_bytes()).hexdigest()
    if RUN_ID.split('-')[1] != BUILD_HASH[:12]:
        raise ValueError('RPG artifact changed before the supervised worker started')
    report['htmlSha256'] = BUILD_HASH
    shutil.copy2(DIST / 'index.html', OUT / 'tested-game.html')
    shutil.copy2(ROOT / 'dist/build-info.json' if os.getenv('RPG_TEST_DIST') else DIST / 'build-info.json', OUT / 'build-info.json')
    CONTENT = json.loads(subprocess.check_output([
        'node', '--input-type=module', '-e',
        "import {CHAPTERS, FINALE} from './rpg/content.js'; console.log(JSON.stringify({chapters:CHAPTERS,finale:FINALE}));",
    ], cwd=ROOT, text=True, timeout=20))


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DIST), **kwargs)

    def log_message(self, *args):
        pass


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def check(condition, label):
    assert condition, label
    report["checks"].append(label)
    checkpoint()


def screenshot(page, name):
    progress('screenshot:' + name + ':start')
    filename = f'{len(report["screenshots"])+1:02d}-{name}.png'
    page.screenshot(path=str(OUT / filename), full_page=True)
    report["screenshots"].append(filename)
    progress('screenshot:' + name + ':complete')


def state(page):
    return page.evaluate("() => window.__IPARI_RPG__.snapshot()")


def check_korean_fonts(page, screen, samples):
    """Read Chromium's actual painted glyph sources for a few visible Korean UI elements."""
    loaded = page.evaluate("""async () => {
      await document.fonts.ready;
      return [...document.fonts].filter(face => face.status === 'loaded').map(face => face.family);
    }""")
    def font_key(name):
        return re.sub(r"[^a-z0-9]", "", name.lower())

    cdp = page.context.new_cdp_session(page)
    try:
        cdp.send("DOM.enable")
        cdp.send("CSS.enable")
        root = cdp.send("DOM.getDocument")["root"]["nodeId"]
        for selector, expected in samples:
            element = page.locator(selector).first
            assert element.is_visible(), f"{screen}: hidden font sample {selector}"
            direct_text = element.evaluate("""n => [...n.childNodes]
                .filter(c => c.nodeType === Node.TEXT_NODE).map(c => c.textContent).join('')""")
            hangul = len(re.findall(r"[가-힣]", direct_text))
            assert hangul, f"{screen}: missing Korean text in {selector}"
            node = cdp.send("DOM.querySelector", {"nodeId": root, "selector": selector})["nodeId"]
            fonts = cdp.send("CSS.getPlatformFontsForNode", {"nodeId": node})["fonts"]
            family = font_key(expected)
            painted = sum(font["glyphCount"] for font in fonts if font["isCustomFont"]
                          and any(family in font_key(font.get(key, "")) for key in ("familyName", "postScriptName")))
            check(any(family in font_key(face) for face in loaded) and painted >= hangul,
                  f"{screen} {selector} paints Korean with bundled {expected} (glyphs {painted}, Hangul {hangul}, {fonts})")
    finally:
        cdp.detach()


def fits(page, label):
    dimensions = page.evaluate("({width:innerWidth,scroll:document.documentElement.scrollWidth})")
    check(dimensions["scroll"] <= dimensions["width"] + 1, label + " " + str(dimensions))
    distorted = page.locator('.sprite').evaluate_all('nodes => nodes.filter(n => {const r=n.getBoundingClientRect(); return r.width>0 && r.height>0 && Math.abs(n.offsetWidth-n.offsetHeight)>1;}).map(n=>n.className)')
    check(not distorted, label + ' preserves square character cells: ' + str(distorted))


def open_game(browser, origin, width=1440, height=1000, init=None):
    progress(f'context:{width}:create')
    context = browser.new_context(viewport={"width": width, "height": height},
                                  device_scale_factor=1, has_touch=width <= 768, is_mobile=width <= 768)
    if init:
        context.add_init_script(init)
    progress(f'context:{width}:new_page')
    page = context.new_page()
    page.on("pageerror", lambda error: report["errors"].append(str(error)))
    page.on("console", lambda message: report["errors"].append(message.text)
            if message.type == "error" and ("Content Security Policy" in message.text or "content security policy" in message.text.lower()) else None)

    def route(request):
        if request.request.url.startswith(origin + "/") or request.request.url.startswith("data:"):
            request.continue_()
        else:
            report["externalRequests"].append(request.request.url)
            request.abort()

    page.route("**/*", route)
    progress(f'context:{width}:navigate')
    page.goto(origin + "/index.html", wait_until="domcontentloaded")
    progress(f'context:{width}:ready')
    page.wait_for_function("() => !!window.__IPARI_RPG__", timeout=20000)
    page.locator('[data-action="start"]').wait_for(state="visible")
    progress(f'context:{width}:opened')
    return context, page


def close_context(context, label):
    progress('context:' + label + ':close')
    context.close()
    progress('context:' + label + ':closed')


def dialogue(page):
    for _ in range(20):
        if state(page)["mode"] != "dialogue":
            return
        page.locator('[data-action="dialogue-next"]').click()
    raise AssertionError("Dialogue did not finish")


def start(page, verify_fonts=False):
    page.locator('[data-action="start"]').click()
    if verify_fonts:
        check_korean_fonts(page, "field dialogue", [(".story-text", "Gowun Dodum"), (".speaker", "Jua")])
    dialogue(page)
    check(state(page)["mode"] == "explore", "start and prologue lead to exploration")


def scene_for(snapshot):
    return (CONTENT["chapters"][snapshot["chapter"]]["rooms"][snapshot["room"]]
            if snapshot["chapter"] < 6 else CONTENT["finale"]["room"])


def approach(page, object_id):
    snapshot = state(page)
    assert snapshot["mode"] == "explore", (object_id, snapshot["mode"])
    scene = scene_for(snapshot)
    target = next(obj for obj in scene["objects"] if obj["id"] == object_id)
    origin = (snapshot["position"]["x"], snapshot["position"]["y"])
    queue = deque([(origin, [])])
    seen = {origin}
    path = None
    moves = [(0, -1, "ArrowUp"), (1, 0, "ArrowRight"), (0, 1, "ArrowDown"), (-1, 0, "ArrowLeft")]
    while queue:
        (x, y), trail = queue.popleft()
        if abs(x - target["x"]) + abs(y - target["y"]) <= 1:
            path = trail
            break
        for dx, dy, key in moves:
            pos = (x + dx, y + dy)
            if pos not in seen and 0 <= pos[1] < len(scene["tiles"]) and 0 <= pos[0] < len(scene["tiles"][pos[1]]) and scene["tiles"][pos[1]][pos[0]] == ".":
                seen.add(pos)
                queue.append((pos, trail + [key]))
    assert path is not None, "No navigable route to " + object_id
    page.locator(".map-board").focus()
    for key in path:
        page.keyboard.press(key)
    arrived = state(page)["position"]
    assert abs(arrived["x"] - target["x"]) + abs(arrived["y"] - target["y"]) <= 1, ("Movement did not reach", object_id, arrived)


def interact(page, object_id):
    approach(page, object_id)
    page.locator('.map-object[data-id="' + object_id + '"]').click()


def read_object(page, object_id):
    interact(page, object_id)
    dialogue(page)


def choose(page, choice):
    page.locator('[data-action="choose"][data-id="' + choice + '"]').click()


def solve(page, chapter):
    kind = chapter["puzzle"]["kind"]
    if kind == "sequence":
        actions = [(0, "press"), (1, "press"), (2, "press")]
    elif kind == "layers":
        actions = [(1, "story"), (0, "storyworld"), (1, "song"), (0, "real"), (1, "meeting"), (2, "bind")]
    elif kind == "wings":
        actions = [(0, "toggle"), (2, "toggle")]
    else:
        actions = list(enumerate(chapter["puzzle"]["solution"]))
    for step, (control, answer) in enumerate(actions):
        interact(page, "control-" + str(control))
        check(state(page)["mode"] == "choice", chapter["id"] + " puzzle offers a real choice")
        if chapter["index"] == 0 and step == 0:
            check_korean_fonts(page, "puzzle choice", [(".choice-panel > p:not(.eyebrow)", "Gowun Dodum"),
                                                        (".choice-button > span:first-child", "Gowun Dodum")])
        choose(page, answer)
    check(chapter["id"] in state(page)["solved"], chapter["id"] + " puzzle solved through public controls")


def begin_battle(page, object_id):
    interact(page, object_id)
    dialogue(page)
    check(state(page)["mode"] == "choice", object_id + " asks before starting the battle")
    choose(page, "start")
    check(state(page)["mode"] == "battle", object_id + " battle started")


def support(page, member):
    button = page.locator('[data-action="support"][data-id="' + member + '"]')
    if not button.is_visible():
        page.locator('[data-action="support-toggle"]').click()
    button.click()


def battle(page, label, capture=False):
    progress('battle:' + label + ':start')
    used = set()
    phases = set()
    for _ in range(200):
        snapshot = state(page)
        if snapshot["mode"] != "battle":
            check(snapshot["mode"] in ("explore", "ending"), label + " won without a progression bypass")
            report.setdefault("battleResults", []).append({"label": label, "phases": sorted(phases), "supports": sorted(used)})
            return
        phases.add(snapshot["battle"]["phase"])
        if snapshot['battle']['turn'] % 10 == 0:
            progress('battle:' + label + ':turn-' + str(snapshot['battle']['turn']))
        if capture:
            screenshot(page, label)
            capture = False
        intent = page.locator(".tac-intent").inner_text()
        player = snapshot["player"]
        known = snapshot["met"]
        member = None
        move = "attack"
        if "ine" in known and player["focus"] >= 2 and player["hp"] < player["maxHp"] * .6:
            member = "ine"
        elif "강한 공격" in intent or "큰 공격" in intent or "결빙 예고" in intent:
            if "lilpa" in known and player["focus"] >= 2:
                member = "lilpa"
            else:
                move = "defend"
        elif player["focus"] >= 2:
            if ("환영" in intent or "진짜 페이지" in intent) and "jururu" in known:
                member = "jururu"
            elif ("뒤집힌" in intent or "규칙 뒤집기" in intent) and "gosegu" in known:
                member = "gosegu"
            elif "단단한 방어" in intent or "방어를 뚫" in intent:
                member = "jingburger"
            elif snapshot["battle"]["counter"]:
                move = "attack"
            elif "viichan" in known and snapshot["battle"]["previousMove"] != "viichan":
                member = "viichan"
            else:
                member = "jingburger"
        if member:
            used.add(member)
            support(page, member)
        else:
            page.locator('[data-action="battle"][data-move="' + move + '"]').click()
    raise AssertionError(label + " did not complete within 200 turns")


def restored(page, origin):
    before = state(page)
    page.reload(wait_until="domcontentloaded")
    page.wait_for_function("() => !!window.__IPARI_RPG__")
    page.locator('[data-action="continue"]').click()
    after = state(page)
    for key in ("chapter", "room", "position", "met", "defeated", "records", "solved", "mode"):
        check(before[key] == after[key], "reload preserves " + key)


def playthrough(browser, origin):
    progress('playthrough:start')
    context, page = open_game(browser, origin)
    try:
        start(page)
        for index, chapter in enumerate(CONTENT["chapters"]):
            progress('chapter:' + chapter['id'])
            check(state(page)["chapter"] == index, "entered " + chapter["year"])
            if index == 0:
                member = page.locator('.map-object[data-id="member"]')
                member.hover()
                check(page.locator('.field-route').evaluate(
                    "node => node.getContext('2d').getImageData(0,0,node.width,node.height).data.some(n=>n)"),
                      "pointing at the first companion previews a walkable route")
                member.click()
                page.locator(".meeting-screen").wait_for()
            else:
                interact(page, "member")
            meeting = page.locator("main .meeting-screen")
            check(meeting.is_visible() and not page.locator(".map-board").count(),
                  chapter["member"] + " enters a separate first-meeting scene")
            check(meeting.get_by_role("heading", name=chapter["meeting"]["title"]).is_visible(),
                  chapter["member"] + " scene has its own title")
            check(meeting.locator(".meeting-illustration").evaluate(
                "node => getComputedStyle(node).backgroundImage.includes('data:image/webp;base64,')"),
                  chapter["member"] + " scene uses embedded event art")
            next_line = meeting.locator('[data-action="dialogue-next"]')
            next_line.click()
            next_line.click()
            if index == 0:
                page.set_viewport_size({"width": 390, "height": 844})
                fits(page, "first meeting fits 390px")
                check_korean_fonts(page, "mobile cutscene", [(".meeting-heading h1", "Jua"),
                                    (".meeting-speaker h2", "Jua"), (".meeting-line", "Gowun Dodum"),
                                    (".meeting-reply", "Gowun Dodum")])
                screenshot(page, "meeting-390")
                page.set_viewport_size({"width": 1440, "height": 1000})
            screenshot(page, "meeting-" + chapter["member"])
            reply = index % 2
            meeting.locator(f'[data-reply="{reply}"]').click()
            expected_reply = chapter["meeting"]["choices"][reply]["reply"]
            check(meeting.locator(".meeting-line").inner_text() == expected_reply,
                  chapter["member"] + " responds to the chosen action")
            if index == 0:
                restored(page, origin)
                check(meeting.locator(".meeting-line").inner_text() == expected_reply,
                      "reload preserves the chosen cutscene response")
            dialogue(page)
            check(chapter["member"] in state(page)["met"], chapter["member"] + " joined")
            if index == 0:
                before_replay = state(page)
                page.locator('[data-action="replay"][data-id="jingburger"]').click()
                replay = page.locator("dialog .meeting-screen")
                replay_next = replay.locator('[data-action="dialogue-next"]')
                replay_next.click()
                replay_next.click()
                replay.locator('[data-reply="1"]').click()
                check(replay.locator(".meeting-line").inner_text() == chapter["meeting"]["choices"][1]["reply"],
                      "companion replay offers the alternate response")
                replay_next.click()
                replay_next.click()
                check(not page.locator("dialog").is_visible(), "companion replay closes on completion")
                page.locator("#journal-button").click()
                page.locator('[data-modal-action="replay"][data-id="jingburger"]').click()
                for _ in chapter["intro"]:
                    replay_next.click()
                check(page.get_by_role("heading", name="우리의 기록첩").is_visible(),
                      "journal replay returns to the journal")
                page.keyboard.press("Escape")
                after_replay = state(page)
                check(all(before_replay[k] == after_replay[k] for k in ("mode", "player", "room", "chapter", "position", "met", "records")),
                      "both replay entry points preserve gameplay and earned powers")
            read_object(page, "record-0")
            read_object(page, "memory")
            interact(page, "rest")
            if index == 0:
                restored(page, origin)
                screenshot(page, "explore-1440")
            interact(page, "forward")
            read_object(page, "clue")
            if index == 1:
                screenshot(page, "winter-spring-garden")
            solve(page, chapter)
            read_object(page, "memory")
            begin_battle(page, "guardian")
            if index == 0:
                leader_before = state(page)["battle"]["field"]["leader"]
                page.locator('.tac-roll-unit[data-id="jingburger"]').click()
                destination = page.locator('.tac-destination[data-x="2"][data-y="2"]')
                destination.focus()
                page.keyboard.press("Enter")
                field = state(page)["battle"]["field"]
                check(field["active"] == "jingburger" and field["allies"][1]["x"] == field["allies"][1]["y"] == 2,
                      "keyboard places the selected companion on a reachable cell")
                check(page.locator(".tac-destination").count() == 0, "a unit cannot move twice before acting")
                support(page, "jingburger")
                snapshot = state(page)
                check(snapshot["battle"]["field"]["acted"] == ["jingburger"] and snapshot["battle"]["turn"] == 0
                      and snapshot["battle"]["hp"] < snapshot["battle"]["maxHp"], "a companion's skill hits before the enemy phase")
                restored(page, origin)
                check(state(page)["battle"]["field"] == snapshot["battle"]["field"], "mid-turn reload preserves deployment and spent actions")
                page.locator('[data-action="battle"][data-move="defend"]').click()
                snapshot = state(page)
                check(snapshot["battle"]["turn"] == 1 and snapshot["battle"]["field"]["leader"] != leader_before
                      and snapshot["player"]["hp"] < snapshot["player"]["maxHp"], "the enemy advances and hits when Ipari ends the round")
                # Deliberately poor public choices produce a real defeat and retry.
                for _ in range(80):
                    if state(page)["mode"] != "battle":
                        break
                    page.locator('[data-action="battle"][data-move="cheer"]').click()
                check(state(page)["mode"] == "defeat", "poor public battle choices produce defeat")
                preserved = state(page)["records"]
                screenshot(page, "defeat-1440")
                page.locator('[data-action="retry"]').click()
                check(state(page)["mode"] == "battle" and state(page)["records"] == preserved, "retry returns to same battle and preserves records")
                defense = page.locator('[data-action="battle"][data-move="defend"]')
                turn_before = state(page)["battle"]["turn"]
                defense.focus()
                page.keyboard.press("Enter")
                check(state(page)["battle"]["lastMove"] == "defend", "Enter activates the focused defense action")
                check(defense.evaluate("node=>document.activeElement===node"), "defense retains focus after the battle rerenders")
                page.keyboard.press("Enter")
                check(state(page)["battle"]["lastMove"] == "defend" and state(page)["battle"]["turn"] == turn_before + 2,
                      "repeated Enter keeps defending instead of switching to attack")
                for width, height in ((320, 720), (390, 844), (768, 1024), (1440, 1000)):
                    page.set_viewport_size({"width": width, "height": height})
                    fits(page, f"battle fits {width}px")
                    if width == 320:
                        check_korean_fonts(page, "mobile battle", [(".tac-pennant", "Gowun Dodum"),
                                            (".tac-action b", "Gowun Dodum"), (".battle-log p", "Gowun Dodum")])
                    screenshot(page, f"battle-{width}")
            battle(page, chapter["id"] + "-guardian", capture=index == 1)
            interact(page, "forward")
            read_object(page, "record-1")
            interact(page, "rest")
            begin_battle(page, "boss")
            if index == 0:
                leader_hp = state(page)["battle"]["hp"]
                page.locator('.tac-unit[data-id="echo"]').click()
                check(state(page)["battle"]["field"]["target"] == "echo", "the boss's echo can be targeted on the field")
                support(page, "jingburger")
                check(state(page)["battle"]["hp"] == leader_hp and state(page)["battle"]["field"]["echo"]["hp"] == 0,
                      "a targeted skill disperses the echo without damaging the boss")
            battle(page, chapter["id"] + "-boss", capture=index in (2, 5))
            read_object(page, "exit")
            check(state(page)["mode"] == "victory", chapter["id"] + " completed")
            page.locator('[data-action="next-chapter"]').click()
            if state(page)["mode"] == "upgrade":
                check(page.locator('[data-action="upgrade"]').count() == 3, "three distinct growth options are available")
                page.locator('[data-action="upgrade"][data-id="spark"]').click()
        read_object(page, "ensemble")
        interact(page, "rest")
        begin_battle(page, "final-boss")
        battle(page, "final-trial", capture=True)
        ended = state(page)
        check(ended["mode"] == "ending", "public UI actions complete all six chapters and the ending")
        check(len(ended["records"]) == 12, "all twelve real activity records collected")
        check(len(ended["solved"]) == 6 and ended["stats"]["battles"] == 13, "six puzzles and thirteen encounters completed")
        check(len(ended["finalContributions"]) == 6, "all six companions appear in the ending")
        check(report["battleResults"][-1]["phases"] == [0, 1, 2], "final trial traverses all three phases")
        report["completedGame"] = {key: ended[key] for key in ("mode", "chapter", "met", "records", "solved", "defeated", "stats")}
        for width, height in ((1440, 1000), (390, 844), (320, 720), (768, 1024)):
            page.set_viewport_size({"width": width, "height": height})
            fits(page, f"ending fits {width}px")
            screenshot(page, f"ending-{width}")
        page.locator("#journal-button").click()
        check_korean_fonts(page, "journal", [(".journal-intro", "Gowun Dodum"),
                                             (".journal-entry p", "Gowun Dodum")])
        check(page.locator(".journal-entry a").count() >= 12, "completed journal exposes source links")
        check(page.locator(".journal-entry a").evaluate_all("links=>links.every(a=>a.href.startsWith('https://'))"), "all source links use HTTPS")
        page.keyboard.press("Escape")
        restored(page, origin)
    except Exception:
        screenshot(page, "failure-playthrough")
        raise
    finally:
        close_context(context, 'playthrough')


def layouts_and_storage(browser, origin):
    for width, height in ((1440, 1000), (390, 844), (320, 720), (768, 1024)):
        progress(f'layout:{width}:start')
        context, page = open_game(browser, origin, width, height)
        try:
            if width == 1440:
                check_korean_fonts(page, "cover", [("#cover-title", "Jua"), (".cover-desc", "Gowun Dodum"),
                                                   ("[data-action=start]", "Gowun Dodum")])
                skip = page.locator('.skip-link')
                check(skip.evaluate("node=>getComputedStyle(node).opacity==='0'"), 'skip link stays hidden outside keyboard focus')
                page.keyboard.press('Tab')
                check(skip.evaluate("node=>document.activeElement===node && getComputedStyle(node).opacity==='1'"), 'first keyboard tab reveals the skip link')
                page.keyboard.press('Tab')
                check(skip.evaluate("node=>getComputedStyle(node).opacity==='0'"), 'skip link hides again after keyboard focus leaves')
            fits(page, f"title fits {width}px")
            screenshot(page, f"title-{width}")
            if width == 320:
                page.locator("#settings-button").click()
                page.locator('[data-setting="help"]').check()
                page.keyboard.press("Escape")
            start(page, verify_fonts=width == 1440)
            if width == 320:
                check(state(page)["help"] is True, "new adventure preserves help selected before starting")
            fits(page, f"exploration fits {width}px")
            before = state(page)["position"]
            if width <= 768:
                page.locator('.dpad .right').tap()
            else:
                page.locator(".map-board").focus()
                page.keyboard.press("ArrowRight")
            check(state(page)["position"]["x"] == before["x"] + 1, f"public movement control works at {width}px")
            screenshot(page, f"explore-{width}")
            page.locator("#settings-button").click()
            page.locator("#rpg-dialog").wait_for(state="visible")
            if width == 1440:
                check_korean_fonts(page, "settings", [(".settings-row small", "Gowun Dodum")])
                credits = page.locator("details.font-licenses")
                credits.locator("summary").click()
                for name, filename in (("고운돋움 (Gowun Dodum)", "GowunDodum-OFL.txt"),
                                       ("주아체 (Jua)", "Jua-OFL.txt")):
                    heading = credits.get_by_role("heading", name=name, exact=True)
                    license_text = heading.locator("xpath=following-sibling::pre[1]")
                    expected = (ROOT / "rpg/fonts" / filename).read_text(encoding="utf-8-sig").strip()
                    check(heading.is_visible() and license_text.is_visible() and
                          license_text.text_content().replace("\r\n", "\n").strip() == expected,
                          f"settings shows {name} with its complete upstream OFL notice")
                credits.locator("summary").click()
                page.locator('[data-setting="dark"]').check()
                page.locator('[data-setting="reduceMotion"]').check()
                check(page.locator("html").get_attribute("data-theme") == "dark", "dark setting changes the rendered theme")
                check(page.locator("html").get_attribute("data-reduced-motion") == "true", "reduced motion setting changes the rendered preference")
                page.locator('[data-setting="help"]').check()
                check(state(page)["help"] is True, "help setting changes real game state")
                page.locator('[data-setting="help"]').uncheck()
                check(state(page)["help"] is False, "help can be turned off without losing progress")
            fits(page, f"settings fit {width}px")
            screenshot(page, f"settings-{width}")
            progress(f'layout:{width}:close_settings')
            page.keyboard.press("Escape")
            check(not page.locator("#rpg-dialog").is_visible(), "Escape closes settings")
            progress(f'layout:{width}:settings_closed')
            if width == 1440:
                restored(page, origin)
                check(page.locator("html").get_attribute("data-theme") == "dark", "dark preference survives reload")
                check(page.locator("html").get_attribute("data-reduced-motion") == "true", "reduced motion preference survives reload")
                page.locator("#settings-button").click()
                check(page.locator('[data-setting="dark"]').is_checked() and page.locator('[data-setting="reduceMotion"]').is_checked(),
                      "saved settings controls match the restored preferences")
                page.keyboard.press("Escape")
                screenshot(page, "dark-1440")
                seconds_before = state(page)["stats"]["seconds"]
                progress('timer:active_gameplay')
                page.wait_for_timeout(5200)
                check(state(page)["stats"]["seconds"] > seconds_before, "active gameplay time advances")
                page.locator("#pause-button").click()
                paused = state(page)
                page.keyboard.press("ArrowRight")
                progress('timer:paused_gameplay')
                page.wait_for_timeout(5200)
                check(state(page)["stats"]["seconds"] == paused["stats"]["seconds"], "pause dialog stops the play timer")
                check(state(page)["position"] == paused["position"], "pause dialog blocks movement input")
                page.keyboard.press("Escape")
        except Exception:
            screenshot(page, f"failure-layout-{width}")
            raise
        finally:
            close_context(context, 'layout-' + str(width))
    progress('storage:settings_recovery')
    context, page = open_game(browser, origin, 390, 844)
    try:
        start(page)
        read_object(page, "member")
        read_object(page, "record-0")
        earned = state(page)
        check(bool(earned["met"]) and bool(earned["records"]), "settings recovery fixture earns its save using public controls")
        page.evaluate("localStorage.setItem('isegye:rpg:settings:v1','{broken-settings')")
        restored(page, origin)
        check(state(page)["met"] == earned["met"] and state(page)["records"] == earned["records"],
              "corrupt settings do not discard a valid adventure save")
        screenshot(page, "settings-recovered-390")
    finally:
        close_context(context, 'settings-recovery')
    fixtures = [
        ("corrupt", "localStorage.setItem('isegye:rpg:v1','{broken-save');"),
        ("denied", "Storage.prototype.getItem=function(){throw new DOMException('denied','SecurityError')};Storage.prototype.setItem=function(){throw new DOMException('denied','QuotaExceededError')};"),
    ]
    for label, fixture in fixtures:
        progress('storage:' + label)
        context, page = open_game(browser, origin, 390, 844, fixture)
        try:
            check(page.locator('[data-action="continue"]').count() == 0, label + " storage does not offer invalid continue")
            start(page)
            check(state(page)["chapter"] == 0, label + " storage permits a new adventure")
            if label == "denied":
                notice = page.locator("#save-notice").inner_text()
                check("저장" in notice and ("없" in notice or "실패" in notice), "blocked storage is explained")
                page.locator(".dpad .right").tap()
                in_memory = state(page)
                page.locator("#pause-button").click()
                page.locator('[data-modal-action="home"]').click()
                check(page.locator("#game-main").get_attribute("data-mode") == "cover", "denied storage still permits returning to the title")
                page.locator('[data-action="continue"]').click()
                resumed = state(page)
                check(resumed["position"] == in_memory["position"] and resumed["mode"] == in_memory["mode"],
                      "denied storage can continue the in-memory adventure after returning home")
            screenshot(page, "storage-" + label)
        finally:
            close_context(context, 'storage-' + label)


def run_worker(run_id):
    initialize_worker(run_id)
    from playwright.sync_api import sync_playwright

    server = Server(("127.0.0.1", 0), Handler)
    origin = f"http://127.0.0.1:{server.server_address[1]}"
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        with sync_playwright() as playwright:
            launch = {"headless": True, "args": ["--no-sandbox"]}
            if os.getenv("CHROMIUM_PATH"):
                launch["executable_path"] = os.environ["CHROMIUM_PATH"]
            progress('browser:launch')
            browser = playwright.chromium.launch(**launch)
            try:
                layouts_and_storage(browser, origin)
                playthrough(browser, origin)
                check(not report["externalRequests"], "offline game requests no external resources")
                check(not report["errors"], "no JavaScript or CSP errors")
                check(BUILD_HASH == hashlib.sha256((DIST / "index.html").read_bytes()).hexdigest(),
                      "tested HTML stays byte-identical throughout browser verification")
                if not os.getenv('RPG_TEST_DIST'):
                    check((DIST / 'index.html').read_bytes() == (DIST / 'review.html').read_bytes(), 'downloadable and review HTML are the same verified artifact')
                report["status"] = "passed"
            except Exception:
                report['failurePhase'] = report.get('lastProgress')
                raise
            finally:
                progress('browser:close')
                browser.close()
                progress('browser:closed')
    except Exception as error:
        report["status"] = "failed"
        report["failure"] = str(error)
        report.setdefault('failurePhase', report.get('lastProgress'))
        raise
    finally:
        progress('server:close')
        server.shutdown()
        server.server_close()
        report["automationSeconds"] = round(time.monotonic() - started, 2)
        report["buildUnchanged"] = BUILD_HASH == hashlib.sha256((DIST / "index.html").read_bytes()).hexdigest()
        write_json(OUT / 'report.json', report)
        checkpoint()
        print(json.dumps({"status": report["status"], "checks": len(report["checks"]), "errors": report["errors"], "screenshots": len(report["screenshots"])}, ensure_ascii=False), flush=True)
    return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--run-id', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        if not args.run_id:
            parser.error('The internal worker requires its supervisor run directory')
        return run_worker(args.run_id)
    if args.run_id:
        parser.error('A run directory is only valid for the internal worker')

    build_hash = hashlib.sha256((DIST / 'index.html').read_bytes()).hexdigest()
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ') + '-' + build_hash[:12] + '-' + uuid.uuid4().hex[:6]
    directory = RESULTS / 'runs' / run_id
    directory.mkdir(parents=True, exist_ok=False)
    print(json.dumps({'rpgWatchdog': 'started', 'limitSeconds': WATCHDOG_SECONDS,
                      'runDirectory': str(directory.relative_to(ROOT))}), flush=True)
    outcome = run_guarded([sys.executable, str(Path(__file__).resolve()), '--worker', '--run-id', run_id])
    value = supervised_report(directory, outcome)
    value.setdefault('runDirectory', str(directory.relative_to(ROOT)))
    value.setdefault('htmlSha256', build_hash)
    value.setdefault('humanPlaytimeMeasured', False)
    value.setdefault('automationSeconds', outcome['elapsedSeconds'])
    for key in ('checks', 'errors', 'externalRequests', 'screenshots'):
        value.setdefault(key, [])
    write_json(directory / 'report.json', value)
    write_json(RESULTS / 'report.json', value)
    if value['status'] == 'passed':
        write_json(RESULTS / 'latest-passed.json', value)
    print(json.dumps({'rpgWatchdog': value['status'], **outcome,
                      'checks': len(value['checks']), 'lastProgress': value.get('lastProgress')}), flush=True)
    return 0 if value['status'] == 'passed' else outcome['exitCode'] if outcome['exitCode'] > 0 else 1


if __name__ == '__main__':
    sys.exit(main())
