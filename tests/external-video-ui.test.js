import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
const rows=[
 {id:'P15VglxEkss',category:'external',type:'external_collaboration',channelName:'IRISÉ',publishedAt:'2026-11-16T10:45:19Z'},
 {id:'teaser',category:'external',type:'external_teaser',channelName:'STUDIO CHOOM',relatedSong:'rebels',publishedAt:'2026-11-10T13:00:38Z'},
 {id:'relay',category:'external',type:'external_performance',channelName:'M2',relatedSong:'rebels',publishedAt:'2026-11-16T09:00:17Z'}
];
const context={D:{videos:rows},esc:String,rowCard:v=>`<a>${v.id}</a>`};
vm.createContext(context);vm.runInContext(readFileSync(new URL('../site/external-videos.js',import.meta.url),'utf8'),context);
test('long replay uses hours and existing durations stay unchanged',()=>{
 for(const [sec,label] of [[0,'0:00'],[31,'0:31'],[188,'3:08'],[192,'3:12'],[198,'3:18'],[3599,'59:59'],[3600,'1:00:00'],[5731,'1:35:31'],[36000,'10:00:00']])assert.equal(context.externalVideoDuration(sec),label);
});
test('unknown duration is not fabricated',()=>{for(const v of [null,undefined,NaN,Infinity,-1,3.5,'5731'])assert.equal(context.externalVideoDuration(v),'');});
test('missing song must not match unrelated collaboration rows',()=>{for(const id of [undefined,null,'',0])assert.equal(context.externalPerformanceLinks(id),'');});
test('related performances preserve exact song and current selection exclusion',()=>{
 const html=context.externalPerformanceLinks('rebels');assert.ok(html.includes('relay'));assert.ok(html.includes('teaser'));assert.ok(!html.includes('P15VglxEkss'));assert.ok(!html.includes('IRISÉ'));assert.ok(html.indexOf('<a>relay')<html.indexOf('<a>teaser'));
 assert.ok(!context.externalPerformanceLinks('rebels','relay').includes('<a>relay'));
 assert.equal(context.externalPerformanceLinks('another-song'),'');
});
test('collaboration never becomes a full performance through a related song field',()=>{
 rows[0].relatedSong='rebels';assert.ok(!context.externalPerformanceLinks('rebels').includes('P15VglxEkss'));delete rows[0].relatedSong;
});
