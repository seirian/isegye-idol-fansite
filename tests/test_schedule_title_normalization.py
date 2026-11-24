"""Real failed public-title regression; no network or production credentials."""
import copy
from datetime import datetime, timedelta
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import cafe_runtime as runtime
from cafe_title import normalize_reviewed_title
import notice_policy
import review_cafe_window as reviewer
import schedule_feed as feed

FIXTURE = json.loads((ROOT / 'tests/fixtures/cafe-title-regression.json').read_text())
NOW = FIXTURE['generatedAt']
CHECKED = FIXTURE['checkedAt']
UNTIL = datetime.fromisoformat(CHECKED)
LO = datetime.fromisoformat(FIXTURE['from'] + 'T00:00:00+09:00')


def upstream(title=None):
    original = FIXTURE['notice']
    return {
        'cafeId': 27842958, 'menuId': 345, 'articleId': original['articleId'],
        'openArticle': True, 'restrictMenu': False,
        'writerInfo': {'nickName': '고세구', 'staff': True},
        'subject': original['title'] if title is None else title,
        'writeDateTimestamp': round(datetime.fromisoformat(original['publishedAt']).timestamp() * 1000),
    }


def packet(row):
    return {
        'schemaVersion': 1, 'from': FIXTURE['from'], 'checkedAt': CHECKED,
        'boards': {'345': {'state': 'reviewed', 'count': 1, 'pages': 1},
                   '1250': {'state': 'reviewed', 'count': 0, 'pages': 1}},
        'notices': [row], 'fan': {},
    }


def evidence(row):
    return {'schemaVersion': 1, 'notices': [dict(row, checkedAt=CHECKED)], 'fanSeries': []}


def unavailable(_url, **_kwargs):
    raise feed.FeedError('fixture_unavailable')


class PublicTitleNormalization(unittest.TestCase):
    def test_real_failed_notice_preserves_provenance_and_publishes(self):
        reviewed = reviewer.approved(upstream(), 345, LO, UNTIL)
        self.assertEqual({k: v for k, v in reviewed.items() if k != 'title'},
                         {k: v for k, v in FIXTURE['notice'].items() if k != 'title'})
        self.assertEqual(reviewed['title'], '[고세구] 하이빵가루~! ＞ㅁ＜')
        result = feed.collect(fetch=unavailable, now=NOW, cafe_review=packet(reviewed))
        url = runtime.cb.PREFIX + str(reviewed['articleId'])
        published = next(row for row in result['news'] if row['sourceUrl'] == url)
        self.assertEqual(published['title'], reviewed['title'])
        self.assertTrue(runtime.matches(published, runtime.source_map(result['cafeEvidence'], NOW)))
        self.assertIn(published, notice_policy.clean_snapshot(result)['news'])
        again = feed.collect(previous=result, fetch=unavailable, now=NOW, cafe_review=packet(reviewed))
        self.assertEqual(sum(row['sourceUrl'] == url for row in again['news']), 1)

    def test_shared_title_cases_remain_identical_through_publication(self):
        for case in FIXTURE['titleCases']:
            with self.subTest(case=case['name']):
                reviewed = reviewer.approved(upstream(case['input']), 345, LO, UNTIL)
                title = reviewed['title']
                self.assertEqual(title, case['expected'])
                self.assertEqual(normalize_reviewed_title(title), title)
                self.assertEqual(feed.text(title), title)
                self.assertLessEqual(len(title.encode('utf-16-le')) // 2, 220)
                runtime.validate_packet(packet(reviewed), NOW)
                proof = evidence(reviewed)
                runtime.validate_evidence(proof, NOW)
                published = feed.public_item('cafe-members', runtime.cb.PREFIX + str(reviewed['articleId']),
                                             title, reviewed['publishedAt'], CHECKED,
                                             members=reviewed['members'])
                self.assertEqual(published['title'], title)
                self.assertTrue(runtime.matches(published, runtime.source_map(proof, NOW)))

    def test_raw_failed_packet_is_rejected_before_publication(self):
        with self.assertRaises(runtime.CafeEvidenceError) as raised:
            runtime.validate_packet(packet(copy.deepcopy(FIXTURE['notice'])), NOW)
        err = raised.exception
        self.assertIsInstance(err, ValueError)
        self.assertEqual((err.code, err.field, err.articleId, err.sourceId),
                         ('invalid_cafe_title', 'title', 22233393, 'cafe-members'))
        self.assertNotIn(FIXTURE['notice']['title'], str(err))

    def test_nonwhitespace_controls_are_not_silently_removed(self):
        for title in ('공지' + chr(0) + '본문', '공지' + chr(27) + '본문', '공지&#0;본문', '공지&#x1B;본문',
                      '공지&amp;#1;본문'):
            with self.subTest(title=repr(title)):
                with self.assertRaisesRegex(ValueError, '^invalid_public_title_control$'):
                    reviewer.approved(upstream(title), 345, LO, UNTIL)

    def test_raw_unsafe_evidence_is_not_repaired(self):
        for title in ('<script>test</script>', '공지' + chr(0) + '본문'):
            row = dict(FIXTURE['notice'], title=title)
            with self.subTest(title=repr(title)):
                with self.assertRaises(runtime.CafeEvidenceError):
                    runtime.validate_packet(packet(row), NOW)
                with self.assertRaises(runtime.CafeEvidenceError):
                    runtime.validate_evidence(evidence(row), NOW)

    def test_approval_and_observation_guards_remain_required(self):
        changes = [
            {'writerInfo': {'nickName': '일반 이용자', 'staff': True}},
            {'writerInfo': {'nickName': '고세구', 'staff': False}},
            {'openArticle': False}, {'restrictMenu': True}, {'menuId': 1250},
            {'cafeId': 1},
            {'writeDateTimestamp': round((UNTIL + timedelta(seconds=1)).timestamp() * 1000)},
            {'writeDateTimestamp': round((LO - timedelta(seconds=1)).timestamp() * 1000)},
        ]
        for change in changes:
            with self.subTest(change=change):
                raw = upstream(); raw.update(change)
                self.assertIsNone(reviewer.approved(raw, 345, LO, UNTIL))
        row = reviewer.approved(upstream(), 345, LO, UNTIL)
        for change in ({'author': 'ine'}, {'verifiedRole': 'member'}, {'public': False},
                       {'menuId': 1}, {'members': ['ine']}):
            with self.subTest(change=change):
                altered = dict(row, **change)
                with self.assertRaises(ValueError):
                    runtime.validate_packet(packet(altered), NOW)


class EvidenceDiagnostics(unittest.TestCase):
    def test_bad_title_diagnostic_never_echoes_raw_text(self):
        row = dict(FIXTURE['notice'], title='<secret-upstream-value>')
        with self.assertRaises(runtime.CafeEvidenceError) as raised:
            runtime.validate_evidence(evidence(row), NOW)
        self.assertEqual(str(raised.exception), 'invalid_cafe_title')
        self.assertEqual(raised.exception.field, 'title')

    def test_timestamp_parse_and_order_have_safe_field_codes(self):
        base = evidence(reviewer.approved(upstream(), 345, LO, UNTIL))
        cases = [
            ('checkedAt', 'secret-upstream-value', 'invalid_cafe_timestamp'),
            ('publishedAt', None, 'invalid_cafe_timestamp'),
            ('publishedAt', '2030-01-01T00:00:00Z', 'invalid_cafe_observation'),
            ('checkedAt', '2030-01-01T00:00:00Z', 'invalid_cafe_observation'),
        ]
        for field, value, code in cases:
            with self.subTest(field=field, code=code):
                proof = copy.deepcopy(base); proof['notices'][0][field] = value
                with self.assertRaises(runtime.CafeEvidenceError) as raised:
                    runtime.validate_evidence(proof, NOW)
                err = raised.exception
                self.assertEqual((err.code, err.field, err.articleId, err.sourceId),
                                 (code, field, 22233393, 'cafe-members'))
                self.assertNotIn('secret-upstream-value', str(err))

    def test_diagnostic_metadata_cannot_supply_arbitrary_fields(self):
        for item in ({'articleId': True, 'menuId': '345'},
                     {'articleId': -1, 'menuId': 999},
                     {'articleId': 'secret-value', 'menuId': 'secret-value'}):
            err = runtime.CafeEvidenceError('invalid_cafe_title', 'title', item)
            self.assertIsNone(err.articleId); self.assertIsNone(err.sourceId)
        for code, field in (('arbitrary', 'title'), ('invalid_cafe_title', 'body')):
            with self.assertRaisesRegex(ValueError, '^invalid cafe evidence diagnostic$'):
                runtime.CafeEvidenceError(code, field, {})


if __name__ == '__main__':
    unittest.main()

