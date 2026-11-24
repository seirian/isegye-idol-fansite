import test from 'node:test';
import assert from 'node:assert/strict';
import { CHAPTERS, MEMBERS } from '../rpg/content.js';
import { createGame, currentScene, dispatch, restore, serialize } from '../rpg/engine.js';
import { createMeetingReplay, meetingSpeaker, relicActionLabel, renderMeeting } from '../rpg/story.js';

function finishDialogue(state) {
  while (state.mode === 'dialogue') state = dispatch(state, { type: 'dialogueNext' });
  return state;
}

function interactAtObject(state, id) {
  const { x, y } = currentScene(state).objects.find(object => object.id === id);
  return dispatch({ ...state, position: { x, y } }, { type: 'interact', id });
}

test('a first meeting recalls a discovered object and preserves the selected reply on reload', () => {
  let state = finishDialogue(createGame());
  state = interactAtObject(state, 'record-0');
  assert.equal(state.dialogue.speaker, CHAPTERS[0].relics[0].name);
  assert.deepEqual(state.records, []);
  assert.equal(relicActionLabel(state), CHAPTERS[0].relics[0].action);
  state = dispatch(restore(serialize(state)), { type: 'dialogueNext' });
  assert.deepEqual(state.records, [CHAPTERS[0].facts[0].id]);
  state = interactAtObject(finishDialogue(state), 'member');
  assert.equal(state.dialogue.lines[0], CHAPTERS[0].meeting.recognized);
  assert.equal(meetingSpeaker(state), '이파리');
  state = dispatch(dispatch(state, { type: 'dialogueNext' }), { type: 'dialogueNext' });
  assert.equal(meetingSpeaker(state), MEMBERS.jingburger.name);
  state = dispatch(state, { type: 'dialogueNext', reply: 1 });
  const resumed = restore(serialize(state));
  assert.equal(resumed.dialogue.lines[resumed.dialogue.index], CHAPTERS[0].meeting.choices[1].reply);
  state = finishDialogue(resumed);
  assert.deepEqual(state.met, ['jingburger']);
  assert.equal(state.mode, 'explore');
});

test('all six scenes offer two distinct replies and replay does not mutate the ongoing journey', () => {
  const progress = createGame();
  assert.equal(createMeetingReplay(progress, 0), null);
  progress.met = CHAPTERS.map(c => c.member);
  const before = structuredClone(progress);
  for (const chapter of CHAPTERS) {
    assert.notEqual(chapter.meeting.choices[0].reply, chapter.meeting.choices[1].reply);
    for (const reply of [0, 1]) {
      let scene = createMeetingReplay(progress, chapter.index);
      assert.equal(scene.dialogue.lines[0], chapter.meeting.opening);
      scene = dispatch(dispatch(scene, { type: 'dialogueNext' }), { type: 'dialogueNext' });
      const html = renderMeeting(scene, { escape: String, replay: true });
      assert.ok(html.includes(chapter.meeting.title) && html.includes('data-reply="1"'));
      scene = dispatch(scene, { type: 'dialogueNext', reply });
      assert.equal(scene.dialogue.lines[scene.dialogue.index], chapter.meeting.choices[reply].reply);
      scene = finishDialogue(scene);
      assert.deepEqual(scene.met, progress.met);
      assert.deepEqual(progress, before);
    }
  }
});
