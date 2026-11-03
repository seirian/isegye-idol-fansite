import test from 'node:test';import assert from 'node:assert/strict';import vm from 'node:vm';import fs from 'node:fs';
const code=fs.readFileSync(new URL('../catalog/daily-music.js',import.meta.url),'utf8');
const row={videoId:'12345678901',title:'연습용 곡',members:['lilpa'],channelKey:'c14',type:'cover',kind:'official_video',publishedAt:'2026-11-01T16:00:00Z',checkedAt:'2026-11-02T10:00:00Z'};
function setup(){const original={id:'a',title:'옛 곡',members:['ine'],videoId:'00000000000'};const c={queueMicrotask:()=>{},window:{addEventListener(){}},catalogProfiles:new Map([['ine',{}],['lilpa',{}]]),CATALOG:{music:{songs:[original],sources:{}}},catalogSongs:new Map([['a',original]]),catalogVideoUrl:v=>'https://www.youtube.com/watch?v='+v,DAILY_MUSIC_CHANNELS:{c14:{name:'릴파',url:'https://www.youtube.com/@lilpa'}}};vm.createContext(c);vm.runInContext(code,c);return c;}
const doc=rows=>({feed:'daily-music',schemaVersion:1,rows});
test('new records join the same music list, detail and source map using KST publication date',()=>{const c=setup();assert.equal(c.applyDailyMusic(doc([row,row])),1);const item=c.catalogSongs.get('daily-'+row.videoId);assert.equal(c.CATALOG.music.songs.length,2);assert.equal(item.date,'2026-11-02');assert.equal(item.dateKind,'영상 공개일');assert.equal(c.CATALOG.music.sources[item.sources[0]].url,item.url);assert.equal(c.applyDailyMusic(doc([row])),1);assert.equal(c.CATALOG.music.songs.length,2);});
test('invalid feed cannot evict last verified entries or change reviewed links',()=>{const c=setup();c.applyDailyMusic(doc([row]));assert.throws(()=>c.applyDailyMusic(doc([{...row,title:'<img>'}])));assert.equal(c.CATALOG.music.songs.length,2);assert.equal(c.applyDailyMusic(doc([{...row,videoId:'00000000000'}])),0);assert.equal(c.catalogSongs.get('a').title,'옛 곡');});

test('official medley and music clip coexist with the work without replacing reviewed or duplicate video IDs',()=>{
 const c=setup();c.DAILY_MUSIC_CHANNELS.c2={name:'ISEGYE IDOL',url:'https://www.youtube.com/@isegyeidol_ofcl'};
 const mk=(videoId,type)=>({...row,videoId,title:'옛 곡',members:['ine'],channelKey:'c2',type,kind:'official_video'});
 const med=mk('lFgCjRoFjyU','album_medley'),clip=mk('8IY44RZHyw8','music_clip');
 assert.equal(c.applyDailyMusic(doc([med,clip,med])),2);assert.equal(c.CATALOG.music.songs.length,3);
 assert.equal(c.catalogSongs.get('daily-lFgCjRoFjyU').format,'앨범 하이라이트 메들리');assert.equal(c.catalogSongs.get('daily-8IY44RZHyw8').format,'음악 스페셜클립');assert.equal(c.catalogSongs.get('a').title,'옛 곡');
 assert.throws(()=>c.applyDailyMusic(doc([{...med,channelKey:'c14'}])));assert.equal(c.CATALOG.music.songs.length,3);
});
