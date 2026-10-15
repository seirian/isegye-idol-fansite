import test from 'node:test';
import assert from 'node:assert/strict';
import {normalize,searchRecords,parseRoute} from '../src/lib.js';
import {RECORDS} from '../src/data.js';
test('NFKC preserves compatibility initial queries',()=>assert.equal(normalize('ㅇㅇㄴ'),'ㅇㅇㄴ'));
test('conjoining initials match the same member',()=>assert.equal(searchRecords(RECORDS,'\u110b\u110b\u1102')[0].id,'ine'));
test('full width Latin normalization remains supported',()=>assert.equal(searchRecords(RECORDS,'ＳＭＩＬＥ')[0].id,'smile-for-you'));
test('search route retains question marks inside query',()=>assert.equal(parseRoute('#/search?q=a?b').params.get('q'),'a?b'));
