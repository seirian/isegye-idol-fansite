import test from 'node:test';
import assert from 'node:assert/strict';
import {scheduleCafeEvidence,scheduleApprovedRows,scheduleCollectionMessage,schedulePostedDate} from '../schedule/core.js';
const now='2026-11-04T10:00:00+00:00';
const proof=()=>({articleId:99911111,menuId:345,author:'ine',members:['ine'],title:'[테스트 전용] 새 공지',publishedAt:'2026-11-03T15:01:00+00:00',verifiedRole:'staff',public:true,titleGeneralized:false,checkedAt:'2026-11-04T09:59:00+00:00'});
const data=()=>({generatedAt:now,cafeEvidence:{schemaVersion:1,notices:[proof()],fanSeries:[]}});
const row=()=>({id:'fixture',sourceId:'cafe-members',sourceUrl:'https://cafe.naver.com/steamindiegame/99911111',title:proof().title,publishedAt:proof().publishedAt,members:['ine'],checkedAt:proof().checkedAt});
test('verified runtime notice is displayed without a compiled URL allowlist',()=>{
 assert.equal(scheduleApprovedRows([row()],new Map()).length,0);
 assert.equal(scheduleApprovedRows([row()],new Map(),data()).length,1);
 assert.equal(schedulePostedDate(row().publishedAt),'2026-11-04');
});
test('runtime notice must match exact public author evidence',()=>{
 for(const change of [{title:'forged'},{sourceId:'naver-search'},{members:['gosegu']},{publishedAt:'2026-11-03T00:00:00Z'},{checkedAt:now},{sourceUrl:'https://cafe.naver.com/steamindiegame/99988888'}]){
  assert.equal(scheduleApprovedRows([{...row(),...change}],new Map(),data()).length,0);
 }
});
test('wrong board, role, author, future date and private fields rejected',()=>{
 for(const change of [{verifiedRole:'member'},{menuId:24},{author:'gosegu'},{public:false},{checkedAt:'2030-01-01T00:00:00Z'},{body:'must not retain'},{articleId:22133027},{title:'<script>test</script>'}]){
  const d=data();Object.assign(d.cafeEvidence.notices[0],change);assert.throws(()=>scheduleCafeEvidence(d));
 }
});
test('duplicated runtime IDs and oversized arrays are rejected',()=>{
 const d=data();d.cafeEvidence.notices.push(proof());assert.throws(()=>scheduleCafeEvidence(d));
 const big=data();big.cafeEvidence.notices=Array.from({length:601},proof);assert.throws(()=>scheduleCafeEvidence(big));
});
test('same-author fan reference stays uncertain and on original KST date',()=>{
 const d=data();d.cafeEvidence.fanSeries=[{articleId:99922222,title:'[11/4(수)] 이세돌 뱅온정보',date:'2026-11-04',publishedAt:'2026-11-04T07:00:00+09:00',sameAuthor:true,sameBoard:true,public:true,checkedAt:'2026-11-04T09:59:00+00:00'}];
 const r={id:'fan-fixture',sourceId:'fan-roundup',sourceUrl:'https://cafe.naver.com/steamindiegame/99922222',publishedAt:d.cafeEvidence.fanSeries[0].publishedAt,date:'2026-11-04',dateBasis:'roundup_title',certainty:'tentative'};
 assert.equal(scheduleApprovedRows([r],new Map(),d).length,1);
 assert.equal(scheduleApprovedRows([{...r,certainty:'confirmed'}],new Map(),d).length,0);
 d.cafeEvidence.fanSeries[0].sameAuthor=false;assert.throws(()=>scheduleCafeEvidence(d));
});
test('data publication time does not conceal stale source observations',()=>{
 const d={collectionHealth:{state:'complete'},sources:[{id:'cafe-members',state:'ok',lastSuccessAt:'2026-11-04T09:59:00Z'}]};
 assert.equal(scheduleCollectionMessage(d,Date.parse(now)),'');
 d.sources[0].lastSuccessAt='2026-11-03T00:00:00Z';assert.match(scheduleCollectionMessage(d,Date.parse(now)),/수집 지연/);
 d.collectionHealth.state='partial';assert.match(scheduleCollectionMessage(d,Date.parse(now)),/이전 확인/);
});
