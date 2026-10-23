import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const music=JSON.parse(readFileSync(new URL('../catalog/music.json',import.meta.url),'utf8'));
const song=music.songs.find(s=>s.id==='cat-save-world');
const videoId='zGOzGcEbd-s';
const url=`https://www.youtube.com/watch?v=${videoId}`;
test('cat-save-world retains the user-specified official MV binding',()=>{
  assert.ok(song);assert.equal(song.videoId,videoId);assert.equal(song.url,url);
});
test('official MV source is attached to the matching song',()=>{
  const sources=song.sources.map(id=>music.sources[id]);
  assert.ok(sources.some(s=>s&&s.url===url&&s.title.includes('Official MV')&&s.checkedAt));
});
test('MV binding does not change release metadata or create a duplicate song',()=>{
  assert.equal(music.songs.filter(s=>s.id==='cat-save-world').length,1);
  assert.equal(song.date,'2026-09-28');assert.equal(song.dateKind,'발매일');
  assert.deepEqual(song.members,['gosegu']);assert.equal(song.album,'NO CAT, NO LIFE!');
});
test('the title-track MV is not reused for other album tracks',()=>{
  assert.deepEqual(music.songs.filter(s=>s.videoId===videoId).map(s=>s.id),['cat-save-world']);
});
