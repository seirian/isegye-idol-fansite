"""Lightweight Melon captures must recover missing hours without inventing ranks."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
import hashlib
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
            if 'artifacts?name=' in url:
                return {'artifacts': [artifact]}
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
        current_workflow = (ROOT / '.github/workflows/albums-daily.yml').read_text()
        self.assertIn('scripts/album_observation_archive.py', current_workflow)
        self.assertIn('steps.due.outputs.needed', current_workflow)


def time_budget():
    import time
    return time.monotonic() + 90


if __name__ == '__main__':
    unittest.main()
