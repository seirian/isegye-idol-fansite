import { CHAPTERS, MEMBERS } from './content.js';

export function relicActionLabel(state) {
  if (state.pending?.kind !== 'relic' || state.dialogue?.index !== 0) return '';
  return CHAPTERS[state.chapter].relics[state.room === 0 ? 0 : 1].action;
}

export function createMeetingReplay(state, chapterIndex) {
  const chapter = CHAPTERS[chapterIndex];
  if (!chapter || !state.met.includes(chapter.member)) return null;
  const lines = [...chapter.intro];
  if (state.records.includes(chapter.facts[0].id)) lines[0] = chapter.meeting.recognized;
  return {
    ...state, chapter: chapterIndex, room: 0, position: { x: 7, y: 4 }, mode: 'dialogue',
    dialogue: { member: chapter.member, speaker: MEMBERS[chapter.member].name, lines, index: 0 },
    pending: { kind: 'meet', id: chapter.member }, battle: null, checkpoint: null, choice: null
  };
}

export function meetingSpeaker(state) {
  const chapter = CHAPTERS[state.chapter], dialogue = state.dialogue;
  if (state.pending?.kind !== 'meet' || !chapter || !dialogue) return dialogue?.speaker || '';
  const line = dialogue.lines[dialogue.index];
  if (line === chapter.meeting.opening || line === chapter.meeting.recognized) return '이파리';
  return MEMBERS[chapter.member].name;
}

export function renderMeeting(state, { escape, replay = false }) {
  const chapter = CHAPTERS[state.chapter], member = MEMBERS[chapter.member];
  const scene = chapter.meeting, dialogue = state.dialogue;
  const titleId = replay ? 'meeting-replay-title' : 'meeting-title';
  const line = dialogue.lines[dialogue.index], speaker = meetingSpeaker(state);
  const atChoice = line === scene.question;
  const finalLine = dialogue.index === dialogue.lines.length - 1;
  const actions = atChoice
    ? scene.choices.map((choice, i) => `<button class="meeting-reply" data-action="${i ? 'dialogue-reply' : 'dialogue-next'}" data-reply="${i}">${escape(choice.label)}</button>`).join('')
    : `<button class="meeting-next" data-action="dialogue-next">${finalLine ? (replay ? '장면 마치기' : '함께 출발하기') : '다음 대사'}<span aria-hidden="true"></span></button>`;
  return `<section class="meeting-screen meeting-${chapter.member}${dialogue.index === 0 ? ' meeting-arrival' : ''}" aria-labelledby="${titleId}">
    <div class="meeting-frame">
      <div class="meeting-canvas" aria-hidden="true"><div class="meeting-illustration"></div></div>
      <header class="meeting-heading">
        <p>${escape(chapter.year)}<span aria-hidden="true"> / </span>${escape(chapter.locations[0])}</p>
        <h1 id="${titleId}">${escape(scene.title)}</h1>
      </header>
    </div>
    <div class="meeting-script">
      <div class="meeting-speaker"><h2>${escape(speaker)}</h2><span>${replay ? '첫 만남 다시 보기' : finalLine ? '동료 합류' : '첫 만남'}</span></div>
      <p class="meeting-line${speaker === '이파리' ? ' meeting-narration' : ''}">${escape(line)}</p>
      <div class="meeting-controls"><div class="meeting-meta"><span class="meeting-page" aria-label="전체 ${dialogue.lines.length}장 중 ${dialogue.index + 1}장">${String(dialogue.index + 1).padStart(2, '0')} <span>/</span> ${String(dialogue.lines.length).padStart(2, '0')}</span><small>${finalLine ? escape(member.skill.name) : '팬 창작 장면'}</small></div>
        <div class="meeting-buttons"${atChoice ? ' role="group" aria-label="이파리의 행동을 선택하세요"' : ''}>${actions}</div>
      </div>
    </div>
  </section>`;
}
