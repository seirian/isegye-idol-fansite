"""Known backup warnings cannot cause repeated verified official publication."""
from datetime import datetime, timedelta, timezone
from contextlib import redirect_stdout
from pathlib import Path
import copy
import hashlib
import io
import json
import os
import sys
import tempfile
import unittest
import zipfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import batch_music_evidence as music
import batch_monitor_snapshot as monitor
import batch_slot_ledger as ledger
import batch_watchdog as watchdog
import check_music_video_sources as audit
import music_source_availability as availability
from music_video_sources import selections

AT = datetime(2026, 11, 27, 22, 30, tzinfo=timezone.utc)
SHA = 'a'*40


class MusicEvidence(unittest.TestCase):
    def setUp(self):
        self.context = {'repository': watchdog.REPO, 'commit': SHA, 'runId': '42', 'runAttempt': '2'}
        env = patch.dict(os.environ, {'GITHUB_REPOSITORY': watchdog.REPO, 'GITHUB_SHA': SHA,
            'GITHUB_RUN_ID': '42', 'GITHUB_RUN_ATTEMPT': '2', 'PRODUCTION_PAUSED': '',
            'ISEGYE_MUSIC_PAUSED': ''})
        env.start(); self.addCleanup(env.stop)
        self.run = {'id': 42, 'run_attempt': 2, 'head_sha': SHA, 'head_branch': 'main',
            'path': '.github/workflows/music-daily.yml', 'repository': {'full_name': watchdog.REPO},
            'head_repository': {'full_name': watchdog.REPO}, 'event': 'schedule',
            'status': 'completed', 'conclusion': 'failure', 'created_at': '2026-11-26T22:00:00Z',
            'run_started_at': '2026-11-27T22:00:00Z'}
        self.config, self.rows = selections()
        self.results = []
        for sid, row in self.rows.items():
            if not row['videoId']:
                continue
            result = {'songId': sid, **row, 'ok': True, 'stage': 'complete', 'metadataStatus': 200,
                'authorUrl': self.config['channels'][row['channelKey']]['url'],
                'thumbnailWidth': 480, 'thumbnailHeight': 360}
            if row['channelKey'] in ('c3', 'c6', 'c16'):
                result.update(ok=False, stage='metadata', metadataStatus=404, reasonCode='metadata_http_404')
            self.results.append(result)
        self.pub = {'status': 'published', 'evidenceVersion': 2, 'publicationAction': 'written',
            'verifiedReadback': True, 'sourceAt': None, 'generatedAt': '2026-11-27T22:05:00Z',
            'publishedAt': '2026-11-27T22:20:00Z', 'readbackAt': '2026-11-27T22:21:00Z',
            'sourceStates': {key: 'ok' for key in music.CHANNELS}, 'added': 1, 'totalAuto': 30}
        self.due = watchdog.due_slot('music', AT)
        self.rebuild()

    def rebuild(self, checked_at='2026-11-27T22:10:00Z'):
        self.report = audit.make_report(self.config, self.rows, self.results, True, checked_at)
        self.raw = (json.dumps(self.report, indent=2)+'\n').encode()
        self.candidate = availability.availability_candidate(self.report, self.raw, self.config, self.rows)

    def files(self, raw=None):
        raw = self.raw if raw is None else raw
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, 'w') as zipped:
            zipped.writestr('music-publication.json', json.dumps(self.pub))
            zipped.writestr(music.AUDIT, raw)
            zipped.writestr(music.AVAILABILITY, json.dumps(self.candidate))
        data = archive.getvalue()
        artifact = {'id': 7, 'name': 'daily-music-42-2', 'size_in_bytes': len(data),
            'digest': 'sha256:'+hashlib.sha256(data).hexdigest(),
            'workflow_run': {'id': 42, 'head_sha': SHA}}
        def get(path, binary=False):
            return data if binary else {'artifacts': [artifact], 'total_count': 1}
        return watchdog.artifact_files(self.run, 'daily-music', 'music-daily.yml', get)

    def result(self):
        return music.music_evidence(self.files(), self.due, AT)

    def test_79_failures_are_partial_but_official_publication_needs_no_retry(self):
        result = self.result()
        self.assertTrue(result['officialPublicationVerified'])
        self.assertTrue(result['recoverySatisfied'])
        self.assertEqual(result['state'], 'attention')
        self.assertEqual(result['backupAvailability']['state'], 'partial')
        self.assertEqual((result['backupAvailability']['available'], result['backupAvailability']['selected'],
                          result['backupAvailability']['unavailable']), (72, 151, 79))
        self.assertEqual(self.report['failed'], 79)
        self.assertIsNone(self.pub['sourceAt'])
        self.assertTrue(watchdog.evidence_ok('music', self.files(), self.due, AT))

    def test_metadata_verified_thumbnail_404_uses_same_v2_checker(self):
        row = next(result for result in self.results if result['channelKey'] == 'c3')
        row.update(stage='thumbnail', metadataStatus=200, thumbnailStatus=404, reasonCode='thumbnail_http_404')
        self.rebuild()
        self.assertTrue(self.result()['recoverySatisfied'])

    def test_failed_workflow_valid_publication_not_redispatched_and_ui_stays_partial(self):
        files = self.files()
        with patch.object(watchdog, 'workflow_runs', return_value=[self.run]), \
             patch.object(watchdog, 'artifact_files', return_value=files), \
             patch.object(monitor, 'listing', return_value=([self.run], True)):
            recovery = watchdog.inspect_batch('music', AT, lambda *args, **kwargs: None)
            row = monitor.inspect('music', AT, SHA, lambda *args, **kwargs: {'jobs': [], 'total_count': 0})
        self.assertEqual(recovery['state'], 'healthy')
        self.assertEqual(recovery['backupAvailability']['state'], 'partial')
        self.assertIn('separate_backup', recovery['healthScope'])
        self.assertEqual(row['dataState'], 'attention')
        self.assertEqual(row['backupAvailability']['unavailable'], 79)
        self.assertTrue(row['officialPublicationVerified'])
        self.assertIsNone(row['evidence']['sourceAt'])
        current = {'checkedAt': AT.isoformat(), 'batches': [row]}
        ledger.merge_slot_ledger({}, current, watchdog.due_slot)
        slot = next(item for item in ledger.unpack_slot_ledger(current['slotLedger'])['entries']
                    if item['batch'] == 'music')
        self.assertEqual(slot['state'], 'partial')
        self.assertEqual(slot['firstFailure']['backupAvailability']['unavailable'], 79)
        self.assertTrue(slot['firstFailure']['officialPublicationVerified'])
        self.assertIsNone(slot['firstFailure']['sourceAt'])
        self.assertIsNotNone(slot['firstFailure']['readbackAt'])

    def test_official_failure_unknown_and_changed_uploader_do_not_gain_exception(self):
        original = copy.deepcopy(self.results)
        cases = [('official', {'ok': False, 'stage': 'metadata', 'metadataStatus': 404, 'reasonCode': 'metadata_http_404'}),
                 ('backup', {'ok': False, 'stage': 'metadata', 'metadataStatus': 503, 'reasonCode': 'metadata_http_503'}),
                 ('backup', {'ok': False, 'stage': 'thumbnail', 'metadataStatus': 200, 'thumbnailStatus': 404,
                             'authorUrl': 'https://youtube.com/@unreviewed', 'reasonCode': 'thumbnail_http_404'})]
        for category, change in cases:
            self.results = copy.deepcopy(original)
            target = next(item for item in self.results if item['kind'].startswith('official')) if category == 'official' else next(item for item in self.results if item['channelKey'] == 'c3')
            target.update(change); self.rebuild()
            with self.subTest(category=category, change=change):
                self.assertFalse(self.result()['recoverySatisfied'])

    def test_same_run_attempt_sha_and_original_bytes_required(self):
        for key, wrong in [('runId', '43'), ('runAttempt', '1'), ('commit', 'b'*40)]:
            with self.subTest(key=key):
                original = self.run.copy()
                if key == 'runId': self.run['id'] = 43
                elif key == 'runAttempt': self.run['run_attempt'] = 1
                else: self.run['head_sha'] = wrong
                files = music.ArtifactFiles(self.run)
                files.update({'music-publication.json': self.pub, music.AUDIT: self.report, music.AVAILABILITY: self.candidate})
                files.audit_bytes = self.raw
                self.assertFalse(music.music_evidence(files, self.due, AT)['recoverySatisfied'])
                self.run = original
        self.assertFalse(music.music_evidence(self.files(self.raw+b' '), self.due, AT)['recoverySatisfied'])

    def test_claimed_counts_registry_and_candidate_tampering_rejected(self):
        original = copy.deepcopy(self.candidate)
        for change in [{'available': 151, 'unavailable': 0, 'state': 'complete'},
                       {'selectionSha256': '0'*64}, {'sourceAuditSha256': '0'*64}]:
            self.candidate = dict(original, **change)
            with self.subTest(change=change):
                self.assertFalse(self.result()['recoverySatisfied'])

    def test_missing_duplicate_or_unchecked_source_never_passes(self):
        self.report['results'][-1] = copy.deepcopy(self.report['results'][0])
        self.raw = json.dumps(self.report).encode()
        self.candidate['sourceAuditSha256'] = hashlib.sha256(self.raw).hexdigest()
        self.assertFalse(self.result()['recoverySatisfied'])

    def test_raw_evidence_is_not_serialized_into_monitoring(self):
        files = self.files()
        self.assertEqual(files.audit_bytes, self.raw)
        json.dumps(files)
        plain = dict(files)
        self.assertFalse(music.music_evidence(plain, self.due, AT)['recoverySatisfied'])

    def test_stale_or_pre_attempt_audit_is_not_accepted(self):
        self.rebuild((AT-timedelta(days=2)).isoformat())
        self.assertFalse(self.result()['recoverySatisfied'])
        self.rebuild('2026-11-27T21:50:00Z')
        self.assertFalse(self.result()['recoverySatisfied'])

    def test_noop_readback_does_not_invent_a_publication_timestamp(self):
        self.pub.update(publicationAction='unchanged_verified', publishedAt=None)
        self.assertTrue(self.result()['recoverySatisfied'])
        self.assertIsNone(self.pub['publishedAt'])

    def test_current_complete_official_channels_and_readback_still_required(self):
        original = copy.deepcopy(self.pub)
        for change in [{'verifiedReadback': False}, {'status': 'failed'},
                       {'generatedAt': '2026-11-26T20:00:00Z'}, {'readbackAt': '2026-11-27T22:01:00Z'},
                       {'sourceStates': {**original['sourceStates'], next(iter(music.CHANNELS)): 'partial'}}]:
            self.pub = dict(original, **change)
            with self.subTest(change=change):
                self.assertFalse(self.result()['recoverySatisfied'])

    def test_blocked_official_audit_keeps_existing_bounded_retry_decision(self):
        selected = next(item for item in self.results if item['kind'].startswith('official'))
        selected.update(ok=False, stage='metadata', metadataStatus=404, reasonCode='metadata_http_404')
        self.rebuild()
        files = self.files()
        with patch.object(watchdog, 'workflow_runs', return_value=[self.run]), \
             patch.object(watchdog, 'artifact_files', return_value=files):
            row = watchdog.inspect_batch('music', AT, lambda *args, **kwargs: None)
        self.assertEqual(row['state'], 'dispatch')
        self.assertFalse(row['recoverySatisfied'])
        self.assertFalse(row['backupAvailability']['verified'])

    def test_legacy_complete_remains_strict_and_short_counts_do_not_pass(self):
        files = {'music-publication.json': self.pub, music.AUDIT: {'selected': 151, 'passed': 151}}
        self.assertTrue(music.music_evidence(files, self.due, AT)['recoverySatisfied'])
        files[music.AUDIT]['passed'] = 72
        self.assertFalse(music.music_evidence(files, self.due, AT)['recoverySatisfied'])

    def test_summary_preserves_coverage_review_and_partial_without_false_source_clock(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/music.AUDIT).parent.mkdir(parents=True)
            (root/music.AUDIT).write_bytes(self.raw)
            (root/music.AVAILABILITY).write_text(json.dumps(self.candidate))
            (root/'music-publication.json').write_text(json.dumps(self.pub))
            discovery = {'sources': {key: {'state': 'ok', 'review': []} for key in music.CHANNELS}}
            discovery['sources'][next(iter(music.CHANNELS))]['review'] = ['one', 'two', 'three']
            (root/'music-discovery.json').write_text(json.dumps(discovery))
            output = io.StringIO()
            with patch.object(music, 'ROOT', root), patch.object(music, 'datetime') as timer, \
                 patch.dict(os.environ, {'GITHUB_REF': 'refs/heads/main', 'AUDIT_OUTCOME': 'success',
                                         'GITHUB_STEP_SUMMARY': str(root/'summary.txt')}), redirect_stdout(output):
                timer.now.return_value = AT
                self.assertEqual(music.main(), 0)
                report = json.loads((root/'music-batch-result.json').read_text())
                self.assertEqual(report['officialSourceCoverage']['needsReview'], 3)
                self.assertEqual(report['officialSourceCoverage']['completeChannels'], 9)
                self.assertEqual(report['backupAvailability']['unavailable'], 79)
                self.assertEqual(report['state'], 'attention')
                self.assertIsNone(report['sourceAt'])
                self.assertIn('fully checked channels 9/9, needs review 3', output.getvalue())
                self.assertIn('availability remains partial', output.getvalue())
                with patch.dict(os.environ, {'AUDIT_OUTCOME': 'failure'}):
                    self.assertEqual(music.main(), 1)


if __name__ == '__main__':
    unittest.main()
