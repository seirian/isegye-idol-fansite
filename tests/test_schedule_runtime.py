"""Runtime source proof, bounded collection and freshness; no network or identities."""
import copy
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import cafe_runtime as runtime
import cafe_batch as cb
import notice_policy as policy
import schedule_feed as feed
import schedule_health as health
import publish_schedule_feed as pub
from test_schedule_feed import FeedRemote

NOW = '2026-11-04T10:00:00+00:00'
OBS = '2026-11-04T09:59:00+00:00'


def packet():
    return {'schemaVersion': 1, 'from': '2026-11-03', 'checkedAt': OBS,
            'boards': {'345': {'state': 'reviewed', 'count': 1, 'pages': 1},
                       '1250': {'state': 'reviewed', 'count': 0, 'pages': 1}},
            'notices': [{'articleId': 99911111, 'menuId': 345, 'author': 'ine', 'members': ['ine'],
                         'title': '[테스트 전용] 오늘 방송', 'publishedAt': '2026-11-03T15:01:00+00:00',
                         'verifiedRole': 'staff', 'public': True, 'titleGeneralized': False}],
            'fanSeries': [{'articleId': 99922222, 'title': '[11/4(수)] 이세돌 뱅온정보', 'date': '2026-11-04',
                          'publishedAt': '2026-11-04T07:00:00+09:00', 'sameBoard': True, 'sameAuthor': True, 'public': True}],
            'fanCheckedAt': OBS, 'cardCheckedAt': OBS,
            'fanCards': {'99922222': {'ine': {'status': 'unknown', 'time': None}}}, 'fanWindowComplete': False}


def collect(previous=None, value=None, now=NOW):
    return feed.collect(previous=previous, fetch=lambda u: (_ for _ in ()).throw(feed.FeedError('fixture')),
                        now=now, cafe_review=value)


class Runtime(unittest.TestCase):
    def test_backfill_three_november_third_notices(self):
        rows = json.loads((ROOT / 'schedule/cafe-batches/2026-11-04-recovery.json').read_text())['notices']
        third = [r for r in rows if cb.timestamp(r['publishedAt']).astimezone(cb.KST).date().isoformat() == '2026-11-03']
        self.assertEqual({r['author'] for r in third}, {'jingburger', 'viichan', 'lilpa'})
        self.assertEqual(len(third), 3)

    def test_new_verified_id_is_published_without_static_rebuild(self):
        value = collect(value=packet())
        row = next(r for r in value['news'] if r['sourceUrl'].endswith('/99911111'))
        self.assertFalse(policy.is_publishable(row))
        self.assertIn(row, policy.clean_snapshot(value)['news'])
        self.assertEqual(row['checkedAt'], OBS)
        event = next(r for r in value['events'] if r['sourceUrl'] == row['sourceUrl'])
        self.assertEqual(event['date'], '2026-11-04')
        self.assertIsNone(event['time'])
        self.assertEqual(next(s for s in value['sources'] if s['id'] == 'cafe-agency')['coverage']['count'], 0)

    def test_repeat_run_has_no_duplicate_articles(self):
        a = collect(value=packet()); b = collect(a, packet())
        for key in ('news', 'events', 'forecasts'):
            self.assertEqual(len(b[key]), len({r['id'] for r in b[key]}))
            self.assertEqual({r['id'] for r in a[key]}, {r['id'] for r in b[key]})
        self.assertEqual(len(b['cafeEvidence']['notices']), 1)

    def test_failed_review_preserves_original_observations(self):
        a = collect(value=packet()); failed = packet()
        failed.update(checkedAt=NOW, notices=[], fanSeries=[], fanCards={})
        failed['boards'] = {str(m): {'state': 'unverified'} for m in cb.IDS}
        b = collect(a, failed, now='2026-11-04T10:01:00+00:00')
        row = next(r for r in b['news'] if r['sourceUrl'].endswith('/99911111'))
        self.assertEqual(row['checkedAt'], OBS)
        state = next(s for s in b['sources'] if s['id'] == 'cafe-members')
        self.assertEqual(state['state'], 'error'); self.assertEqual(state['lastSuccessAt'], OBS)
        self.assertEqual(health.assess(b)['state'], 'partial')
        self.assertTrue(any(r['sourceUrl'].endswith('/99922222') for r in b['forecasts']))

    def test_missing_review_never_becomes_fresh_success(self):
        b = collect(collect(value=packet()))
        self.assertEqual(next(s for s in b['sources'] if s['id'] == 'cafe-members')['state'], 'error')
        self.assertEqual(health.assess(b)['state'], 'partial')

    def test_partial_board_success_is_not_all_source_success(self):
        value = packet(); value['boards']['1250'] = {'state': 'unverified'}
        result = collect(value=value)
        self.assertEqual(next(s for s in result['sources'] if s['id'] == 'cafe-members')['state'], 'ok')
        self.assertEqual(next(s for s in result['sources'] if s['id'] == 'cafe-agency')['state'], 'error')

    def test_unverified_search_and_false_source_rows_remain_blocked(self):
        value = collect(value=packet())
        original = next(r for r in value['news'] if r['sourceUrl'].endswith('/99911111'))
        for changes in ({'sourceId': 'naver-search'}, {'title': 'changed title'}, {'members': ['gosegu']},
                        {'publishedAt': '2026-11-03T00:00:00Z'}, {'sourceUrl': cb.PREFIX + '99888888'}):
            fake = {**original, **changes, 'id': 'test-injection'}
            value['news'].append(fake)
            self.assertNotIn(fake, policy.clean_snapshot(value)['news']); value['news'].pop()

    def test_wrong_author_role_board_and_private_fields_rejected(self):
        for changes in ({'verifiedRole': 'member'}, {'menuId': 24}, {'author': 'gosegu'}, {'public': False},
                        {'body': 'private'}, {'title': '<script>test</script>'}):
            value = packet(); value['notices'][0].update(changes)
            with self.assertRaises(ValueError): collect(value=value)

    def test_excluded_article_stays_excluded(self):
        p = packet(); p['notices'][0]['articleId'] = 22133027
        with self.assertRaises(ValueError): collect(value=p)

    def test_future_observation_and_publication_rejected(self):
        for key in ('checkedAt', 'publishedAt'):
            data = collect(value=packet())['cafeEvidence']
            data['notices'][0][key] = '2030-01-01T00:00:00Z'
            with self.assertRaises(ValueError): runtime.validate_evidence(data, NOW)

    def test_duplicate_proof_and_extra_fields_rejected(self):
        a = collect(value=packet())['cafeEvidence']
        for mode in ('duplicate', 'extra', 'fan'):
            b = copy.deepcopy(a)
            if mode == 'duplicate': b['notices'].append(b['notices'][0])
            elif mode == 'extra': b['notices'][0]['token'] = 'must not persist'
            else: b['fanSeries'][0]['sameAuthor'] = False
            with self.assertRaises(ValueError): runtime.validate_evidence(b, NOW)

    def test_fan_cards_never_promoted_to_official(self):
        value = collect(value=packet())
        rows = [r for r in value['forecasts'] if r['sourceUrl'].endswith('/99922222')]
        self.assertEqual(len(rows), 1); self.assertEqual(rows[0]['certainty'], 'unknown')
        self.assertFalse(any(r['sourceId'] == 'fan-roundup' for r in value['events']))
        data = packet(); data['fanCards']['99922222']['ine']['status'] = 'confirmed'
        with self.assertRaises(ValueError): collect(value=data)

    def test_publication_and_backup_retain_valid_runtime_proof(self):
        remote = FeedRemote(); one = collect(value=packet())
        result = pub.publish(remote, lambda **kwargs: one)
        self.assertEqual(result['status'], 'published')
        self.assertEqual(result['runtimeEvidenceCounts']['notices'], 1)
        old = remote.files[pub.path('current.json')]
        def next_run(previous): return collect(previous, None, now='2026-11-04T10:01:00+00:00')
        pub.publish(remote, next_run)
        self.assertEqual(remote.files[pub.path('previous.json')], old)
        current = json.loads(remote.files[pub.path('current.json')])
        self.assertTrue(any(r['sourceUrl'].endswith('/99911111') for r in current['news']))
        self.assertTrue(all(p.startswith(pub.FOLDER + '/') for p in remote.writes))

    def test_changed_title_retires_old_extracted_schedule(self):
        a = collect(value=packet()); p = packet(); p['checkedAt'] = NOW
        p['notices'][0]['title'] = '[테스트 전용] 일정은 추후 공지'
        b = collect(a, p, now='2026-11-04T10:01:00+00:00')
        self.assertFalse(any(r['sourceUrl'].endswith('/99911111') for r in b['events']))

    def test_old_outage_gap_is_not_hidden_by_short_successful_window(self):
        old = collect(value=packet())
        for source in old['sources']:
            if source['id'] in cb.IDS.values(): source['lastSuccessAt'] = '2026-10-30T10:00:00Z'
        result = collect(old, packet())
        state = next(s for s in result['sources'] if s['id'] == 'cafe-members')
        self.assertEqual(state['coverage']['gapFromKst'], '2026-10-30')
        self.assertIn('uncovered_gap', health.assess(result)['sources']['cafe-members']['reasons'])
        next_value = collect(result, packet())
        self.assertIn('uncovered_gap', health.assess(next_value)['sources']['cafe-members']['reasons'])
        wide = packet(); wide['from'] = '2026-10-30'
        filled = collect(next_value, wide)
        self.assertNotIn('gapFromKst', next(s for s in filled['sources'] if s['id'] == 'cafe-members')['coverage'])

    def test_hourly_review_is_separate_from_credentials(self):
        text = (ROOT / '.github/workflows/schedule-refresh.yml').read_text()
        reviewer = text.split('- name: Verify approved Cafe')[1].split('- name: Collect permitted')[0]
        self.assertIn('refresh_reviewed_cafe.py', reviewer)
        self.assertNotIn('secrets.', reviewer)
        self.assertIn('ISEGYE_CAFE_REVIEW_PATH: cafe-window.json', text)
        self.assertIn('python scripts/schedule_health.py', text)


class Health(unittest.TestCase):
    def base(self):
        return {'generatedAt': NOW, 'sources': [{'id': sid, 'state': 'ok', 'lastSuccessAt': OBS,
                'lastAttemptAt': OBS, 'coverage': {'complete': True}} for sid in health.REQUIRED]}

    def test_all_required_sources_current(self):
        self.assertEqual(health.assess(self.base())['state'], 'complete')

    def test_snapshot_does_not_claim_completed_collection(self):
        data = self.base(); data['sources'][0]['state'] = 'snapshot'
        self.assertIn('cafe-members', health.assess(data)['incompleteSources'])

    def test_staleness_uses_source_observation_not_publication_time(self):
        data = self.base(); data['sources'][0]['lastSuccessAt'] = '2026-11-03T00:00:00Z'
        self.assertEqual(health.assess(data)['sources']['cafe-members']['state'], 'stale')

    def test_missing_future_and_invalid_time(self):
        for value in (None, '2030-01-01T00:00:00Z', 'invalid'):
            data = self.base(); data['sources'][0]['lastSuccessAt'] = value
            self.assertEqual(health.assess(data)['state'], 'partial')

    def test_incomplete_page_window_not_success(self):
        data = self.base(); data['sources'][0]['coverage']['complete'] = False
        self.assertEqual(health.assess(data)['state'], 'partial')

    def test_reference_scope_does_not_pretend_exhaustive_fan_history(self):
        data = self.base(); data['sources'][2]['coverage'] = {'complete': False, 'scope': 'same-author-series-references-only'}
        self.assertEqual(health.assess(data)['state'], 'complete')
        self.assertIn('not confirmed', health.assess(data)['scope'])

if __name__ == '__main__': unittest.main()
