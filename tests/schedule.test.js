import {test} from 'node:test';import assert from 'node:assert/strict';import fs from 'node:fs';
import {scheduleValidDate,scheduleSafeUrl,scheduleValidate,scheduleFiltered,scheduleMergeEvents,scheduleCurrentForecasts,scheduleStale} from '../schedule/core.js';
const seed=()=>JSON.parse(fs.readFileSync(new URL('../schedule/seed.json',import.meta.url)));
test('calendar snapshot validates',()=>assert.equal(scheduleValidate(seed()).schemaVersion,1));
test('impossible dates rejected',()=>{assert.equal(scheduleValidDate('2026-02-30'),false);assert.equal(scheduleValidDate('2028-02-29'),true);});
test('source URLs only',()=>{for(const s of ['javascript:alert(1)','https://cafe.naver.com/other/1','https://user:pass@parable-asia.com/'])assert.equal(scheduleSafeUrl(s),null);});
test('fan never official',()=>assert.deepEqual(scheduleFiltered(seed().forecasts,{source:'official'}),[]));
test('fan forecasts exact day only',()=>assert.equal(scheduleCurrentForecasts(seed().forecasts,'2026-10-31').length,0));
test('member filter',()=>assert.equal(scheduleFiltered(seed().forecasts,{member:'ine'}).length,1));
test('dedup same observation',()=>{const r=seed().events[0];assert.equal(scheduleMergeEvents([r],[r]).length,1);});
test('no stale claim',()=>assert.equal(scheduleStale({checkedAt:'2026-01-01T00:00:00Z'},Date.parse('2026-10-30')),true));
test('fan confirmed rejected',()=>{const s=seed();s.forecasts[0].certainty='confirmed';assert.throws(()=>scheduleValidate(s));});
test('invalid time rejected',()=>{const s=seed();s.events[0].time='25:99';assert.throws(()=>scheduleValidate(s));});
import {scheduleApprovedRows,scheduleNoticeEvent,schedulePostedDate} from '../schedule/core.js';
test('search and unknown cafe authors never visible',()=>{
 const url='https://cafe.naver.com/steamindiegame/123';const allowed=new Map([[url,'cafe-members']]);
 const rows=[{sourceId:'naver-search',sourceUrl:url},{sourceId:'cafe-members',sourceUrl:url},{sourceId:'cafe-members',sourceUrl:'https://cafe.naver.com/steamindiegame/22133027'},{sourceId:'fan-roundup',sourceUrl:'https://cafe.naver.com/steamindiegame/22133865'}];
 assert.deepEqual(scheduleApprovedRows(rows,allowed),[rows[1]]);
});
test('designated fan post only',()=>assert.equal(scheduleApprovedRows([{sourceId:'fan-roundup',sourceUrl:'https://cafe.naver.com/steamindiegame/22137397'}],new Map()).length,1));
test('publication archive is not a broadcast appointment',()=>{
 const r=scheduleNoticeEvent({id:'1',publishedAt:'2021-08-25T16:00:00Z'});
 assert.equal(r.date,'2021-08-26');assert.equal(r.type,'notice');assert.equal(r.dateBasis,'publication');assert.equal(r.time,null);
});
test('publication KST boundary',()=>assert.equal(schedulePostedDate('2026-10-29T16:00:00Z'),'2026-10-30'));
