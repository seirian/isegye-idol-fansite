import { CONTENT, CHAPTERS, MEMBERS, UPGRADES, FINALE, ALL_FACTS } from './content.js';
import { createGame, dispatch, currentScene, describeObjective, enemyIntent, availableSupports, serialize, restore, SAVE_KEY } from './engine.js';

const uiMain = document.getElementById('game-main');
const uiDialog = document.getElementById('rpg-dialog');
const uiDialogContent = document.getElementById('dialog-content');
const uiAnnouncer = document.getElementById('announcer');
const uiSettingsKey = 'isegye:rpg:settings:v1';
const uiMemberOrder = ['ine', 'jingburger', 'lilpa', 'jururu', 'gosegu', 'viichan'];
const uiEscape = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
let uiSettings = { sound: false, dark: matchMedia('(prefers-color-scheme: dark)').matches, reduceMotion: matchMedia('(prefers-reduced-motion: reduce)').matches };
let uiState = createGame();
let uiHasSave = false;
let uiHasSession = false;
let uiStarted = false;
let uiSupportOpen = false;
let uiSavingAvailable = true;
let uiStorageWarned = false;
let uiNoticeTimer = null;
let uiAudio = null;
let uiPathTimer = null;
let uiWalking = false;
let uiLastTime = performance.now();
let uiDialogKind = '';
let uiPreviousFocus = null;
let uiLastAnnouncement = '';
let uiAnimationTimer = null;

function uiNotice(message, persistent = false) {
  clearTimeout(uiNoticeTimer);
  const node = document.getElementById('save-notice');
  node.textContent = message;
  node.classList.add('visible');
  if (!persistent) uiNoticeTimer = setTimeout(() => node.classList.remove('visible'), 6500);
}
function uiStorageFailure() {
  uiSavingAvailable = false;
  if (!uiStorageWarned) { uiStorageWarned = true; uiNotice('브라우저에 저장할 수 없습니다. 현재 탭에서는 계속할 수 있지만, 탭을 닫으면 진행이 사라질 수 있어요.', true); }
}
try {
  const settings = JSON.parse(localStorage.getItem(uiSettingsKey) || 'null');
  if (settings && typeof settings === 'object') for (const key of ['sound', 'dark', 'reduceMotion']) if (typeof settings[key] === 'boolean') uiSettings[key] = settings[key];
} catch (error) {
  if (!(error instanceof SyntaxError)) uiStorageFailure();
}
try {
  const saved = localStorage.getItem(SAVE_KEY);
  if (saved) {
    const restored = restore(saved);
    if (restored) { uiState = restored; uiHasSave = true; uiHasSession = true; }
    else uiNotice('이전 저장 기록을 읽을 수 없습니다. 새 모험을 시작하면 이 게임의 기록만 다시 저장합니다.');
  }
} catch { uiStorageFailure(); }

function uiApplySettings() {
  document.documentElement.dataset.theme = uiSettings.dark ? 'dark' : 'light';
  document.documentElement.dataset.reducedMotion = String(uiSettings.reduceMotion);
}
for (const key of ['worlds', 'members', 'cast']) {
  if (typeof RPG_ART !== 'undefined' && /^data:image\/webp;base64,/.test(RPG_ART[key] || '')) document.documentElement.style.setProperty('--art-' + key, 'url("' + RPG_ART[key] + '")');
}
uiApplySettings();

function uiSave() {
  if (!uiStarted) return;
  uiHasSession = true;
  try { localStorage.setItem(SAVE_KEY, serialize(uiState)); uiHasSave = true; uiSavingAvailable = true; }
  catch { uiStorageFailure(); }
}
function uiSaveSettings() {
  try { localStorage.setItem(uiSettingsKey, JSON.stringify(uiSettings)); }
  catch { uiStorageFailure(); }
}
function uiSound(kind = 'step') {
  if (!uiSettings.sound) return;
  try {
    uiAudio ||= new (window.AudioContext || window.webkitAudioContext)();
    if (uiAudio.state === 'suspended') uiAudio.resume().catch(() => {});
    const oscillator = uiAudio.createOscillator(), gain = uiAudio.createGain();
    const now = uiAudio.currentTime;
    oscillator.type = 'sine';
    oscillator.frequency.setValueAtTime(({step:330, talk:440, battle:180, support:660, win:880})[kind] || 440, now);
    if (kind === 'win' || kind === 'support') oscillator.frequency.exponentialRampToValueAtTime(kind === 'win' ? 1320 : 990, now + .16);
    gain.gain.setValueAtTime(.0001, now); gain.gain.exponentialRampToValueAtTime(.045, now + .015); gain.gain.exponentialRampToValueAtTime(.0001, now + .2);
    oscillator.connect(gain); gain.connect(uiAudio.destination); oscillator.start(now); oscillator.stop(now + .21);
  } catch { /* Sound is optional; an unavailable audio device never blocks play. */ }
}
function uiStopWalking() { clearTimeout(uiPathTimer); uiWalking = false; }
function uiAct(action, quiet = false) {
  if (!uiStarted || uiDialog.open) return;
  if (action.type !== 'move') uiStopWalking();
  const previous = uiState;
  try { uiState = dispatch(uiState, action); }
  catch { uiNotice('이 행동을 진행하지 못했어요. 현재 장면은 유지됩니다.'); return; }
  if (action.type === 'tick') { uiSave(); return; }
  if (uiState === previous) return;
  if (action.type !== 'support') uiSupportOpen = false;
  uiSave();
  if (!quiet && action.type !== 'move') uiSound(uiState.mode === 'victory' || uiState.mode === 'ending' ? 'win' : action.type === 'support' ? 'support' : action.type === 'battle' ? 'battle' : 'talk');
  uiRender();
  if (action.type === 'battle' || action.type === 'support') {
    const actor = uiMain.querySelector('.battle-actor.enemy');
    if (actor && !uiSettings.reduceMotion) { actor.classList.add('hit'); clearTimeout(uiAnimationTimer); uiAnimationTimer = setTimeout(() => actor.classList.remove('hit'), 320); }
  }
}
function uiSprite(kind, id, extra = '') { return `<span class="sprite ${kind}-sprite ${kind}-${uiEscape(id)} ${extra}" aria-hidden="true"></span>`; }
function uiWorld(index, extra = '') { return `<div class="world-art world-${index >= 6 ? 4 : Math.max(0, index)} ${extra}" aria-hidden="true"></div>`; }
function uiChapter() { return CHAPTERS[uiState.chapter] || FINALE; }
function uiTime(seconds) { const minutes = Math.floor((seconds || 0) / 60); return `${minutes}분`; }
function uiFocusMax() { return uiState.player.maxFocus || uiState.player.focusMax || 6 + uiState.upgrades.filter(x => x === 'bond').length; }
function uiMeter(current, maximum, kind = '') {
  return `<div class="meter ${kind}" role="meter" aria-label="${kind === 'focus' ? '응원' : '체력'}" aria-valuemin="0" aria-valuemax="${maximum}" aria-valuenow="${Math.max(0, current)}"><span data-fill="${Math.max(0, Math.min(100, current / maximum * 100))}"></span></div>`;
}
function uiPlayerStats() {
  const player = uiState.player;
  return `<div class="player-stats" aria-label="이파리 상태"><div class="player-badge">이파리 <b>Lv.${player.level}</b></div><div class="stat"><div class="stat-label"><span>체력</span><b>${player.hp} / ${player.maxHp}</b></div>${uiMeter(player.hp, player.maxHp)}</div><div class="stat"><div class="stat-label"><span>응원</span><b>${player.focus} / ${uiFocusMax()}</b></div>${uiMeter(player.focus, uiFocusMax(), 'focus')}</div></div>`;
}
function uiRenderCover() {
  const completed = uiState.mode === 'ending';
  return `<section class="cover" aria-labelledby="cover-title"><div class="cover-copy"><p class="eyebrow">A little adventure for every leaf</p><h1 id="cover-title" class="serif">이파리 연대기<span>마지막 앙코르</span></h1><p class="cover-desc">오래된 티켓 한 장, 여섯 해의 풍경.<br>이파리의 작은 발걸음으로 기록의 길을 잇고<br>당신을 기다리는 마지막 무대에 도착하세요.</p><div class="cover-meta"><span>이야기 RPG</span><span>여섯 개의 장</span><span>언제든 이어하기</span></div><div class="button-row">${uiHasSession ? `<button class="primary" data-action="continue">${completed ? '앙코르 다시 보기' : '이어서 모험하기'} <span aria-hidden="true">→</span></button><button class="secondary" data-action="new-confirm">새 모험</button>` : '<button class="primary" data-action="start">모험 시작하기 <span aria-hidden="true">→</span></button><button class="secondary" data-action="how-to">플레이 안내</button>'}</div>${uiHasSession ? `<p class="continue-note">${completed ? '모든 장을 완료했어요.' : `${uiEscape(uiChapter().year)} · ${uiEscape(uiChapter().title)}`} · 플레이 ${uiTime(uiState.stats.seconds)}<br>${uiSavingAvailable && uiHasSave ? '이 기기에 저장된 모험입니다.' : '현재 탭에 남아 있는 모험입니다. 탭을 닫지 마세요.'}</p>` : ''}<span class="cover-tag">주인공은 당신, 이파리</span></div><div class="cover-art">${uiWorld(0)}<div class="cover-orbit"></div><div class="cover-hero">${uiSprite('cast', 0)}</div><div class="cover-caption"><span>PROLOGUE / 첫 번째 티켓</span><span>2021 — 2026</span></div></div></section><section aria-label="여섯 해의 여정"><div class="chapter-heading"><h2>당신이 지나갈 여섯 개의 풍경</h2><span>각 장에서 새로운 동료와 능력을 만나요</span></div><div class="chapter-strip">${CHAPTERS.map((chapter, index) => `<article class="chapter-card ${uiState.chapter > index || completed ? 'is-complete' : ''}"><div class="chapter-art">${uiWorld(index)}</div><span class="chapter-number">CH. 0${index + 1} / ${chapter.year}</span><strong>${uiEscape(chapter.title)}</strong><small>${uiEscape(MEMBERS[chapter.member].name)}와 함께</small></article>`).join('')}</div></section>`;
}
function uiNearby(scene = currentScene(uiState)) {
  return (scene.objects || []).filter(obj => Math.abs(obj.x - uiState.position.x) + Math.abs(obj.y - uiState.position.y) <= 1);
}
function uiMap(scene) {
  const near = uiNearby(scene);
  return `<div class="stage-wrap"><div class="stage-topline"><span class="place-pill">${uiEscape(scene.title)}</span><span class="room-mark">${uiState.chapter < 6 ? `장소 ${uiState.room + 1} / 3` : 'THE LAST ENCORE'}</span></div><div class="map-board room-${uiState.room}" tabindex="0" role="group" aria-label="${uiEscape(scene.title)} 탐험 지도. 방향키로 이동하고 E로 상호작용합니다.">${uiWorld(uiState.chapter)}<div class="map-shade"></div><div class="tiles" aria-hidden="true">${scene.tiles.flatMap((row, y) => [...row].map((tile, x) => `<button class="tile ${tile === '#' ? 'wall' : 'floor'}" data-action="walk" data-x="${x}" data-y="${y}" tabindex="-1" ${tile === '#' ? 'disabled' : ''}></button>`)).join('')}</div>${(scene.objects || []).map(obj => {
    const sprite = obj.type === 'member' ? uiSprite('member', obj.member || uiChapter().member) : obj.type === 'battle' ? uiSprite('cast', uiState.chapter < 6 ? uiState.chapter + 1 : 7) : null;
    return `<button class="map-object ${near.some(o => o.id === obj.id) ? 'is-near' : ''} ${obj.done ? 'is-done' : ''} ${obj.locked ? 'is-locked' : ''}" data-action="object" data-id="${uiEscape(obj.id)}" data-x="${obj.x}" data-y="${obj.y}" aria-label="${uiEscape(obj.name)}${obj.done ? ' · 완료' : ''}${obj.locked ? ' · 조건 필요' : ''}" title="${uiEscape(obj.name)}">${sprite || `<span class="object-icon" aria-hidden="true">${obj.done ? '✓' : uiEscape(obj.icon || '◇')}</span>`}<span class="object-label">${uiEscape(obj.name)}</span></button>`;
  }).join('')}<div class="map-player" data-x="${uiState.position.x}" data-y="${uiState.position.y}">${uiSprite('cast', 0)}</div></div><div class="stage-foot"><span class="keyboard-note"><kbd>W A S D</kbd> / <kbd>↑ ↓ ← →</kbd> 이동　<kbd>E</kbd> 대화·조사</span><span class="touch-note">장소를 누르면 이동 · 인물을 누르면 대화</span><span class="save-indicator">${uiSavingAvailable ? '◌ 자동 저장' : '저장 불가 · 탭 유지'}</span></div>${uiState.mode === 'explore' ? `<div class="mobile-controls"><div class="dpad" role="group" aria-label="이동 버튼"><button class="up" data-action="move" data-dx="0" data-dy="-1" aria-label="위로 이동">↑</button><button class="left" data-action="move" data-dx="-1" data-dy="0" aria-label="왼쪽으로 이동">←</button><button class="down" data-action="move" data-dx="0" data-dy="1" aria-label="아래로 이동">↓</button><button class="right" data-action="move" data-dx="1" data-dy="0" aria-label="오른쪽으로 이동">→</button></div><button class="primary interact-button" data-action="interact-near" ${near.length ? '' : 'disabled'}>${near.length ? uiEscape(near[0].name) + ' ↗' : '대상 옆으로 이동'}</button></div>` : ''}</div>`;
}
function uiCompanions() {
  return `<section class="companions-card" aria-label="함께하는 동료"><h2>함께하는 여섯 빛 · ${uiState.met.length} / 6</h2><div class="companion-row">${uiMemberOrder.map(id => uiState.met.includes(id) ? `<div class="companion-chip" title="${uiEscape(MEMBERS[id].name)} · ${uiEscape(MEMBERS[id].skill.name)}" aria-label="${uiEscape(MEMBERS[id].name)} 합류">${uiSprite('member', id)}</div>` : '<div class="companion-chip locked" aria-label="아직 만나지 않은 동료">?</div>').join('')}</div></section>`;
}
function uiSidebar(scene) {
  const chapter = uiChapter();
  return `<aside class="side-panel"><section class="quest-card"><p class="eyebrow">YOUR NEXT STEP</p><h2>${uiEscape(chapter.title)}</h2><p>${uiEscape(scene.description || chapter.description || '')}</p><p class="objective">${uiEscape(describeObjective(uiState))}</p><div class="chapter-progress" aria-label="${Math.min(uiState.chapter, 6)}개 장 완료">${CHAPTERS.map((_, i) => `<span class="${i < uiState.chapter ? 'done' : ''}"></span>`).join('')}</div>${uiState.help ? '<span class="help-tag">도움 모드 적용 중</span>' : ''}${uiState.mode === 'explore' ? `<div class="explore-actions">${uiNearby(scene).map(obj => `<button data-action="interact" data-id="${uiEscape(obj.id)}">${uiEscape(obj.name)} ↗</button>`).join('')}</div>` : ''}</section>${uiCompanions()}<div class="journey-log" aria-label="최근 모험 기록">${(uiState.log || []).slice(0,2).reverse().map(line => `<p>${uiEscape(line)}</p>`).join('')}</div></aside>`;
}
function uiDialogue() {
  const d = uiState.dialogue;
  if (!d) return '';
  const member = d.member || (Object.values(MEMBERS).find(m => m.name === d.speaker) || {}).id;
  const portrait = member ? uiSprite('member', member) : uiSprite('cast', String(d.speaker || '').includes('우왁굳') ? 7 : 0);
  const line = d.lines[d.index] || '';
  return `<section class="story-panel" aria-label="대화"><div class="story-portrait">${portrait}</div><div><p class="speaker">${uiEscape(d.speaker || '이파리')}<span>STORY</span></p><p class="story-text">${uiEscape(typeof line === 'string' ? line : line.text)}</p><div class="story-footer"><small>${d.index + 1} / ${d.lines.length} · ${String(d.speaker).includes('실제 자료') ? '실제 활동 기록' : '창작 이야기'}</small><button class="primary" data-action="dialogue-next">${d.index + 1 === d.lines.length ? '계속하기' : '다음'} <span aria-hidden="true">→</span></button></div></div></section>`;
}
function uiChoice() {
  const choice = uiState.choice;
  if (!choice) return '';
  return `<section class="choice-panel"><p class="eyebrow">A SMALL DECISION</p><h2>${uiEscape(choice.title)}</h2><p>${uiEscape(choice.text)}</p><div class="choices">${choice.options.map(option => `<button class="choice-button" data-action="choose" data-id="${uiEscape(option.id)}"><span>${uiEscape(option.label)}${option.description ? `<small>${uiEscape(option.description)}</small>` : ''}</span><span class="arrow" aria-hidden="true">→</span></button>`).join('')}</div></section>`;
}
function uiSupportList() {
  const supports = availableSupports(uiState).map(s => typeof s === 'string' ? MEMBERS[s] : s);
  return `<section class="support-picker" aria-label="멤버 지원기"><h3>함께하는 힘 <span>응원을 사용해 지원을 받아요</span></h3><div class="support-options">${supports.map(member => { const m = member.skill ? member : MEMBERS[member.id]; return `<button class="support-option" data-action="support" data-id="${uiEscape(m.id)}" ${uiState.player.focus < m.skill.cost ? 'disabled' : ''}><strong>${uiEscape(m.name)}<span>✦ ${m.skill.cost}</span></strong><span>${uiEscape(m.skill.name)}</span><small>${uiEscape(m.skill.description)}</small></button>`; }).join('')}</div>${supports.length ? '' : '<p class="dialog-copy">첫 동료를 만나면 지원기를 사용할 수 있어요.</p>'}</section>`;
}
function uiBattle() {
  const battle = uiState.battle;
  if (!battle) return '';
  const intent = enemyIntent(uiState) || {};
  const phase = battle.phase || 0;
  const name = battle.name || '기록의 수호자';
  return `<div class="stage-wrap"><div class="battle-board">${uiWorld(uiState.chapter)}<div class="battle-hud"><div><small>${uiState.chapter >= 6 ? uiEscape(FINALE.phases[phase] || '마지막 시험') : battle.id.includes('boss') ? 'CHAPTER GUARDIAN' : 'A LITTLE CHALLENGE'}</small><h2>${uiEscape(name)}</h2><div class="enemy-health"><div class="stat-label"><span>수호자의 기운</span><b>${battle.hp} / ${battle.maxHp}</b></div>${uiMeter(battle.hp, battle.maxHp)}</div></div><span class="turn-label">TURN ${(battle.turn || 0) + 1}</span></div><div class="battle-actor hero">${uiSprite('cast', 0)}</div><div class="battle-actor enemy ${uiState.chapter >= 6 ? 'final-enemy' : ''}">${uiSprite('cast', uiState.chapter < 6 ? uiState.chapter + 1 : 7)}</div><div class="intent-banner"><b>다음 행동</b><span>${uiEscape([intent.name,intent.text].filter(Boolean).join(' · ') || '다음 행동을 살펴보세요.')}</span></div></div><div class="stage-foot"><span>차례는 기다려 줍니다. 예고를 읽고 천천히 선택하세요.</span><span class="save-indicator">${uiSavingAvailable ? '◌ 자동 저장' : '저장 불가'}</span></div></div>${uiState.mode === 'battle' ? `<div class="battle-actions" role="group" aria-label="전투 행동"><button class="battle-action" data-action="battle" data-move="attack"><span class="action-symbol" aria-hidden="true">⚔</span><span>공격 <kbd>1</kbd></span><small>빈틈에 피해</small></button><button class="battle-action" data-action="battle" data-move="defend"><span class="action-symbol" aria-hidden="true">◇</span><span>방어 <kbd>2</kbd></span><small>피해를 줄이고 응원</small></button><button class="battle-action" data-action="battle" data-move="cheer"><span class="action-symbol" aria-hidden="true">✧</span><span>응원 <kbd>3</kbd></span><small>지원기의 힘을 모아요</small></button><button class="battle-action support-action" data-action="support-toggle" aria-expanded="${uiSupportOpen}"><span class="action-symbol" aria-hidden="true">❧</span><span>멤버 지원 <kbd>4</kbd></span><small>동료의 특별한 능력</small></button></div>${uiSupportOpen ? uiSupportList() : ''}` : ''}<div class="battle-log" aria-label="전투 기록">${(uiState.log || []).slice(0,4).reverse().map(line => `<p>${uiEscape(line)}</p>`).join('')}</div>`;
}
function uiResult() {
  if (uiState.mode === 'defeat') return `<section class="result-panel"><p class="eyebrow">TAKE A BREATH</p><h2>잠깐, 숨을 고르고</h2><p>걷던 길과 만난 동료들은 그대로 기다립니다.<br>이 전투의 시작부터 다시 도전할 수 있어요.</p><div class="button-row"><button class="primary" data-action="retry">다시 도전하기 ↗</button><button class="secondary" data-action="help-retry">도움받고 재도전</button></div><p class="map-help">도움 모드는 받는 피해를 줄여 줍니다. 설정에서 언제든 바꿀 수 있어요.</p></section>`;
  if (uiState.mode === 'victory') return `<section class="result-panel"><p class="eyebrow">ONE MORE PAGE</p><h2>한 걸음 더, 함께</h2><p>${uiEscape((uiState.log || []).slice(0,2).reverse().join('\n'))}</p><button class="primary" data-action="next-chapter">${uiState.chapter >= 5 ? '마지막 무대로' : '다음 해로 걸어가기'} <span aria-hidden="true">→</span></button></section>`;
  if (uiState.mode === 'upgrade') return `<section class="result-panel"><p class="eyebrow">A LITTLE GROWTH</p><h2>어떤 이파리로 자랄까요?</h2><p>이번 여정에서 얻은 힘을 골라 주세요. 어느 선택으로도 끝까지 갈 수 있어요.</p><div class="upgrade-grid">${UPGRADES.map(upgrade => `<button data-action="upgrade" data-id="${uiEscape(upgrade.id)}"><strong>${uiEscape(upgrade.name)}</strong><small>${uiEscape(upgrade.description)}</small></button>`).join('')}</div></section>`;
  return '';
}
function uiEnding() {
  return `<section class="ending"><p class="eyebrow">YOUR SEAT WAS ALWAYS HERE</p><h1 class="serif">당신의 자리에서, 앙코르.</h1><p>처음 켠 작은 불빛이 마지막 객석까지 이어졌습니다.<br>여섯 해를 걸어온 이파리의 모험이 완성되었어요.</p><div class="ending-cast">${uiMemberOrder.slice(0,3).map(id => uiSprite('member', id)).join('')}${uiSprite('cast',0)}${uiMemberOrder.slice(3).map(id => uiSprite('member', id)).join('')}</div><div class="ending-stats"><div><b>6 / 6</b>함께한 동료</div><div><b>${uiState.records.length} / ${ALL_FACTS.length}</b>발견한 기록</div><div><b>${Math.floor((uiState.stats.seconds || 0) / 60)}분</b>실제 플레이</div></div><p>${uiEscape(CONTENT.ending[CONTENT.ending.length - 1])}</p><div class="button-row"><button class="primary" data-action="journal">우리의 기록첩 펼치기 ↗</button><button class="secondary" data-action="ending-story">엔딩 이야기 다시 읽기</button><button class="text-button" data-action="home">시작 화면으로</button></div><div class="ending-messages">${uiMemberOrder.map(id => `<article><h2>${uiEscape(MEMBERS[id].name)}</h2><p>${uiEscape(MEMBERS[id].ending)}</p></article>`).join('')}</div><p class="ending-credits">${uiEscape(CONTENT.fictionNotice)}<br>기록의 출처는 기록첩에서 확인할 수 있습니다. 이파리와 세계의 그림은 이 게임을 위해 새로 제작했습니다.</p></section>`;
}
function uiRender() {
  const active = document.activeElement;
  const focusAction = active?.dataset?.action;
  const focusId = active?.dataset?.id;
  const focusMove = active?.dataset?.move;
  const focusDx = active?.dataset?.dx;
  const focusDy = active?.dataset?.dy;
  uiMain.dataset.mode = uiStarted ? uiState.mode : 'cover';
  uiMain.dataset.chapter = String(uiState.chapter);
  uiMain.dataset.room = String(uiState.room);
  document.getElementById('pause-button').disabled = !uiStarted;
  if (!uiStarted) uiMain.innerHTML = uiRenderCover();
  else if (uiState.mode === 'ending') uiMain.innerHTML = uiEnding();
  else {
    const chapter = uiChapter(), scene = currentScene(uiState);
    const battleVisible = (uiState.mode === 'battle' || uiState.mode === 'defeat') && uiState.battle;
    uiMain.innerHTML = `<div class="journey-bar"><div class="journey-title"><p class="eyebrow">${uiState.chapter < 6 ? `CHAPTER 0${uiState.chapter + 1} / ${uiEscape(chapter.year)}` : 'FINAL CHAPTER'}</p><h1>${uiEscape(chapter.title)}</h1><p>${uiState.chapter < 6 ? `${uiEscape(MEMBERS[chapter.member].name)}와 함께 걷는 기록의 길` : '우왁굳의 마지막 시험 · 함께하는 앙코르'}</p></div>${uiPlayerStats()}</div><div class="game-layout"><div class="game-column">${battleVisible ? uiBattle() : uiMap(scene)}${uiState.mode === 'dialogue' ? uiDialogue() : uiState.mode === 'choice' ? uiChoice() : uiResult()}${uiState.mode === 'explore' ? '<p class="map-caption">지도의 인물·표지를 누르면 가까이 이동합니다. 기록은 선택해서 읽고, 진행 목표는 오른쪽 안내에서 확인하세요.</p>' : ''}</div>${uiSidebar(scene)}</div>`;
  }
  for (const node of uiMain.querySelectorAll('[data-fill]')) node.style.width = node.dataset.fill + '%';
  for (const node of uiMain.querySelectorAll('.map-object,.map-player')) { node.style.left = ((Number(node.dataset.x) + .5) / 15 * 100) + '%'; node.style.top = ((Number(node.dataset.y) + .5) / 9 * 100) + '%'; }
  if (focusAction && !uiWalking && focusAction !== 'walk' && focusAction !== 'object') {
    const candidate = [...uiMain.querySelectorAll('[data-action]')].find(node => node.dataset.action === focusAction && (!focusId || node.dataset.id === focusId) && (focusMove === undefined || node.dataset.move === focusMove) && (focusDx === undefined || node.dataset.dx === focusDx) && (focusDy === undefined || node.dataset.dy === focusDy));
    if (candidate && !candidate.disabled) candidate.focus({preventScroll:true});
  }
  const announcement = uiStarted ? uiState.mode === 'dialogue' ? `${uiState.dialogue?.speaker || '이야기'}. ${uiState.dialogue?.lines[uiState.dialogue.index] || ''}` : uiState.mode === 'battle' ? `${(uiState.log || []).slice(0,2).reverse().join(' ')} 다음 행동: ${enemyIntent(uiState)?.text || ''}` : describeObjective(uiState) : '이파리 연대기. 마지막 앙코르.';
  if (announcement !== uiLastAnnouncement) { uiAnnouncer.textContent = announcement; uiLastAnnouncement = announcement; }
}
function uiPathTo(x, y, adjacent = false) {
  const scene = currentScene(uiState), start = uiState.position;
  const queue = [{x:start.x,y:start.y,path:[]}], seen = new Set([`${start.x},${start.y}`]);
  while (queue.length) {
    const at = queue.shift();
    if (adjacent ? Math.abs(at.x - x) + Math.abs(at.y - y) <= 1 : at.x === x && at.y === y) return at.path;
    for (const [dx,dy] of [[1,0],[-1,0],[0,1],[0,-1]]) {
      const nx = at.x + dx, ny = at.y + dy, key = `${nx},${ny}`;
      if (!seen.has(key) && scene.tiles[ny]?.[nx] && scene.tiles[ny][nx] !== '#') { seen.add(key); queue.push({x:nx,y:ny,path:[...at.path,{dx,dy}]}); }
    }
  }
  return null;
}
function uiWalk(x, y, objectId = null) {
  if (uiState.mode !== 'explore' || uiDialog.open || !uiStarted) return;
  uiStopWalking();
  const path = uiPathTo(x, y, !!objectId);
  if (!path) { uiNotice('이쪽에서는 닿을 수 없어요. 다른 길을 찾아보세요.'); return; }
  uiWalking = true;
  const chapter = uiState.chapter, room = uiState.room;
  const next = () => {
    if (!uiWalking || uiState.mode !== 'explore' || uiDialog.open || uiState.chapter !== chapter || uiState.room !== room) { uiStopWalking(); return; }
    const step = path.shift();
    if (step) { uiAct({type:'move',...step},true); uiPathTimer = setTimeout(next, uiSettings.reduceMotion ? 45 : 95); }
    else { uiStopWalking(); if (objectId) uiAct({type:'interact',id:objectId}); }
  };
  next();
}
function uiDialogFrame(title, body) { return `<div class="dialog-inner"><div class="dialog-heading"><h2 id="dialog-title">${uiEscape(title)}</h2><button class="close-dialog" data-modal-action="close" aria-label="닫기">×</button></div>${body}</div>`; }
function uiOpenDialog(kind) {
  uiStopWalking(); uiSave(); uiDialogKind = kind;
  if (!uiDialog.open) uiPreviousFocus = document.activeElement;
  let title, body;
  if (kind === 'journal') {
    title = '우리의 기록첩';
    body = `<p class="journal-intro">모험 속에서 발견한 실제 활동 기록입니다. 엔딩 이후에는 놓친 기록도 모두 열립니다. 멤버 대사와 퍼즐은 창작이며, 아래 날짜·활동과 구분됩니다. 기존 아카이브의 확인 자료를 사용했습니다.</p><div class="journal-list">${ALL_FACTS.map(fact => (uiState.records.includes(fact.id) || uiState.mode === 'ending') ? `<article class="journal-entry"><span class="record-date">${uiEscape(fact.date)}${!uiState.records.includes(fact.id) ? ' · 엔딩 후 열린 기록' : ''}</span><h3>${uiEscape(fact.title)}</h3><p>${uiEscape(fact.text)}</p><a href="${uiEscape(fact.url)}" target="_blank" rel="noopener noreferrer">${uiEscape(fact.sourceTitle)} ↗</a></article>` : `<article class="journal-entry locked"><span class="record-date">아직 펼치지 않은 페이지</span><h3>${uiEscape(fact.date.slice(0,4))}년의 기록</h3><p>탐험 지도에서 ▤ 기록 표지를 찾아보세요.</p></article>`).join('')}</div><p class="dialog-note">주요 연혁 확인 기준: 2026-10-23. Across Dimensions는 별도 앨범 카탈로그의 2026-11-09 확인 기록입니다. 공지일·발매일·공연일은 구분하며 이 목록은 전체 활동의 완전한 연표가 아닙니다.</p>`;
  } else if (kind === 'settings') {
    title = '모험 설정';
    body = `<label class="settings-row"><span><strong>작은 효과음</strong><small>행동과 전투에 짧은 소리를 더합니다.</small></span><input type="checkbox" data-setting="sound" ${uiSettings.sound ? 'checked' : ''}></label><label class="settings-row"><span><strong>어두운 화면</strong><small>종이와 메뉴의 밝기를 낮춥니다.</small></span><input type="checkbox" data-setting="dark" ${uiSettings.dark ? 'checked' : ''}></label><label class="settings-row"><span><strong>움직임 줄이기</strong><small>반짝임과 화면 효과를 줄입니다.</small></span><input type="checkbox" data-setting="reduceMotion" ${uiSettings.reduceMotion ? 'checked' : ''}></label><label class="settings-row"><span><strong>도움 모드</strong><small>전투에서 받는 피해를 줄입니다. 진행 기록은 유지됩니다.</small></span><input type="checkbox" data-setting="help" ${uiState.help ? 'checked' : ''}></label><p class="dialog-note">저장은 이 브라우저에서만 유지됩니다. 기기를 바꾸거나 사이트 데이터를 지우면 이어할 수 없습니다. 다른 놀이터 게임의 기록에는 영향을 주지 않습니다.</p><div class="button-row"><button class="text-button" data-modal-action="new-confirm">이 게임의 모험을 처음부터 시작</button></div>`;
  } else if (kind === 'new-confirm') {
    title = '새 티켓을 펼칠까요?';
    body = '<p class="dialog-copy">새 모험을 시작하면 이 게임에 저장된 현재 여정이 새 기록으로 바뀝니다.</p><div class="button-row"><button class="primary" data-modal-action="new-game">새 모험 시작</button><button class="secondary" data-modal-action="close">지금 여정 유지</button></div>';
  } else if (kind === 'pause') {
    title = '잠깐 쉬어 가요';
    body = `<p class="dialog-copy">${uiEscape(uiChapter().title)}에서 기다리고 있어요.<br>메뉴를 닫으면 지금 장면부터 계속됩니다.</p><div class="button-row"><button class="primary" data-modal-action="close">모험 계속하기 →</button><button class="secondary" data-modal-action="home">${uiSavingAvailable ? '저장하고 시작 화면으로' : '현재 탭에 유지하고 시작 화면으로'}</button></div><p class="dialog-note">현재 플레이 ${uiTime(uiState.stats.seconds)} · ${uiSavingAvailable ? '이 브라우저에 저장했습니다.' : '저장을 사용할 수 없습니다. 탭을 유지해 주세요.'}</p>`;
  } else if (kind === 'ending-story') {
    title = '마지막 앙코르';
    body = CONTENT.ending.map(line => `<p class="dialog-copy">${uiEscape(line)}</p>`).join('');
  } else {
    title = '모험을 시작하기 전에';
    body = '<p class="dialog-copy">이파리가 되어 여섯 시대의 작은 장소를 탐험합니다. 인물과 기록 표지 옆에서 대화하고, 단서를 읽어 길을 열어 주세요.</p><p class="dialog-copy">PC: 방향키 또는 WASD로 이동, E로 조사합니다. 화면의 장소와 인물을 눌러 이동할 수도 있어요.<br>모바일: 지도를 누르거나 방향 버튼을 사용하세요.</p><p class="dialog-copy">전투는 공격 · 방어 · 응원 · 멤버 지원 중 하나를 선택합니다. 적의 다음 행동이 아래에 표시됩니다. 큰 공격을 방어하고, 응원으로 동료의 지원기를 사용하세요.</p><p class="dialog-copy">여섯 장과 마지막 시험을 지나면 엔딩에 도착합니다. 장면마다 자동 저장하며, 전투에 실패해도 그 전투부터 재도전할 수 있습니다.</p><p class="dialog-note">30~60분 분량을 목표로 설계한 게임입니다. 실제 소요 시간은 탐색과 선택 속도에 따라 달라집니다. 대사·모험은 팬 창작이며, 실제 활동 기록은 기록첩에서 볼 수 있습니다.</p><button class="primary" data-modal-action="close">알겠어요 →</button>';
  }
  uiDialogContent.innerHTML = uiDialogFrame(title, body);
  if (!uiDialog.open) uiDialog.showModal();
}
function uiCloseDialog() { uiDialog.close(); uiDialogKind = ''; uiLastTime = performance.now(); if (uiPreviousFocus?.isConnected) uiPreviousFocus.focus({preventScroll:true}); }
function uiStart(newGame) {
  if (newGame) { const help = uiState.help; uiState = createGame(); uiState.help = help; }
  uiStarted = true; uiSupportOpen = false; uiLastTime = performance.now(); uiSave(); uiSound('talk'); uiRender(); uiMain.focus({preventScroll:true}); window.scrollTo({top:0,behavior:'instant'});
}
function uiHome() { uiStopWalking(); uiSave(); uiStarted = false; uiSupportOpen = false; uiRender(); uiMain.focus({preventScroll:true}); window.scrollTo({top:0,behavior:'instant'}); }
uiMain.addEventListener('click', event => {
  const button = event.target.closest('[data-action]');
  if (!button || button.disabled) return;
  const action = button.dataset.action;
  if (action === 'start') return uiStart(true);
  if (action === 'continue') return uiStart(false);
  if (action === 'home') return uiHome();
  if (['journal','settings','how-to','new-confirm','ending-story'].includes(action)) return uiOpenDialog(action);
  if (action === 'support-toggle') { uiSupportOpen = !uiSupportOpen; uiRender(); return; }
  if (action === 'walk') return uiWalk(Number(button.dataset.x), Number(button.dataset.y));
  if (action === 'object') return uiWalk(Number(button.dataset.x), Number(button.dataset.y), button.dataset.id);
  if (action === 'interact-near') { const object = uiNearby()[0]; if (object) uiAct({type:'interact',id:object.id}); return; }
  if (action === 'move') { uiStopWalking(); return uiAct({type:'move',dx:Number(button.dataset.dx),dy:Number(button.dataset.dy)},true); }
  if (action === 'interact') return uiAct({type:'interact',id:button.dataset.id});
  if (action === 'dialogue-next') return uiAct({type:'dialogueNext'});
  if (action === 'choose') return uiAct({type:'choose',id:button.dataset.id});
  if (action === 'battle') return uiAct({type:'battle',move:button.dataset.move});
  if (action === 'support') { uiSupportOpen = false; return uiAct({type:'support',id:button.dataset.id}); }
  if (action === 'upgrade') return uiAct({type:'upgrade',id:button.dataset.id});
  if (action === 'next-chapter') return uiAct({type:'nextChapter'});
  if (action === 'retry') return uiAct({type:'retry'});
  if (action === 'help-retry') { uiAct({type:'help',enabled:true},true); return uiAct({type:'retry'}); }
});
uiDialogContent.addEventListener('click', event => {
  const button = event.target.closest('[data-modal-action]');
  if (!button) return;
  const action = button.dataset.modalAction;
  if (action === 'close') uiCloseDialog();
  else if (action === 'home') { uiCloseDialog(); uiHome(); }
  else if (action === 'new-confirm') uiOpenDialog('new-confirm');
  else if (action === 'new-game') { uiCloseDialog(); uiStart(true); }
});
uiDialogContent.addEventListener('change', event => {
  const key = event.target.dataset.setting;
  if (key === 'help') { uiState = dispatch(uiState,{type:'help',enabled:event.target.checked}); if (uiStarted) uiSave(); uiRender(); }
  else if (['sound','dark','reduceMotion'].includes(key)) { uiSettings[key] = event.target.checked; uiApplySettings(); uiSaveSettings(); if (key === 'sound' && uiSettings.sound) uiSound('support'); }
});
uiDialog.addEventListener('cancel', event => { event.preventDefault(); uiCloseDialog(); });
document.getElementById('home-button').addEventListener('click', () => uiStarted ? uiOpenDialog('pause') : uiHome());
document.getElementById('journal-button').addEventListener('click', () => uiOpenDialog('journal'));
document.getElementById('settings-button').addEventListener('click', () => uiOpenDialog('settings'));
document.getElementById('pause-button').addEventListener('click', () => uiOpenDialog('pause'));
window.addEventListener('keydown', event => {
  if (uiDialog.open || !uiStarted || event.ctrlKey || event.metaKey || event.altKey || /INPUT|TEXTAREA|SELECT/.test(event.target.tagName)) return;
  const key = event.key.toLowerCase();
  if (key === 'escape') { event.preventDefault(); uiOpenDialog('pause'); return; }
  if (uiState.mode === 'explore') {
    const directions = {arrowup:[0,-1],w:[0,-1],arrowdown:[0,1],s:[0,1],arrowleft:[-1,0],a:[-1,0],arrowright:[1,0],d:[1,0]};
    if (directions[key]) { event.preventDefault(); uiStopWalking(); const [dx,dy] = directions[key]; uiAct({type:'move',dx,dy},true); }
    else if (key === 'e') { event.preventDefault(); const obj = uiNearby()[0]; if (obj) uiAct({type:'interact',id:obj.id}); }
  } else if (uiState.mode === 'dialogue' && (key === 'e' || key === ' ')) { event.preventDefault(); if (!event.repeat) uiAct({type:'dialogueNext'}); }
  else if (uiState.mode === 'battle' && !event.repeat && ['1','2','3','4'].includes(key)) { event.preventDefault(); if (key === '4') { uiSupportOpen = !uiSupportOpen; uiRender(); } else uiAct({type:'battle',move:({1:'attack',2:'defend',3:'cheer'})[key]}); }
});
document.addEventListener('visibilitychange', () => { uiStopWalking(); uiSave(); uiLastTime = performance.now(); if (document.hidden && uiStarted && !uiDialog.open) uiOpenDialog('pause'); });
window.addEventListener('pagehide', uiSave);
setInterval(() => {
  const now = performance.now(), seconds = Math.min(10,Math.floor((now - uiLastTime) / 1000));
  uiLastTime = now;
  if (seconds > 0 && uiStarted && !uiDialog.open && !document.hidden && uiState.mode !== 'ending') uiAct({type:'tick',seconds},true);
},5000);
Object.defineProperty(window, '__IPARI_RPG__', {value:Object.freeze({snapshot:() => JSON.parse(JSON.stringify(uiState)),scene:() => JSON.parse(JSON.stringify(currentScene(uiState))),intent:() => JSON.parse(JSON.stringify(enemyIntent(uiState) || {}))}),writable:false,configurable:false});
uiRender();
