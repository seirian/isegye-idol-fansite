import test from 'node:test';import assert from 'node:assert/strict';import fs from 'node:fs';
import {catalogFilter,catalogIsOfficialTrack} from '../catalog/core.js';
const music=JSON.parse(fs.readFileSync(new URL('../catalog/music.json',import.meta.url),'utf8'));const rewind={...music.songs.find(s=>s.id==='rewind'),videoSource:{kind:'official_mv',channel:'왁타버스 WAKTAVERSE'}};
test('Rewind accepts Korean, joined Latin, punctuation, group and source queries',()=>{for(const q of ['리와인드','REWIND','RE:WIND','RE : WIND','이세계아이돌 리와인드','왁타버스 REWIND'])assert.equal(catalogFilter([rewind],{q}).length,1,q);});
test('official MV filter includes reviewed originals without reclassification',()=>{assert.equal(rewind.type,'original');assert.ok(catalogIsOfficialTrack(rewind));assert.equal(catalogFilter([rewind],{type:'official_track'}).length,1);assert.equal(catalogFilter([rewind],{type:'original'}).length,1);assert.equal(catalogFilter([rewind],{type:'cover'}).length,0);});
