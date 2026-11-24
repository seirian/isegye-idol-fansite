(() => {
  'use strict';
  const E = globalThis.CourierEngine;
  const $ = id => document.getElementById(id);
  const key = 'isegye:review:courier:v2';
  const sitePrefsKey = 'isegye:archive:prefs:v1';
  const legacyThemeKey = 'isegye:theme:v1';
  const systemTheme = matchMedia('(prefers-color-scheme: dark)');
  const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const compactField = matchMedia('(max-width: 700px)');
  const portraits = ['ine', 'jing', 'lilpa', 'jururu', 'gosegu', 'viichan'];
  const art = {};
  const keys = new Set();
  const touches = new Set();
  let stepDirection = '', stepTime = 0;
  const canvas = $('arena'), ctx = canvas.getContext('2d');
  let selected = 'ine', state = null, screen = 'loading', paused = false, raf = 0, lastFrame = 0;
  let audio = null, sound = false, runs = 0, storageOK = true, countdown = 0;
  let particles = [], floaters = [], rings = [], joystick = { x: 0, y: 0 }, joystickPointer = null;
  let sceneTime = 0, bannerTimer = 0, hudFrame = 0, finished = false, currentMode = '';
  let difficulty = 'easy', records = readRecords(null), skillCast = null;
  const upgradesById = new Map(E.UPGRADES.map(item => [item.id, item]));
  const gearFrames = ['speed','shield','magnet','quill','spool','fan','ribbon'];
  const gearEffects = {
    speed:'이동 속도 +14%', shield:'최대 하트 +1 · 하트 1 회복', magnet:'편지 수집 거리 +34',
    quill:'별탄 피해 +5', spool:'발사 간격 15% 단축', fan:'추가 별탄 +1발', ribbon:'특기 대기시간 18% 단축'
  };
  const routeAt = stage => E.ROUTES[Math.min(stage, E.ROUTES.length - 1)];
  let themePreference = readTheme();
  function readTheme() {
    try {
      const prefs = JSON.parse(localStorage.getItem(sitePrefsKey) || 'null');
      if (prefs?.theme === 'dark' || prefs?.theme === 'light') return prefs.theme;
      const legacy = localStorage.getItem(legacyThemeKey);
      if (legacy === 'dark' || legacy === 'light') return legacy;
    } catch { /* Restricted storage still follows the device. */ }
    return 'system';
  }
  function applyTheme() {
    const dark = themePreference === 'dark' || (themePreference === 'system' && systemTheme.matches);
    document.documentElement.dataset.theme = dark ? 'dark' : 'light';
    $('theme-button').setAttribute('aria-pressed', String(dark));
    $('theme-button').title = dark ? '밝은 화면으로 전환' : '어두운 화면으로 전환';
    $('theme-icon').textContent = dark ? '☀' : '☾';
    $('theme-setting').value = themePreference;
    document.querySelector('meta[name="theme-color"]').content = dark ? '#162725' : '#eceddf';
  }
  function setTheme(preference) {
    themePreference = preference;
    applyTheme();
    try {
      const saved = localStorage.getItem(sitePrefsKey);
      // The archive creates this record after migrating the visitor's old bookmarks.
      if (saved === null) {
        if (preference === 'system') localStorage.removeItem(legacyThemeKey);
        else localStorage.setItem(legacyThemeKey, preference);
        return;
      }
      const prefs = JSON.parse(saved);
      if (!prefs || typeof prefs !== 'object' || Array.isArray(prefs)) throw new Error('Invalid preferences');
      if (preference === 'system') {
        delete prefs.theme;
        localStorage.removeItem(legacyThemeKey);
      } else prefs.theme = preference;
      localStorage.setItem(sitePrefsKey, JSON.stringify(prefs));
    } catch { announce('이번 탭에 화면 설정을 적용했어요.'); }
  }
  applyTheme();
  systemTheme.addEventListener('change', applyTheme);
  globalThis.addEventListener('storage', event => {
    if (event.key === null || event.key === sitePrefsKey || event.key === legacyThemeKey) {
      themePreference = readTheme(); applyTheme();
    }
  });
  if (typeof activateGameFonts === 'function') activateGameFonts();
  if (typeof gameFontNotices === 'function') {
    const labels = {'Gowun Dodum':'고운돋움 (Gowun Dodum)', Jua:'주아체 (Jua)'};
    for (const [family, notice] of Object.entries(gameFontNotices())) {
      const license = node('pre', '', notice);
      license.lang = 'en';
      document.querySelector('.font-licenses').append(node('h3', '', labels[family]), license);
    }
  }
  function node(tag, className, text) {
    const el = document.createElement(tag);
    if (className) el.className = className;
    if (text !== undefined) el.textContent = text;
    return el;
  }
  function bestLabel() {
    const {best,lastDelivery} = records[difficulty];
    const level = E.DIFFICULTIES[difficulty].name;
    const score = lastDelivery || best ? `최고 ${best.toLocaleString()}점` : '첫 배달 전';
    const recent = lastDelivery ? ` · 최근 ${lastDelivery.completed}곳 배송` : '';
    return `${level} · ${score}${recent}${storageOK ? '' : ' · 이 탭에서만 기록'}`;
  }
  function announce(text) { $('announcement').textContent = text; }
  function validCount(number) { return Number.isSafeInteger(number) && number >= 0; }
  function readRecords(data) {
    return Object.fromEntries(Object.keys(E.DIFFICULTIES).map(id => {
      const entry = data?.recordsByDifficulty?.[id] ?? (id === 'easy' ? data : null);
      const best = validCount(entry?.best) ? entry.best : 0;
      const completed = entry?.lastDelivery?.completed;
      const lastDelivery = validCount(completed) && completed <= E.ROUTES.length ? {completed} : null;
      return [id, {best, lastDelivery}];
    }));
  }
  function readProgress() {
    let raw;
    try { raw = localStorage.getItem(key); } catch { storageOK = false; return null; }
    try {
      const data = JSON.parse(raw);
      return data?.version === 2 ? data : null;
    } catch { return null; }
  }
  function save(changes, result) {
    const stored = storageOK ? readProgress() : null;
    if (stored) {
      records = readRecords(stored);
      if (validCount(stored.runs)) runs = stored.runs;
    }
    let newBest = false;
    if (result) {
      const record = records[result.difficulty];
      newBest = result.score > record.best;
      if (newBest) record.best = result.score;
      record.lastDelivery = {completed:result.deliveries};
      runs++;
    }
    if (storageOK) {
      try {
        const data = {version:2, selected:stored?.selected ?? selected, sound:stored?.sound ?? sound,
          difficulty:stored?.difficulty ?? difficulty, ...changes, best:records.easy.best,
          lastDelivery:records.easy.lastDelivery, recordsByDifficulty:records, runs};
        localStorage.setItem(key, JSON.stringify(data));
      } catch { storageOK = false; }
    }
    return newBest;
  }
  const restored = readProgress();
  if (restored) {
    records = readRecords(restored);
    if (validCount(restored.runs)) runs = restored.runs;
    if (portraits.includes(restored.selected)) selected = restored.selected;
    if (typeof restored.difficulty === 'string' && Object.hasOwn(E.DIFFICULTIES, restored.difficulty)) difficulty = restored.difficulty;
    sound = restored.sound === true;
  }
  function soundLabel() {
    $('sound-button').textContent = sound ? '♪ 소리 켜짐' : '소리 꺼짐';
    $('sound-button').setAttribute('aria-pressed', String(sound));
  }
  function initAudio() {
    if (!sound) return;
    try {
      const A = globalThis.AudioContext || globalThis.webkitAudioContext;
      if (!audio && A) audio = new A();
      if (audio?.state === 'suspended') audio.resume().catch(() => {});
    } catch { audio = null; }
  }
  function note(freq, duration = .09, delay = 0, type = 'sine', volume = .035) {
    if (!sound || !audio || audio.state !== 'running') return;
    const osc = audio.createOscillator(), gain = audio.createGain(), t = audio.currentTime + delay;
    osc.type = type; osc.frequency.setValueAtTime(freq, t);
    gain.gain.setValueAtTime(0, t); gain.gain.linearRampToValueAtTime(volume, t + .007);
    gain.gain.exponentialRampToValueAtTime(.001, t + duration);
    osc.connect(gain); gain.connect(audio.destination); osc.start(t); osc.stop(t + duration + .02);
  }
  function chime(type) {
    if (type === 'pickup') { note(660 + Math.min(state?.combo || 0, 8) * 65, .10); note(1320, .08, .04, 'sine', .014); }
    else if (type === 'delivery' || type === 'win') [523, 659, 784, 1047].forEach((f, i) => note(f, .24, i * .075));
    else if (type === 'hit') { note(180, .16, 0, 'triangle', .06); note(120, .12, .08, 'triangle'); }
    else if (type === 'dash') note(450, .08, 0, 'triangle', .02);
    else if (type === 'skill') [440, 880].forEach((f, i) => note(f, .2, i * .055));
    else if (type === 'lose') [440, 349, 261].forEach((f, i) => note(f, .2, i * .12));
  }
  function sprite(context, sheet, index, x, y, w, h = w, flip = false) {
    const img = art[sheet]; if (!img) return;
    const sw = img.naturalWidth / 3, sh = img.naturalHeight / 2;
    context.save(); context.translate(x, y); if (flip) context.scale(-1, 1);
    context.drawImage(img, (index % 3) * sw, Math.floor(index / 3) * sh, sw, sh, -w / 2, -h / 2, w, h); context.restore();
  }
  function paintSprite(element, sheet, index, scale = 1) {
    const c = element.getContext('2d'); c.clearRect(0, 0, element.width, element.height);
    const size = Math.min(element.width, element.height) * scale;
    sprite(c, sheet, index, element.width / 2, element.height / 2, size);
  }
  function paintGear(canvas, id) {
    const image = art.gear;
    const frame = gearFrames.indexOf(id);
    const width = image.naturalWidth / 4, height = image.naturalHeight / 2;
    const scale = Math.min(canvas.width / width, canvas.height / height);
    const dw = width * scale, dh = height * scale;
    canvas.getContext('2d').drawImage(image, (frame % 4) * width, Math.floor(frame / 4) * height, width, height,
      (canvas.width - dw) / 2, (canvas.height - dh) / 2, dw, dh);
  }
  function drawHero() {
    const c = $('hero-background'), g = c.getContext('2d'); c.width = 1536; c.height = 1024;
    g.drawImage(art.plaza, 0, 0, c.width, c.height);
    paintSprite($('hero-character'), 'characters', portraits.indexOf(selected), .98);
    $('hero-character').setAttribute('aria-label', `${E.MEMBERS[selected].name} 배송부 캐릭터`);
  }
  function refreshDeparture() {
    const level = E.DIFFICULTIES[difficulty];
    $('start-button').textContent = `${E.MEMBERS[selected].name} · ${level.name} 출발`;
    $('difficulty-description').textContent = level.description;
    $('best-label').textContent = bestLabel();
  }
  function select(id, persist = true) {
    if (!portraits.includes(id)) return;
    selected = id; const m = E.MEMBERS[id];
    document.querySelectorAll('.member-card').forEach(b => {
      const active = b.dataset.member === id;
      b.setAttribute('aria-pressed', String(active)); b.querySelector('.chosen').hidden = !active;
    });
    $('member-name').textContent = m.name; $('member-skill').textContent = m.skill;
    $('member-description').textContent = m.skillDescription;
    if (persist) save({selected});
    if (art.characters) drawHero();
    refreshDeparture();
  }
  function setupDifficulties() {
    for (const [id, level] of Object.entries(E.DIFFICULTIES)) {
      const label = node('label','difficulty-option');
      const radio = node('input');
      radio.type = 'radio'; radio.name = 'difficulty'; radio.value = id; radio.checked = difficulty === id;
      radio.addEventListener('change', () => {
        if (!radio.checked) return;
        difficulty = id; save({difficulty}); refreshDeparture();
      });
      label.append(radio, node('span','',level.name));
      $('difficulty-options').append(label);
    }
  }
  function setupRoster() {
    $('roster').replaceChildren();
    portraits.forEach((id, i) => {
      const b = document.createElement('button'); b.type = 'button'; b.className = 'member-card'; b.dataset.member = id;
      b.setAttribute('aria-label', `${E.MEMBERS[id].name} 선택`); b.setAttribute('aria-pressed', String(id === selected));
      b.innerHTML = '<span class="chosen" aria-hidden="true">✓</span><canvas width="150" height="155" aria-hidden="true"></canvas><strong></strong>';
      b.querySelector('strong').textContent = E.MEMBERS[id].name;
      paintSprite(b.querySelector('canvas'), 'characters', i, 1.08);
      b.addEventListener('click', () => { select(id); initAudio(); note(550 + i * 70); });
      $('roster').append(b);
    });
  }
  function setupManifest() {
    $('first-stop').textContent = E.ROUTES[0].name;
    $('last-stop').textContent = E.ROUTES[E.ROUTES.length - 1].name;
    $('route-manifest').replaceChildren(...E.ROUTES.map((route, index) => {
      const li = node('li');
      li.append(node('span', 'stop-num', String(index + 1).padStart(2, '0')), node('b', '', route.name));
      if (route.boss) li.append(node('span', 'special-stop', '보스'));
      return li;
    }));
  }
  function renderGear(parent) {
    parent.replaceChildren();
    if (!state.upgrades.length) {
      parent.append(node('p', 'gear-empty', '첫 배송을 마치면 장비를 골라 가방에 넣을 수 있어요.'));
    }
    const counts = new Map();
    for (const id of state.upgrades) counts.set(id, (counts.get(id) || 0) + 1);
    const list = node('ul', 'gear-list');
    for (const [id,count] of counts) {
      const item = upgradesById.get(id);
      list.append(node('li', '', `${item.name}${count > 1 ? ' ×' + count : ''} · ${item.description}`));
    }
    for (const item of state.evolutions) list.append(node('li', 'evolved', `진화 · ${item.name} — ${item.description}`));
    if (list.childElementCount) parent.append(list);
    const recipes = node('details','gear-recipes');
    recipes.append(node('summary','','진화 조합 보기'));
    const combos = node('ul','recipe-list');
    for (const evo of E.EVOLUTIONS) {
      const row = node('li');
      const names = evo.requires.map(id => upgradesById.get(id).name);
      row.append(node('strong','',evo.name), node('span','',names.join(' + ')), node('p','',evo.description));
      combos.append(row);
    }
    recipes.append(combos); parent.append(recipes);
  }
  function updateRoute() {
    const route = routeAt(state.stage);
    $('run-difficulty').textContent = `난이도 · ${E.DIFFICULTIES[state.difficulty].name}`;
    $('stage-label').textContent = `${String(Math.min(state.stage + 1, E.ROUTES.length)).padStart(2,'0')} / ${E.ROUTES.length} · ${route.name}`;
    $('route-brief').textContent = route.brief;
    $('loadout-summary').textContent = `장비 ${state.upgrades.length}개 · 진화 ${state.evolutions.length}개`;
    renderGear($('current-gear'));
  }
  function clearControls() {
    keys.clear(); touches.clear(); joystick = { x: 0, y: 0 }; joystickPointer = null;
    stepDirection = ''; stepTime = 0;
    $('joystick-knob').style.transform = '';
  }
  function showLobby() {
    cancelAnimationFrame(raf); raf = 0; clearControls(); screen = 'lobby'; state = null; paused = false;
    $('game').hidden = true; $('lobby').hidden = false; $('game-overlay').hidden = true;
    $('stage-arrival').hidden = true;
    lockOverlayControls(false);
    document.body.classList.remove('on-route');
    select(selected, false); $('start-button').focus({ preventScroll: true });
  }
  function start() {
    if (screen === 'loading' || document.hidden) return;
    cancelAnimationFrame(raf); clearControls(); initAudio();
    state = E.create(selected, (Date.now() ^ Math.floor(Math.random() * 1000000)) >>> 0, difficulty);
    screen = 'game'; paused = false; finished = false; lastFrame = 0; currentMode = ''; hudFrame = 0;
    $('lobby').hidden = true; $('game').hidden = false; $('game-overlay').hidden = true; $('game-overlay').className = 'game-overlay';
    lockOverlayControls(false); $('pause-button').disabled = false;
    $('pause-button').textContent = '일시정지'; $('skill-name').textContent = '특기';
    $('skill-button').setAttribute('aria-label', `특기: ${E.MEMBERS[selected].skill}`); $('skill-button').title = E.MEMBERS[selected].skill;
    $('field-skill').textContent = `E · ${E.MEMBERS[selected].skill}`; $('delivery-banner').hidden = true;
    document.body.classList.add('on-route');
    document.querySelector('.loadout').open = false;
    events(); updateHUD(); draw();
    $('main').scrollIntoView({ behavior: 'instant', block: 'start' }); canvas.focus({ preventScroll: true });
    raf = requestAnimationFrame(frame);
  }
  function showStageArrival() {
    const route = routeAt(state.stage);
    particles = []; floaters = []; rings = []; skillCast = null;
    clearControls(); sceneTime = 0; countdown = state.stage ? 2.7 : 2.1; bannerTimer = 0;
    $('delivery-banner').hidden = true;
    $('arrival-index').textContent = `배송지 ${String(state.stage + 1).padStart(2,'0')} / ${E.ROUTES.length}`;
    $('arrival-title').textContent = route.name;
    $('arrival-brief').textContent = route.brief;
    $('stage-arrival').hidden = false;
    updateRoute();
    announce(`${state.stage + 1}번째 배송지, ${route.name}. ${route.brief} 편지 ${route.goal}개를 모으세요.`);
  }
  function banner(text, duration = 2.1) {
    $('delivery-banner').textContent = text; $('delivery-banner').hidden = false; bannerTimer = duration; announce(text);
  }
  function burst(x, y, color, count = 16) {
    if (reducedMotion) return;
    for (let i = 0; i < count; i++) { const a = Math.random() * Math.PI * 2, speed = 35 + Math.random() * 110;
      particles.push({ x, y, vx: Math.cos(a) * speed, vy: Math.sin(a) * speed - 30, life: .5 + Math.random() * .5, color, size: 2 + Math.random() * 3 }); }
    if (particles.length > 240) particles.splice(0, particles.length - 240);
  }
  function events() {
    const evolutions = [];
    for (const ev of state.events.splice(0)) {
      if (ev.type === 'stage') showStageArrival();
      if (ev.type === 'pickup') {
        const stamp = { express:'속달 보너스', ward:'보호막', signal:'특기 충전' }[ev.stamp];
        burst(ev.x, ev.y, '#ffe39d', 9);
        floaters.push({ x:ev.x, y:ev.y - 28, text:stamp || `+${ev.points || 100}`, life:1, color:'#fff0b7' });
        chime('pickup');
      }
      if (ev.type === 'cargo-full') banner(state.boss ? '편지 준비 완료 · 보스를 물리치세요!' : '가방이 가득 찼어요! 우체통으로 출발', 3);
      if (ev.type === 'delivery') { burst(ev.x, ev.y, '#b5ffe0', 36); rings.push({ x: ev.x, y: ev.y, radius: 45, life: 1, color: '#b5ffe0' }); chime('delivery'); }
      if (ev.type === 'hit') { burst(ev.x, ev.y, '#ff9cab', 18); floaters.push({ x: ev.x, y: ev.y - 45, text: '피격!', life: 1.2, color: '#ffd2df' }); banner('피격 · 대시와 특기로 적의 포위를 벗어나세요', 1.7); chime('hit'); }
      if (ev.type === 'skill') {
        skillCast = {member:ev.member ?? state.member, x:ev.x, y:ev.y, startedAt:state.stageElapsed, restoredHealth:ev.restoredHealth};
        banner(ev.name, 1.2); chime('skill');
      }
      if (ev.type === 'dash') chime('dash');
      if (ev.type === 'boss-down') banner('우체통 봉쇄 해제! 편지를 가득 채워 배달하세요.', 2.5);
      if (ev.type === 'impact') burst(ev.x, ev.y, '#f6c67b', 3);
      if (ev.type === 'kill') burst(ev.x, ev.y, '#bdeadc', 5);
      if (ev.type === 'split') { burst(ev.x,ev.y,'#ffc78e',8); burst(ev.x,ev.y,'#a8a2f0',7); }
      if (ev.type === 'pulse') {
        const color = {express:'#ffd179',refrain:'#f6b5e8',orbit:'#91f3e6'}[ev.kind] || '#c0f4df';
        rings.push({ x:ev.x, y:ev.y, radius:ev.radius * .76, limit:ev.radius, life:.55, color });
      }
      if (ev.type === 'evolve') evolutions.push(ev.name);
      if (ev.type === 'win' || ev.type === 'lose') chime(ev.type);
    }
    if (evolutions.length) banner(`장비 진화 · ${evolutions.join(' · ')}`, 3);
  }
  function input() {
    const has = a => keys.has(a);
    const direction = name => touches.has(name) || (stepTime > 0 && stepDirection === name);
    const x = (has('ArrowRight') || has('KeyD') || direction('right') ? 1 : 0) - (has('ArrowLeft') || has('KeyA') || direction('left') ? 1 : 0);
    const y = (has('ArrowDown') || has('KeyS') || direction('down') ? 1 : 0) - (has('ArrowUp') || has('KeyW') || direction('up') ? 1 : 0);
    return { x: x || joystick.x, y: y || joystick.y };
  }
  function frame(t) {
    const dt = Math.min(.05, (t - (lastFrame || t)) / 1000); lastFrame = t;
    if (!paused && !document.hidden) {
      sceneTime += dt;
      if (countdown > 0) {
        countdown = Math.max(0, countdown - dt);
        if (!countdown) {
          $('stage-arrival').hidden = true;
          if (!state.stage) banner('이동하며 편지를 모아요 · 가까운 적은 자동 공격', 2);
        }
      }
      else if (state.mode === 'playing') { E.update(state, dt, input()); stepTime = Math.max(0, stepTime - dt); events(); }
      updateEffects(dt);
      if (state.mode !== currentMode) { currentMode = state.mode; if (state.mode === 'upgrade') showUpgrade(); if (state.mode === 'won' || state.mode === 'lost') showResult(); }
      if (bannerTimer > 0) { bannerTimer -= dt; if (bannerTimer <= 0) $('delivery-banner').hidden = true; }
    }
    draw(); if (++hudFrame % 3 === 0) updateHUD();
    raf = requestAnimationFrame(frame);
  }
  function updateEffects(dt) {
    for (const p of particles) { p.x += p.vx * dt; p.y += p.vy * dt; p.vy += 55 * dt; p.life -= dt; }
    particles = particles.filter(p => p.life > 0);
    for (const f of floaters) { f.y -= dt * 24; f.life -= dt; } floaters = floaters.filter(f => f.life > 0);
    for (const r of rings) { r.radius = Math.min(r.limit ?? Infinity,r.radius + dt * 180); r.life -= dt; } rings = rings.filter(r => r.life > 0);
  }
  function draw() {
    if (!state) return;
    const vector = input();
    CourierRenderer.draw(ctx, art, state, {
      compact: compactField.matches, reducedMotion, elapsed: sceneTime, countdown:0,
      moving: !paused && !countdown && state.mode === 'playing' && Math.hypot(vector.x, vector.y) > .1,
      particles, floaters, rings, paused, skillCast
    });
  }
  function updateHUD() {
    if (!state) return;
    const seconds = Math.ceil(state.timeLeft);
    $('time-value').firstChild.nodeValue = String(seconds);
    document.querySelector('.hud-time').classList.toggle('urgent', seconds <= 10);
    const delivered = state.mode === 'upgrade' || state.mode === 'won';
    const goal = delivered ? routeAt(state.deliveries - 1).goal : state.required;
    const count = delivered ? goal : state.cargo;
    $('cargo-value').textContent = `${count} / ${goal}`;
    $('cargo-fill').style.width = `${Math.min(100, count / goal * 100)}%`;
    const left = Math.max(0, state.required - state.cargo);
    const progress = { upgrade:'배달 완료 · 다음 장비 선택', won:'전 구간 배송 완료', lost:'이번 여정 종료' };
    $('objective').textContent = progress[state.mode] || (left ? `편지 ${left}개 더 모으기` : state.boss ? '보스를 물리쳐 우체통 열기' : '편지 준비 완료 · 우체통으로!');
    $('score-value').textContent = state.score.toLocaleString();
    $('hearts-value').textContent = `♥ ${state.hearts} / ${state.maxHearts}`;
    $('hearts-value').setAttribute('aria-label', `체력 ${state.hearts} / ${state.maxHearts}`);
    $('combo-label').textContent = `수집 콤보 ${state.combo} · 퇴치 ${state.stats.kills}`;
    const boss = state.boss;
    $('boss-status').hidden = !boss || state.mode !== 'playing';
    if (boss) {
      const hp = Math.max(0,Math.ceil(boss.hp));
      $('boss-name').textContent = `우체통 봉쇄 · ${boss.name}`;
      $('boss-health').textContent = `${hp} / ${boss.maxHp}`;
      $('boss-meter').max = boss.maxHp;
      $('boss-meter').value = hp;
    }
    $('dash-label').textContent = state.dashCooldown > 0 ? `${state.dashCooldown.toFixed(1)}초` : compactField.matches ? '준비' : 'Space';
    $('skill-label').textContent = state.skillCooldown > 0 ? `${Math.ceil(state.skillCooldown)}초` : compactField.matches ? '준비' : 'E';
    $('dash-button').classList.toggle('cooling', state.dashCooldown > 0);
    $('skill-button').classList.toggle('cooling', state.skillCooldown > 0);
  }
  function lockOverlayControls(lock) {
    for (const selector of ['.masthead', '.game-top', '.control-deck', '.loadout', '#arena']) {
      document.querySelector(selector).inert = lock;
    }
  }
  function overlayCard(title, label) {
    const overlay = $('game-overlay');
    clearControls(); $('delivery-banner').hidden = true;
    overlay.hidden = false;
    overlay.className = 'game-overlay';
    overlay.setAttribute('aria-labelledby', 'overlay-title');
    const card = node('div', 'overlay-card');
    if (label) card.append(node('p', 'eyebrow', label));
    const heading = node('h2', '', title); heading.id = 'overlay-title';
    card.append(heading); overlay.replaceChildren(card);
    lockOverlayControls(true);
    return card;
  }
  function closeOverlay() {
    $('game-overlay').hidden = true;
    lockOverlayControls(false);
    $('pause-button').disabled = false;
    clearControls(); lastFrame = 0;
    canvas.focus({ preventScroll:true });
  }
  function addButton(parent, label, css, id, action) {
    const button = node('button', css, label);
    button.type = 'button'; button.id = id;
    button.addEventListener('click', action);
    parent.append(button);
    return button;
  }
  function showUpgrade() {
    const card = overlayCard('장비 하나를 골라 주세요', `${state.deliveries}번째 배달 완료`);
    card.classList.add('reward-card');
    const list = node('div','upgrade-list');
    for (const id of state.draft) {
      const item = upgradesById.get(id);
      const button = node('button','upgrade-option');
      button.type = 'button'; button.dataset.upgrade = id;
      const illustration = node('canvas','gear-art');
      illustration.width = illustration.height = 288;
      illustration.setAttribute('aria-hidden','true'); paintGear(illustration,id);
      button.append(illustration,node('strong','',item.name),node('span','gear-effect',gearEffects[id]));
      const ready = E.EVOLUTIONS.filter(recipe => recipe.requires.includes(id) &&
        !state.evolutions.some(earned => earned.id === recipe.id) &&
        recipe.requires.every(part => part === id || state.upgrades.includes(part)));
      if (ready.length) button.append(node('small','ready-evolution',`즉시 진화 · ${ready.map(evo => evo.name).join(' · ')}`));
      button.addEventListener('click', () => {
        if (document.hidden || state?.mode !== 'upgrade' || !E.chooseUpgrade(state,id)) return;
        currentMode = state.mode; closeOverlay(); events(); updateHUD(); draw();
      });
      list.append(button);
    }
    card.append(list);
    list.querySelector('button').focus({preventScroll:true});
    announce(`${state.deliveries}번째 배달 완료. 장비 세 개 중 하나를 고르세요.`);
  }
  function showResult() {
    if (finished) return;
    finished = true;
    const win = state.mode === 'won', fresh = save({}, state);
    const total = E.ROUTES.length;
    const level = E.DIFFICULTIES[state.difficulty].name;
    const title = win ? '별빛 우편, 전 구간 배송 완료!' : `${routeAt(state.stage).name}에서 운행 종료`;
    const card = overlayCard(title, `${E.MEMBERS[selected].name}의 배송 일지 · ${level}`);
    $('game-overlay').classList.add('result-overlay');
    const message = win ? '마지막 환승역 우체통에 편지가 도착했어요. 열 곳의 불빛이 하나씩 켜집니다.' : state.lossReason === 'time'
      ? '이 구간의 마감 시간이 지났어요. 편지를 채우면 우체통 표시를 따라 바로 이동해 보세요.'
      : '가방을 들 힘이 다했어요. 적이 몰리거나 보스 공격이 예고될 때 대시하면 빠져나올 수 있어요.';
    const intro = node('div','result-intro');
    const portrait = node('canvas','result-hero'); portrait.width = portrait.height = 160; portrait.setAttribute('aria-hidden','true');
    paintSprite(portrait,'characters',portraits.indexOf(selected));
    let grade = state.deliveries >= 7 ? 'C' : 'D';
    if (win) grade = state.stats.hits === 0 ? 'S+' : state.hearts >= 2 ? 'A' : 'B';
    const note = node('div');
    note.append(node('strong','result-grade',`배송 등급 ${grade} · 최고 ${state.maxCombo}콤보`),node('p','result-message',message));
    intro.append(portrait,note); card.append(intro);
    const stats = node('div','result-stats');
    for (const [label,value] of [['배달 점수',state.score.toLocaleString()],['배송 완료',`${state.deliveries} / ${total}`],['보스 격파',`${state.stats.bosses} / ${E.ROUTES.filter(r => r.boss).length}`],['적 퇴치',state.stats.kills]]) {
      const cell = node('div'); cell.append(node('strong','',value),node('span','',label)); stats.append(cell);
    }
    card.append(stats);
    const journey = node('ol','result-route'); journey.setAttribute('aria-label','배송지별 결과');
    E.ROUTES.forEach((route,index) => {
      const complete = index < state.deliveries, stopped = !win && index === state.stage;
      const status = complete ? '배송 완료' : stopped ? '운행 종료' : '미도착';
      const stop = node('li',complete ? 'completed' : stopped ? 'last-stop' : '',`${complete ? '✓ ' : ''}${route.name}`);
      stop.setAttribute('aria-label',`${route.name} · ${status}`); stop.title = status;
      journey.append(stop);
    });
    card.append(journey);
    const build = node('details','result-build');
    build.append(node('summary','',`이번 가방 · 장비 ${state.upgrades.length}개, 진화 ${state.evolutions.length}개`));
    const items = node('div'); renderGear(items); build.append(items); card.append(build);
    if (fresh) card.append(node('p','new-best', `${level} 최고 기록을 세웠어요. ${state.score.toLocaleString()}점`));
    const retry = addButton(card,`${level} 난이도로 다시 출발`,'primary-button','retry-button',start);
    addButton(card,'다른 배송부 선택','secondary-button','result-home',showLobby);
    retry.focus({preventScroll:true}); announce(`${title}. ${state.score}점, ${state.deliveries}곳 배송 완료.`);
  }
  function pause(reason) {
    if (screen !== 'game' || state.mode !== 'playing' || paused) return;
    paused = true; $('pause-button').textContent = '계속하기';
    $('stage-arrival').hidden = true;
    const card = overlayCard('잠시 정차 중', `${routeAt(state.stage).name} · ${E.DIFFICULTIES[state.difficulty].name}`);
    card.append(node('p','',reason === 'hidden' ? '다른 화면을 보는 동안 배달 시간을 멈췄어요.' : '배송 시간과 적의 움직임이 멈췄어요. 지금 가방에 든 장비를 살펴볼 수 있어요.'));
    const items = node('div','result-build'); renderGear(items); card.append(items);
    const button = addButton(card,'배달 계속하기','primary-button','resume-button',resume);
    addButton(card,'도움말과 설정','secondary-button','pause-settings',openSettings);
    addButton(card,'이번 여정을 마치고 배송부 선택','secondary-button','pause-home',showLobby);
    button.focus({preventScroll:true}); announce('배달이 일시정지되었습니다.');
  }
  function resume() {
    if (!paused || document.hidden || $('how-dialog').open) return;
    paused = false; $('pause-button').textContent = '일시정지'; closeOverlay();
    $('stage-arrival').hidden = countdown <= 0;
  }
  function openSettings() {
    if (screen === 'game' && !paused && state.mode === 'playing') pause();
    $('how-dialog').showModal();
  }
  function action(name) {
    if (screen !== 'game' || paused || countdown > 0 || state.mode !== 'playing') return;
    if (name === 'dash') E.dash(state); else E.skill(state);
    events(); updateHUD();
  }
  $('start-button').addEventListener('click', start);
  $('home-button').addEventListener('click', () => { if (state && state.mode === 'playing') pause(); else showLobby(); });
  $('pause-button').addEventListener('click', () => paused ? resume() : pause());
  $('how-button').addEventListener('click', openSettings);
  $('settings-button').addEventListener('click', openSettings);
  $('theme-button').addEventListener('click', () => setTheme(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark'));
  $('theme-setting').addEventListener('change', event => setTheme(event.target.value));
  $('close-how').addEventListener('click', () => $('how-dialog').close());
  $('ready-button').addEventListener('click', () => $('how-dialog').close());
  $('sound-button').addEventListener('click', () => { sound = !sound; initAudio(); soundLabel(); save({sound}); if (sound) note(660); });
  $('dash-button').addEventListener('pointerdown', e => { e.preventDefault(); action('dash'); });
  $('skill-button').addEventListener('pointerdown', e => { e.preventDefault(); action('skill'); });
  for (const [id, name] of [['dash-button', 'dash'], ['skill-button', 'skill']]) $(id).addEventListener('click', e => { if (e.detail === 0) action(name); });
  document.addEventListener('keydown', e => {
    if (screen !== 'game' || $('how-dialog').open) return;
    if (e.key === 'Tab' && !$('game-overlay').hidden) {
      const buttons = [...$('game-overlay').querySelectorAll('button:not(:disabled),summary')];
      if (e.shiftKey && document.activeElement === buttons[0]) { e.preventDefault(); buttons.at(-1)?.focus(); }
      else if (!e.shiftKey && document.activeElement === buttons.at(-1)) { e.preventDefault(); buttons[0]?.focus(); }
      return;
    }
    if (e.code === 'Escape') { e.preventDefault(); if (paused) resume(); else pause(); return; }
    if (paused || state.mode !== 'playing') return;
    if (e.target.closest('button,a,input,select,textarea,[contenteditable="true"]')) return;
    if (['ArrowUp','ArrowDown','ArrowLeft','ArrowRight','KeyW','KeyA','KeyS','KeyD','Space','KeyE'].includes(e.code)) e.preventDefault();
    keys.add(e.code); if (!e.repeat && e.code === 'Space') action('dash'); if (!e.repeat && e.code === 'KeyE') action('skill');
  });
  document.addEventListener('keyup', e => keys.delete(e.code));
  globalThis.addEventListener('blur', () => { clearControls(); pause('hidden'); });
  document.addEventListener('visibilitychange', () => { if (document.hidden) { clearControls(); pause('hidden'); } });
  const stick = $('joystick');
  function moveStick(e) {
    const r = stick.getBoundingClientRect(), max = r.width * .31;
    let dx = e.clientX - (r.left + r.width / 2), dy = e.clientY - (r.top + r.height / 2), len = Math.hypot(dx, dy);
    if (len > max) { dx *= max / len; dy *= max / len; }
    joystick = { x: dx / max, y: dy / max }; $('joystick-knob').style.transform = `translate(${dx}px,${dy}px)`;
  }
  stick.addEventListener('pointerdown', e => { if (paused || state?.mode !== 'playing' || joystickPointer !== null) return; e.preventDefault(); joystickPointer = e.pointerId; stick.setPointerCapture(e.pointerId); moveStick(e); });
  stick.addEventListener('pointermove', e => { if (joystickPointer === e.pointerId) { e.preventDefault(); moveStick(e); } });
  const stopStick = e => { if (joystickPointer === e.pointerId) { joystickPointer = null; joystick = { x: 0, y: 0 }; $('joystick-knob').style.transform = ''; } };
  ['pointerup', 'pointercancel', 'lostpointercapture'].forEach(ev => stick.addEventListener(ev, stopStick));
  document.querySelectorAll('[data-direction]').forEach(b => {
    b.addEventListener('pointerdown', e => { e.preventDefault(); touches.add(b.dataset.direction); b.setPointerCapture(e.pointerId); });
    b.addEventListener('click', e => {
      if (e.detail === 0 && !paused && state?.mode === 'playing') { stepDirection = b.dataset.direction; stepTime = .16; }
    });
    ['pointerup', 'pointercancel', 'lostpointercapture'].forEach(ev => b.addEventListener(ev, () => touches.delete(b.dataset.direction)));
  });
  soundLabel();
  // Read-only state visibility supports diagnostics; normal controls own mutations.
  globalThis.CourierApp = Object.freeze({ start, select, pause, resume, get state() { return state; }, get screen() { return screen; }, get paused() { return paused; }, get ready() { return screen !== 'loading'; } });
  Promise.all(Object.entries(COURIER_ART).map(([name, uri]) => new Promise((resolve, reject) => {
    const img = new Image(); img.onload = () => { art[name] = img; resolve(); }; img.onerror = () => reject(new Error(name)); img.src = uri;
  }))).then(() => {
    setupRoster(); setupDifficulties(); setupManifest(); select(selected, false); $('loading').hidden = true; $('lobby').hidden = false; screen = 'lobby'; $('start-button').disabled = false;
  }).catch(() => {
    $('loading').innerHTML = '<h1>그림을 불러오지 못했어요.</h1><p>페이지를 새로고침해 다시 시도해 주세요.</p>';
  });
})();
