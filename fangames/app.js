(() => {
  'use strict';
  const E = globalThis.CourierEngine;
  const $ = id => document.getElementById(id);
  const key = 'isegye:review:courier:v2';
  const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const compactField = matchMedia('(max-width: 700px)');
  const portraits = ['ine', 'jing', 'lilpa', 'jururu', 'gosegu', 'viichan'];
  const art = {};
  const keys = new Set();
  const touches = new Set();
  const canvas = $('arena'), ctx = canvas.getContext('2d');
  let selected = 'ine', state = null, screen = 'loading', paused = false, raf = 0, lastFrame = 0;
  let audio = null, sound = false, best = 0, runs = 0, storageOK = true, countdown = 0;
  let particles = [], floaters = [], rings = [], trails = [], joystick = { x: 0, y: 0 }, joystickPointer = null;
  let sceneTime = 0, bannerTimer = 0, hudFrame = 0, finished = false, currentMode = '';
  function announce(text) { $('announcement').textContent = text; }
  function save() {
    try { localStorage.setItem(key, JSON.stringify({ version: 2, best, runs, selected, sound })); }
    catch { storageOK = false; }
  }
  try {
    const data = JSON.parse(localStorage.getItem(key) || 'null');
    if (data && data.version === 2) {
      best = Number.isSafeInteger(data.best) && data.best >= 0 && data.best < 1000000 ? data.best : 0;
      runs = Number.isSafeInteger(data.runs) && data.runs >= 0 ? data.runs : 0;
      if (portraits.includes(data.selected)) selected = data.selected;
      sound = data.sound === true;
    }
  } catch { storageOK = false; }
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
  function drawHero() {
    const c = $('hero-background'), g = c.getContext('2d'); c.width = 1536; c.height = 1024;
    g.drawImage(art.plaza, 0, 0, c.width, c.height);
    paintSprite($('hero-character'), 'characters', portraits.indexOf(selected), .98);
    $('hero-character').setAttribute('aria-label', `새로 그린 ${E.MEMBERS[selected].name} 별빛 배송부 캐릭터`);
  }
  function select(id) {
    if (!portraits.includes(id)) return;
    selected = id; const m = E.MEMBERS[id];
    document.querySelectorAll('.member-card').forEach(b => {
      const active = b.dataset.member === id;
      b.setAttribute('aria-pressed', String(active)); b.querySelector('.chosen').hidden = !active;
    });
    $('member-name').textContent = m.name; $('member-skill').textContent = m.skill;
    $('member-description').textContent = m.skillDescription;
    $('start-button').textContent = `${m.name}와 배달 시작  →`;
    document.querySelector('.hero-number').textContent = `0${portraits.indexOf(id) + 1} / 06`;
    if (art.characters) drawHero(); save();
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
  function clearControls() {
    keys.clear(); touches.clear(); joystick = { x: 0, y: 0 }; joystickPointer = null;
    $('joystick-knob').style.transform = '';
  }
  function showLobby() {
    cancelAnimationFrame(raf); raf = 0; clearControls(); screen = 'lobby'; state = null; paused = false;
    $('game').hidden = true; $('lobby').hidden = false; $('game-overlay').hidden = true;
    $('best-label').textContent = storageOK ? (best ? `최고 기록 ${best.toLocaleString()}점` : '첫 배달을 기다리는 중') : '기록 저장을 사용할 수 없어요';
    select(selected); $('start-button').focus({ preventScroll: true });
  }
  function start() {
    if (screen === 'loading') return;
    cancelAnimationFrame(raf); clearControls(); initAudio();
    state = E.create(selected, (Date.now() ^ Math.floor(Math.random() * 1000000)) >>> 0);
    screen = 'game'; paused = false; finished = false; particles = []; floaters = []; rings = []; trails = [];
    countdown = 2.1; sceneTime = 0; lastFrame = 0; currentMode = ''; hudFrame = 0;
    $('lobby').hidden = true; $('game').hidden = false; $('game-overlay').hidden = true; $('game-overlay').className = 'game-overlay';
    $('pause-button').textContent = '일시정지'; $('skill-name').textContent = '특기';
    $('skill-button').setAttribute('aria-label', `특기: ${E.MEMBERS[selected].skill}`); $('skill-button').title = E.MEMBERS[selected].skill;
    $('field-skill').textContent = `E · ${E.MEMBERS[selected].skill}`; $('delivery-banner').hidden = true;
    updateHUD(); draw();
    $('main').scrollIntoView({ behavior: 'instant', block: 'start' }); canvas.focus({ preventScroll: true });
    announce(`${E.MEMBERS[selected].name}의 배달 시작. 편지 4개를 모아 중앙 우체통으로 가세요.`);
    raf = requestAnimationFrame(frame);
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
    for (const ev of state.events.splice(0)) {
      if (ev.type === 'pickup') { burst(ev.x, ev.y, '#ffe39d', 9); floaters.push({ x: ev.x, y: ev.y - 28, text: `+${ev.points || 100}`, life: .9, color: '#fff0b7' }); chime('pickup'); }
      if (ev.type === 'cargo-full') banner('가방이 가득 찼어요! 중앙 우체통으로 ✉', 3);
      if (ev.type === 'delivery') { burst(480, 320, '#b5ffe0', 48); rings.push({ x: 480, y: 320, radius: 45, life: 1, color: '#b5ffe0' }); chime('delivery'); }
      if (ev.type === 'hit') { burst(ev.x, ev.y, '#ff9cab', 18); floaters.push({ x: ev.x, y: ev.y - 45, text: '앗! 편지를 놓쳤어요', life: 1.2, color: '#ffd2df' }); banner('잠깐! 대시와 특기로 유령을 피하세요', 1.7); chime('hit'); }
      if (ev.type === 'skill') { rings.push({ x: ev.x, y: ev.y, radius: 40, life: .8, color: E.MEMBERS[selected].color }); burst(ev.x, ev.y, E.MEMBERS[selected].color, 24); banner(ev.name, 1.2); chime('skill'); }
      if (ev.type === 'dash') chime('dash');
      if (ev.type === 'upgrade') banner(`${state.stage + 1}번째 배달 · 편지 ${state.required}개`, 2.2);
      if (ev.type === 'win' || ev.type === 'lose') chime(ev.type);
    }
  }
  function input() {
    const has = a => keys.has(a);
    const x = (has('ArrowRight') || has('KeyD') || touches.has('right') ? 1 : 0) - (has('ArrowLeft') || has('KeyA') || touches.has('left') ? 1 : 0);
    const y = (has('ArrowDown') || has('KeyS') || touches.has('down') ? 1 : 0) - (has('ArrowUp') || has('KeyW') || touches.has('up') ? 1 : 0);
    return { x: x || joystick.x, y: y || joystick.y };
  }
  function frame(t) {
    const dt = Math.min(.05, (t - (lastFrame || t)) / 1000); lastFrame = t;
    if (!paused) {
      sceneTime += dt;
      if (countdown > 0) { countdown = Math.max(0, countdown - dt); if (!countdown) banner('편지를 모아 중앙 우체통으로!', 2); }
      else if (state.mode === 'playing') { E.update(state, dt, input()); events(); }
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
    for (const r of rings) { r.radius += dt * 180; r.life -= dt; } rings = rings.filter(r => r.life > 0);
    for (const tr of trails) tr.life -= dt; trails = trails.filter(tr => tr.life > 0);
    if (!reducedMotion && state.dashTime > 0) trails.push({ x: state.x, y: state.y, life: .25 });
  }
  function ellipse(x, y, rx, ry, fill) { ctx.beginPath(); ctx.ellipse(x, y, rx, ry, 0, 0, Math.PI * 2); ctx.fillStyle = fill; ctx.fill(); }
  function draw() {
    if (!state || !art.plaza) return;
    ctx.clearRect(0, 0, 960, 640);
    ctx.save();
    if (compactField.matches) { ctx.scale(1.25, 1.25); ctx.translate(-96, -60); }
    ctx.drawImage(art.plaza, 0, 0, 960, 640);
    ctx.fillStyle = '#111b341c'; ctx.fillRect(0, 0, 960, 640);
    const pulse = reducedMotion ? 0 : Math.sin(sceneTime * 3);
    const ready = state.cargo >= state.required;
    const glow = ctx.createRadialGradient(480, 320, 15, 480, 320, ready ? 110 : 75);
    glow.addColorStop(0, ready ? '#b6ffe270' : '#acb4f02a'); glow.addColorStop(1, '#b6ffe200');
    ctx.fillStyle = glow; ctx.beginPath(); ctx.arc(480, 320, ready ? 110 : 75, 0, Math.PI * 2); ctx.fill();
    ctx.save(); ctx.strokeStyle = ready ? '#bdffe4' : '#d9c78475'; ctx.lineWidth = ready ? 3 : 1.5;
    ctx.setLineDash(ready ? [] : [6, 7]); ctx.beginPath(); ctx.ellipse(480, 333, 58 + pulse * 2, 26, 0, 0, Math.PI * 2); ctx.stroke(); ctx.restore();
    ellipse(480, 335, 39, 12, '#17213d55'); sprite(ctx, 'items', 5, 480, 296, 102);
    ctx.font = 'bold 13px sans-serif'; ctx.textAlign = 'center'; ctx.fillStyle = ready ? '#e4fff1' : '#eee5cc';
    ctx.shadowColor = '#0c153a'; ctx.shadowBlur = 5; ctx.fillText(ready ? '여기에 배달! ↓' : '별빛 우체통', 480, 235); ctx.shadowBlur = 0;
    for (let i = 0; i < 3; i++) { ctx.fillStyle = i < state.deliveries ? '#baffdf' : '#69758a'; ctx.beginPath(); ctx.arc(464 + i * 16, 359, 4, 0, Math.PI * 2); ctx.fill(); }
    for (const star of state.stars) {
      if (star.availableAt > state.elapsed) continue;
      const bob = reducedMotion ? 0 : Math.sin(sceneTime * 3 + star.phase) * 4;
      ellipse(star.x, star.y + 9, 17, 5, '#17213d45');
      const g = ctx.createRadialGradient(star.x, star.y, 1, star.x, star.y, 30); g.addColorStop(0, '#ffda6570'); g.addColorStop(1, '#ffda6500'); ctx.fillStyle = g; ctx.fillRect(star.x - 30, star.y - 30, 60, 60);
      sprite(ctx, 'items', 0, star.x, star.y - 6 + bob, 43);
    }
    const entities = state.enemies.map(e => ({ ...e, entity: 'enemy' })); entities.push({ x: state.x, y: state.y, entity: 'player' }); entities.sort((a, b) => a.y - b.y);
    for (const entity of entities) {
      if (entity.entity === 'player') drawPlayer(pulse);
      else {
        const e = entity; ctx.save(); if (e.spawnTime > 0) ctx.globalAlpha = .35 + Math.sin(sceneTime * 15) * .15;
        ellipse(e.x, e.y + 10, 22, 7, '#151a3650');
        const bob = reducedMotion ? 0 : Math.sin(sceneTime * 4 + e.phase) * 3;
        sprite(ctx, 'items', e.kind === 'mote' ? 2 : 1, e.x, e.y - 9 + bob, e.kind === 'mote' ? 61 : 57);
        if (e.stunTime > 0) { ctx.fillStyle = '#fff0ab'; ctx.font = '18px sans-serif'; ctx.fillText('✦', e.x, e.y - 40); }
        if (state.slowTime > 0) { ctx.strokeStyle = '#8bddff99'; ctx.lineWidth = 2; ctx.beginPath(); ctx.ellipse(e.x, e.y + 12, 25, 9, 0, 0, Math.PI * 2); ctx.stroke(); }
        ctx.restore();
      }
    }
    for (const p of particles) { ctx.globalAlpha = Math.min(1, p.life * 2); ctx.fillStyle = p.color; ctx.fillRect(p.x, p.y, p.size, p.size); } ctx.globalAlpha = 1;
    for (const r of rings) { ctx.globalAlpha = r.life; ctx.strokeStyle = r.color; ctx.lineWidth = 3; ctx.beginPath(); ctx.ellipse(r.x, r.y, r.radius, r.radius * .6, 0, 0, Math.PI * 2); ctx.stroke(); } ctx.globalAlpha = 1;
    ctx.font = 'bold 16px sans-serif'; ctx.textAlign = 'center';
    for (const f of floaters) { ctx.globalAlpha = Math.min(1, f.life * 2); ctx.fillStyle = f.color; ctx.shadowColor = '#172038'; ctx.shadowBlur = 5; ctx.fillText(f.text, f.x, f.y); } ctx.globalAlpha = 1; ctx.shadowBlur = 0;
    if (ready && !state.nearBeacon && state.mode === 'playing') {
      const a = Math.atan2(320 - state.y, 480 - state.x), x = state.x + Math.cos(a) * 65, y = state.y + Math.sin(a) * 50;
      ctx.save(); ctx.translate(x, y); ctx.rotate(a); ctx.fillStyle = '#d2ffe8'; ctx.beginPath(); ctx.moveTo(12, 0); ctx.lineTo(-6, -8); ctx.lineTo(-2, 0); ctx.lineTo(-6, 8); ctx.fill(); ctx.restore();
    }
    if (countdown > 0) {
      ctx.fillStyle = '#15233a66'; ctx.fillRect(0, 0, 960, 640); ctx.fillStyle = '#f5f2dc'; ctx.textAlign = 'center'; ctx.font = '900 90px sans-serif';
      ctx.shadowColor = '#15203a'; ctx.shadowBlur = 15; ctx.fillText(countdown > 1.25 ? 'READY' : 'GO!', 480, 325); ctx.font = '18px sans-serif'; ctx.fillText('편지 4개를 모아 중앙 우체통으로!', 480, 370); ctx.shadowBlur = 0;
    }
    ctx.restore();
  }
  function drawPlayer(pulse) {
    const s = state, idx = portraits.indexOf(selected), inv = s.invulnerableTime > 0;
    ellipse(s.x, s.y + 8, 26, 9, '#12213b60');
    if (s.shieldTime > 0 || s.magnetTime > 0) {
      ctx.save(); ctx.strokeStyle = s.shieldTime > 0 ? '#a5efffe0' : '#ffb3ddd0'; ctx.lineWidth = 2;
      ctx.fillStyle = s.shieldTime > 0 ? '#9ce2ff18' : '#ffb3dd15';
      ctx.beginPath(); ctx.ellipse(s.x, s.y - 15, 45 + pulse * 3, 48, 0, 0, Math.PI * 2); ctx.fill(); ctx.stroke(); ctx.restore();
    }
    for (const tr of trails) { ctx.globalAlpha = tr.life * 1.4; sprite(ctx, 'characters', idx, tr.x, tr.y - 31, 92, 92, s.dir.x < -.1); } ctx.globalAlpha = 1;
    const moving = Math.hypot(input().x, input().y) > .1;
    const bob = moving && !paused && !reducedMotion && !countdown ? Math.sin(sceneTime * 22) * 3 : 0;
    ctx.save(); if (inv && !reducedMotion) ctx.globalAlpha = .58 + Math.abs(Math.sin(sceneTime * 12)) * .42;
    sprite(ctx, 'characters', idx, s.x, s.y - 32 + bob, 96, 96, s.dir.x < -.1); ctx.restore();
    ctx.fillStyle = '#f5f7ed'; ctx.font = 'bold 11px sans-serif'; ctx.textAlign = 'center'; ctx.shadowColor = '#17243a'; ctx.shadowBlur = 4; ctx.fillText(E.MEMBERS[selected].name, s.x, s.y - 86); ctx.shadowBlur = 0;
    if (s.cargo) { ctx.fillStyle = '#183d32'; ctx.beginPath(); ctx.roundRect(s.x + 21, s.y - 64, 25, 19, 8); ctx.fill(); ctx.fillStyle = '#d9ffe9'; ctx.font = 'bold 11px sans-serif'; ctx.fillText(String(s.cargo), s.x + 33, s.y - 50); }
  }
  function updateHUD() {
    if (!state) return;
    $('time-value').innerHTML = `${Math.ceil(state.timeLeft)}<small>초</small>`;
    document.querySelector('.hud-time').classList.toggle('urgent', state.timeLeft <= 10);
    $('cargo-value').textContent = `${state.cargo} / ${state.required}`;
    $('cargo-fill').style.width = `${state.cargo / state.required * 100}%`;
    $('objective').textContent = state.cargo >= state.required ? '가방 완성! 중앙 우체통으로' : `편지 ${state.required - state.cargo}개 더 모으기`;
    $('score-value').textContent = state.score.toLocaleString();
    $('hearts-value').textContent = `${'♥ '.repeat(Math.max(0, state.hearts))}${'♡ '.repeat(Math.max(0, state.maxHearts - state.hearts))}`.trim();
    $('hearts-value').setAttribute('aria-label', `남은 체력 ${state.hearts}`);
    $('stage-label').textContent = `${Math.min(3, state.stage + 1)} / 3 번째 배달`;
    $('combo-label').textContent = state.combo > 1 ? `${state.combo} COMBO · 연속으로 모으면 점수도 쑥!` : '마음을 모아, 별빛을 전해!';
    $('dash-label').textContent = state.dashCooldown > 0 ? `${state.dashCooldown.toFixed(1)}초` : 'SPACE';
    $('skill-label').textContent = state.skillCooldown > 0 ? `${Math.ceil(state.skillCooldown)}초` : 'E';
    $('dash-button').classList.toggle('cooling', state.dashCooldown > 0);
    $('skill-button').classList.toggle('cooling', state.skillCooldown > 0);
  }
  function showUpgrade() {
    clearControls(); $('delivery-banner').hidden = true; const overlay = $('game-overlay');
    overlay.className = 'game-overlay'; overlay.hidden = false;
    overlay.innerHTML = '<div class="overlay-card"><p class="eyebrow">DELIVERY COMPLETE</p><h2>마음이 잘 도착했어요!</h2><p>다음 배달을 위한 선물을 골라 주세요.<br>고르는 동안 시간은 멈춰요.</p><div class="upgrade-list"></div></div>';
    E.UPGRADES.forEach((u, i) => {
      const b = document.createElement('button'); b.className = 'upgrade-option'; b.dataset.upgrade = u.key;
      b.innerHTML = '<canvas width="110" height="110" aria-hidden="true"></canvas><strong></strong><span></span>';
      b.querySelector('strong').textContent = u.name; b.querySelector('span').textContent = u.description;
      paintSprite(b.querySelector('canvas'), 'items', [0, 3, 4][i]);
      b.addEventListener('click', () => { E.chooseUpgrade(state, u.key); overlay.hidden = true; currentMode = ''; clearControls(); events(); canvas.focus({ preventScroll: true }); });
      overlay.querySelector('.upgrade-list').append(b);
    });
    overlay.querySelector('button').focus({ preventScroll: true }); announce('배달 완료! 다음 배달을 위한 선물을 선택하세요.');
  }
  function showResult() {
    if (finished) return; finished = true; clearControls(); $('delivery-banner').hidden = true;
    const win = state.mode === 'won', fresh = state.score > best;
    if (fresh) best = state.score; runs++; save();
    const grade = win ? (state.stats.hits === 0 ? 'S+' : state.hearts >= 2 ? 'A' : 'B') : (state.deliveries >= 2 ? 'C' : 'D');
    const overlay = $('game-overlay'); overlay.className = 'game-overlay result-overlay'; overlay.hidden = false;
    overlay.innerHTML = '<div class="overlay-card"><canvas class="result-hero" width="220" height="220" aria-hidden="true"></canvas><p class="eyebrow">STARRY DELIVERY REPORT</p><div class="result-grade"></div><h2></h2><p class="result-message"></p><div class="result-stats"></div><button class="primary-button" id="retry-button">한 번 더 배달하기 →</button><button class="secondary-button" id="result-home">다른 배송부 선택</button></div>';
    paintSprite(overlay.querySelector('canvas'), 'characters', portraits.indexOf(selected));
    overlay.querySelector('.result-grade').textContent = grade;
    overlay.querySelector('h2').textContent = win ? '오늘의 별빛, 배송 완료!' : '다음 배달은 더 잘할 거예요';
    overlay.querySelector('.result-message').textContent = win ? `${E.MEMBERS[selected].name}의 손끝에서 무대가 환하게 빛나요.` : state.lossReason === 'time' ? '공연 시작 시간이 되었어요. 대시를 자주 쓰면 더 빠르게 모을 수 있어요.' : '잠깐 쉬어가요. 대시와 멤버 특기로 유령을 피할 수 있어요.';
    overlay.querySelector('.result-stats').innerHTML = `<div><strong>${state.score.toLocaleString()}</strong><span>배달 점수</span></div><div><strong>${state.deliveries} / 3</strong><span>완료한 배달</span></div><div><strong>${state.maxCombo}</strong><span>최대 콤보</span></div>`;
    if (fresh) { const badge = document.createElement('div'); badge.className = 'new-best'; badge.textContent = storageOK ? '✦ 새로운 최고 기록' : '✦ 이번 탭 최고 기록 · 저장 불가'; overlay.querySelector('.result-message').append(document.createElement('br'), badge); }
    $('retry-button').addEventListener('click', start); $('result-home').addEventListener('click', showLobby);
    $('retry-button').focus({ preventScroll: true }); announce(`${win ? '배달 성공' : '배달 종료'}. ${state.score}점, ${state.deliveries}번 배달 완료.`);
  }
  function pause(reason) {
    if (screen !== 'game' || state.mode !== 'playing' || paused) return;
    paused = true; clearControls(); $('pause-button').textContent = '계속하기';
    const overlay = $('game-overlay'); overlay.className = 'game-overlay'; overlay.hidden = false;
    overlay.innerHTML = '<div class="overlay-card"><p class="eyebrow">TAKE A LITTLE BREAK</p><h2>별빛도 잠깐 쉬어가요.</h2><p></p><button class="primary-button" id="resume-button">배달 계속하기 →</button><button class="secondary-button" id="pause-home">배송부 선택으로 돌아가기</button></div>';
    overlay.querySelector('p:not(.eyebrow)').textContent = reason === 'hidden' ? '다른 화면을 보는 동안 게임을 멈췄어요.' : '시간과 유령은 잠시 멈춰 있어요.';
    $('resume-button').addEventListener('click', resume); $('pause-home').addEventListener('click', showLobby);
    $('resume-button').focus({ preventScroll: true }); announce('게임이 일시정지되었습니다.');
  }
  function resume() {
    if (!paused) return; paused = false; clearControls(); lastFrame = 0;
    $('pause-button').textContent = '일시정지'; $('game-overlay').hidden = true; canvas.focus({ preventScroll: true });
  }
  function action(name) {
    if (screen !== 'game' || paused || countdown > 0 || state.mode !== 'playing') return;
    if (name === 'dash') E.dash(state); else E.skill(state);
    events(); updateHUD();
  }
  $('start-button').addEventListener('click', start);
  $('home-button').addEventListener('click', () => { if (state && state.mode === 'playing') pause(); else showLobby(); });
  $('pause-button').addEventListener('click', () => paused ? resume() : pause());
  $('how-button').addEventListener('click', () => $('how-dialog').showModal());
  $('close-how').addEventListener('click', () => $('how-dialog').close());
  $('ready-button').addEventListener('click', () => { $('how-dialog').close(); $('start-button').focus(); });
  $('sound-button').addEventListener('click', () => { sound = !sound; initAudio(); soundLabel(); save(); if (sound) note(660); });
  $('dash-button').addEventListener('pointerdown', e => { e.preventDefault(); action('dash'); });
  $('skill-button').addEventListener('pointerdown', e => { e.preventDefault(); action('skill'); });
  for (const [id, name] of [['dash-button', 'dash'], ['skill-button', 'skill']]) $(id).addEventListener('click', e => { if (e.detail === 0) action(name); });
  document.addEventListener('keydown', e => {
    if (screen !== 'game' || $('how-dialog').open) return;
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
    ['pointerup', 'pointercancel', 'lostpointercapture'].forEach(ev => b.addEventListener(ev, () => touches.delete(b.dataset.direction)));
  });
  soundLabel();
  // Read-only state visibility supports diagnostics; normal controls own mutations.
  globalThis.CourierApp = Object.freeze({ start, select, pause, resume, get state() { return state; }, get screen() { return screen; }, get paused() { return paused; }, get ready() { return screen !== 'loading'; } });
  Promise.all(Object.entries(COURIER_ART).map(([name, uri]) => new Promise((resolve, reject) => {
    const img = new Image(); img.onload = () => { art[name] = img; resolve(); }; img.onerror = () => reject(new Error(name)); img.src = uri;
  }))).then(() => {
    setupRoster(); select(selected); $('loading').hidden = true; $('lobby').hidden = false; screen = 'lobby'; $('start-button').disabled = false;
    $('best-label').textContent = storageOK ? (best ? `최고 기록 ${best.toLocaleString()}점` : '첫 배달을 기다리는 중') : '기록 저장을 사용할 수 없어요';
  }).catch(() => {
    $('loading').innerHTML = '<h1>그림을 불러오지 못했어요.</h1><p>페이지를 새로고침해 다시 시도해 주세요.</p>';
  });
})();
