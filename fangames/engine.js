/*
 * DOM-free game simulation. All distances are in a 960 × 640 arena; dt is seconds.
 * CourierEngine.create(memberId, seed) -> mutable state.
 * update(state, dt, {x, y}) accepts keyboard or analogue-stick vectors and limits
 * delayed frames to 100 ms. dash/skill/chooseUpgrade return whether they acted.
 * Renderer consumes state.events.splice(0); no renderer or clock is required.
 * State uses x/y directly, dir:{x,y}, stage:0..2 and mode:
 * playing -> upgrade -> playing -> ... -> won | lost.
 */
(function (global) {
  'use strict';

  // Match the illustrated plaza: feet stay below the stage and inside the shops.
  const BOUNDS = Object.freeze({ left: 155, right: 805, top: 165, bottom: 550 });
  const ARENA = Object.freeze({ width: 960, height: 640, padding: 34, bounds: BOUNDS });
  const BEACON = Object.freeze({ x: 480, y: 320, radius: 57 });
  const REQUIREMENTS = Object.freeze([4, 6, 8]);
  const MEMBERS = Object.freeze({
    ine: Object.freeze({ id: 'ine', name: '아이네', color: '#b397ff', skill: '별빛 보호막', skillDescription: '4초 동안 피해를 막고 가까운 젤리를 밀어내요.', cooldown: 10 }),
    jing: Object.freeze({ id: 'jing', name: '징버거', color: '#ffcc69', skill: '젤리 슬로 타임', skillDescription: '5초 동안 모든 젤리가 느리게 움직여요.', cooldown: 11 }),
    lilpa: Object.freeze({ id: 'lilpa', name: '릴파', color: '#8cafff', skill: '밤하늘 비행', skillDescription: '4초 동안 빨라지고 출발할 때 피해를 막아요.', cooldown: 11 }),
    jururu: Object.freeze({ id: 'jururu', name: '주르르', color: '#ff9bc6', skill: '하트 자석', skillDescription: '4초 동안 멀리 있는 별 편지를 끌어당겨요.', cooldown: 10 }),
    gosegu: Object.freeze({ id: 'gosegu', name: '고세구', color: '#7be4f0', skill: '구름 팡!', skillDescription: '주변 젤리를 밀어내고 3초 동안 멈춰요.', cooldown: 10 }),
    viichan: Object.freeze({ id: 'viichan', name: '비챤', color: '#afe58e', skill: '숲의 응원', skillDescription: '하트를 하나 회복해요. 하트가 가득 차면 보호막!', cooldown: 13 })
  });
  const UPGRADES = Object.freeze([
    Object.freeze({ id: 'speed', key: 'speed', name: '가벼운 운동화', description: '이동 속도 +14%', icon: 'speed' }),
    Object.freeze({ id: 'shield', key: 'shield', name: '든든한 우편 가방', description: '최대 하트 +1 · 하트 1 회복', icon: 'shield' }),
    Object.freeze({ id: 'magnet', key: 'magnet', name: '반짝이는 나침반', description: '별 편지를 더 멀리서 수집', icon: 'magnet' })
  ]);
  const STEP = 1 / 120;
  const clamp = (value, min, max) => Math.max(min, Math.min(max, value));
  const distance = (a, b) => Math.hypot(a.x - b.x, a.y - b.y);

  function seedNumber(seed) {
    if (typeof seed === 'number' && Number.isFinite(seed)) return seed >>> 0;
    let hash = 2166136261;
    for (const ch of String(seed ?? 1)) hash = Math.imul(hash ^ ch.charCodeAt(0), 16777619);
    return hash >>> 0;
  }

  function random(s) {
    s._rng = (s._rng + 0x6D2B79F5) >>> 0;
    let value = s._rng;
    value = Math.imul(value ^ (value >>> 15), value | 1);
    value ^= value + Math.imul(value ^ (value >>> 7), value | 61);
    return ((value ^ (value >>> 14)) >>> 0) / 4294967296;
  }

  function emit(s, type, detail = {}) {
    s.events.push({ type, x: s.x, y: s.y, ...detail });
    if (s.events.length > 256) s.events.splice(0, s.events.length - 256);
  }

  function star(s, x, y, delay = 0) {
    return {
      id: ++s._id, x: clamp(x, BOUNDS.left + 14, BOUNDS.right - 14),
      y: clamp(y, BOUNDS.top + 14, BOUNDS.bottom - 14),
      kind: 'letter', variant: Math.floor(random(s) * 3),
      phase: random(s) * Math.PI * 2, availableAt: s.elapsed + delay
    };
  }

  function spawnStars(s) {
    const count = s.required + 3;
    const angleOffset = random(s) * Math.PI * 2;
    s.stars = [];
    // Alternating near/far letters makes short safe routes and longer score routes.
    for (let i = 0; i < count; i += 1) {
      const angle = angleOffset + i / count * Math.PI * 2;
      const ring = i % 2 === 0 ? 0.84 + random(s) * 0.08 : 0.95 + random(s) * 0.05;
      const x = 480 + Math.cos(angle) * 305 * ring;
      const y = 355 + Math.sin(angle) * 176 * ring;
      s.stars.push(star(s, x, y));
    }
  }

  function spawnEnemy(s, index, count) {
    // Enemy entrances are telegraphed and always away from the player/beacon.
    let x = BOUNDS.left + 12, y = BOUNDS.top + 12;
    for (let attempt = 0; attempt < 32; attempt += 1) {
      const angle = (index / count) * Math.PI * 2 + random(s) * 0.45 + attempt * 0.36;
      x = 480 + Math.cos(angle) * 313;
      y = 357.5 + Math.sin(angle) * 180.5;
      if (Math.hypot(x - s.x, y - s.y) > 180 && s.enemies.every((enemy) => Math.hypot(enemy.x - x, enemy.y - y) > 58)) break;
    }
    return {
      id: ++s._id, x, y, kind: index % 3 === 2 ? 'mote' : 'jelly',
      speed: 47 + s.stage * 10 + random(s) * 12,
      phase: random(s) * Math.PI * 2, spawnTime: 1.25 + index * 0.12,
      stunTime: 0, radius: index % 3 === 2 ? 16 : 20
    };
  }

  function spawnStage(s) {
    spawnStars(s);
    const count = 3 + s.stage * 2;
    s.enemies = [];
    for (let index = 0; index < count; index += 1) s.enemies.push(spawnEnemy(s, index, count));
    s.invulnerableTime = Math.max(s.invulnerableTime, 1.2);
    emit(s, 'stage', { stage: s.stage, required: s.required });
  }

  function create(member = 'ine', seed = 1) {
    const memberId = typeof member === 'string' ? member : member?.id;
    const resolved = Object.hasOwn(MEMBERS, memberId) ? memberId : 'ine';
    const normalizedSeed = seedNumber(seed);
    const s = {
      version: 1, seed: normalizedSeed, member: resolved, mode: 'playing',
      arena: ARENA, beacon: BEACON, x: 480, y: 398, dir: { x: 0, y: -1 },
      timeLeft: 75, elapsed: 0, stage: 0, deliveries: 0,
      cargo: 0, required: REQUIREMENTS[0], hearts: 3, maxHearts: 3,
      score: 0, combo: 0, comboTime: 0, maxCombo: 0,
      baseSpeed: 195, speedBonus: 0, magnetBonus: 0, nearBeacon: false,
      dashCooldown: 0, dashTime: 0, skillCooldown: 0,
      shieldTime: 0, slowTime: 0, hasteTime: 0, magnetTime: 0,
      invulnerableTime: 1.2, stars: [], enemies: [], events: [], upgrades: [],
      stats: { letters: 0, hits: 0, dashes: 0, skills: 0 },
      lossReason: null, _rng: normalizedSeed, _id: 0, _accumulator: 0,
      _dashDir: { x: 0, y: -1 }
    };
    spawnStage(s);
    return s;
  }

  function dash(s) {
    if (s.mode !== 'playing' || s.dashCooldown > 0 || s.dashTime > 0) return false;
    s.dashTime = 0.19;
    s.dashCooldown = 2.3;
    s._dashDir = { ...s.dir };
    s.stats.dashes += 1;
    emit(s, 'dash', { dir: { ...s.dir } });
    return true;
  }

  function repel(s, radius, force, stunTime) {
    for (const enemy of s.enemies) {
      const dx = enemy.x - s.x, dy = enemy.y - s.y;
      const dist = Math.hypot(dx, dy);
      if (dist > radius) continue;
      const angle = dist > 0.01 ? Math.atan2(dy, dx) : enemy.phase;
      enemy.x = clamp(enemy.x + Math.cos(angle) * force, BOUNDS.left, BOUNDS.right);
      enemy.y = clamp(enemy.y + Math.sin(angle) * force, BOUNDS.top, BOUNDS.bottom);
      enemy.stunTime = Math.max(enemy.stunTime, stunTime);
    }
  }

  function skill(s) {
    if (s.mode !== 'playing' || s.skillCooldown > 0) return false;
    s.skillCooldown = MEMBERS[s.member].cooldown;
    s.stats.skills += 1;
    switch (s.member) {
      case 'ine': s.shieldTime = 4; repel(s, 210, 85, 0.7); break;
      case 'jing': s.slowTime = 5; break;
      case 'lilpa': s.hasteTime = 4; s.shieldTime = Math.max(s.shieldTime, 1); break;
      case 'jururu': s.magnetTime = 4; break;
      case 'gosegu': repel(s, 280, 115, 3.2); break;
      case 'viichan':
        if (s.hearts < s.maxHearts) s.hearts += 1;
        else s.shieldTime = Math.max(s.shieldTime, 3);
        s.magnetTime = 2;
        break;
    }
    emit(s, 'skill', { member: s.member, name: MEMBERS[s.member].skill });
    return true;
  }

  function chooseUpgrade(s, key) {
    if (s.mode !== 'upgrade' || !UPGRADES.some((upgrade) => upgrade.key === key)) return false;
    if (key === 'speed') s.speedBonus += 0.14;
    if (key === 'shield') { s.maxHearts += 1; s.hearts = Math.min(s.maxHearts, s.hearts + 1); }
    if (key === 'magnet') s.magnetBonus += 30;
    s.upgrades.push(key);
    s.mode = 'playing';
    s.dashCooldown = 0;
    s.skillCooldown = Math.max(0, s.skillCooldown - 4);
    s.shieldTime = Math.max(2, s.shieldTime);
    s._accumulator = 0;
    spawnStage(s);
    emit(s, 'upgrade', { key });
    return true;
  }

  function finish(s, won, reason) {
    s.mode = won ? 'won' : 'lost';
    s.lossReason = reason || null;
    s._accumulator = 0;
    if (won) s.score += Math.ceil(s.timeLeft) * 15 + s.hearts * 100;
    emit(s, won ? 'win' : 'lose', { score: s.score, reason: s.lossReason });
  }

  function deliver(s) {
    const stage = s.stage;
    const points = 300 + stage * 150 + s.combo * 20;
    s.score += points;
    s.deliveries += 1;
    s.cargo = 0;
    emit(s, 'delivery', { stage, deliveries: s.deliveries, points });
    if (s.deliveries === REQUIREMENTS.length) { finish(s, true); return; }
    s.stage += 1;
    s.required = REQUIREMENTS[s.stage];
    s.mode = 'upgrade';
    s.stars = [];
    s._accumulator = 0;
    emit(s, 'checkpoint', { stage: s.stage });
  }

  function hurt(s, enemy) {
    s.hearts -= 1;
    s.stats.hits += 1;
    s.combo = 0;
    s.comboTime = 0;
    s.invulnerableTime = 1.6;
    if (s.cargo > 0) {
      s.cargo -= 1;
      const away = Math.atan2(s.y - enemy.y, s.x - enemy.x);
      s.stars.push(star(s, s.x + Math.cos(away) * 52, s.y + Math.sin(away) * 52, 0.65));
    }
    repel(s, 115, 55, 0.9);
    emit(s, 'hit', { hearts: s.hearts });
    if (s.hearts <= 0) finish(s, false, 'hearts');
  }

  function moveEnemies(s, dt) {
    for (let index = 0; index < s.enemies.length; index += 1) {
      const enemy = s.enemies[index];
      if (enemy.spawnTime > 0) { enemy.spawnTime = Math.max(0, enemy.spawnTime - dt); continue; }
      if (enemy.stunTime > 0) { enemy.stunTime = Math.max(0, enemy.stunTime - dt); continue; }
      const dx = s.x - enemy.x, dy = s.y - enemy.y;
      const dist = Math.hypot(dx, dy) || 1;
      const sway = Math.sin(s.elapsed * 1.65 + enemy.phase) * 0.38;
      const speed = enemy.speed * (s.slowTime > 0 ? 0.3 : 1);
      enemy.x += (dx / dist - dy / dist * sway) * speed * dt;
      enemy.y += (dy / dist + dx / dist * sway) * speed * dt;
      // The beacon is a predictable safe landing circle, never a spawn trap.
      const fromBeacon = distance(enemy, BEACON);
      const safeRadius = BEACON.radius + enemy.radius + 17;
      if (fromBeacon < safeRadius) {
        const angle = Math.atan2(enemy.y - BEACON.y, enemy.x - BEACON.x);
        enemy.x = BEACON.x + Math.cos(angle) * safeRadius;
        enemy.y = BEACON.y + Math.sin(angle) * safeRadius;
      }
      // A little separation keeps enemies legible instead of forming one stack.
      for (let otherIndex = 0; otherIndex < index; otherIndex += 1) {
        const other = s.enemies[otherIndex];
        const ox = enemy.x - other.x, oy = enemy.y - other.y;
        const gap = Math.hypot(ox, oy);
        if (gap > 0.01 && gap < 39) {
          enemy.x += ox / gap * (39 - gap) * dt * 2;
          enemy.y += oy / gap * (39 - gap) * dt * 2;
        }
      }
      enemy.x = clamp(enemy.x, BOUNDS.left, BOUNDS.right);
      enemy.y = clamp(enemy.y, BOUNDS.top, BOUNDS.bottom);
      if (s.invulnerableTime <= 0 && s.shieldTime <= 0 && s.dashTime <= 0 && distance(enemy, s) < enemy.radius + 14) {
        hurt(s, enemy);
        if (s.mode !== 'playing') return;
      }
    }
  }

  function moveStars(s, dt) {
    if (s.cargo >= s.required) return;
    const magnetRadius = 44 + s.magnetBonus + (s.magnetTime > 0 ? (s.member === 'jururu' ? 105 : 50) : 0);
    for (let index = s.stars.length - 1; index >= 0; index -= 1) {
      const item = s.stars[index];
      if (item.availableAt > s.elapsed) continue;
      const dist = distance(item, s);
      if (dist < magnetRadius && dist > 23) {
        const move = Math.min(dist - 20, (180 + (magnetRadius - dist) * 3) * dt);
        item.x += (s.x - item.x) / dist * move;
        item.y += (s.y - item.y) / dist * move;
      }
      if (distance(item, s) <= 25) {
        s.stars.splice(index, 1);
        s.cargo += 1;
        s.stats.letters += 1;
        s.combo = s.comboTime > 0 ? Math.min(8, s.combo + 1) : 1;
        s.comboTime = 4;
        s.maxCombo = Math.max(s.maxCombo, s.combo);
        const points = 40 + (s.combo - 1) * 10;
        s.score += points;
        emit(s, 'pickup', { x: item.x, y: item.y, points, cargo: s.cargo, combo: s.combo });
        if (s.cargo >= s.required) { emit(s, 'cargo-full'); break; }
      }
    }
  }

  function tick(s, dt, input) {
    s.elapsed += dt;
    s.timeLeft = Math.max(0, s.timeLeft - dt);
    for (const key of ['dashCooldown', 'skillCooldown', 'shieldTime', 'slowTime', 'hasteTime', 'magnetTime', 'invulnerableTime', 'comboTime']) {
      s[key] = Math.max(0, s[key] - dt);
    }
    if (s.comboTime === 0) s.combo = 0;
    const ix = Number.isFinite(input?.x) ? input.x : 0;
    const iy = Number.isFinite(input?.y) ? input.y : 0;
    const magnitude = Math.hypot(ix, iy);
    const dx = magnitude > 1 ? ix / magnitude : ix;
    const dy = magnitude > 1 ? iy / magnitude : iy;
    if (magnitude > 0.08 && s.dashTime <= 0) s.dir = { x: ix / magnitude, y: iy / magnitude };
    const dashing = s.dashTime > 0;
    const speed = s.baseSpeed * (1 + s.speedBonus) * (s.hasteTime > 0 ? 1.5 : 1);
    s.x = clamp(s.x + (dashing ? s._dashDir.x * 720 : dx * speed) * dt, BOUNDS.left, BOUNDS.right);
    s.y = clamp(s.y + (dashing ? s._dashDir.y * 720 : dy * speed) * dt, BOUNDS.top, BOUNDS.bottom);
    s.nearBeacon = distance(s, BEACON) <= BEACON.radius;
    moveStars(s, dt);
    if (s.nearBeacon && s.cargo >= s.required) { deliver(s); return; }
    moveEnemies(s, dt);
    s.dashTime = Math.max(0, s.dashTime - dt);
    if (s.mode === 'playing' && s.timeLeft <= 0) finish(s, false, 'time');
  }

  function update(s, dt, input = {}) {
    if (s.mode !== 'playing' || !Number.isFinite(dt) || dt <= 0) return s;
    s._accumulator += Math.min(0.1, dt);
    while (s._accumulator + 1e-10 >= STEP && s.mode === 'playing') {
      s._accumulator = Math.max(0, s._accumulator - STEP);
      tick(s, STEP, input);
    }
    return s;
  }

  global.CourierEngine = Object.freeze({ create, update, dash, skill, chooseUpgrade, MEMBERS, MEMBER_LIST: Object.values(MEMBERS), UPGRADES, ARENA, BEACON, REQUIREMENTS });
})(globalThis);
