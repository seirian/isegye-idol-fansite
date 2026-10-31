import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import {kstDate} from '../src/lib.js';
const ctx=vm.createContext({URL,kstDate,document:{addEventListener(){}},setInterval(){}});
const read=p=>fs.readFileSync(new URL(p,import.meta.url),'utf8');
vm.runInContext(read('../schedule/core.js').replace(/^export /gm,'')+'\n'+read('../home-review/ui.js'),ctx);
const now=new Date('2026-10-31T15:05:00Z'); // Nov 1, 00:05 KST
const note=(id,stamp)=>({id:'berriz-notice-'+id,sourceId:'berriz-notice',sourceUrl:'https://berriz.in/ko/isegyeidol/notice/'+id+'/',publishedAt:stamp});
const event=(id,date,time)=>({id:'berriz-calendar-'+id,calendarId:id,sourceId:'berriz-calendar',sourceUrl:'https://berriz.in/ko/isegyeidol/calendar/',dateBasis:'official_calendar',certainty:'confirmed',status:'scheduled',date,time});
test('home picks most recent actually published official notice, rejecting fan and mismatched sources',()=>{
 const news=[note(1,'2026-10-30'),note(2,'2026-10-31'),note(3,'2027-01-01'),{...note(4,'2026-10-31'),sourceId:'naver-search'},{...note(5,'2026-10-31'),sourceUrl:'https://example.com'}];
 assert.equal(ctx.homeBriefItems({news,events:[]},now).notice.id,'berriz-notice-2'); assert.equal(news[0].id,'berriz-notice-1');
});
test('nearest confirmed calendar time is based on KST, not current UTC day',()=>{
 const events=[event('late','2026-11-02','18:00'),event('past','2026-10-31','23:59'),event('ended','2026-11-01','00:01'),{...event('cancel','2026-11-01','00:06'),status:'cancelled'},{...event('maybe','2026-11-01','00:07'),certainty:'tentative'},event('next','2026-11-01','00:10')];
 assert.equal(ctx.homeBriefItems({news:[],events},now).next.calendarId,'next'); assert.equal(events[0].calendarId,'late');
});
test('all-day event stays for its local date; empty sources never create invented content',()=>{
 const row={...event('all','2026-11-01',null),allDay:true};assert.equal(ctx.homeBriefItems({news:[],events:[row]},now).next,row);
 const none=ctx.homeBriefItems({news:[],events:[]},now);assert.equal(none.notice,undefined);assert.equal(none.next,undefined);
});
