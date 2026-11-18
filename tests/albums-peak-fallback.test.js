import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {albumPeakKinds,albumVerifiedFallback,albumVerifiedPeakDates,albumMergedPeaks} from '../albums/peak-fallback.js';
const now=Date.parse('2026-11-18T02:00:00Z');
const ranks={top100:6,hot100:2,realtime:2,hot100_30:1,daily:42,new_week:1,new_month:1};
const secondary={schemaVersion:1,state:'verified',sourceType:'guyso_observed_peaks',trackId:'123',albumId:'456',source:'https://xn--o39an51b2re.com/song/melon/123',checkedAt:'2026-11-18T01:00:00Z',fetchState:'ok',responseSha256:'a'.repeat(64),datePolicy:'summary_does_not_provide_dates',records:Object.fromEntries(albumPeakKinds.map(([key])=>[key,{rank:ranks[key],date:null}]))};
const item={melon:{trackId:'123',albumId:'456'},melonPeaks:{state:'verified',dailyBestRank:41},melonPeakFallback:secondary};
test('seven categories all use Guyso rather than a mixture of providers',()=>{const rows=albumMergedPeaks(item,now);assert.equal(rows.length,7);assert.ok(rows.every(r=>r.sourceLabel==='가이섬'));assert.equal(rows[4].rank,42);});
test('hourly peak is not a selected-window maximum',()=>assert.equal(albumMergedPeaks({...item,charts:{melon_top100:[{rank:1}]}},now)[0].rank,6));
test('HOT100 periods remain separate',()=>{const r=albumMergedPeaks(item,now);assert.equal(r[1].rank,2);assert.equal(r[3].rank,1);});
test('legacy provenance is rejected rather than relabeled',()=>{const i={...item,melonPeakFallback:{...secondary,sourceType:'isegyechart_observed_peaks'}};assert.equal(albumVerifiedFallback(i,now),null);assert.ok(albumMergedPeaks(i,now).every(r=>r.rank===null));});
test('original data alone is not attributed to Guyso',()=>assert.ok(albumMergedPeaks({...item,melonPeakFallback:null},now).every(r=>r.rank===null)));
test('unknown remains dash, not zero or chart-out',()=>assert.ok(albumMergedPeaks({},now).every(r=>r.rank===null)));
test('identity URL digest and timezone validated',()=>{for(const patch of [{trackId:'124'},{albumId:'457'},{source:'https://xn--o39an51b2re.com.evil.test/song/melon/123'},{source:secondary.source+'?x=1'},{responseSha256:''},{checkedAt:'2099-01-01T00:00:00Z'},{checkedAt:'2026-11-18T01:00:00'}])assert.equal(albumVerifiedFallback({...item,melonPeakFallback:{...secondary,...patch}},now),null);});
test('invalid rank and borrowed dates rejected',()=>{for(const row of [{rank:101,date:null},{rank:0,date:null},{rank:'6',date:null},{rank:true,date:null},{rank:6,date:'2023-08-19'},{rank:6}])assert.equal(albumVerifiedFallback({...item,melonPeakFallback:{...secondary,records:{...secondary.records,top100:row}}},now),null);});
test('failed refresh preserves checked timestamp',()=>{const r=albumMergedPeaks({...item,melonPeakFallback:{...secondary,fetchState:'error'}},now)[0];assert.ok(r.stale);assert.equal(r.checkedAt,secondary.checkedAt);});
test('daily above100 is accepted without changing other bounds',()=>assert.equal(albumVerifiedFallback({...item,melonPeakFallback:{...secondary,records:{...secondary.records,daily:{rank:527,date:null}}}},now).records.daily.rank,527));
test('source markup is only in expandable details, not peak cards',()=>{const ui=readFileSync(new URL('../albums/ui.js',import.meta.url),'utf8');const peaks=ui.slice(ui.indexOf('function aiPeaks('),ui.indexOf('function aiStreaming('));const tile=peaks.split('const tile=')[1].split('\n')[0];assert.ok(!tile.includes('sourceLabel'));assert.ok(!tile.includes('<a'));assert.ok(!peaks.includes('이세계차트'));assert.ok(peaks.includes('최고 성적 출처와 확인 시각'));assert.ok(peaks.includes('최고 성적은 가이섬'));});
test('all actual reviewed references render exact source ranks',()=>{const d=JSON.parse(readFileSync(new URL('../albums/peak-reference/guyso-20261118.json',import.meta.url),'utf8'));for(const e of Object.values(d.tracks)){const rows=albumMergedPeaks({melon:e.identity,melonPeakFallback:e.reference},Date.now());assert.deepEqual(rows.map(r=>r.rank),albumPeakKinds.map(([k])=>e.reference.records[k].rank));assert.ok(rows.every(r=>r.sourceLabel==='가이섬'));}});

const chartPaths={top100:'top100',hot100:'hot100-d100',realtime:'realtime',hot100_30:'hot100-d30',daily:'daily',new_week:'newest-w1',new_month:'newest-w4'};
const dateEvidence={schemaVersion:1,sourceType:'guyso_peak_date_evidence',trackId:'123',albumId:'456',records:Object.fromEntries(albumPeakKinds.map(([key])=>[key,{rank:ranks[key],date:'2026-11-11',observedAt:'2026-11-11T00:00:00+09:00',source:`https://xn--o39an51b2re.com/chart/melon/${chartPaths[key]}/trend/ranking/123`,checkedAt:'2026-11-18T01:30:00Z',responseSha256:'b'.repeat(64),rangeStart:'2026-11-10T00:00:00+09:00',rangeEnd:'2026-11-18T00:00:00+09:00',timeUnit:key==='daily'?'DAYS':'HOURS',basis:'earliest_observed_matching_peak'}]))};
const datedItem={...item,melonPeakDates:dateEvidence};
function withDateRecord(key,patch){return {...datedItem,melonPeakDates:{...dateEvidence,records:{...dateEvidence.records,[key]:{...dateEvidence.records[key],...patch}}}};}
test('independently verified dates join all seven current summary ranks without changing summaries',()=>{
  const before=JSON.stringify(secondary),rows=albumMergedPeaks(datedItem,now);
  assert.deepEqual(rows.map(r=>r.rank),albumPeakKinds.map(([key])=>ranks[key]));
  assert.ok(rows.every(r=>r.date==='2026-11-11'&&r.dateEvidence.checkedAt===dateEvidence.records[r.key].checkedAt));
  assert.equal(JSON.stringify(secondary),before);assert.ok(Object.values(secondary.records).every(r=>r.date===null));
});
test('date identity and provider must match the current verified summary',()=>{
  for(const patch of [{trackId:'124'},{albumId:'457'},{schemaVersion:2},{sourceType:'isegyechart_peak_date_evidence'},{records:[]},{records:{...dateEvidence.records,weekly:dateEvidence.records.daily}}]){
    const bad={...datedItem,melonPeakDates:{...dateEvidence,...patch}};
    assert.equal(albumVerifiedPeakDates(bad,now),null);assert.ok(albumMergedPeaks(bad,now).every(r=>r.date===null));
  }
  assert.ok(albumMergedPeaks({...datedItem,melonPeakFallback:null},now).every(r=>r.date===null));
});
test('mismatched or newly improved summary rank suppresses only the affected date',()=>{
  for(const rank of [5,'6',0,null,true]){
    const rows=albumMergedPeaks(withDateRecord('top100',{rank}),now);
    assert.equal(rows[0].date,null);assert.equal(rows[0].rank,6);assert.ok(rows.slice(1).every(r=>r.date));
  }
  const changed={...datedItem,melonPeakFallback:{...secondary,records:{...secondary.records,top100:{rank:5,date:null}}}};
  assert.equal(albumMergedPeaks(changed,now)[0].date,null);
});
test('chart URL and exact source provenance cannot be borrowed across categories or hosts',()=>{
  for(const patch of [{source:dateEvidence.records.hot100.source},{source:dateEvidence.records.top100.source.replace('/123','/124')},{source:'https://xn--o39an51b2re.com.evil.test/chart/melon/top100/trend/ranking/123'},{source:dateEvidence.records.top100.source+'?end=2026-11-18&trackId=124'},{source:dateEvidence.records.top100.source+'?end=2026-02-30'},{source:secondary.source},{responseSha256:''},{basis:'first_ever'},{timeUnit:'DAYS'}])assert.equal(albumMergedPeaks(withDateRecord('top100',patch),now)[0].date,null);
  assert.equal(albumMergedPeaks(withDateRecord('top100',{source:dateEvidence.records.top100.source+'?end=2026-11-18'}),now)[0].date,'2026-11-11');
});
test('date evidence requires explicit timezone, real dates, KST day and bounded observed range',()=>{
  for(const patch of [{date:'2026-02-30'},{date:'2026-11-10'},{observedAt:'2026-11-11T00:00:00'},{observedAt:'2026-02-30T00:00:00+09:00'},{observedAt:'2026-11-11T24:00:00+09:00'},{checkedAt:'2026-11-18T12:00:00Z'},{checkedAt:'2026-11-18T01:30:00'},{rangeStart:'2026-11-12T00:00:00+09:00'},{rangeEnd:'2026-11-10T00:00:00+09:00'},{rangeEnd:'2026-11-19T00:00:00+09:00'},{rangeEnd:'invalid'}])assert.equal(albumMergedPeaks(withDateRecord('top100',patch),now)[0].date,null,JSON.stringify(patch));
  assert.equal(albumMergedPeaks(withDateRecord('top100',{observedAt:'2026-11-10T15:00:00Z'}),now)[0].date,'2026-11-11');
  assert.equal(albumMergedPeaks(withDateRecord('daily',{observedAt:'2026-11-11T01:00:00+09:00'}),now)[4].date,null);
});
test('unknown rank and video-only items cannot gain dates from a separate evidence object',()=>{
  const unknown={...datedItem,melonPeakFallback:{...secondary,records:{...secondary.records,hot100:{rank:null,date:null},hot100_30:{rank:null,date:null}}}};
  const rows=albumMergedPeaks(unknown,now);assert.equal(rows[1].date,null);assert.equal(rows[3].date,null);
  assert.ok(albumMergedPeaks({melonPeakDates:dateEvidence},now).every(r=>r.rank===null&&r.date===null));
});
test('legacy records stay independent and missing evidence is unconfirmed instead of provider omission',()=>{
  const ui=readFileSync(new URL('../albums/ui.js',import.meta.url),'utf8');const peaks=ui.slice(ui.indexOf('function aiPeaks('),ui.indexOf('function aiStreaming('));
  assert.ok(peaks.includes('기록일 미확인'));assert.ok(!peaks.includes('기록일 미제공'));assert.ok(peaks.includes('최초 달성일을 보증하지 않습니다'));
  assert.ok(albumMergedPeaks(item,now).every(r=>r.date===null));
});
test('all 24 reviewed songs preserve seven summary ranks and use only matching collected dates',()=>{
  const reference=JSON.parse(readFileSync(new URL('../albums/peak-reference/guyso-20261118.json',import.meta.url),'utf8'));
  const evidence=JSON.parse(readFileSync(new URL('../albums/peak-reference/guyso-dates-20261118.json',import.meta.url),'utf8'));
  assert.equal(Object.keys(reference.tracks).length,24);
  assert.deepEqual(Object.keys(evidence.tracks).sort(),Object.keys(reference.tracks).sort());
  let dated=0,absentRanks=0;
  for(const [sid,e] of Object.entries(reference.tracks)){
    const dates=evidence.tracks[sid],rows=albumMergedPeaks({melon:e.identity,melonPeakFallback:e.reference,melonPeakDates:dates},Date.now());
    for(const row of rows){
      const expected=dates.records[row.key],rank=e.reference.records[row.key].rank;
      assert.equal(row.rank,rank,`${sid} ${row.key} summary`);
      assert.equal(row.date,expected?.date||null,`${sid} ${row.key} date`);
      if(expected){dated++;assert.equal(row.dateEvidence.source,expected.source);assert.equal(row.dateEvidence.checkedAt,expected.checkedAt);}
      if(rank===null){absentRanks++;assert.equal(row.date,null);}
    }
  }
  assert.equal(absentRanks,4);assert.equal(dated,164);assert.deepEqual(evidence.unresolved,[]);
});
