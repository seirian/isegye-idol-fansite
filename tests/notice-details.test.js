import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
const code=readFileSync(new URL('../site/notice-details.js',import.meta.url),'utf8');
const ctx=vm.createContext({esc:s=>String(s).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;'),stamp:s=>s});
vm.runInContext(code,ctx);
test('bounded verified facts render in operating notice detail',()=>{
 const html=vm.runInContext('archiveNoticeHighlights({contentHighlights:["행사 일시: 11월 15일","응모 기간: 11월 6일까지"],contentCheckedAt:"2026-11-05T09:00:00Z"})',ctx);
 assert.match(html,/공지 주요 내용/);assert.match(html,/응모 기간/);assert.match(html,/공식 원문 우선/);
});
test('content is escaped and unavailable details point to original',()=>{
 const html=vm.runInContext('archiveNoticeHighlights({contentHighlights:["<img src=x onerror=1>"]})',ctx);
 assert.doesNotMatch(html,/<img/);assert.match(html,/&lt;img/);
 const missing=vm.runInContext('archiveNoticeHighlights({})',ctx);assert.match(missing,/공식 원문에서 확인/);
});
