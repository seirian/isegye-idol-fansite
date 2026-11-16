import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const source=fs.readFileSync(new URL('../monitoring/monitor.js',import.meta.url),'utf8');
const match=source.match(/function rowExpired\(row\) \{([\s\S]*?)\n  \}/);
assert.ok(match,'Freshness guard must exist');
const at=Date.parse('2026-11-17T01:05:00Z');
function expired(row,stale=false){
  return vm.runInNewContext('(function(row){'+match[1]+'})(row)',{row,isStale:()=>stale,Date:{now:()=>at,parse:Date.parse}});
}
test('new scheduled slot invalidates a still-recent previous result',()=>assert.equal(expired({key:'schedule',nextDueAt:'2026-11-17T01:05:00Z'}),true));
test('upcoming slot preserves snapshot interpretation',()=>assert.equal(expired({key:'music',nextDueAt:'2026-11-18T01:05:00Z'}),false));
test('watchdog uses its five-minute inspection grace',()=>{
  assert.equal(expired({key:'watchdog',nextDueAt:'2026-11-17T01:02:00Z'}),false);
  assert.equal(expired({key:'watchdog',nextDueAt:'2026-11-17T01:00:00Z'}),true);
});
test('stale snapshot is never current, including event-driven jobs',()=>assert.equal(expired({key:'production',nextDueAt:null},true),true));
