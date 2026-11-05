import test from 'node:test';
import assert from 'node:assert/strict';
import {esc,normalized,initials,safeExternal,kstDay,validDay,queryParts,matchesQuery,memberMatches,calendarDays,icsEscape,makeCalendar} from '../review-1st/core.js';

const names={lilpa:'릴파',ine:'아이네',viichan:'비챤'};
const row={title:'[릴파] 오늘은 휴방입니다!',members:['lilpa'],date:'2026-11-03',tags:['공지']};
const event={id:'example',key:'event:example',kind:'event',certainty:'confirmed',status:'scheduled',date:'2026-11-09',time:'18:00',title:'일정, 확인; 다음\\단계\n안내',url:'https://berriz.in/ko/isegyeidol/calendar/'};
const cases=[
 ['escape markup and attributes',()=>assert.equal(esc(`<img a="x">&'`),'&lt;img a=&quot;x&quot;&gt;&amp;&#39;')],
 ['normalization handles width and spacing',()=>assert.equal(normalized('ＲＥ: ＷＩＮＤ'),'rewind')],
 ['Korean initials',()=>assert.equal(initials('아이네 릴파'),'ㅇㅇㄴ ㄹㅍ')],
 ['HTTPS canonical URL',()=>assert.equal(safeExternal('https://example.com/a?q=1'),'https://example.com/a?q=1')],
 ...['javascript:alert(1)','data:text/html,a','http://example.com','https://user:pass@example.com','not-a-url'].map(u=>['reject unsafe URL '+u,()=>assert.equal(safeExternal(u),'')]),
 ['KST day boundary',()=>assert.equal(kstDay('2026-11-02T16:00:00Z'),'2026-11-03')],
 ['date-only remains date-only',()=>assert.equal(kstDay('2026-11-03'),'2026-11-03')],
 ['bad timestamp is not dated',()=>assert.equal(kstDay('invalid'),'')],
 ['leap day accepted',()=>assert.ok(validDay('2028-02-29'))],
 ['invalid date rejected',()=>assert.ok(!validDay('2026-02-29'))],
 ['Korean query date',()=>assert.deepEqual(queryParts('릴파 11월 3일',2026),{dates:['2026-11-03'],tokens:['릴파']})],
 ['explicit year query',()=>assert.deepEqual(queryParts('2025년 12월 1일',2026).dates,['2025-12-01'])],
 ['ISO query date',()=>assert.deepEqual(queryParts('릴파 2026-11-03').dates,['2026-11-03'])],
 ['invalid query date not silently corrected',()=>assert.equal(queryParts('2월 30일',2026).dates.length,0)],
 ['member and date match',()=>assert.ok(matchesQuery(row,'릴파 11월 3일',names,2026))],
 ['wrong date excluded',()=>assert.ok(!matchesQuery(row,'릴파 11월 4일',names,2026))],
 ['initial-search match',()=>assert.ok(matchesQuery(row,'ㄹㅍ',names,2026))],
 ['initials do not match incidental description syllables',()=>assert.ok(!matchesQuery({title:'아이네',members:['ine'],summary:'노래로 팬들을 만납니다.'},'ㄹㅍ',names,2026))],
 ['no fuzzy invented result',()=>assert.ok(!matchesQuery(row,'비챤',names,2026))],
 ['empty member filter means all',()=>assert.ok(memberMatches(row,[]))],
 ['any selected member',()=>assert.ok(memberMatches(row,['ine','lilpa'],'any'))],
 ['all selected members',()=>assert.ok(!memberMatches(row,['ine','lilpa'],'all'))],
 ['calendar November 2026 starts Sunday',()=>assert.equal(calendarDays('2026-11')[0],'2026-11-01')],
 ['calendar correct month length',()=>assert.equal(calendarDays('2026-11').filter(Boolean).length,30)],
 ['calendar rejects invalid month',()=>assert.deepEqual(calendarDays('2026-13'),[])],
 ['ICS string escaping prevents line injection',()=>assert.equal(icsEscape('a,b;c\\d\ne'),'a\\,b\\;c\\\\d\\ne')],
 ['ICS converts KST to UTC',()=>assert.ok(makeCalendar(event).includes('DTSTART:20261109T090000Z'))],
 ['ICS always says not a subscription',()=>assert.ok(makeCalendar(event).replace(/\r\n /g,'').includes('자동 동기화되지'))],
 ['ICS stable UID',()=>assert.ok(makeCalendar(event).includes('UID:event:example@review.isegye-idol.kr'))],
 ['all-day exclusive next date',()=>assert.ok(makeCalendar({...event,time:null,date:'2026-12-31'}).includes('DTEND;VALUE=DATE:20270101'))],
 ['ICS Unicode line folding respects bytes',()=>assert.ok(makeCalendar({...event,title:'긴 한국어 제목 '.repeat(35)}).split('\r\n').every(l=>Buffer.byteLength(l)<=75))],
 ...[{certainty:'tentative'},{status:'cancelled'},{kind:'notice'},{date:'2026-02-30'},{time:'25:00'},{time:'09:99'}].map(p=>['ICS refuses '+JSON.stringify(p),()=>assert.throws(()=>makeCalendar({...event,...p}))]),
];
for(const [name,fn] of cases)test(name,fn);
