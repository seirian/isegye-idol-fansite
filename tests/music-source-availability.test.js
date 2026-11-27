import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';

function renderer(){
 const context={esc:String,stamp:String,external:(url,label,css)=>url?`<a class="${css}" href="${url}">${label}</a>`:''};
 vm.createContext(context);
 vm.runInContext(readFileSync(new URL('../site/music-source-availability.js',import.meta.url),'utf8'),context);
 return context;
}
test('a quarantined or unknown selection cannot produce a playback button even if a stale URL remains',()=>{
 const context=renderer();
 for(const state of ['unavailable','unknown']){
  const row={videoId:'abcdefghijk',url:'https://www.youtube.com/watch?v=abcdefghijk',videoSource:{availability:state,availabilityCheckedAt:'2026-11-27T13:00:00Z'}};
  const html=context.sourceAvailabilityAction(row,'팬 백업 영상 보기');
  assert.match(html,/disabled/);assert.doesNotMatch(html,/href=|abcdefghijk/);
  assert.match(context.sourceAvailabilityNotice(row),/곡과 발매 기록/);
 }
});
test('verified available source keeps its exact link',()=>{
 const context=renderer();
 const html=context.sourceAvailabilityAction({videoId:'abcdefghijk',videoSource:{availability:'available'}},'공식 영상 보기');
 assert.match(html,/watch\?v=abcdefghijk/);assert.doesNotMatch(html,/disabled/);
});
test('official daily feed updates preserve the quarantined reviewed baseline and cannot add a fan backup',()=>{
 const quarantined={id:'historical-song',title:'기록 곡',type:'cover',members:['ine'],originalVideoId:'OLDVIDEO123',videoSource:{kind:'fan_backup',availability:'unavailable',reviewedVideoId:'BADVIDEO123'}};
 const context={CATALOG:{music:{songs:[quarantined],sources:{}}},DAILY_MUSIC_CHANNELS:{c1:{name:'공식 채널',url:'https://www.youtube.com/@official'}},catalogProfiles:new Map([['ine',{}]]),catalogSongs:new Map(),catalogVideoUrl:id=>'https://www.youtube.com/watch?v='+id};
 vm.createContext(context);
 vm.runInContext(readFileSync(new URL('../catalog/daily-music.js',import.meta.url),'utf8').split('let dailyMusicPending=')[0],context);
 const feed={feed:'daily-music',schemaVersion:1,rows:[{videoId:'NEWVIDEO123',channelKey:'c1',title:'다른 곡',members:['ine'],type:'cover',kind:'official_video',publishedAt:'2026-11-25T00:00:00Z',checkedAt:'2026-11-27T13:00:00Z'}]};
 assert.equal(context.applyDailyMusic(feed),1);
 const retained=context.CATALOG.music.songs.find(s=>s.id==='historical-song');
 assert.equal(retained.videoId,undefined);assert.equal(retained.url,undefined);
 assert.equal(retained.videoSource.availability,'unavailable');assert.equal(retained.originalVideoId,'OLDVIDEO123');
 const bad={...feed,rows:[{...feed.rows[0],channelKey:'c3',kind:'fan_backup',videoId:'BADVIDEO123'}]};
 assert.throws(()=>context.applyDailyMusic(bad),/Invalid music record/);
});
