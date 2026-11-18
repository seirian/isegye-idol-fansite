"""Historical date evidence stays bound to exact current Guyso peak ranks."""
from copy import deepcopy
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch
import hashlib
import json
import sys
import tempfile
import unittest
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import collect_album_peak_dates as dates
import collect_album_peak_fallback as peaks


def fixture():
    entry = deepcopy(peaks.reviewed_records()['kidding'])
    melon, summary = entry['identity'], entry['reference']
    melon['state'] = 'ok'
    for key in summary['records']:
        if key != 'top100':
            summary['records'][key]['rank'] = None
    row = {'rank': 6, 'date': '2023-08-20', 'observedAt': '2023-08-20T00:00:00+09:00',
        'source': dates.source_url(melon['trackId'], 'top100')+'?end=2023-08-21',
        'checkedAt': datetime.now(timezone.utc).isoformat(), 'responseSha256': 'a'*64,
        'rangeStart': '2023-08-01T00:00:00+09:00', 'rangeEnd': '2023-08-21T23:00:00+09:00',
        'basis': dates.BASIS, 'timeUnit': 'HOURS'}
    value = dates.envelope(melon, {'top100': row})
    return melon, summary, value


class PeakDateTests(unittest.TestCase):
    def setUp(self):
        self.melon, self.summary, self.value = fixture()

    def page(self, key='top100'):
        return {'props': {'pageProps': {'song': {'platform': 'melon', 'id': self.melon['trackId'],
            'name': self.melon['title'], 'album': {'id': self.melon['albumId'], 'platform': 'melon'},
            'artists': [{'name': self.melon['artist']}], 'lyrics': 'NEVER_EXPORT_LYRICS'},
            'data': {'platform': 'melon', 'songId': self.melon['trackId'], 'chart': dates.CHART_ENUMS[key],
                'timeUnit': 'DAYS' if key == 'daily' else 'HOURS', 'data': [
                    {'ranking': 7, 'time': '2023-08-19T23:00:00'},
                    {'ranking': 6, 'time': '2023-08-20T01:00:00'},
                    {'ranking': 6, 'time': '2023-08-20T00:00:00'}]}}}}

    def parse(self, page=None, key='top100'):
        raw = '<script id="__NEXT_DATA__">'+json.dumps(page or self.page(key))+'</script>'
        return dates.parse_trend(raw, self.melon, key, 6, dates.source_url(self.melon['trackId'], key), datetime.now(timezone.utc).isoformat())

    def test_earliest_matching_rank_and_real_time_not_summary_timestamp(self):
        row = self.parse()
        self.assertEqual(row['date'], '2023-08-20')
        self.assertEqual(row['observedAt'], '2023-08-20T00:00:00+09:00')
        self.assertEqual(row['rangeStart'], '2023-08-19T23:00:00+09:00')
        self.assertNotIn('NEVER_EXPORT', json.dumps(row))
        self.assertEqual(len(row['responseSha256']), 64)

    def test_mismatched_track_album_title_artist_and_chart_refused(self):
        for target, field, value in [('song', 'id', '1'), ('song', 'name', 'Other title'),
                ('data', 'songId', '1'), ('data', 'chart', 'MELON_REALTIME_CHART'), ('data', 'timeUnit', 'DAYS')]:
            page = self.page(); page['props']['pageProps'][target][field] = value
            with self.assertRaises(ValueError): self.parse(page)
        for field, value in [('album', {'id': '1', 'platform': 'melon'}), ('artists', [{'name': 'Other artist'}])]:
            page = self.page(); page['props']['pageProps']['song'][field] = value
            with self.assertRaises(ValueError): self.parse(page)

    def test_duplicate_conflict_or_invalid_rank_refused(self):
        for point in ({'ranking': 0, 'time': '2023-08-20T00:00:00'}, {'ranking': 7, 'time': '2023-08-20T00:00:00'}):
            page = self.page(); page['props']['pageProps']['data']['data'].append(point)
            with self.assertRaises(ValueError): self.parse(page)

    def test_extended_realtime_points_do_not_invalidate_matching_peak(self):
        page = self.page('realtime')
        page['props']['pageProps']['data']['data'][0]['ranking'] = 250
        self.assertEqual(self.parse(page, 'realtime')['rank'], 6)

    def test_no_matching_rank_has_no_date(self):
        page = self.page()
        for point in page['props']['pageProps']['data']['data']: point['ranking'] = 7
        self.assertIsNone(self.parse(page))

    def test_exact_identity_rank_and_chart_source_binding(self):
        self.assertEqual(len(dates.verified_records(self.value, self.melon, self.summary)), 1)
        for update in ({'trackId': '1'}, {'albumId': '1'}, {'sourceType': 'isegyechart_observed_peaks'}):
            self.assertFalse(dates.verified_records({**self.value, **update}, self.melon, self.summary))
        changed = deepcopy(self.summary); changed['records']['top100']['rank'] = 5
        self.assertFalse(dates.verified_records(self.value, self.melon, changed))
        wrong = deepcopy(self.value); wrong['records']['top100']['source'] = dates.source_url(self.melon['trackId'], 'realtime')
        self.assertFalse(dates.verified_records(wrong, self.melon, self.summary))

    def test_bad_dates_coverage_units_and_provenance_rejected_individually(self):
        row = self.value['records']['top100']
        for update in ({'date': '2023-02-30'}, {'date': '2023-08-19'}, {'observedAt': '2023-08-20T00:00:00'},
                {'checkedAt': '2099-01-01T00:00:00Z'}, {'rangeStart': '2023-08-21T00:00:00+09:00'},
                {'rangeEnd': '2023-08-19T00:00:00+09:00'}, {'basis': 'first_ever'}, {'timeUnit': 'DAYS'},
                {'responseSha256': ''}, {'rank': True}):
            self.assertFalse(dates.record_ok({**row, **update}, self.melon, 'top100', 6), update)

    def test_daily_has_midnight_day_precision(self):
        row = {**self.value['records']['top100'], 'source': dates.source_url(self.melon['trackId'], 'daily'), 'timeUnit': 'DAYS'}
        self.assertTrue(dates.record_ok(row, self.melon, 'daily', 6))
        self.assertFalse(dates.record_ok({**row, 'observedAt': '2023-08-20T01:00:00+09:00'}, self.melon, 'daily', 6))

    def test_allowlist_is_chart_song_and_bounded_query_only(self):
        from collect_album_records import allowed
        base = dates.source_url(self.melon['trackId'], 'top100')
        self.assertEqual(allowed(base+'?end=2023-08-21'), base+'?end=2023-08-21')
        for url in (base+'?end=2023-02-30', base+'?x=1', base+'?end=2023-08-21&end=2023-08-22',
                    base+'#x', base.replace('https:', 'http:'), base.replace('.com/', '.com.evil.test/'),
                    base.replace('https://', 'https://u:p@')):
            self.assertFalse(dates.allowed_source(url))
            with self.assertRaises(ValueError): allowed(url)

    def data(self, dates_value=None):
        item = {'melon': deepcopy(self.melon), 'melonPeakFallback': deepcopy(self.summary), 'charts': {'sentinel': [1]}}
        if dates_value is not None: item['melonPeakDates'] = dates_value
        return {'tracks': {'kidding': item}}

    def test_existing_dates_preserved_without_refetch_or_clock_changes(self):
        previous = self.data(deepcopy(self.value)); result = self.data(); before = deepcopy(result)
        with patch.object(dates, 'reviewed_records', return_value={}):
            report = dates.collect_peak_dates(result, previous, lambda url: self.fail('Verified date must not refetch'))
        self.assertEqual(report['requested'], 0)
        self.assertEqual(result['tracks']['kidding']['melonPeakDates'], self.value)
        result['tracks']['kidding'].pop('melonPeakDates')
        self.assertEqual(result, before)

    def test_new_peak_invalidates_old_date_fetches_latest_and_caches_failure(self):
        previous = self.data(deepcopy(self.value)); result = self.data()
        result['tracks']['kidding']['melonPeakFallback']['records']['top100']['rank'] = 5
        with patch.object(dates, 'reviewed_records', return_value={}):
            first = dates.collect_peak_dates(result, previous, lambda _: (_ for _ in ()).throw(TimeoutError()))
            second = self.data(); second['tracks']['kidding']['melonPeakFallback']['records']['top100']['rank'] = 5
            report = dates.collect_peak_dates(second, result, lambda _: self.fail('Failed same-rank date query retries after 24h'))
        self.assertEqual(first['requested'], 1); self.assertEqual(report['requested'], 0)
        self.assertFalse(second['tracks']['kidding']['melonPeakDates']['records'])

    def test_missing_dates_bounded_global_fetch_budget(self):
        result = {'tracks': {str(i): deepcopy(self.data()['tracks']['kidding']) for i in range(30)}}
        with patch.object(dates, 'reviewed_records', return_value={}):
            report = dates.collect_peak_dates(result, {}, lambda _: (_ for _ in ()).throw(TimeoutError()))
        self.assertEqual(report['requested'], dates.MAX_FETCHES)
        self.assertEqual(len(report['missing']), 30)

    def test_offline_application_touches_only_date_field(self):
        data = self.data(); before = deepcopy(data)
        with patch.object(dates, 'reviewed_records', return_value={'kidding': self.value}):
            report = dates.apply_reviewed(data, strict=True)
        self.assertEqual(report['datedRankCount'], 1)
        data['tracks']['kidding'].pop('melonPeakDates')
        self.assertEqual(data, before)

    def test_publication_boundary_rejects_mismatched_date_evidence(self):
        import daily_albums
        data = {'schemaVersion': 1, 'generatedAt': datetime.now(timezone.utc).isoformat(),
            'providers': {}, **self.data(deepcopy(self.value))}
        daily_albums.validate(data)
        data['tracks']['kidding']['melonPeakDates']['records']['top100']['rank'] = 5
        with self.assertRaisesRegex(ValueError, 'peak-date evidence'): daily_albums.validate(data)

    def test_static_old_seed_gains_all_registered_peak_dates_without_api_claims(self):
        from prepare_album_release import apply_reference_seed
        source = ROOT/'albums/release-seed/snapshot.json'
        raw = source.read_bytes(); data = json.loads(raw); before = deepcopy(data)
        apply_reference_seed(data)
        self.assertEqual(len(data['tracks']), 26)
        self.assertEqual(sum(bool(item.get('melonPeakDates')) for item in data['tracks'].values()), 24)
        self.assertEqual(sum(len(item.get('melonPeakDates', {}).get('records', {})) for item in data['tracks'].values()), 164)
        self.assertEqual(data['generatedAt'], before['generatedAt'])
        added = set(data['tracks'])-set(before['tracks'])
        self.assertEqual(added, {'love-cells', 'rebels', 'back-2-the-future', 'anti-hero', 'dream-residue'})
        for sid in added:
            item = data['tracks'][sid]
            self.assertEqual(set(item), {'melon', 'melonPeakFallback', 'melonPeakDates'})
            self.assertEqual(set(item['melon']), {'trackId', 'albumId', 'state'})
            self.assertEqual(item['melon']['state'], 'reference_only')
        for sid, prior in before['tracks'].items():
            current = deepcopy(data['tracks'][sid]); prior = deepcopy(prior)
            for key in ('melonPeakFallback', 'melonPeakDates'):
                current.pop(key, None); prior.pop(key, None)
            self.assertEqual(current, prior)
        self.assertEqual(source.read_bytes(), raw)
        once = deepcopy(data); apply_reference_seed(data); self.assertEqual(data, once)

    def test_reviewed_dataset_digest_rejects_tampering(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'data.json'; path.write_text('{}')
            dates.reviewed_records.cache_clear()
            with patch.object(dates, 'REVIEW_PATH', path):
                with self.assertRaisesRegex(ValueError, 'dataset changed'): dates.reviewed_records()
        dates.reviewed_records.cache_clear()

    def test_reviewed_catalog_every_row_matches_current_pinned_summary(self):
        reviewed = dates.reviewed_records(); summaries = peaks.reviewed_records()
        self.assertEqual(set(reviewed), set(summaries))
        self.assertEqual(sum(len(row['records']) for row in reviewed.values()), 164)
        for sid, value in reviewed.items():
            valid = dates.verified_records(value, summaries[sid]['identity'], summaries[sid]['reference'])
            self.assertEqual(len(valid), len(value['records']), sid)
            self.assertGreaterEqual(len(valid), 5, sid)


if __name__ == '__main__': unittest.main()
