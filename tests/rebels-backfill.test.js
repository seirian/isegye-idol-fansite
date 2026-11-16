import test from 'node:test';
import assert from 'node:assert/strict';
import {albumHistoricalReference} from '../albums/flow.js';
const sample=()=>({melon:{trackId:'603813508',albumId:'15120216'},melonHistoricalBackfill:{schemaVersion:1,sourceType:'guyso_public_historical',trackId:'603813508',albumId:'15120216',datasetSha256:'a'.repeat(64),charts:{melon_top100:{source:'https://xn--o39an51b2re.com/chart/melon/top100/trend/ranking/603813508',at:['2026-11-09T10:00:00+00:00']}}}});
test('REBELS source is explicit and timestamp-specific',()=>{const r=albumHistoricalReference(sample(),'melon_top100');assert.match(r.url,/603813508$/);assert.ok(r.times.has(Date.parse('2026-11-09T19:00:00+09:00')));});
test('other songs and arbitrary URLs have no attribution',()=>{assert.equal(albumHistoricalReference({},'melon_top100'),null);let d=sample();d.melon.trackId='1';assert.equal(albumHistoricalReference(d,'melon_top100'),null);d=sample();d.melonHistoricalBackfill.charts.melon_top100.source='javascript:alert(1)';assert.equal(albumHistoricalReference(d,'melon_top100'),null);});
test('out-of-window and malformed times are rejected',()=>{for(const t of ['invalid','2026-11-09T09:01:00Z','2026-11-16T01:00:00Z']){const d=sample();d.melonHistoricalBackfill.charts.melon_top100.at=[t];assert.equal(albumHistoricalReference(d,'melon_top100'),null);}});
