import { CONTENT, CHAPTERS, MEMBERS, UPGRADES, FINALE, ALL_FACTS, LEGACY_MAPS, previousRoomTiles } from './content.js';
import { createTacticalField, restoreTacticalField, tacticalCommand, tacticalActive, tacticalApproach, tacticalRange, tacticalTarget, tacticalTerrain, tacticalFlank, advanceTacticalEnemy } from './tactics.js';

export const SAVE_KEY = 'isegye:rpg:v1';
export const SAVE_VERSION = 1;
const RPG_MAX_SAVE = 100000;
const RPG_DIRECTIONS = [[0, -1], [1, 0], [0, 1], [-1, 0]];
const rpgClone = value => JSON.parse(JSON.stringify(value));
const rpgClamp = (n, low, high) => Math.max(low, Math.min(high, n));
const rpgMemberIds = Object.keys(MEMBERS);
const rpgEncounterIds = CHAPTERS.flatMap(c => c.encounters.map(e => e.id)).concat(FINALE.encounter.id);
const rpgModes = ['dialogue', 'explore', 'choice', 'battle', 'victory', 'defeat', 'upgrade', 'ending'];

function rpgLog(state, text) { state.log = [text, ...state.log].slice(0, 8); }
function rpgMaxFocus(state) { return 6 + state.upgrades.filter(u => u === 'bond').length; }
function rpgFocus(state, n) { state.player.focus = rpgClamp(state.player.focus + n, 0, rpgMaxFocus(state)); }
function rpgHeal(state, n) { state.player.hp = Math.min(state.player.maxHp, state.player.hp + n); }
function rpgDialogue(state, speaker, lines, pending = null, member = null) {
  state.mode = 'dialogue';
  state.dialogue = { speaker, lines: [...lines], index: 0, member };
  state.pending = pending;
  state.choice = null;
}
function rpgPuzzleInitial(chapter) {
  return { sequence: [], values: [null, null, null], layer: 'real', wings: [false, true, false], attempts: 0 };
}

export function createGame() {
  const state = {
    version: SAVE_VERSION, mapRevision: 3, mode: 'explore', chapter: 0, room: 0, position: { x: 2, y: 4 },
    player: { hp: 100, maxHp: 100, attack: 12, focus: 3, level: 1 },
    met: [], defeated: [], solved: [], records: [], memories: [], upgrades: [],
    puzzle: Object.fromEntries(CHAPTERS.map(c => [c.id, rpgPuzzleInitial(c)])),
    dialogue: null, pending: null, choice: null, battle: null, checkpoint: null,
    log: ['티켓을 따라 기록의 길에 들어섰다.'], help: false, failures: 0,
    stats: { steps: 0, turns: 0, seconds: 0, battles: 0, retries: 0 },
    finalMet: false, finalContributions: []
  };
  rpgDialogue(state, '기록의 안내', CONTENT.prologue);
  return state;
}

export function currentScene(state) {
  const chapter = CHAPTERS[state.chapter];
  const raw = chapter ? chapter.rooms[state.room] : FINALE.room;
  const scene = rpgClone(raw);
  scene.chapter = chapter ? { id: chapter.id, year: chapter.year, title: chapter.title, member: chapter.member, theme: chapter.theme } : { id: FINALE.id, year: FINALE.year, title: FINALE.title, theme: FINALE.theme };
  for (const obj of scene.objects) {
    obj.near = Math.abs(obj.x - state.position.x) + Math.abs(obj.y - state.position.y) <= 1;
    if (!chapter) { obj.done = obj.id === 'ensemble' && state.finalMet; continue; }
    if (obj.type === 'member') obj.done = state.met.includes(chapter.member);
    if (obj.type === 'record') obj.done = state.records.includes(chapter.facts[Number(obj.id.slice(-1))].id);
    if (obj.type === 'memory') obj.done = state.memories.includes(`${chapter.id}-${state.room}`);
    if (obj.type === 'battle') obj.done = state.defeated.includes(chapter.encounters[obj.encounter].id);
    if (obj.type === 'puzzle') obj.done = state.solved.includes(chapter.id);
    if (obj.id === 'forward') obj.locked = state.room === 0 ? !state.met.includes(chapter.member) : !(state.solved.includes(chapter.id) && state.defeated.includes(chapter.encounters[0].id));
    if (obj.type === 'exit') obj.locked = !state.defeated.includes(chapter.encounters[1].id);
  }
  return scene;
}

export function describeObjective(state) {
  if (state.mode === 'ending') return '마지막 앙코르 완주! 기록첩에서 지나온 여정을 돌아보세요.';
  if (state.mode === 'defeat') return '전투 시작 지점에서 다시 도전할 수 있습니다. 어려우면 도움 모드를 켜 보세요.';
  if (state.mode === 'battle') return `${state.battle.name}에게 길을 부탁하세요. 동료가 먼저 움직일 수 있습니다. 이파리가 행동하면 상대 차례가 됩니다.`;
  if (state.mode === 'upgrade') return '이번 여정에서 얻은 힘을 골라 주세요. 세 번의 성장 선택이 있습니다.';
  if (state.mode === 'victory') return '이 장의 길을 이었습니다. 다음 해로 출발할 준비가 되었습니다.';
  if (state.chapter === 6) return '여섯 동료와 인사하고 우왁굳의 마지막 친선 시험에 도전하세요.';
  const c = CHAPTERS[state.chapter];
  if (!state.met.includes(c.member)) return `${MEMBERS[c.member].name}에게 다가가 말을 걸어 보세요.`;
  if (state.room === 0) return `열린 문을 지나세요. 다음 목적지는 ‘${c.locations[1]}’입니다.`;
  if (!state.solved.includes(c.id)) return `${c.puzzle.title} · 안내를 읽고 세 장치를 연결하세요. ${puzzleStatus(state)}`;
  if (!state.defeated.includes(c.encounters[0].id)) return `${c.encounters[0].name}에게 도전해 기록의 문을 여세요.`;
  if (state.room < 2) return `‘${c.locations[2]}’ 입구가 열렸습니다. 문을 지나 다음 장소로 가세요.`;
  if (!state.defeated.includes(c.encounters[1].id)) return `쉼터에서 준비한 뒤 ${c.encounters[1].name}에게 도전하세요.`;
  return '오른쪽 빛나는 출구에서 이번 장을 마치세요.';
}

export function puzzleStatus(state) {
  const chapter = CHAPTERS[state.chapter];
  if (!chapter) return '';
  if (state.solved.includes(chapter.id)) return '장치 연결 완료';
  const p = state.puzzle[chapter.id];
  const kind = chapter.puzzle.kind;
  if (kind === 'sequence') return `켜진 조명 ${p.sequence.length}/3`;
  if (kind === 'layers') return `${p.layer === 'real' ? '현실' : '이야기'} 거리 · 모은 페이지 ${p.sequence.length}/3`;
  if (kind === 'wings') return `날개: ${p.wings.map(v => v ? '펼침' : '접힘').join(' / ')}`;
  const labels = { winter: '겨울', spring: '봄', guard: '보호', heal: '회복', break: '돌파', sun: '해', moon: '달', left: '왼쪽', right: '오른쪽', up: '위', down: '아래' };
  return p.values.map(v => labels[v] || '미설정').join(' / ');
}

export function availableSupports(state) {
  return state.met.map(id => ({ ...MEMBERS[id], available: state.player.focus >= MEMBERS[id].skill.cost, usedInFinal: state.finalContributions.includes(id) }));
}

function rpgEncounter(id) { return id === FINALE.encounter.id ? FINALE.encounter : CHAPTERS.flatMap(c => c.encounters).find(e => e.id === id); }
export function enemyIntent(state) {
  const b = state.battle;
  if (!b) return null;
  const patterns = {
    plain: ['attack', 'heavy', 'rest', 'attack'], armor: ['guard', 'heavy', 'rest', 'attack'],
    frost: ['attack', 'heavy', 'rest', 'heavy'], illusion: ['illusion', 'heavy', 'rest', 'illusion'],
    storm: ['heavy', 'rest', 'attack', 'heavy'], relay: ['guard', 'heavy', 'rest', 'attack'],
    reverse: ['reverse', 'heavy', 'rest', 'reverse']
  };
  const pattern = b.mechanic === 'final'
    ? (b.phase === 0 ? ['heavy', 'rest', 'attack', 'guard'] : b.phase === 1 ? ['illusion', 'heavy', 'reverse', 'rest'] : ['heavy', 'guard', 'rest', 'attack'])
    : patterns[b.mechanic];
  const kind = pattern[b.turn % pattern.length];
  const power = Math.round(b.attack * ({ heavy: 2.1, rest: 0, guard: 0.7, illusion: 0.8, reverse: 0.75, attack: 1 }[kind]) * (state.help ? 0.6 : 1));
  const descriptions = {
    attack: ['다가오는 일격', '다음 차례에 보통 공격. 공격하거나 응원을 모을 기회입니다.'],
    heavy: [b.mechanic === 'frost' ? '결빙 예고' : '큰 공격 예고', '다음 차례에 강한 공격! 방어 또는 릴파·고세구 지원을 권합니다.'],
    rest: [b.mechanic === 'frost' ? '해빙의 빈틈' : '숨 고르기', '이번 차례에는 공격하지 않습니다. 피해를 1.5배 받는 빈틈입니다.'],
    guard: ['단단한 방어', '일반 공격 피해를 줄입니다. 징버거·주르르 지원으로 방어를 뚫을 수 있습니다.'],
    illusion: ['환영 펼치기', '일반 공격 피해를 크게 줄입니다. 주르르의 진짜 페이지로 드러내 보세요.'],
    reverse: ['뒤집힌 방패', '일반 공격에 강한 저항. 고세구의 규칙 뒤집기로 해제할 수 있습니다.']
  };
  return { name: descriptions[kind][0], text: descriptions[kind][1], kind, power, phase: b.phase, phaseName: b.mechanic === 'final' ? FINALE.phases[b.phase] : null };
}

function rpgStartBattle(state, id, phase = 0) {
  const e = rpgEncounter(id);
  state.battle = { ...e, hp: e.maxHp + (id === 'final-trial' ? phase * 26 : 0), maxHp: e.maxHp + (id === 'final-trial' ? phase * 26 : 0), turn: 0, phase, exposed: 0, counter: false, previousMove: null, lastMove: null };
  state.battle.field = createTacticalField(state);
  state.mode = 'battle'; state.choice = null; state.dialogue = null; state.pending = null;
  state.checkpoint = { id, phase, chapter: state.chapter, room: state.room, position: { ...state.position } };
  rpgLog(state, `${e.name} · ${id === 'final-trial' ? FINALE.phases[phase] : '친선 전투 시작'}. 적의 예고를 먼저 확인하세요.`);
}

function rpgSolve(state) {
  const c = CHAPTERS[state.chapter];
  if (!state.solved.includes(c.id)) {
    state.solved.push(c.id); rpgFocus(state, 3); rpgHeal(state, 15);
    rpgLog(state, `${c.puzzleResult} 체력 15, 응원 3 회복.`);
  }
}
function rpgChoice(state, target, title, text, options) {
  state.choice = { target, title, text, options: [...options, { id: 'cancel', label: '돌아가기' }] };
  state.mode = 'choice';
}
function rpgPuzzleChoice(state, control) {
  const c = CHAPTERS[state.chapter]; const p = state.puzzle[c.id];
  if (state.solved.includes(c.id)) { rpgLog(state, '장치가 안정적으로 작동하고 있습니다.'); return; }
  const puzzle = c.puzzle;
  const options = [];
  if (puzzle.kind === 'sequence') options.push({ id: 'press', label: '조명 켜기' });
  if (puzzle.kind === 'seasons') options.push({ id: 'winter', label: '겨울로 바꾸기' }, { id: 'spring', label: '봄으로 바꾸기' });
  if (puzzle.kind === 'layers') {
    if (control === 0) options.push({ id: 'real', label: '현실 거리로' }, { id: 'storyworld', label: '이야기 거리로' });
    if (control === 1) options.push(...(p.layer === 'real' ? [{ id: 'story', label: '이야기 페이지 꺼내기' }, { id: 'meeting', label: '만남 페이지 꺼내기' }] : [{ id: 'song', label: '노래 페이지 꺼내기' }]));
    if (control === 2) options.push({ id: 'bind', label: '모은 페이지 제본하기' }, { id: 'reset', label: '페이지 순서 처음부터' });
  }
  if (puzzle.kind === 'wings') options.push({ id: 'toggle', label: '손잡이 움직이기' }, { id: 'reset', label: '날개 처음 상태로' });
  if (puzzle.kind === 'relay') options.push({ id: 'guard', label: '보호 역할 배치' }, { id: 'heal', label: '회복 역할 배치' }, { id: 'break', label: '돌파 역할 배치' });
  if (puzzle.kind === 'reverse') options.push(...[
    [{ id: 'sun', label: '해' }, { id: 'moon', label: '달' }],
    [{ id: 'left', label: '왼쪽' }, { id: 'right', label: '오른쪽' }],
    [{ id: 'down', label: '아래' }, { id: 'up', label: '위' }]
  ][control]);
  rpgChoice(state, { kind: 'puzzle', control }, puzzle.controls[control].name, `${puzzle.controls[control].description} ${puzzleStatus(state)}`, options);
}

function rpgChoosePuzzle(state, target, id) {
  const c = CHAPTERS[state.chapter], p = state.puzzle[c.id], spec = c.puzzle, control = target.control;
  p.attempts += 1;
  if (spec.kind === 'sequence') {
    if (control === spec.solution[p.sequence.length]) { p.sequence.push(control); rpgLog(state, `불빛이 이어집니다. ${p.sequence.length}/3`); }
    else { p.sequence = []; rpgLog(state, '불빛 순서가 맞지 않아 꺼졌습니다. 모집 → 준비 → 무대 순서를 떠올려 보세요.'); }
    if (p.sequence.length === 3) rpgSolve(state);
  } else if (['seasons', 'relay', 'reverse'].includes(spec.kind)) {
    if (spec.kind === 'relay') p.values = p.values.map(v => v === id ? null : v);
    p.values[control] = id; rpgLog(state, `장치를 바꿨습니다. ${puzzleStatus(state)}`);
    if (spec.solution.every((v, i) => p.values[i] === v)) rpgSolve(state);
    else if (p.values.every(Boolean)) rpgLog(state, '세 장치를 골랐지만 아직 길이 이어지지 않습니다. 안내문에서 각 자리의 조건을 확인하세요.');
  } else if (spec.kind === 'layers') {
    if (control === 0) { p.layer = id === 'real' ? 'real' : 'story'; rpgLog(state, `${p.layer === 'real' ? '현실' : '이야기'} 거리로 넘어왔습니다.`); }
    if (control === 1) {
      if (p.sequence.length >= 3) rpgLog(state, '페이지를 모두 모았습니다. 제본대로 가져가세요.');
      else if (id === spec.solution[p.sequence.length]) { p.sequence.push(id); rpgLog(state, `페이지를 모았습니다. ${p.sequence.length}/3`); }
      else { p.sequence = []; rpgLog(state, '이야기가 엉켜 페이지가 돌아갔습니다. 이야기 → 노래 → 만남 순서입니다.'); }
    }
    if (control === 2 && id === 'reset') { p.sequence = []; rpgLog(state, '페이지 순서를 초기화했습니다.'); }
    if (control === 2 && id === 'bind') { if (spec.solution.every((v, i) => p.sequence[i] === v)) rpgSolve(state); else rpgLog(state, '세 페이지를 먼저 모아야 합니다. 두 거리를 오가며 순서대로 꺼내세요.'); }
  } else if (spec.kind === 'wings') {
    if (id === 'reset') p.wings = [false, true, false];
    else for (const index of [[0, 1], [0, 1, 2], [1, 2]][control]) p.wings[index] = !p.wings[index];
    rpgLog(state, puzzleStatus(state));
    if (p.wings.every(Boolean)) rpgSolve(state);
  }
}

function rpgInteract(state, id) {
  const scene = currentScene(state), obj = scene.objects.find(o => o.id === id);
  if (!obj || !obj.near) { rpgLog(state, '먼저 대상 옆으로 이동해 주세요.'); return; }
  const c = CHAPTERS[state.chapter];
  if (obj.type === 'portal') {
    if (obj.locked) { rpgLog(state, state.room === 0 ? '먼저 동료와 이야기를 나누세요.' : '퍼즐과 이곳의 전투를 모두 마쳐야 문이 열립니다.'); return; }
    state.room += obj.id === 'back' ? -1 : 1;
    state.position = { x: obj.id === 'back' ? 12 : 2, y: 4 };
    rpgLog(state, currentScene(state).title + '에 도착했습니다.'); return;
  }
  if (obj.type === 'member') {
    if (state.met.includes(c.member)) rpgDialogue(state, MEMBERS[c.member].name, ['잘하고 있어, 이파리. 서두르지 않아도 돼.', ...c.puzzle.clue], null, c.member);
    else {
      const lines = [...c.intro];
      if (state.records.includes(c.facts[0].id)) lines[0] = c.meeting.recognized;
      rpgDialogue(state, MEMBERS[c.member].name, lines, { kind: 'meet', id: c.member }, c.member);
    }
  } else if (obj.type === 'record') {
    const index = Number(obj.id.slice(-1)), f = c.facts[index], relic = c.relics[index];
    rpgDialogue(state, relic.name, relic.lines, { kind: 'relic', id: f.id });
  } else if (obj.type === 'rest') {
    state.player.hp = state.player.maxHp; state.player.focus = rpgMaxFocus(state);
    rpgLog(state, '잠시 쉬었습니다. 체력과 응원이 모두 회복되었습니다.');
  } else if (obj.type === 'memory') {
    const memory = c.memories[state.room === 0 ? 0 : 1], key = `${c.id}-${state.room}`;
    if (!state.memories.includes(key)) { state.memories.push(key); rpgHeal(state, 8); rpgFocus(state, 1); }
    rpgDialogue(state, memory.title + ' · 창작 이야기', memory.lines);
  } else if (obj.type === 'clue') rpgDialogue(state, c.puzzle.clueTitle, [...c.puzzle.clue, `현재 상태: ${puzzleStatus(state)}`, ...(state.help ? [`도움 힌트: ${c.puzzle.hint}`] : ['막히면 설정에서 도움 모드를 켜고 이 안내를 다시 읽어 보세요.'])]);
  else if (obj.type === 'puzzle') rpgPuzzleChoice(state, obj.control);
  else if (obj.type === 'battle') {
    const e = c ? c.encounters[obj.encounter] : FINALE.encounter;
    if (state.defeated.includes(e.id)) { rpgLog(state, '이미 길을 내준 상대입니다. 다음 장소로 나아가세요.'); return; }
    if (c && !state.met.includes(c.member)) { rpgLog(state, '동료와 먼저 만나 지원기술을 받아 주세요.'); return; }
    if (!c && !state.finalMet) rpgDialogue(state, '우왁굳 · 창작 대사', FINALE.dialogue, { kind: 'finalTalk' });
    else rpgChoice(state, { kind: 'battle', id: e.id }, e.name, e.description, [{ id: 'start', label: '도전하기' }]);
  } else if (obj.type === 'exit') {
    if (obj.locked) { rpgLog(state, '이 무대의 상대를 이겨야 다음 해로 나아갈 수 있습니다.'); return; }
    const lines = [...c.outro];
    if (state.records.includes(c.facts[1].id)) lines[0] = c.relics[1].echo;
    rpgDialogue(state, MEMBERS[c.member].name, lines, { kind: 'chapterClear' }, c.member);
  } else if (obj.type === 'ensemble') {
    rpgDialogue(state, '여섯 동료 · 창작 이야기', rpgMemberIds.map(mid => `${MEMBERS[mid].name}: ${MEMBERS[mid].ending}`));
  }
}

function rpgAdvance(state) {
  state.chapter += 1; state.room = 0; state.position = { x: 2, y: 4 };
  state.mode = 'explore'; state.battle = null; state.checkpoint = null; state.dialogue = null; state.pending = null; state.choice = null;
  state.player.level += 1; state.player.maxHp += 10; state.player.attack += 2;
  state.player.hp = state.player.maxHp; state.player.focus = rpgMaxFocus(state);
  rpgLog(state, `${state.chapter === 6 ? '마지막 앙코르' : CHAPTERS[state.chapter].year + ' · ' + CHAPTERS[state.chapter].title}에 도착했습니다. 체력과 공격력이 성장했습니다.`);
}

function rpgDamage(state, amount, bypass, move, intent) {
  let damage = amount;
  if (!bypass && state.battle.exposed === 0 && ['guard', 'illusion', 'reverse'].includes(intent.kind)) damage *= intent.kind === 'illusion' ? 0.35 : 0.5;
  if (intent.kind === 'rest') damage *= 1.5;
  if (state.battle.mechanic === 'relay') damage *= state.battle.previousMove === move ? 0.55 : 1.25;
  if (state.battle.mechanic === 'final' && state.battle.phase === 2) damage *= 1 + state.finalContributions.length * 0.04;
  if (state.help) damage *= 1.2;
  if (tacticalFlank(state)) damage *= 1.35;
  const value = Math.max(1, Math.round(damage));
  const recipient = state.battle.field.target === 'echo' ? state.battle.field.echo : state.battle;
  recipient.hp = Math.max(0, recipient.hp - value);
  return value;
}

function rpgBattleTurn(state, move, support) {
  const b = state.battle, intent = enemyIntent(state);
  if (!b || !intent) return;
  if (support && (!state.met.includes(support) || state.player.focus < MEMBERS[support].skill.cost)) { rpgLog(state, '지원기술을 쓰려면 동료를 만나고 응원 2를 모아야 합니다.'); return; }
  const field = b.field, unit = tacticalActive(state);
  const unitName = MEMBERS[unit.id]?.name || '이파리';
  const attackTarget = tacticalTarget(state);
  if (move === 'attack' || (support && support !== 'ine')) {
    const dest = tacticalApproach(state, support ? 4 : tacticalRange(unit));
    if (!dest) { rpgLog(state, '거리가 멉니다. 다음 차례에 가까이 다가가거나 다른 대상을 골라 주세요.'); return; }
    if (dest.cost) {
      unit.x = dest.x; unit.y = dest.y;
      field.moved.push(unit.id);
    }
  }
  let guard = 0, cancel = false, dealt = 0, actionName = '', usedCounter = false, grantsExposure = false;
  const power = state.player.attack;
  if (move === 'attack') {
    const multiplier = b.counter ? 1.8 : 1; usedCounter = b.counter;
    dealt = rpgDamage(state, power * multiplier, false, move, intent); rpgFocus(state, 1); actionName = usedCounter ? '힘을 실은 반격' : `${unitName}의 공격`;
  } else if (move === 'defend') { guard = 0.76; rpgFocus(state, 2); actionName = '단단히 방어'; }
  else if (move === 'cheer') {
    rpgFocus(state, 3 + state.upgrades.filter(u => u === 'bond').length); rpgHeal(state, 5); actionName = '응원을 모아 체력 5 회복';
  } else if (support) {
    rpgFocus(state, -MEMBERS[support].skill.cost); actionName = `${MEMBERS[support].name} · ${MEMBERS[support].skill.name}`;
    if (b.mechanic === 'final' && !state.finalContributions.includes(support)) state.finalContributions.push(support);
    if (support === 'jingburger') dealt = rpgDamage(state, power * 2.3, true, support, intent);
    if (support === 'ine') { const healed = Math.round(state.player.maxHp * 0.36); rpgHeal(state, healed); guard = 0.45; actionName += ` · 체력 ${healed} 회복`; }
    if (support === 'jururu') { dealt = rpgDamage(state, power * 1.7, true, support, intent); b.exposed = 2; grantsExposure = true; }
    if (support === 'lilpa') { dealt = rpgDamage(state, power * 0.9, false, support, intent); guard = 0.85; b.counter = true; }
    if (support === 'viichan') { dealt = rpgDamage(state, power * 1.05, false, support, intent) + rpgDamage(state, power * 1.05, false, support, intent); rpgFocus(state, 1); }
    if (support === 'gosegu') { dealt = rpgDamage(state, power * 1.4, true, support, intent); cancel = true; b.exposed = Math.max(b.exposed, 1); grantsExposure = true; }
  } else return;
  if (usedCounter) b.counter = false;
  b.previousMove = support || move; b.lastMove = support || move;
  if (unit.id === 'hero') state.stats.turns += 1;
  rpgLog(state, `${actionName}${dealt ? ` · ${attackTarget.id === 'echo' ? '잔향' : b.name}에게 ${dealt} 피해` : ''}.`);
  if (attackTarget.id === 'echo' && !field.echo.hp) { field.target = 'leader'; rpgLog(state, '잔향이 사라졌습니다. 수호자의 협공이 풀립니다.'); }
  if (b.hp <= 0) {
    if (b.mechanic === 'final' && b.phase < 2) {
      b.phase += 1; b.maxHp = FINALE.encounter.maxHp + b.phase * 26; b.hp = b.maxHp; b.turn = 0; b.exposed = 0; b.previousMove = null;
      b.field = createTacticalField(state);
      rpgHeal(state, Math.round(state.player.maxHp * 0.4)); rpgFocus(state, 3);
      state.checkpoint.phase = b.phase;
      rpgLog(state, `${FINALE.phases[b.phase]}! 체력과 응원을 회복했습니다. 이 단계부터 재도전할 수 있습니다.`);
      return;
    }
    state.defeated.push(b.id); state.stats.battles += 1;
    rpgHeal(state, 24); rpgFocus(state, 2);
    if (b.mechanic === 'final') {
      state.mode = 'ending'; state.dialogue = null; state.pending = null;
      // Every companion takes part in the story resolution regardless of build.
      state.finalContributions = [...rpgMemberIds];
      rpgLog(state, '마지막 시험 통과! 마지막 앙코르에서 당신의 자리를 찾았습니다.');
    } else {
      state.mode = 'explore'; state.battle = null; state.checkpoint = null;
      rpgLog(state, '친선 전투 승리! 체력 24와 응원 2 회복. 기록의 길이 조금 더 밝아졌습니다.');
    }
    return;
  }
  if (dealt > 0 && !grantsExposure) b.exposed = Math.max(0, b.exposed - 1);
  if (unit.id !== 'hero') {
    field.acted.push(unit.id); field.active = 'hero';
    field.guard = Math.max(field.guard,guard); field.silence ||= cancel;
    rpgLog(state, `${unitName} 행동 완료. 이파리가 이어서 움직입니다.`);
    return;
  }
  guard = Math.max(guard, field.guard); cancel ||= field.silence;
  const strike = (foe, scale) => {
    if (cancel || intent.kind === 'rest') return 0;
    const victim = advanceTacticalEnemy(state, foe);
    if (!victim) return 0;
    const cover = tacticalTerrain(state, victim.x, victim.y) === '+' ? .65 : 1;
    return Math.max(0, Math.round(intent.power * scale * cover * (1 - guard)));
  };
  const leaderDamage = strike(field.leader, field.echo ? .83 : 1);
  const echoDamage = field.echo?.hp > 0 ? strike(field.echo,.17) : 0;
  const damage = leaderDamage + echoDamage;
  state.player.hp = Math.max(0, state.player.hp - damage);
  if (cancel) rpgLog(state, '규칙이 뒤집혀 상대의 이번 행동이 취소되었습니다.');
  else if (damage) rpgLog(state, `${intent.name}${echoDamage ? ' · 잔향 협공' : ''} · 일행 체력 −${damage}${guard ? ' (방어 적용)' : ''}.`);
  else rpgLog(state, intent.kind === 'rest' ? '상대가 숨을 고릅니다.' : '상대가 거리를 좁혔습니다. 일행은 무사합니다.');
  field.active = 'hero'; field.moved = []; field.acted = []; field.guard = 0; field.silence = false;
  b.turn += 1;
  if (state.player.hp === 0) { state.mode = 'defeat'; state.failures += 1; rpgLog(state, '잠시 넘어졌습니다. 진행 기록은 유지됩니다. 이번 전투부터 다시 도전할 수 있습니다.'); }
}

/** Pure public state transition. Unknown, unavailable and nonlocal actions are ignored. */
export function dispatch(original, action) {
  if (!original || !action || typeof action.type !== 'string') return original;
  const state = rpgClone(original);
  if (action.type === 'tick') {
    if (Number.isFinite(action.seconds) && action.seconds > 0 && action.seconds <= 30 && state.mode !== 'ending') state.stats.seconds = Math.min(3600000, state.stats.seconds + Math.floor(action.seconds));
    return state;
  }
  if (action.type === 'help') { state.help = Boolean(action.enabled); rpgLog(state, state.help ? '도움 모드: 받는 피해 40% 감소, 주는 피해 20% 증가. 이야기는 같습니다.' : '기본 난이도로 돌아왔습니다.'); return state; }
  if (action.type === 'dialogueNext' && state.mode === 'dialogue') {
    if (state.pending?.kind === 'relic' && state.dialogue.index === 0 && !state.records.includes(state.pending.id)) {
      state.records.push(state.pending.id);
    }
    const meeting = state.pending?.kind === 'meet' && CHAPTERS[state.chapter]?.meeting;
    if (meeting && state.dialogue.lines[state.dialogue.index] === meeting.question && action.reply === 1) {
      state.dialogue.lines[state.dialogue.index + 1] = meeting.choices[1].reply;
    }
    if (state.dialogue.index < state.dialogue.lines.length - 1) state.dialogue.index += 1;
    else {
      const pending = state.pending; state.mode = 'explore'; state.dialogue = null; state.pending = null;
      if (pending?.kind === 'meet' && !state.met.includes(pending.id)) { state.met.push(pending.id); rpgFocus(state, 3); rpgLog(state, `${MEMBERS[pending.id].name}의 지원기술 ${MEMBERS[pending.id].skill.name}을 배웠습니다!`); }
      if (pending?.kind === 'chapterClear') state.mode = 'victory';
      if (pending?.kind === 'finalTalk') { state.finalMet = true; rpgChoice(state, { kind: 'battle', id: FINALE.encounter.id }, FINALE.encounter.name, FINALE.encounter.description, [{ id: 'start', label: '최종 시험 시작' }]); }
    }
  } else if (action.type === 'move' && state.mode === 'explore') {
    if (!RPG_DIRECTIONS.some(([dx, dy]) => dx === action.dx && dy === action.dy)) return original;
    const x = state.position.x + action.dx, y = state.position.y + action.dy;
    if (currentScene(state).tiles[y]?.[x] === '.') { state.position = { x, y }; state.stats.steps += 1; }
  } else if (action.type === 'interact' && state.mode === 'explore') rpgInteract(state, action.id);
  else if (action.type === 'choose' && state.mode === 'choice') {
    if (!state.choice.options.some(o => o.id === action.id)) return original;
    const target = state.choice.target; state.choice = null; state.mode = 'explore';
    if (action.id !== 'cancel') {
      if (target.kind === 'puzzle') rpgChoosePuzzle(state, target, action.id);
      if (target.kind === 'battle' && action.id === 'start') rpgStartBattle(state, target.id);
    }
  } else if (action.type === 'tactic' && state.mode === 'battle') tacticalCommand(state, action);
  else if (action.type === 'battle' && state.mode === 'battle') rpgBattleTurn(state, action.move, null);
  else if (action.type === 'support' && state.mode === 'battle' && MEMBERS[action.id]) rpgBattleTurn(state, 'support', action.id);
  else if (action.type === 'nextChapter' && state.mode === 'victory') {
    if ([0, 2, 4].includes(state.chapter)) state.mode = 'upgrade'; else rpgAdvance(state);
  } else if (action.type === 'upgrade' && state.mode === 'upgrade' && UPGRADES.some(u => u.id === action.id)) {
    state.upgrades.push(action.id);
    if (action.id === 'heart') state.player.maxHp += 24;
    if (action.id === 'spark') state.player.attack += 3;
    rpgAdvance(state);
  } else if (action.type === 'retry' && state.mode === 'defeat' && state.checkpoint) {
    const cp = state.checkpoint;
    state.chapter = cp.chapter; state.room = cp.room; state.position = { ...cp.position };
    state.player.hp = state.player.maxHp; state.player.focus = rpgMaxFocus(state); state.stats.retries += 1;
    rpgStartBattle(state, cp.id, cp.phase);
  }
  return state;
}

function rpgIsRecord(value) { return value !== null && typeof value === 'object' && !Array.isArray(value); }
function rpgNumber(value, min, max) { return Number.isInteger(value) && value >= min && value <= max; }
function rpgIds(value, allowed, max = allowed.length, duplicates = false) {
  return Array.isArray(value) && value.length <= max && value.every(v => typeof v === 'string' && allowed.includes(v)) && (duplicates || new Set(value).size === value.length);
}
function rpgString(value, max = 1800) { return typeof value === 'string' && value.length <= max; }

/** Restore only this version; malformed, old, oversized and inconsistent data is rejected. */
export function restore(raw) {
  if (typeof raw !== 'string' || raw.length > RPG_MAX_SAVE) return null;
  let value;
  try { value = JSON.parse(raw); } catch { return null; }
  if (!rpgIsRecord(value) || value.version !== SAVE_VERSION || !rpgModes.includes(value.mode) || !rpgNumber(value.chapter, 0, 6) || !rpgNumber(value.room, 0, value.chapter === 6 ? 0 : 2)) return null;
  if (!rpgIsRecord(value.position) || !rpgNumber(value.position.x, 1, 13) || !rpgNumber(value.position.y, 1, 7)) return null;
  const p = value.player;
  if (!rpgIsRecord(p) || !rpgNumber(p.maxHp, 100, 232) || !rpgNumber(p.hp, 0, p.maxHp) || !rpgNumber(p.attack, 12, 33) || !rpgNumber(p.focus, 0, 9) || !rpgNumber(p.level, 1, 7)) return null;
  if (!rpgIds(value.met, rpgMemberIds) || !rpgIds(value.defeated, rpgEncounterIds) || !rpgIds(value.solved, CHAPTERS.map(c => c.id)) || !rpgIds(value.records, ALL_FACTS.map(f => f.id)) || !rpgIds(value.upgrades, UPGRADES.map(u => u.id), 3, true)) return null;
  if (!rpgIds(value.memories, CHAPTERS.flatMap(c => [`${c.id}-0`, `${c.id}-1`])) || !rpgIds(value.finalContributions, rpgMemberIds)) return null;
  if (typeof value.help !== 'boolean' || typeof value.finalMet !== 'boolean' || !rpgNumber(value.failures, 0, 100000)) return null;
  if (!rpgIsRecord(value.stats) || !['steps', 'turns', 'seconds', 'battles', 'retries'].every(k => rpgNumber(value.stats[k], 0, 3600000))) return null;
  if (!Array.isArray(value.log) || value.log.length > 8 || !value.log.every(v => rpgString(v))) return null;
  if (!rpgIsRecord(value.puzzle)) return null;
  for (const c of CHAPTERS) {
    const z = value.puzzle[c.id];
    if (!rpgIsRecord(z) || !Array.isArray(z.sequence) || z.sequence.length > 3 || !z.sequence.every(v => [0, 1, 2, 'story', 'song', 'meeting'].includes(v)) || !['real', 'story'].includes(z.layer)) return null;
    if (!Array.isArray(z.values) || z.values.length !== 3 || !z.values.every(v => [null, 'winter', 'spring', 'guard', 'heal', 'break', 'sun', 'moon', 'left', 'right', 'up', 'down'].includes(v))) return null;
    if (!Array.isArray(z.wings) || z.wings.length !== 3 || !z.wings.every(v => typeof v === 'boolean') || !rpgNumber(z.attempts, 0, 1000000)) return null;
  }
  if (value.dialogue !== null) {
    const d = value.dialogue;
    if (!rpgIsRecord(d) || !rpgString(d.speaker, 100) || !Array.isArray(d.lines) || !d.lines.length || d.lines.length > 12 || !d.lines.every(v => rpgString(v)) || !rpgNumber(d.index, 0, d.lines.length - 1) || !(d.member === null || rpgMemberIds.includes(d.member))) return null;
  }
  if ((value.mode === 'dialogue') !== Boolean(value.dialogue)) return null;
  if (value.pending !== null) {
    if (!rpgIsRecord(value.pending) || !['meet', 'relic', 'chapterClear', 'finalTalk'].includes(value.pending.kind) || value.mode !== 'dialogue') return null;
    if (value.pending.kind === 'relic') {
      const index = value.room === 0 ? 0 : 1;
      const chapter = CHAPTERS[value.chapter];
      if (!chapter || value.room === 1 || value.pending.id !== chapter.facts[index].id || value.dialogue.speaker !== chapter.relics[index].name) return null;
    }
    if (value.pending.kind === 'meet' && value.pending.id !== CHAPTERS[value.chapter]?.member) return null;
    if (value.pending.kind === 'chapterClear' && !value.defeated.includes(CHAPTERS[value.chapter]?.encounters[1].id)) return null;
    if (value.pending.kind === 'finalTalk' && value.chapter !== 6) return null;
  }
  if (value.choice !== null) {
    const choice = value.choice;
    if (!rpgIsRecord(choice) || !rpgIsRecord(choice.target) || !['puzzle', 'battle'].includes(choice.target.kind) || !rpgString(choice.title, 100) || !rpgString(choice.text) || !Array.isArray(choice.options) || choice.options.length < 1 || choice.options.length > 5 || !choice.options.every(o => rpgIsRecord(o) && rpgString(o.id, 20) && rpgString(o.label, 100))) return null;
    if (choice.target.kind === 'puzzle' && (value.chapter === 6 || !rpgNumber(choice.target.control, 0, 2))) return null;
    if (choice.target.kind === 'battle' && !rpgEncounterIds.includes(choice.target.id)) return null;
    if (choice.target.kind === 'puzzle') {
      if (value.room !== 1 || value.solved.includes(CHAPTERS[value.chapter].id)) return null;
      const rebuilt = rpgClone(value);
      rpgPuzzleChoice(rebuilt, choice.target.control);
      if (JSON.stringify(rebuilt.choice.options.map(o => o.id)) !== JSON.stringify(choice.options.map(o => o.id))) return null;
      value.choice = rebuilt.choice;
    } else {
      const expected = value.chapter === 6 ? FINALE.encounter : CHAPTERS[value.chapter].encounters[value.room - 1];
      if (!expected || choice.target.id !== expected.id || value.defeated.includes(expected.id) || JSON.stringify(choice.options.map(o => o.id)) !== JSON.stringify(['start', 'cancel'])) return null;
    }
  }
  if ((value.mode === 'choice') !== Boolean(value.choice)) return null;
  if (value.battle !== null) {
    const b = value.battle;
    if (!rpgIsRecord(b)) return null;
    const e = rpgEncounter(b.id);
    if (!e || !rpgNumber(b.phase, 0, e.mechanic === 'final' ? 2 : 0) || !rpgNumber(b.turn, 0, 1000000) || b.maxHp !== e.maxHp + (e.mechanic === 'final' ? b.phase * 26 : 0) || !rpgNumber(b.hp, 0, b.maxHp) || !rpgNumber(b.exposed, 0, 3) || typeof b.counter !== 'boolean' || ![null, 'attack', 'defend', 'cheer', ...rpgMemberIds].includes(b.previousMove) || ![null, 'attack', 'defend', 'cheer', ...rpgMemberIds].includes(b.lastMove)) return null;
    // Combat power and labels always come from the current built-in content.
    value.battle = { ...e, hp: b.hp, maxHp: b.maxHp, turn: b.turn, phase: b.phase, exposed: b.exposed, counter: b.counter, previousMove: b.previousMove, lastMove: b.lastMove };
    value.battle.field = restoreTacticalField(value, b.field);
    if (!value.battle.field) return null;
    const expected = value.chapter === 6 ? FINALE.encounter : CHAPTERS[value.chapter].encounters[value.room - 1];
    if (!expected || expected.id !== b.id || (value.mode !== 'ending' && b.hp === 0)) return null;
  }
  if (['battle', 'defeat', 'ending'].includes(value.mode) !== Boolean(value.battle)) return null;
  if (value.checkpoint !== null) {
    const cp = value.checkpoint;
    if (!rpgIsRecord(cp) || !rpgEncounterIds.includes(cp.id) || !rpgNumber(cp.phase, 0, cp.id === 'final-trial' ? 2 : 0) || cp.chapter !== value.chapter || cp.room !== value.room || !rpgIsRecord(cp.position) || !rpgNumber(cp.position.x, 1, 13) || !rpgNumber(cp.position.y, 1, 7)) return null;
    if (cp.id !== value.battle?.id || cp.phase !== value.battle?.phase) return null;
  }
  if (Boolean(value.battle) !== Boolean(value.checkpoint)) return null;
  if (value.mode === 'defeat' && value.player.hp !== 0) return null;
  if (value.mode !== 'defeat' && value.player.hp === 0) return null;
  if (value.mode === 'ending' && (!value.defeated.includes('final-trial') || value.chapter !== 6 || value.battle.hp !== 0)) return null;
  if (value.player.level !== value.chapter + 1 || value.player.maxHp !== 100 + value.chapter * 10 + value.upgrades.filter(u => u === 'heart').length * 24 || value.player.attack !== 12 + value.chapter * 2 + value.upgrades.filter(u => u === 'spark').length * 3 || value.player.focus > rpgMaxFocus(value)) return null;
  if (value.upgrades.length !== Math.floor((value.chapter + 1) / 2) || value.stats.battles !== value.defeated.length) return null;
  for (let i = 0; i < value.chapter; i++) if (!value.met.includes(CHAPTERS[i].member) || !value.solved.includes(CHAPTERS[i].id) || !CHAPTERS[i].encounters.every(e => value.defeated.includes(e.id))) return null;
  if (value.met.some(id => CHAPTERS.findIndex(c => c.member === id) > value.chapter)) return null;
  if (value.met.some((id, i) => id !== CHAPTERS[i]?.member)) return null;
  if (value.solved.some(id => CHAPTERS.findIndex(c => c.id === id) > value.chapter)) return null;
  if (value.records.some(id => CHAPTERS.findIndex(c => c.facts.some(f => f.id === id)) > value.chapter)) return null;
  for (const c of CHAPTERS) {
    if (value.defeated.some(id => c.encounters.some(e => e.id === id)) && (c.index > value.chapter || !value.met.includes(c.member))) return null;
    if (value.defeated.includes(c.encounters[1].id) && (!value.defeated.includes(c.encounters[0].id) || !value.solved.includes(c.id))) return null;
  }
  if (value.room > 0 && !value.met.includes(CHAPTERS[value.chapter].member)) return null;
  if (value.room === 2 && (!value.solved.includes(CHAPTERS[value.chapter].id) || !value.defeated.includes(CHAPTERS[value.chapter].encounters[0].id))) return null;
  if (['victory', 'upgrade'].includes(value.mode) && (value.chapter === 6 || !value.defeated.includes(CHAPTERS[value.chapter].encounters[1].id))) return null;
  if (value.mode === 'upgrade' && ![0, 2, 4].includes(value.chapter)) return null;
  if (![undefined, 2, 3].includes(value.mapRevision)) return null;
  const tiles = currentScene(value).tiles;
  const legacy = value.mapRevision !== 3;
  let oldTiles = tiles;
  if (legacy) {
    oldTiles = LEGACY_MAPS[value.chapter === 6 ? 2 : value.room];
    if (value.mapRevision === 2 && value.chapter < 6) oldTiles = previousRoomTiles(CHAPTERS[value.chapter], value.room);
  }
  // Validate both coordinates against the map on which this save was created.
  // Move only newly blocked positions, including a battle's retry checkpoint.
  for (const position of [value.position, ...(value.checkpoint ? [value.checkpoint.position] : [])]) {
    if (legacy && oldTiles[position.y]?.[position.x] !== '.') return null;
    if (tiles[position.y]?.[position.x] === '.') continue;
    if (!legacy) return null;
    const candidates = [];
    for (let y=1; y<8; y++) for (let x=1; x<14; x++) if (tiles[y][x] === '.') candidates.push({x,y});
    candidates.sort((a,b) => (Math.abs(a.x-position.x)+Math.abs(a.y-position.y))-(Math.abs(b.x-position.x)+Math.abs(b.y-position.y)));
    Object.assign(position, candidates[0]);
  }
  value.mapRevision = 3;
  // Copy known top-level properties only; no storage-derived properties become API input.
  const clean = createGame();
  for (const key of Object.keys(clean)) clean[key] = rpgClone(value[key]);
  return clean;
}

export function serialize(state) {
  const encoded = JSON.stringify(state);
  if (!restore(encoded)) throw new Error('저장할 수 없는 모험 상태입니다.');
  return encoded;
}
