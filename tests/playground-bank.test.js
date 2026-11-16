import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {checkedBank,fetchBank,canonical} from '../site/playground-bank.js';
const seed=JSON.parse(readFileSync(new URL('../playground/catalog.json',import.meta.url),'utf8'));
const feed=()=>({schemaVersion:1,feed:'playground',baseVersion:seed.version,generatedAt:new Date().toISOString(),catalog:structuredClone(seed)});
test('accepts approved seed without losing uppercase source IDs',()=>assert.equal(checkedBank(feed(),seed).questions.length,80));
test('canonical comparison ignores object key order',()=>assert.equal(canonical({a:1,b:2}),canonical({b:2,a:1})));
for(const [name,mutate] of Object.entries({
 'answer replacement':f=>f.catalog.questions[0].answer=1,
 'seed removal':f=>f.catalog.questions.pop(),
 'unsafe source':f=>f.catalog.sources.rewind.url='javascript:alert(1)',
 'release date replacement':f=>f.catalog.tracks[0].date='2025-01-01',
 'duplicate id':f=>f.catalog.questions.push(f.catalog.questions[0]),
 'injected stem':f=>f.catalog.questions[0].stem='<img onerror=alert(1)>',
 'different schema':f=>f.baseVersion='other',
 'future observation':f=>f.generatedAt='2999-01-01T00:00:00Z',
 'invalid observation':f=>f.generatedAt='no date'
}))test('reject '+name,()=>{const f=feed();mutate(f);assert.throws(()=>checkedBank(f,seed));});
test('safe additive question is accepted without changing state version',()=>{const f=feed();f.catalog.questions.push({...structuredClone(seed.questions[0]),id:'test-addition',eligibleFrom:'2026-11-17'});assert.equal(checkedBank(f,seed).questions.length,81);assert.equal(f.catalog.version,seed.version);});
test('unavailable feed falls back to bundled bank',async()=>{const r=await fetchBank(seed,async()=>{throw new Error('offline')});assert.equal(r.data,seed);assert.ok(r.message);});
test('invalid JSON falls back to bundled bank',async()=>{const r=await fetchBank(seed,async()=>({ok:true,text:async()=>'{'}));assert.equal(r.data,seed);});
test('successful bank loads with credentials only to same origin',async()=>{const r=await fetchBank(seed,async(u,o)=>{assert.equal(u,'/api/playground');assert.equal(o.credentials,'same-origin');return {ok:true,text:async()=>JSON.stringify(feed())};});assert.equal(r.data.questions.length,80);assert.equal(r.message,'');});
