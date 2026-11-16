import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import {albumValidSnapshot} from '../albums/core.js';
const source=fs.readFileSync(new URL('../albums/runtime.js',import.meta.url),'utf8');
function fixture(){
  const at=Date.now()-60000;
  const ctx=vm.createContext({albumValidSnapshot,albumInsights:{generatedAt:new Date(at-60000).toISOString()},ALBUMS_ART:{},ALBUMS_BRANDS:{},ALBUMS_BADGES:{}});
  vm.runInContext(source,ctx);
  const data={schemaVersion:1,feed:'daily-albums',generatedAt:new Date(at).toISOString(),tracks:{rebels:{match:'unmatched'}},providers:{},assets:{}};
  return {ctx,data};
}
test('newer snapshot replaces the old fixed-version requirement',()=>{const {ctx,data}=fixture();assert.equal(ctx.albumAcceptRuntime(data),true);});
test('older, future and wrong feed snapshots are rejected',()=>{
  for(const mutation of [d=>d.generatedAt='2020-01-01T00:00:00Z',d=>d.generatedAt=new Date(Date.now()+3600000).toISOString(),d=>d.feed='other']){
    const {ctx,data}=fixture();mutation(data);assert.equal(ctx.albumAcceptRuntime(data),false);
  }
});
test('asset URLs are derived from exact hashes and stay same-origin',()=>{
  const {ctx,data}=fixture();const sha='a'.repeat(64);
  data.assets.covers={[sha]:{sha256:sha,path:`albums/asset-cache/${sha}.webp`,source:'https://example.invalid/ignored'}};
  assert.equal(ctx.albumAcceptRuntime(data),true);assert.equal(ctx.ALBUMS_ART[sha],`/api/albums/assets/${sha}.webp`);
});
test('unsafe asset path cannot partially change existing maps',()=>{
  const {ctx,data}=fixture();const sha='a'.repeat(64);data.assets.covers={[sha]:{sha256:sha,path:'../../private'}};
  assert.equal(ctx.albumAcceptRuntime(data),false);assert.equal(Object.keys(ctx.ALBUMS_ART).length,0);
});
function freshnessFixture(){
  const {ctx}=fixture();
  const data={generatedAt:'2026-11-10T22:01:00Z',publication:{publishedAt:'2026-11-10T22:04:00Z'},
    domesticCharts:{melon_hot100:{state:'ok',updatedAt:'2026-11-10T22:00:00Z'}},hourlyCoverage:{charts:{melon_hot100:{missingSlots:[]}}}};
  return {ctx,data};
}
test('source collection and publication timestamps remain separate',()=>{
  const {ctx,data}=freshnessFixture();const h=ctx.albumFreshness(data,'melon_hot100',Date.parse('2026-11-10T22:20:00Z'));
  assert.equal(h.state,'current');assert.notEqual(h.chartAt,h.collectedAt);assert.notEqual(h.collectedAt,h.publishedAt);
});
test('night pause ends at 07 KST and is not treated as a normal error',()=>{
  const {ctx,data}=freshnessFixture();data.domesticCharts.melon_hot100.updatedAt='2026-11-10T15:00:00Z';
  for(let hour=16;hour<22;hour++)assert.equal(ctx.albumFreshness(data,'melon_hot100',Date.parse(`2026-11-10T${hour}:30:00Z`)).state,'paused');
  assert.equal(ctx.albumFreshness(data,'melon_hot100',Date.parse('2026-11-10T22:20:00Z')).state,'delayed');
});
test('old chart does not look current just because metadata was refreshed',()=>{
  const {ctx,data}=freshnessFixture();data.generatedAt='2026-11-11T00:05:00Z';
  assert.equal(ctx.albumFreshness(data,'melon_hot100',Date.parse('2026-11-11T00:20:00Z')).state,'delayed');
});
test('publication clock unavailable is shown as unknown, not fabricated',()=>{
  const {ctx,data}=freshnessFixture();delete data.publication;
  assert.equal(ctx.albumFreshness(data,'melon_hot100',Date.parse('2026-11-10T22:20:00Z')).publishedAt,null);
});
test('intentional night hours are excluded from UI missing count',()=>{
  const {ctx,data}=freshnessFixture();data.hourlyCoverage.charts.melon_hot100.missingSlots=['2026-11-10T16:00:00Z','2026-11-10T21:00:00Z','2026-11-10T14:00:00Z'];
  assert.equal(ctx.albumFreshness(data,'melon_hot100',Date.parse('2026-11-10T22:20:00Z')).missing,1);
});
