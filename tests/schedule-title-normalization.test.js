import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import {
  scheduleValidate, scheduleCafeEvidence, scheduleCafeMatches, scheduleApprovedRows
} from '../schedule/core.js';

const fixture = JSON.parse(readFileSync(new URL('./fixtures/cafe-title-regression.json', import.meta.url), 'utf8'));

function snapshot(title) {
  const proof = { ...fixture.notice, title, checkedAt: fixture.checkedAt };
  const row = {
    id: 'title-regression-' + proof.articleId, sourceId: 'cafe-members',
    sourceUrl: 'https://cafe.naver.com/steamindiegame/' + proof.articleId,
    title, members: proof.members, publishedAt: proof.publishedAt, checkedAt: proof.checkedAt
  };
  return {
    schemaVersion: 1, timezone: 'Asia/Seoul', generatedAt: fixture.generatedAt,
    sources: ['cafe-members', 'cafe-agency', 'fan-roundup', 'parable-web', 'naver-search'].map(id => ({ id })),
    news: [row], events: [], forecasts: [],
    cafeEvidence: { schemaVersion: 1, notices: [proof], fanSeries: [] }
  };
}

test('canonical public-title fixtures pass existing browser validation and exact proof matching', () => {
  for (const { name, expected } of fixture.titleCases) {
    const data = snapshot(expected);
    assert.ok(expected.length <= 220, name);
    assert.equal(scheduleValidate(data), data, name);
    assert.equal(scheduleCafeMatches(data.news[0], scheduleCafeEvidence(data)), true, name);
    assert.deepEqual(scheduleApprovedRows(data.news, new Map(), data), data.news, name);
    const changed = { ...data.news[0], title: expected + ' changed' };
    assert.equal(scheduleCafeMatches(changed, scheduleCafeEvidence(data)), false, name);
  }
});

test('raw angle punctuation, markup and nonwhitespace controls remain rejected', () => {
  for (const title of [fixture.notice.title, '<script>test</script>', 'notice' + String.fromCharCode(0)]) {
    assert.throws(() => scheduleValidate(snapshot(title)), /invalid Cafe metadata/);
  }
});

test('title normalization does not permit changed authors, boards or observation times', () => {
  for (const change of [
    { author: 'ine' }, { verifiedRole: 'member' }, { public: false }, { menuId: 999 },
    { checkedAt: '2030-01-01T00:00:00Z' }, { publishedAt: '2030-01-01T00:00:00Z' }
  ]) {
    const data = snapshot(fixture.titleCases[0].expected);
    Object.assign(data.cafeEvidence.notices[0], change);
    assert.throws(() => scheduleValidate(data));
  }
});

