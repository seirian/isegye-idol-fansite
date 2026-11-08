import test from 'node:test';
import assert from 'node:assert/strict';
import {albumRankSeries,albumRankGeometry} from '../albums/core.js';
test('Genie TOP200 has a complete axis without changing TOP100 defaults',()=>{
 const end=Date.now(), point={at:new Date(end).toISOString(),rank:200,status:'ranked'};
 assert.equal(albumRankSeries([point],24,end).length,0);
 const rows=albumRankSeries([point],24,end,200);
 assert.equal(rows.length,1); assert.equal(albumRankGeometry(rows,end-3600000,end,7200000,200).points[0].y,248);
});
