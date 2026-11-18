import test from 'node:test';
import assert from 'node:assert/strict';
import '../fangames/engine.js';

const Engine = globalThis.CourierEngine;
const frame = 1 / 60;

function advance(state, seconds, input = {}) {
  for (let time = 0; time < seconds - 1e-8; time += frame) {
    Engine.update(state, Math.min(frame, seconds - time), input);
  }
}

function routeTo(state, target, maxSeconds = 10) {
  for (let frames = 0; frames < maxSeconds * 60; frames += 1) {
    const dx = target.x - state.x, dy = target.y - state.y;
    const distance = Math.hypot(dx, dy);
    if (distance < 6 || state.mode !== 'playing') return;
    Engine.update(state, frame, { x: dx / distance, y: dy / distance });
  }
}

test('seeded rounds and replays are deterministic, with safe and reachable entrances', () => {
  const one = Engine.create('jing', 'same-round');
  const two = Engine.create('jing', 'same-round');
  assert.deepEqual(one, two);
  for (const enemy of one.enemies) {
    assert.ok(Math.hypot(enemy.x - one.x, enemy.y - one.y) > 180);
    assert.ok(enemy.spawnTime >= 1.25);
    assert.ok(enemy.x >= Engine.ARENA.bounds.left && enemy.x <= Engine.ARENA.bounds.right);
    assert.ok(enemy.y >= Engine.ARENA.bounds.top && enemy.y <= Engine.ARENA.bounds.bottom);
    for (const other of one.enemies) {
      if (other.id !== enemy.id) assert.ok(Math.hypot(other.x - enemy.x, other.y - enemy.y) > 58);
    }
  }
  for (const letter of one.stars) {
    assert.ok(letter.x >= Engine.ARENA.bounds.left && letter.x <= Engine.ARENA.bounds.right);
    assert.ok(letter.y >= Engine.ARENA.bounds.top && letter.y <= Engine.ARENA.bounds.bottom);
  }
  for (let index = 0; index < 180; index += 1) {
    const input = { x: Math.sin(index / 40), y: Math.cos(index / 40) };
    Engine.update(one, frame, input);
    Engine.update(two, frame, input);
  }
  assert.deepEqual(one, two);
  assert.notDeepEqual(Engine.create('jing', 11).stars, Engine.create('jing', 12).stars);
});

test('movement normalizes diagonals and bounds delayed or invalid frames', () => {
  const straight = Engine.create('ine', 20);
  const diagonal = Engine.create('ine', 20);
  advance(straight, 0.5, { x: 1, y: 0 });
  advance(diagonal, 0.5, { x: 1, y: 1 });
  assert.ok(Math.abs(Math.hypot(diagonal.x - 480, diagonal.y - 398) - (straight.x - 480)) < 1e-8);
  const saved = structuredClone(straight);
  for (const dt of [NaN, Infinity, -1, 0]) Engine.update(straight, dt, { x: 1 });
  assert.deepEqual(straight, saved);
  Engine.update(straight, 999, { x: 1 });
  assert.ok(Math.abs(straight.timeLeft - (saved.timeLeft - 0.1)) < 1e-8);
  advance(straight, 3, { x: 1, y: 0 });
  assert.equal(straight.x, Engine.ARENA.bounds.right);
  Engine.update(straight, frame, { x: NaN, y: Infinity });
  assert.ok(Number.isFinite(straight.x) && Number.isFinite(straight.y));
  for (const [x, y, dir] of [
    [Engine.ARENA.bounds.left, 300, { x: -1, y: 0 }],
    [Engine.ARENA.bounds.right, 300, { x: 1, y: 0 }],
    [480, Engine.ARENA.bounds.top, { x: 0, y: -1 }],
    [480, Engine.ARENA.bounds.bottom, { x: 0, y: 1 }]
  ]) {
    const edge = Engine.create('gosegu', 24);
    edge.x = x; edge.y = y; edge.dir = dir;
    Engine.dash(edge);
    advance(edge, 0.2, dir);
    assert.equal(edge.x, x);
    assert.equal(edge.y, y);
    edge.enemies[0].x = x; edge.enemies[0].y = y;
    Engine.skill(edge);
    for (const enemy of edge.enemies) {
      assert.ok(enemy.x >= Engine.ARENA.bounds.left && enemy.x <= Engine.ARENA.bounds.right);
      assert.ok(enemy.y >= Engine.ARENA.bounds.top && enemy.y <= Engine.ARENA.bounds.bottom);
    }
  }
});

test('a genuine collection route delivers, pauses for a choice and resumes the next wave', () => {
  const state = Engine.create('ine', 21);
  while (state.cargo < state.required) {
    const next = state.stars.toSorted((a, b) => Math.hypot(a.x - state.x, a.y - state.y) - Math.hypot(b.x - state.x, b.y - state.y))[0];
    routeTo(state, next);
  }
  assert.ok(state.stats.letters >= 4);
  routeTo(state, Engine.BEACON);
  assert.equal(state.mode, 'upgrade');
  assert.equal(state.deliveries, 1);
  assert.equal(state.stage, 1);
  assert.equal(state.required, 6);
  assert.equal(state.cargo, 0);
  const paused = structuredClone(state);
  advance(state, 15, { x: 1, y: 1 });
  assert.deepEqual(state, paused);
  assert.equal(Engine.dash(state), false);
  assert.equal(Engine.skill(state), false);
  assert.equal(Engine.chooseUpgrade(state, 'invalid'), false);
  assert.equal(state.mode, 'upgrade');
  assert.equal(Engine.chooseUpgrade(state, 'speed'), true);
  assert.equal(state.mode, 'playing');
  assert.equal(state.enemies.length, 5);
  assert.equal(state.speedBonus, 0.14);
  assert.equal(state.timeLeft, paused.timeLeft);
  assert.equal(Engine.chooseUpgrade(state, 'shield'), false);
});

test('damage drops a recoverable letter, breaks the combo, and grants invulnerability', () => {
  const state = Engine.create('jing', 30);
  state.x = 210; state.y = 210;
  state.cargo = 3; state.combo = 3; state.comboTime = 3;
  state.invulnerableTime = 0;
  state.enemies = [{ id: 100, x: 211, y: 210, kind: 'jelly', speed: 0, phase: 0, spawnTime: 0, stunTime: 0, radius: 20 }];
  const beforeLetters = state.stars.length;
  Engine.update(state, frame, {});
  assert.equal(state.hearts, 2);
  assert.equal(state.cargo, 2);
  assert.equal(state.combo, 0);
  assert.equal(state.stars.length, beforeLetters + 1);
  assert.ok(state.stars.at(-1).availableAt > state.elapsed);
  assert.ok(state.invulnerableTime > 1.5);
  state.enemies[0].x = state.x;
  state.enemies[0].y = state.y;
  state.enemies[0].stunTime = 0;
  Engine.update(state, frame, {});
  assert.equal(state.hearts, 2);
  assert.equal(state.stats.hits, 1);
  assert.ok(state.events.some((event) => event.type === 'hit'));
});

test('dash is a finite directional burst with cooldown and damage protection', () => {
  const state = Engine.create('gosegu', 31);
  state.x = 210; state.y = 210; state.invulnerableTime = 0;
  state.enemies = [{ id: 100, x: 220, y: 210, kind: 'jelly', speed: 0, phase: 0, spawnTime: 0, stunTime: 0, radius: 20 }];
  state.dir = { x: 1, y: 0 };
  assert.equal(Engine.dash(state), true);
  assert.equal(Engine.dash(state), false);
  advance(state, 0.2);
  assert.ok(state.x > 340);
  assert.equal(state.hearts, 3);
  assert.equal(state.dashTime, 0);
  assert.ok(state.dashCooldown > 2);
  advance(state, 2.2);
  assert.equal(Engine.dash(state), true);
  assert.equal(state.stats.dashes, 2);
});

test('all six skills have distinct live effects and enforce cooldowns', () => {
  for (const member of Engine.MEMBER_LIST) {
    const state = Engine.create(member.id, 40);
    state.hearts = 2;
    state.enemies[0].x = state.x + 100;
    state.enemies[0].y = state.y;
    assert.equal(Engine.skill(state), true);
    assert.equal(Engine.skill(state), false);
    assert.equal(state.skillCooldown, member.cooldown);
    switch (member.id) {
      case 'ine': assert.equal(state.shieldTime, 4); assert.ok(state.enemies[0].x > state.x + 150); break;
      case 'jing': assert.equal(state.slowTime, 5); break;
      case 'lilpa': assert.equal(state.hasteTime, 4); assert.equal(state.shieldTime, 1); break;
      case 'jururu': assert.equal(state.magnetTime, 4); break;
      case 'gosegu': assert.equal(state.enemies[0].stunTime, 3.2); assert.ok(state.enemies[0].x > state.x + 200); break;
      case 'viichan': assert.equal(state.hearts, 3); assert.equal(state.magnetTime, 2); break;
    }
    assert.equal(state.stats.skills, 1);
    assert.ok(state.events.some((event) => event.type === 'skill' && event.member === member.id));
  }
  const healthy = Engine.create('viichan', 41);
  Engine.skill(healthy);
  assert.equal(healthy.hearts, healthy.maxHearts);
  assert.equal(healthy.shieldTime, 3);
});

test('magnet skill collects distant letters and haste increases real travel', () => {
  const magnetic = Engine.create('jururu', 44);
  const ordinary = Engine.create('jururu', 44);
  magnetic.stars = [{ id: 90, x: 610, y: 398, kind: 'letter', availableAt: 0 }];
  ordinary.stars = structuredClone(magnetic.stars);
  Engine.skill(magnetic);
  advance(magnetic, 0.8);
  advance(ordinary, 0.8);
  assert.equal(magnetic.cargo, 1);
  assert.equal(ordinary.cargo, 0);
  const fast = Engine.create('lilpa', 45);
  const regular = Engine.create('lilpa', 45);
  Engine.skill(fast);
  advance(fast, 0.5, { x: 1 });
  advance(regular, 0.5, { x: 1 });
  assert.ok(fast.x - 480 > (regular.x - 480) * 1.49);
});

test('timer and final heart have distinct terminal results that freeze the simulation', () => {
  const timed = Engine.create('ine', 50);
  timed.timeLeft = 0.02;
  advance(timed, 0.1);
  assert.equal(timed.mode, 'lost');
  assert.equal(timed.lossReason, 'time');
  assert.equal(timed.timeLeft, 0);
  const saved = structuredClone(timed);
  advance(timed, 10, { x: 1 });
  assert.deepEqual(timed, saved);
  const hurt = Engine.create('ine', 51);
  hurt.x = 210; hurt.y = 210; hurt.hearts = 1; hurt.invulnerableTime = 0;
  hurt.enemies = [{ id: 100, x: 211, y: 210, kind: 'jelly', speed: 0, phase: 0, spawnTime: 0, stunTime: 0, radius: 20 }];
  Engine.update(hurt, frame);
  assert.equal(hurt.mode, 'lost');
  assert.equal(hurt.lossReason, 'hearts');
  assert.equal(hurt.hearts, 0);
});

test('each member can complete three deliveries through real movement within the time budget', () => {
  for (const member of Engine.MEMBER_LIST) {
    const state = Engine.create(member.id, 770);
    for (let frames = 0; frames < 76 * 60 && !['won', 'lost'].includes(state.mode); frames += 1) {
      if (state.mode === 'upgrade') {
        Engine.chooseUpgrade(state, state.stage === 1 ? 'magnet' : 'shield');
        continue;
      }
      const target = state.cargo >= state.required ? Engine.BEACON : state.stars.toSorted((a, b) => Math.hypot(a.x - state.x, a.y - state.y) - Math.hypot(b.x - state.x, b.y - state.y))[0];
      const dx = target.x - state.x, dy = target.y - state.y;
      const distance = Math.hypot(dx, dy) || 1;
      let ix = dx / distance, iy = dy / distance, closestEnemy = Infinity;
      // A simple player follows letters, steers around nearby active enemies,
      // and uses the two advertised controls; no simulation state is bypassed.
      for (const enemy of state.enemies) {
        if (enemy.spawnTime > 0 || enemy.stunTime > 0) continue;
        const ex = state.x - enemy.x, ey = state.y - enemy.y;
        const gap = Math.hypot(ex, ey) || 1;
        closestEnemy = Math.min(closestEnemy, gap);
        if (gap < 100) {
          ix += ex / gap * (100 - gap) / 42;
          iy += ey / gap * (100 - gap) / 42;
        }
      }
      if (state.skillCooldown === 0 && (closestEnemy < 130 || ['jururu', 'lilpa'].includes(member.id) || state.hearts < 3)) Engine.skill(state);
      Engine.update(state, frame, { x: ix, y: iy });
      if (state.dashCooldown === 0 && (closestEnemy < 85 || distance > 150)) Engine.dash(state);
      for (const entity of [state, ...state.stars, ...state.enemies]) {
        assert.ok(entity.x >= Engine.ARENA.bounds.left && entity.x <= Engine.ARENA.bounds.right);
        assert.ok(entity.y >= Engine.ARENA.bounds.top && entity.y <= Engine.ARENA.bounds.bottom);
      }
    }
    assert.equal(state.mode, 'won', `${member.id}: ${state.lossReason}, ${state.deliveries} deliveries`);
    assert.equal(state.deliveries, 3);
    assert.equal(state.stage, 2);
    assert.equal(state.stats.letters >= 18, true);
    assert.equal(state.maxHearts, 4);
    assert.equal(state.magnetBonus, 30);
    assert.ok(state.timeLeft > 0);
    assert.ok(state.score > 2000);
    assert.ok(state.events.some((event) => event.type === 'win'));
  }
});
