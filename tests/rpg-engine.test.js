import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { CONTENT, CHAPTERS, MEMBERS, UPGRADES, FINALE, ALL_FACTS } from '../rpg/content.js';
import { createGame, dispatch, currentScene, describeObjective, enemyIntent, availableSupports, serialize, restore } from '../rpg/engine.js';

function send(state, action) {
  const next = dispatch(state, action);
  assert.deepEqual(restore(serialize(next)), next, `Save round-trip after ${JSON.stringify(action)} / ${next.mode}`);
  return next;
}
function closeDialogue(state) {
  for (let i = 0; state.mode === 'dialogue' && i < 20; i++) state = send(state, { type: 'dialogueNext' });
  assert.notEqual(state.mode, 'dialogue');
  return state;
}
function walkTo(state, id) {
  assert.equal(state.mode, 'explore');
  const scene = currentScene(state), obj = scene.objects.find(o => o.id === id);
  assert.ok(obj, `Object exists: ${id}`);
  const queue = [[state.position.x, state.position.y, []]], seen = new Set();
  let path;
  while (queue.length) {
    const [x, y, moves] = queue.shift(), key = `${x},${y}`;
    if (seen.has(key)) continue; seen.add(key);
    if (Math.abs(x - obj.x) + Math.abs(y - obj.y) <= 1) { path = moves; break; }
    for (const [dx, dy] of [[0,-1],[1,0],[0,1],[-1,0]]) if (scene.tiles[y + dy]?.[x + dx] === '.') queue.push([x + dx, y + dy, [...moves, { type: 'move', dx, dy }]]);
  }
  assert.ok(path, `Object reachable: ${scene.id}/${id}`);
  for (const move of path) state = send(state, move);
  return state;
}
function interact(state, id) { return send(walkTo(state, id), { type: 'interact', id }); }
function pick(state, id, choice) {
  state = interact(state, id);
  assert.equal(state.mode, 'choice');
  return send(state, { type: 'choose', id: choice });
}
function puzzle(state) {
  const actions = [
    [[0,'press'],[1,'press'],[2,'press']],
    [[0,'winter'],[1,'spring'],[2,'spring']],
    [[1,'story'],[0,'storyworld'],[1,'song'],[0,'real'],[1,'meeting'],[2,'bind']],
    [[0,'toggle'],[2,'toggle']],
    [[0,'guard'],[1,'heal'],[2,'break']],
    [[0,'moon'],[1,'right'],[2,'up']]
  ][state.chapter];
  for (const [id, choice] of actions) state = pick(state, `control-${id}`, choice);
  assert.ok(state.solved.includes(CHAPTERS[state.chapter].id));
  return state;
}
function battleAction(state) {
  const intent = enemyIntent(state), can = id => state.met.includes(id) && state.player.focus >= 2;
  if (state.player.hp < state.player.maxHp * 0.62 && can('ine')) return { type: 'support', id: 'ine' };
  if (intent.kind === 'heavy') return can('lilpa') ? { type: 'support', id: 'lilpa' } : { type: 'battle', move: 'defend' };
  if (intent.kind === 'reverse' && can('gosegu')) return { type: 'support', id: 'gosegu' };
  if (intent.kind === 'illusion' && can('jururu')) return { type: 'support', id: 'jururu' };
  if (can('jingburger')) return { type: 'support', id: 'jingburger' };
  return { type: 'battle', move: 'attack' };
}
function fight(state, records = []) {
  if (state.mode === 'choice') state = send(state, { type: 'choose', id: 'start' });
  assert.equal(state.mode, 'battle');
  const id = state.battle.id, before = state.stats.turns;
  for (let i = 0; state.mode === 'battle' && i < 300; i++) {
    if (state.battle.id === 'final-trial' && state.battle.phase === 2 && !finalPhaseSnapshot) finalPhaseSnapshot = structuredClone(state);
    state = send(state, battleAction(state));
  }
  assert.notEqual(state.mode, 'defeat', `Strategy must clear ${id}`);
  assert.notEqual(state.mode, 'battle', `Finite combat ${id}`);
  records.push({ id, turns: state.stats.turns - before });
  return state;
}

let completeState, finalPhaseSnapshot, battleSnapshots = [], turnCounts = [];
test('the entire six-chapter campaign and three-phase finale are completable through public actions', () => {
  let state = closeDialogue(createGame());
  for (let chapter = 0; chapter < 6; chapter++) {
    assert.equal(state.chapter, chapter);
    assert.ok(describeObjective(state).includes(MEMBERS[CHAPTERS[chapter].member].name));
    state = closeDialogue(interact(state, 'record-0'));
    state = closeDialogue(interact(state, 'memory'));
    state = closeDialogue(interact(state, 'member'));
    assert.equal(state.met.length, chapter + 1);
    state = interact(state, 'rest');
    state = interact(state, 'forward');
    state = closeDialogue(interact(state, 'clue'));
    state = closeDialogue(interact(state, 'memory'));
    state = puzzle(state);
    state = interact(state, 'guardian');
    state = send(state, { type: 'choose', id: 'start' });
    battleSnapshots.push(structuredClone(state));
    state = fight(state, turnCounts);
    state = interact(state, 'forward');
    state = closeDialogue(interact(state, 'record-1'));
    state = interact(state, 'rest');
    state = fight(interact(state, 'boss'), turnCounts);
    state = closeDialogue(interact(state, 'exit'));
    assert.equal(state.mode, 'victory');
    state = send(state, { type: 'nextChapter' });
    if (state.mode === 'upgrade') state = send(state, { type: 'upgrade', id: ['heart', 'spark', 'bond'][Math.floor(chapter / 2)] });
  }
  assert.equal(state.chapter, 6);
  assert.equal(state.upgrades.length, 3);
  state = closeDialogue(interact(state, 'ensemble'));
  state = interact(state, 'rest');
  state = closeDialogue(interact(state, 'final-boss'));
  state = fight(state, turnCounts);
  assert.equal(state.mode, 'ending');
  assert.equal(state.defeated.length, 13);
  assert.equal(state.solved.length, 6);
  assert.equal(state.records.length, 12);
  assert.equal(state.memories.length, 12);
  assert.equal(state.finalContributions.length, 6);
  assert.ok(turnCounts.slice(0, 12).every(b => b.turns >= 5 && b.turns <= 25));
  completeState = state;
  console.log('RPG public-action campaign:', JSON.stringify({ turns: turnCounts, totalTurns: state.stats.turns, steps: state.stats.steps }));
});

test('every growth combination can finish on normal and help difficulty with a readable defensive strategy', () => {
  const results = [];
  for (const help of [false, true]) for (const a of UPGRADES) for (const b of UPGRADES) for (const c of UPGRADES) {
    const build = [a.id, b.id, c.id];
    let state = closeDialogue(send(createGame(), {type:'help', enabled:help})), upgrade = 0;
    for (let chapter = 0; chapter < 6; chapter++) {
      state = closeDialogue(interact(state, 'member'));
      state = interact(state, 'rest');
      state = puzzle(interact(state, 'forward'));
      state = fight(interact(state, 'guardian'));
      state = interact(state, 'forward');
      state = interact(state, 'rest');
      state = fight(interact(state, 'boss'));
      state = closeDialogue(interact(state, 'exit'));
      state = send(state, {type:'nextChapter'});
      if (state.mode === 'upgrade') state = send(state, {type:'upgrade', id:build[upgrade++]});
    }
    state = closeDialogue(interact(state, 'ensemble'));
    state = interact(state, 'rest');
    state = fight(closeDialogue(interact(state, 'final-boss')));
    assert.equal(state.mode, 'ending', `${build.join('/')} help=${help}`);
    results.push({build,help,turns:state.stats.turns});
  }
  console.log('Growth balance audit (not human playtime):', JSON.stringify({campaigns:results.length,normalTurns:results.filter(r=>!r.help).map(r=>r.turns),helpTurns:results.filter(r=>r.help).map(r=>r.turns)}));
});

test('all eighteen chapter rooms have distinct walkable layouts', () => {
  assert.equal(new Set(CHAPTERS.flatMap(c=>c.rooms.map(r=>r.tiles.join('\n')))).size, 18);
});

test('first-review saves survive changed scenery without losing battle or chapter progress', () => {
  const old = structuredClone(battleSnapshots[1]);
  delete old.mapRevision;
  old.position = {x:7,y:3};
  old.checkpoint.position = {...old.position};
  const migrated = restore(JSON.stringify(old));
  assert.ok(migrated);
  assert.equal(migrated.mapRevision, 2);
  assert.equal(Math.abs(migrated.position.x-7)+Math.abs(migrated.position.y-3), 1);
  assert.deepEqual(migrated.checkpoint.position, migrated.position);
  for (const key of ['battle','chapter','room','met','records','solved','upgrades','stats']) assert.deepEqual(migrated[key],old[key]);
  assert.deepEqual(restore(serialize(migrated)), migrated);
  assert.equal(restore(JSON.stringify({...old,mapRevision:2})), null, 'new saves cannot place the player inside a wall');
  assert.equal(restore(JSON.stringify({...old,position:{x:6,y:3}})), null, 'invalid old wall saves are still rejected');
});

test('movement, range, chapter doors and battle actions enforce their gates', () => {
  let state = closeDialogue(createGame());
  const frozen = structuredClone(state);
  state = dispatch(state, { type: 'move', dx: 12, dy: 0 });
  assert.deepEqual(state.position, frozen.position);
  state = dispatch(state, { type: 'interact', id: 'member' });
  assert.equal(state.met.length, 0);
  state = interact(state, 'forward');
  assert.equal(state.room, 0);
  state = closeDialogue(interact(state, 'member'));
  state = interact(state, 'forward');
  state = interact(state, 'forward');
  assert.equal(state.room, 1);
  state = send(state, { type: 'battle', move: 'attack' });
  assert.equal(state.stats.turns, 0);
  assert.equal(frozen.met.length, 0, 'Transitions do not mutate input');
});

test('a wrong puzzle action is recoverable; the layer puzzle requires switching world and binding', () => {
  let state = closeDialogue(createGame());
  state = closeDialogue(interact(state, 'member'));
  state = interact(state, 'forward');
  state = pick(state, 'control-2', 'press');
  assert.equal(state.puzzle['first-light'].sequence.length, 0);
  state = puzzle(state);
  assert.ok(state.solved.includes('first-light'));
  let layer = structuredClone(battleSnapshots[2]);
  layer.mode = 'explore'; layer.battle = null; layer.checkpoint = null;
  layer.solved = layer.solved.filter(id => id !== 'paper-city');
  layer.puzzle['paper-city'].sequence = [];
  layer = pick(layer, 'control-2', 'bind');
  assert.ok(!layer.solved.includes('paper-city'));
  layer = puzzle(layer);
  assert.ok(layer.solved.includes('paper-city'));
});

test('all six skills have materially different combat effects and consume earned focus', () => {
  const base = structuredClone(battleSnapshots[5]);
  base.player.hp = 50; base.player.focus = 6;
  const results = Object.fromEntries(Object.keys(MEMBERS).map(id => [id, send(base, { type: 'support', id })]));
  assert.ok(results.jingburger.battle.hp < results.ine.battle.hp);
  assert.ok(results.ine.player.hp > base.player.hp);
  assert.ok(results.jururu.battle.exposed > 0);
  assert.equal(results.lilpa.battle.counter, true);
  assert.equal(results.viichan.player.focus, 5, 'Viichan returns one focus');
  assert.equal(results.gosegu.player.hp, base.player.hp, 'Gosegu cancels the attack');
  assert.ok(results.gosegu.battle.exposed > 0);
  for (const id of ['jingburger', 'ine', 'jururu', 'lilpa', 'gosegu']) assert.equal(results[id].player.focus, 4);
  const empty = { ...base, player: { ...base.player, focus: 0 } };
  assert.equal(send(empty, { type: 'support', id: 'gosegu' }).stats.turns, base.stats.turns);
  assert.equal(availableSupports(base).length, 6);
});

test('Jururu exposes exactly two later offensive actions; defense, cheering and healing preserve charges', () => {
  let state = structuredClone(battleSnapshots[5]);
  state.player.focus = 6;
  state = send(state, { type: 'support', id: 'jururu' });
  assert.equal(state.battle.exposed, 2, 'The granting skill does not consume its own charge');
  for (const action of [{ type: 'battle', move: 'defend' }, { type: 'battle', move: 'cheer' }, { type: 'support', id: 'ine' }]) {
    state = send(state, action);
    assert.equal(state.battle.exposed, 2, `${JSON.stringify(action)} preserves both offensive charges`);
  }
  assert.equal(enemyIntent(state).kind, 'reverse');
  const hpBefore = state.battle.hp;
  state = send(state, { type: 'battle', move: 'attack' });
  assert.equal(hpBefore - state.battle.hp, state.player.attack, 'First attack bypasses the reversed shield');
  assert.equal(state.battle.exposed, 1);
  state = send(state, { type: 'battle', move: 'defend' });
  assert.equal(state.battle.exposed, 1);
  state = send(state, { type: 'support', id: 'viichan' });
  assert.equal(state.battle.exposed, 0, 'Two-hit support consumes one offensive action');
  const hpBeforeShield = state.battle.hp;
  assert.equal(enemyIntent(state).kind, 'reverse');
  state = send(state, { type: 'battle', move: 'attack' });
  assert.equal(hpBeforeShield - state.battle.hp, Math.round(state.player.attack * 0.5), 'Shield reduction resumes after exactly two offensive actions');
});

test('help mode adds the actual solution to the clue without requiring or changing puzzle progress', () => {
  let state = closeDialogue(createGame());
  state = closeDialogue(interact(state, 'member'));
  state = interact(state, 'forward');
  state = interact(state, 'clue');
  assert.ok(!state.dialogue.lines.some(line => line.startsWith('도움 힌트:')));
  state = closeDialogue(state);
  const before = structuredClone(state.puzzle);
  state = send(state, { type: 'help', enabled: true });
  state = interact(state, 'clue');
  assert.ok(state.dialogue.lines.includes(`도움 힌트: ${CHAPTERS[0].puzzle.hint}`));
  assert.deepEqual(state.puzzle, before);
  assert.equal(state.solved.length, 0);
});

test('telegraphed heavy attacks reward defense; a defeat restores only the current encounter', () => {
  const base = structuredClone(battleSnapshots[0]);
  base.battle.turn = 1;
  assert.equal(enemyIntent(base).kind, 'heavy');
  const defended = send(base, { type: 'battle', move: 'defend' });
  const attacked = send(base, { type: 'battle', move: 'attack' });
  assert.ok(defended.player.hp > attacked.player.hp);
  const doomed = { ...base, player: { ...base.player, hp: 1 } };
  let lost = send(doomed, { type: 'battle', move: 'attack' });
  assert.equal(lost.mode, 'defeat');
  lost = send(lost, { type: 'retry' });
  assert.equal(lost.mode, 'battle');
  assert.equal(lost.player.hp, lost.player.maxHp);
  assert.equal(lost.battle.id, base.battle.id);
  assert.deepEqual(lost.solved, base.solved);
});

test('final phase retry and save restore preserve the reached phase, including ending reload', () => {
  let state = structuredClone(finalPhaseSnapshot);
  state.player.hp = 1;
  const phase = state.battle.phase;
  state = send(state, { type: 'battle', move: 'attack' });
  assert.equal(state.mode, 'defeat');
  state = send(state, { type: 'retry' });
  assert.equal(state.battle.phase, phase);
  assert.equal(state.checkpoint.phase, phase);
  state = fight(state);
  assert.equal(state.mode, 'ending');
  assert.equal(restore(serialize(state)).mode, 'ending');
});

test('save loader rejects corruption, wrong versions, invalid rooms and impossible progression without throwing', () => {
  for (const raw of ['', 'null', '[]', '{', 'x'.repeat(100001), JSON.stringify({ version: 1 }), JSON.stringify({ ...createGame(), version: 99 })]) assert.equal(restore(raw), null);
  const corrupt = patch => JSON.stringify({ ...createGame(), ...patch });
  assert.equal(restore(corrupt({ player: { hp: -1, maxHp: 100, attack: 12, focus: 3, level: 1 } })), null);
  assert.equal(restore(corrupt({ chapter: 6, room: 1 })), null);
  assert.equal(restore(corrupt({ position: { x: 0, y: 0 } })), null);
  assert.equal(restore(corrupt({ met: ['gosegu'] })), null);
  assert.equal(restore(corrupt({ battle: true })), null);
  const missing = createGame(); delete missing.battle;
  assert.equal(restore(JSON.stringify(missing)), null);
  const injected = createGame(); injected.__proto__ = { admin: true };
  assert.equal(Object.hasOwn(restore(JSON.stringify(injected)), 'admin'), false);
});

test('record IDs, chronology, membership scope and dates match the curated local history and album snapshot', () => {
  const history = JSON.parse(fs.readFileSync(new URL('../visuals/history.json', import.meta.url)));
  const albums = JSON.parse(fs.readFileSync(new URL('../catalog/album-releases.json', import.meta.url)));
  assert.equal(CHAPTERS.length, 6); assert.equal(ALL_FACTS.length, 12);
  for (const fact of ALL_FACTS) {
    const source = history.events.find(e => e.id === fact.id) || albums.releases.find(e => e.id === fact.id);
    assert.ok(source, fact.id);
    assert.ok(fact.date.startsWith(source.date));
    if (source.endDate) assert.ok(fact.date.endsWith(source.endDate.slice(5)));
    if (fact.id === 'across-dimensions') assert.equal(fact.title, source.title + ' 발매');
    else assert.equal(fact.title, source.title);
    assert.ok(fact.url.startsWith('https://'));
    assert.ok(!fact.url.includes('namu.moe'), 'No internal mirror provenance exposed');
  }
  assert.deepEqual(history.events.find(e => e.id === 'event-2026-09-28-55').members, ['gosegu']);
  assert.equal(new Set(CHAPTERS.map(c => c.member)).size, 6);
  assert.equal(new Set(CHAPTERS.map(c => c.puzzle.kind)).size, 6);
  assert.ok(CONTENT.fictionNotice.includes('창작'));
  assert.equal(UPGRADES.length, 3); assert.equal(FINALE.phases.length, 3);
});

test('all map objects can be reached and active play time never creates waits or alters progress', () => {
  for (const c of CHAPTERS) for (let room = 0; room < c.rooms.length; room++) {
    const base = { ...createGame(), mode: 'explore', dialogue: null, chapter: c.index, room, position: { x: 2, y: 4 } };
    const scene = currentScene(base);
    assert.equal(scene.tiles.length, 9);
    assert.ok(scene.tiles.every(row => row.length === 15));
    for (const obj of scene.objects) {
      assert.equal(scene.tiles[obj.y][obj.x], '.', `Object sits on walkable floor: ${scene.id}/${obj.id}`);
      const queue = [[2,4]], seen = new Set(); let found = false;
      while (queue.length) {
        const [x,y] = queue.shift(), key = `${x},${y}`;
        if (seen.has(key)) continue; seen.add(key);
        if (Math.abs(x-obj.x)+Math.abs(y-obj.y)<=1) { found = true; break; }
        for (const [dx,dy] of [[0,-1],[1,0],[0,1],[-1,0]]) if (scene.tiles[y+dy]?.[x+dx] === '.') queue.push([x+dx,y+dy]);
      }
      assert.ok(found, `${scene.id}/${obj.id}`);
    }
  }
  const state = createGame(), advanced = send(state, { type: 'tick', seconds: 20 });
  assert.equal(advanced.stats.seconds, 20);
  assert.equal(advanced.mode, state.mode);
  assert.equal(send(state, { type: 'tick', seconds: 999 }).stats.seconds, 0);
});
