import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {applyEditorial} from '../site/playground-editorial.js';
import {checkedBank} from '../site/playground-bank.js';
import {createSession} from '../playground/core.js';
const read=p=>JSON.parse(readFileSync(new URL(p,import.meta.url),'utf8'));
const seed=read('../playground/catalog.json'), manifest=read('../playground/editorial.json');
test('approved wording fixes exact example without changing source or scoring',()=>{
 const original=structuredClone(seed), changed=applyEditorial(seed,manifest);
 assert.deepEqual(seed,original);
 assert.equal(changed.questions.find(q=>q.id==='stories-ruru-festival-solo').stem,'이세페2에서 주르르가 솔로 무대로 선보인 곡은 무엇일까요?');
 for(let i=0;i<seed.questions.length;i++){
  const a={...seed.questions[i]},b={...changed.questions[i]};
  for(const field of ['stem','hint','explanation']){delete a[field];delete b[field];}
  assert.deepEqual(a,b);
 }
 assert.equal(changed.version,seed.version);assert.deepEqual(changed.sources,seed.sources);
});
test('editorial cannot authorize answer, ID, status or evidence mutations',()=>{
 for(const key of ['answer','id','status','sources','choices','eligibleFrom']){
  const m=structuredClone(manifest); m.edits[0].before[key]=seed.questions[0][key];m.edits[0].after[key]='forged';
  assert.throws(()=>applyEditorial(seed,m));
 }
});
test('mismatched original wording and HTML are rejected',()=>{
 const m=structuredClone(manifest);m.edits[0].before.stem='wrong';assert.throws(()=>applyEditorial(seed,m));
 const x=structuredClone(manifest);x.edits[0].after.stem='<script>';assert.throws(()=>applyEditorial(seed,x));
});
test('untrusted bank is still rejected before wording changes',()=>{
 const feed={schemaVersion:1,feed:'playground',baseVersion:seed.version,generatedAt:new Date().toISOString(),catalog:structuredClone(seed)};
 feed.catalog.questions[0].answer=3;
 assert.throws(()=>checkedBank(feed,seed));
});
test('same-day five and saved IDs stay identical after wording review',()=>{
 const options={mode:'daily',day:'2026-11-24',seed:seed.version+':2026-11-24',count:5};
 assert.deepEqual(createSession(seed,options).ids,createSession(applyEditorial(seed,manifest),options).ids);
});
