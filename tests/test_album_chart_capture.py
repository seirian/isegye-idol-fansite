"""Lightweight Melon captures must recover missing hours without inventing ranks."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
import hashlib
from urllib.error import URLError
import json
import sys
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import album_chart_capture as producer
import album_capture_recovery as recover


AT = datetime(2026, 11, 18, 13, 50, tzinfo=timezone.utc)
HOUR = AT.replace(minute=0)
IDS = ['603813508' if rank == 12 else '603813507' if rank == 25 else str(600000000 + rank)
       for rank in range(1, 101)]


def document(kinds=None, at=AT, source_at=HOUR):
    kinds = kinds if kinds is not None else producer.KINDS
    return {'schemaVersion': 1, 'repository': producer.REPOSITORY, 'workflow': producer.WORKFLOW,
            'runId': 123, 'runAttempt': 2, 'checkedAt': at.isoformat(),
            'sourceType': producer.SOURCE_TYPE, 'status': 'complete' if len(kinds) == 2 else 'partial',
            'errors': {}, 'charts': {
                kind: {'source': recover.SOURCES[kind], 'sourceAt': source_at.isoformat(),
                       'responseSha256': 'a' * 64,
                       'rows': [[sid, rank] for rank, sid in enumerate(IDS, 1)]}
                for kind in kinds}}


def zipped(data):
    buf = BytesIO()
    with zipfile.ZipFile(buf, 'w') as z:
        z.writestr('melon-chart-capture.json', json.dumps(data))
    raw = buf.getvalue()
    return raw, 'sha256:' + hashlib.sha256(raw).hexdigest()


def current():
    return {'domesticCharts': {}, 'tracks': {
        'rebels': {'melon': {'trackId': '603813508', 'albumId': '15120216'}, 'charts': {}},
        'another': {'melon': {'trackId': '999999', 'albumId': '15120216'}, 'charts': {}}}}


class CaptureReliability(unittest.TestCase):
    def test_producer_only_accepts_current_full_hour(self):
        ranking = {song: idx for idx, song in enumerate(IDS, 1)}
        with patch.object(producer, 'chart_rows', return_value=(ranking, HOUR.isoformat())):
            result = producer.capture(at=AT, reader=lambda url: b'public-chart',
                                      run_id=123, attempt=2)
        self.assertEqual(result['status'], 'complete')
        self.assertEqual(set(result['charts']), set(producer.KINDS))
        self.assertTrue(all(len(v['rows']) == 100 for v in result['charts'].values()))
        self.assertEqual(result['charts']['melon_top100']['responseSha256'],
                         hashlib.sha256(b'public-chart').hexdigest())
        old = HOUR - timedelta(hours=1)
        with patch.object(producer, 'chart_rows', return_value=(ranking, old.isoformat())):
            stale = producer.capture(at=AT, reader=lambda url: b'public-chart')
        self.assertEqual(stale['status'], 'failed')
        self.assertEqual(set(stale['errors']), set(producer.KINDS))
        self.assertFalse(stale['charts'])

    def test_producer_partial_chart_is_distinguished_from_complete(self):
        ranking = {song: idx for idx, song in enumerate(IDS, 1)}
        def fetch(url):
            if 'hot100' in url:
                raise ConnectionError('source down')
            return b'public-chart'
        with patch.object(producer, 'chart_rows', return_value=(ranking, HOUR.isoformat())):
            result = producer.capture(at=AT, reader=fetch)
        self.assertEqual(result['status'], 'partial')
        self.assertIn('melon_hot100', result['errors'])
        self.assertEqual(set(result['charts']), {'melon_top100'})

    def test_transient_public_transport_retried_once_without_fake_data(self):
        ranking = {song: idx for idx, song in enumerate(IDS, 1)}
        attempts = {}
        def source(url, binary=False):
            attempts[url] = attempts.get(url, 0) + 1
            if 'hot100' in url and attempts[url] == 1:
                raise URLError(TimeoutError('transient'))
            return b'public-chart'
        with patch.object(producer, 'fetch', side_effect=source), \
             patch.object(producer, 'chart_rows', return_value=(ranking, HOUR.isoformat())), \
             patch.object(producer.time, 'sleep') as sleep:
            result = producer.capture(at=AT)
        self.assertEqual(result['status'], 'complete')
        self.assertEqual(attempts[producer.CHARTS['melon_hot100'][1]], 2)
        self.assertEqual(sleep.call_count, 1)
        self.assertFalse(result['errors'])

    def test_network_diagnostics_never_expose_internal_error_body(self):
        with patch.object(producer, 'fetch', side_effect=URLError('private diagnostic URL')), \
             patch.object(producer.time, 'sleep'):
            result = producer.capture(at=AT)
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(set(result['errorClasses'].values()), {'network'})
        self.assertNotIn('private diagnostic URL', json.dumps(result))

    def test_night_pause_cannot_produce_artificial_rank(self):
        paused = datetime(2026, 11, 18, 19, 15, tzinfo=timezone.utc)  # 04:15 KST
        with patch.object(producer, 'chart_rows') as parser:
            result = producer.capture(at=paused, reader=lambda _: b'ignored')
        parser.assert_not_called()
        self.assertEqual(result['status'], 'scheduled_night_pause')

    def test_archive_needs_exact_zip_hash_run_attempt_and_full_chart(self):
        raw, digest = zipped(document())
        parsed = recover.read_capture(raw, digest, 123, 2, AT)
        self.assertEqual(parsed['charts']['melon_top100']['rows'][11], ['603813508', 12])
        for invalid in [digest.replace('a', 'b'), 'sha256:' + '0' * 64]:
            with self.assertRaises(ValueError):
                recover.read_capture(raw, invalid, 123, 2, AT)
        with self.assertRaises(ValueError):
            recover.read_capture(raw, digest, 123, 1, AT)
        with self.assertRaises(ValueError):
            recover.read_capture(raw, digest, 999, 2, AT)

    def test_unverified_chart_out_and_unavailable_night_refused(self):
        bad = document()
        bad['charts']['melon_top100']['rows'].pop()
        raw, digest = zipped(bad)
        with self.assertRaises(ValueError):
            recover.read_capture(raw, digest, 123, 2, AT)
        bad = document()
        bad['charts']['melon_top100']['sourceAt'] = (HOUR-timedelta(hours=1)).isoformat()
        raw, digest = zipped(bad)
        with self.assertRaises(ValueError):
            recover.read_capture(raw, digest, 123, 2, AT)
        night_at = datetime(2026, 11, 18, 18, tzinfo=timezone.utc)  # 03 KST
        bad = document(at=night_at+timedelta(minutes=20), source_at=night_at)
        raw, digest = zipped(bad)
        with self.assertRaises(ValueError):
            recover.read_capture(raw, digest, 123, 2, night_at+timedelta(minutes=30))

    def test_capture_merges_ranked_and_proven_out_without_overwrite(self):
        source = current()
        row = document()
        added, conflicts = recover.add_capture(source, row, AT)
        self.assertEqual((added, conflicts), (4, 0))
        self.assertEqual(source['tracks']['rebels']['charts']['melon_top100'][0]['rank'], 12)
        self.assertEqual(source['tracks']['another']['charts']['melon_hot100'][0]['status'], 'out')
        self.assertEqual(recover.add_capture(source, row, AT), (0, 0))
        row['charts']['melon_top100']['rows'][11][1] = 11
        self.assertEqual(recover.add_capture(source, row, AT), (0, 1))
        self.assertEqual(source['tracks']['rebels']['charts']['melon_top100'][0]['rank'], 12)

    def test_authenticated_main_only_artifact_provenance_and_hash(self):
        data = document()
        raw, digest = zipped(data)
        artifact = {'id': 555, 'name': recover.ARTIFACT, 'created_at': (HOUR+timedelta(minutes=12)).isoformat(),
                    'expired': False, 'size_in_bytes': len(raw), 'digest': digest,
                    'workflow_run': {'id': 123, 'head_sha': 'a'*40}}
        good_run = {'id': 123, 'head_branch': 'main', 'path': recover.WORKFLOW,
                    'event': 'schedule', 'status': 'completed', 'run_attempt': 2,
                    'head_sha': 'a'*40, 'repository': {'full_name': recover.REPO}}
        def reader(url, token, binary=False):
            if 'artifacts?per_page=' in url:
                return {'artifacts': [artifact], 'total_count': 1}
            if '/actions/runs/' in url:
                return good_run
            if url.endswith('/zip') and binary:
                return raw
            raise ValueError('Unexpected endpoint')
        report = {'addedPoints': 0, 'conflicts': 0, 'artifacts': [], 'errors': []}
        source = current()
        recover.recover(source, report, 'synthetic-token', time_budget(), reader, AT)
        self.assertEqual(report['addedPoints'], 4)
        self.assertEqual(report['errors'], [])
        self.assertEqual(report['artifacts'][0]['sourceType'], recover.SOURCE_TYPE)
        source = current()
        forged = {**good_run, 'head_branch': 'fork'}
        def reader_forged(url, token, binary=False):
            if '/actions/runs/' in url:
                return forged
            return reader(url, token, binary)
        report = {'addedPoints': 0, 'conflicts': 0, 'artifacts': [], 'errors': []}
        recover.recover(source, report, 'synthetic-token', time_budget(), reader_forged, AT)
        self.assertEqual(report['addedPoints'], 0)
        self.assertEqual(report['errors'][0]['error'], 'ValueError')

    def test_new_workflow_isolated_from_production_publish(self):
        workflow = (ROOT / '.github/workflows/melon-chart-capture.yml').read_text()
        self.assertIn('11,37 0-15,22-23 * * *', workflow)
        self.assertIn('group: isegye-melon-capture', workflow)
        self.assertNotIn('group: isegye-inour-production', workflow)
        self.assertNotIn('ISEGYE_SFTP_PASSWORD', workflow)
        self.assertIn('if: always()', workflow)
        self.assertIn('name: melon-chart-capture-${{ github.run_id }}-${{ github.run_attempt }}', workflow)
        self.assertNotIn('overwrite:', workflow)
        current_workflow = (ROOT / '.github/workflows/albums-daily.yml').read_text()
        self.assertIn('scripts/album_observation_archive.py', current_workflow)
        self.assertIn('steps.due.outputs.needed', current_workflow)

    def recovery_fixture(self, values, mutate_run=None, *, incomplete_listing=False, mutate_inventory=None):
        artifacts, archives, calls = [], {}, []
        for aid, name, data in values:
            raw, digest = zipped(data)
            artifacts.append({'id': aid, 'name': name, 'created_at': data['checkedAt'],
                'expired': False, 'size_in_bytes': len(raw), 'digest': digest,
                'workflow_run': {'id': data['runId'], 'head_sha': 'a'*40}})
            archives[aid] = raw
        def reader(url, token, binary=False):
            calls.append(url)
            if '/actions/runs/' in url and '/artifacts?' in url:
                result = {'artifacts': artifacts, 'total_count': len(artifacts)}
                return mutate_inventory(result) if mutate_inventory else result
            if 'artifacts?per_page=' in url:
                if incomplete_listing:
                    page = int(url.rsplit('=', 1)[1])
                    rows = [{'id': 10000+page*100+i, 'name': 'unrelated'} for i in range(100)]
                    if page == 1:
                        rows[:len(artifacts)] = artifacts
                    return {'artifacts': rows, 'total_count': 2000}
                return {'artifacts': artifacts, 'total_count': len(artifacts)}
            if '/actions/runs/' in url:
                run_id, attempt = int(url.split('/runs/')[1].split('/')[0]), int(url.rsplit('/', 1)[1])
                run = {'id': run_id, 'run_attempt': attempt, 'head_branch': 'main', 'path': recover.WORKFLOW,
                    'event': 'schedule', 'status': 'completed', 'head_sha': 'a'*40,
                    'repository': {'full_name': recover.REPO}}
                return mutate_run(run) if mutate_run else run
            if url.endswith('/zip') and binary:
                return archives[int(url.split('/artifacts/')[1].split('/')[0])]
            raise ValueError('Unexpected endpoint')
        report = {'addedPoints': 0, 'conflicts': 0, 'artifacts': [], 'errors': []}
        source = current()
        recover.recover(source, report, 'synthetic-token', time_budget(), reader, AT)
        return source, report, calls

    def test_named_rerun_and_legacy_original_attempt_recover_both_original_hours(self):
        earlier = document(at=AT-timedelta(hours=1), source_at=HOUR-timedelta(hours=1))
        earlier['runAttempt'] = 1
        for name in (recover.ARTIFACT, recover.ARTIFACT+'-123-1'):
            with self.subTest(name=name):
                source, report, calls = self.recovery_fixture([(555, name, earlier),
                    (556, recover.ARTIFACT+'-123-2', document())])
                self.assertEqual(report['addedPoints'], 8)
                self.assertEqual(report['errors'], [])
                points = source['tracks']['rebels']['charts']['melon_top100']
                self.assertEqual([point['at'] for point in points],
                    [(HOUR-timedelta(hours=1)).isoformat(), HOUR.isoformat()])
                self.assertEqual({item['runAttempt'] for item in report['artifacts']}, {1, 2})
                self.assertIn(recover.API+'/actions/runs/123/attempts/1', calls)
                self.assertIn(recover.API+'/actions/runs/123/attempts/2', calls)

    def test_named_capture_preferred_to_legacy_same_attempt(self):
        source, report, calls = self.recovery_fixture([(555, recover.ARTIFACT, document()),
            (556, recover.ARTIFACT+'-123-2', document())])
        self.assertEqual(report['addedPoints'], 4)
        self.assertEqual([item['id'] for item in report['artifacts']], [556])
        self.assertEqual(report['captureInspection']['pageBudget'], 12)
        self.assertTrue(report['captureInspection']['listingComplete'])

    def test_bad_named_capture_cannot_fall_back_to_same_attempt_legacy(self):
        malformed = document(); malformed['charts']['melon_top100']['rows'].pop()
        _, report, _ = self.recovery_fixture([(555, recover.ARTIFACT, document()),
            (556, recover.ARTIFACT+'-123-2', malformed)])
        self.assertEqual(report['addedPoints'], 0)
        self.assertTrue(report['errors'])
        self.assertEqual(report['skippedArtifacts'][0]['reason'], 'explicit_attempt_artifact_present')

    def test_duplicate_named_artifact_and_name_json_attempt_mismatch_refused(self):
        wrong_attempt = document(); wrong_attempt['runAttempt'] = 1
        variants = [[(555, recover.ARTIFACT+'-123-2', document()), (556, recover.ARTIFACT+'-123-2', document())],
                    [(555, recover.ARTIFACT+'-123-2', wrong_attempt)],
                    [(555, recover.ARTIFACT+'-999-2', document())]]
        for values in variants:
            with self.subTest(values=[item[:2] for item in values]):
                _, report, _ = self.recovery_fixture(values)
                self.assertEqual(report['addedPoints'], 0)
                self.assertTrue(report['errors'])

    def test_attempt_api_must_match_the_explicit_attempt(self):
        _, report, _ = self.recovery_fixture([(555, recover.ARTIFACT+'-123-2', document())],
                                            mutate_run=lambda run: dict(run, run_attempt=1))
        self.assertEqual(report['addedPoints'], 0)
        self.assertTrue(report['errors'])

    def test_repository_listing_budget_reports_incomplete_gaps(self):
        calls = []
        def reader(url, token, binary=False):
            calls.append(url)
            page = int(url.rsplit('=', 1)[1])
            return {'total_count': 2000, 'artifacts': [{'id': page*100+i+1, 'name': 'unrelated'} for i in range(100)]}
        report = {'addedPoints': 0, 'conflicts': 0, 'artifacts': [], 'errors': []}
        recover.recover(current(), report, 'synthetic-token', time_budget(), reader, AT)
        self.assertEqual(len(calls), 12)
        self.assertEqual(report['captureInspection']['apiCalls'], 12)
        self.assertEqual(report['captureInspection']['artifactsSeen'], 1200)
        self.assertEqual(report['captureInspection']['listingScope'], 'repository_artifacts')
        self.assertFalse(report['captureInspection']['listingComplete'])
        self.assertTrue(any(item['error'] == 'CaptureListingIncomplete' for item in report['errors']))
        self.assertTrue(any(report['captureMissingAfter'].values()))

    def test_incomplete_global_listing_only_merges_run_verified_subset_and_caches_inventory(self):
        earlier = document(at=AT-timedelta(hours=1), source_at=HOUR-timedelta(hours=1))
        earlier['runAttempt'] = 1
        source, report, calls = self.recovery_fixture([(555, recover.ARTIFACT, earlier),
            (556, recover.ARTIFACT+'-123-2', document())], incomplete_listing=True)
        self.assertEqual(report['addedPoints'], 8)
        self.assertFalse(report['captureInspection']['listingComplete'])
        self.assertEqual(report['captureInspection']['runArtifactQueries'], 1)
        self.assertEqual(sum('/actions/runs/123/artifacts?' in url for url in calls), 1)
        self.assertEqual(report['errors'][0]['error'], 'CaptureListingIncomplete')
        self.assertTrue(any(report['captureMissingAfter'].values()))
        self.assertEqual(source['tracks']['rebels']['charts']['melon_top100'][0]['at'],
                         (HOUR-timedelta(hours=1)).isoformat())

    def test_incomplete_global_listing_cannot_hide_new_duplicate_or_unverified_run_artifacts(self):
        def more(row, *, name):
            return {'total_count': 2, 'artifacts': row['artifacts'] +
                    [dict(row['artifacts'][0], id=999, name=name, digest='sha256:'+'0'*64)]}
        variants = [lambda row: dict(row, total_count=2000),
                    lambda row: more(row, name=recover.ARTIFACT),
                    lambda row: more(row, name=recover.ARTIFACT+'-123-2')]
        for mutate in variants:
            with self.subTest(mutate=mutate):
                _, report, _ = self.recovery_fixture([(555, recover.ARTIFACT, document())],
                    incomplete_listing=True, mutate_inventory=mutate)
                self.assertEqual(report['addedPoints'], 0)
                self.assertTrue(any(report['captureMissingAfter'].values()))
                reasons = [item.get('reason') for item in report['errors'] + report.get('skippedArtifacts', [])]
                self.assertTrue(set(reasons) & {'capture_run_artifact_listing_unverified',
                    'capture_artifact_name_ambiguous', 'explicit_attempt_artifact_present'})


def time_budget():
    import time
    return time.monotonic() + 90


if __name__ == '__main__':
    unittest.main()
