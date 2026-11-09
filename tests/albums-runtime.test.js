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
