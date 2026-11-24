"""Actionable failure evidence without source text, secrets or false outages."""
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import cafe_runtime as runtime
import publish_schedule_feed as pub
import schedule_health as health
from test_schedule_feed import FeedRemote, seed
from test_schedule_runtime import packet, NOW


class FailureEvidence(unittest.TestCase):
    def invalid_title(self):
        p = packet()
        row = dict(p['notices'][0], checkedAt=p['checkedAt'])
        row['title'] = '[고세구] 하이빵가루~! >ㅁ<'
        try:
            runtime.validate_evidence({'schemaVersion': 1, 'notices': [row], 'fanSeries': []}, NOW)
        except ValueError as err:
            return err
        self.fail('invalid runtime title was accepted')

    def test_validation_failure_identifies_record_without_title(self):
        report = pub.failure_report(self.invalid_title(), 'source_collection')
        self.assertEqual(report['errorCode'], 'invalid_cafe_title')
        self.assertEqual(report['field'], 'title')
        self.assertEqual(report['articleId'], 99911111)
        self.assertEqual(report['sourceId'], 'cafe-members')
        self.assertEqual(report['stage'], 'source_collection')
        self.assertEqual(report['location']['file'], 'scripts/cafe_runtime.py')
        self.assertNotIn('하이빵가루', json.dumps(report, ensure_ascii=False))
        self.assertNotIn('reason', report)

    def test_unknown_exception_never_exposes_its_message(self):
        secret = 'fixture-password@example.invalid?token=do-not-log'
        report = pub.failure_report(ValueError(secret), 'source_collection')
        self.assertEqual(report['errorType'], 'ValueError')
        self.assertNotIn(secret, json.dumps(report))
        self.assertNotIn('reason', report)

    def test_collection_abort_keeps_previous_snapshot_and_releases_own_lock(self):
        remote = FeedRemote()
        pub.publish(remote, lambda **kw: seed())
        old = remote.files[pub.path('current.json')]
        progress = {}
        failure = self.invalid_title()
        def fail(**kwargs):
            raise failure
        with self.assertRaises(runtime.CafeEvidenceError):
            pub.publish(remote, fail, progress)
        self.assertEqual(progress['stage'], 'source_collection')
        self.assertEqual(remote.files[pub.path('current.json')], old)
        self.assertNotIn(pub.path('.lock'), remote.files)

    def test_previous_snapshot_validation_has_distinct_stage(self):
        remote = FeedRemote()
        pub.publish(remote, lambda **kw: seed())
        remote.files[pub.path('current.json')] = b'{broken-json'
        old = remote.files[pub.path('current.json')]
        progress = {}
        with self.assertRaises(ValueError):
            pub.publish(remote, lambda **kw: self.fail('collection must not start'), progress)
        self.assertEqual(progress['stage'], 'previous_snapshot_validation')
        self.assertEqual(remote.files[pub.path('current.json')], old)
        self.assertNotIn(pub.path('.lock'), remote.files)


class HealthEvidence(unittest.TestCase):
    def test_aborted_publication_does_not_invent_six_source_outages(self):
        result = health.publication_result({'status': 'failed', 'errorType': 'ValueError',
            'stage': 'source_collection', 'errorCode': 'invalid_cafe_title', 'articleId': 99911111})
        self.assertFalse(result['verified'])
        self.assertEqual(result['collectionHealth']['state'], 'unknown')
        self.assertEqual(result['collectionHealth']['incompleteSources'], [])
        self.assertEqual(result['collectionHealth']['unassessedSources'], list(health.REQUIRED))
        self.assertEqual(result['publicationFailure']['articleId'], 99911111)

    def test_missing_report_is_not_success(self):
        result = health.publication_result({})
        self.assertEqual(result['publicationStatus'], 'not_published')
        self.assertFalse(result['verified'])

    def test_measured_partial_failure_is_preserved(self):
        assessment = {'state': 'partial', 'incompleteSources': ['berriz-calendar'],
                      'sources': {'berriz-calendar': {'state': 'partial'}}}
        result = health.publication_result({'status': 'published', 'collectionHealth': assessment})
        self.assertEqual(result['collectionHealth'], assessment)
        self.assertFalse(result['verified'])
        self.assertNotIn('publicationFailure', result)

    def test_old_successful_assessment_cannot_turn_failed_publication_green(self):
        result = health.publication_result({'status': 'failed', 'collectionHealth': {'state': 'complete'}})
        self.assertFalse(result['verified'])

    def test_published_complete_is_success(self):
        result = health.publication_result({'status': 'published', 'collectionHealth': {'state': 'complete'}})
        self.assertTrue(result['verified'])

    def test_health_command_remains_nonzero_and_avoids_six_false_warnings(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(health, 'Path',
                side_effect=lambda name: Path(folder) / name), patch.dict('os.environ', {}, clear=True):
            (Path(folder) / 'schedule-publication.json').write_text('{"status":"failed","errorType":"ValueError"}')
            output = io.StringIO()
            with redirect_stdout(output):
                status = health.main()
            self.assertEqual(status, 1)
            self.assertIn('평가 불가', output.getvalue())
            self.assertIn('no source assessment is recorded', output.getvalue())
            self.assertNotIn('cafe-members — collection incomplete', output.getvalue())
            self.assertFalse(json.loads((Path(folder) / 'schedule-health.json').read_text())['verified'])


if __name__ == '__main__':
    unittest.main()
