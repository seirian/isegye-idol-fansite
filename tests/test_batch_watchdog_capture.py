"""Current-hour capture and deployment evidence are not workflow green badges."""
from datetime import timedelta
from pathlib import Path
import copy
import hashlib
import io
import json
import sys
import unittest
import zipfile
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import batch_watchdog as policy
import batch_monitor_snapshot as monitor
from batch_publication_evidence import capture_summary, production_evidence_ok, read_capture_evidence
from test_batch_watchdog_reliability import AT, run


def capture_document(candidate=None):
    candidate = candidate or run(kind='capture')
    due = policy.due_slot('capture', AT)
    return {'schemaVersion': 1, 'repository': policy.REPO, 'workflow': 'melon-chart-capture.yml',
            'sourceType': 'melon_public_full_chart', 'runId': candidate['id'],
            'runAttempt': candidate['run_attempt'], 'checkedAt': (AT-timedelta(minutes=2)).isoformat(),
            'status': 'complete', 'charts': {kind: {'source': url, 'sourceAt': due.isoformat(),
                'responseSha256': 'b'*64, 'rows': [[str(i), i] for i in range(1, 101)]}
                for kind, url in __import__('batch_publication_evidence').CAPTURE_SOURCES.items()}}


def publication():
    return {'status': 'deployed_and_verified', 'commit': 'a'*40,
            'browserVerified': True, 'privatePathsBlocked': True, 'protectedFilesUnchanged': True,
            'lockRemoved': True, 'maintenanceActive': True,
            'checkedAt': (AT-timedelta(minutes=25)).isoformat(),
            'verifiedAt': (AT-timedelta(minutes=10)).isoformat()}


class CaptureEvidence(unittest.TestCase):
    def test_capture_is_separate_fixed_recovery_target(self):
        self.assertEqual(policy.SPECS['capture'][0], 'melon-chart-capture.yml')
        self.assertIn('capture', monitor.META)
        self.assertIn('melon-chart-capture.yml', monitor.ALLOWED_WORKFLOWS)
        self.assertNotIn('capture', (Path(__file__).resolve().parents[1]/'monitoring/manual.js').read_text())

    def test_same_hour_complete_two_charts_are_observations_not_publication(self):
        proof = capture_summary(capture_document(), run(kind='capture'), policy.due_slot('capture', AT), AT)
        self.assertTrue(proof['currentComplete'])
        self.assertEqual(proof['chartsComplete'], 2)
        self.assertFalse(proof['publicationVerified'])

    def test_partial_or_failed_capture_cannot_be_healthy(self):
        for count, status in [(1, 'partial'), (0, 'failed')]:
            doc = capture_document(); doc['charts'] = dict(list(doc['charts'].items())[:count]); doc['status'] = status
            self.assertFalse(capture_summary(doc, run(kind='capture'), policy.due_slot('capture', AT), AT)['currentComplete'])

    def test_previous_hour_cannot_certify_current_hour(self):
        earlier = AT-timedelta(hours=1)
        doc = capture_document(); doc['checkedAt'] = earlier.isoformat()
        for chart in doc['charts'].values(): chart['sourceAt'] = policy.due_slot('capture', earlier).isoformat()
        candidate = run(kind='capture', minutes=90)
        self.assertFalse(capture_summary(doc, candidate, policy.due_slot('capture', AT), AT)['currentComplete'])

    def test_fixed_artifact_name_requires_exact_attempt_and_source(self):
        for mutation in ('attempt', 'rank', 'source', 'clock'):
            doc = capture_document()
            if mutation == 'attempt': doc['runAttempt'] = 2
            elif mutation == 'rank': doc['charts']['melon_top100']['rows'][1][1] = 1
            elif mutation == 'source': doc['charts']['melon_top100']['source'] = 'https://example.invalid/'
            else: doc['charts']['melon_top100']['sourceAt'] = (AT-timedelta(hours=1)).isoformat()
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                capture_summary(doc, run(kind='capture'), policy.due_slot('capture', AT), AT)

    def test_night_and_partial_pause_never_request_capture(self):
        for at, env in [(policy.clock('2026-11-15T03:30:00+09:00'), {}), (AT, {'ISEGYE_ALBUMS_PAUSED': 'true'})]:
            getter = Mock()
            with patch.dict('os.environ', env, clear=True):
                result = policy.recover_batch('capture', True, getter, lambda: at)
            self.assertIn(result['state'], ('night_pause', 'paused'))
            getter.assert_not_called()

    def test_current_capture_proof_suppresses_recovery(self):
        candidate = run(kind='capture', conclusion='success')
        proof = capture_summary(capture_document(), candidate, policy.due_slot('capture', AT), AT)
        with patch.object(policy, 'workflow_runs', return_value=[candidate]), patch.object(policy, 'read_capture_evidence', return_value=proof):
            self.assertEqual(policy.inspect_batch('capture', AT, Mock())['state'], 'healthy')

    def test_fixed_artifact_validates_archive_digest(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w') as archive:
            archive.writestr('melon-chart-capture.json', json.dumps(capture_document()))
        raw = buffer.getvalue(); candidate = run(kind='capture')
        artifact = {'id': 77, 'name': 'melon-chart-capture', 'size_in_bytes': len(raw),
                    'digest': 'sha256:'+hashlib.sha256(raw).hexdigest(),
                    'workflow_run': {'id': candidate['id'], 'head_sha': candidate['head_sha'], 'head_branch': 'main'}}
        getter = lambda path, binary=False: raw if binary else {'artifacts': [artifact], 'total_count': 1}
        self.assertTrue(read_capture_evidence(getter, candidate, policy.due_slot('capture', AT), AT)['currentComplete'])
        artifact['digest'] = 'sha256:'+'0'*64
        with self.assertRaises(ValueError): read_capture_evidence(getter, candidate, policy.due_slot('capture', AT), AT)

    def read_artifacts(self, candidate, records):
        artifacts, archives = [], {}
        for aid, name, document, corrupt in records:
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, 'w') as archive:
                archive.writestr('melon-chart-capture.json', json.dumps(document))
            raw = buffer.getvalue(); archives[aid] = raw
            artifacts.append({'id': aid, 'name': name, 'size_in_bytes': len(raw),
                'digest': 'sha256:'+('0'*64 if corrupt else hashlib.sha256(raw).hexdigest()),
                'workflow_run': {'id': candidate['id'], 'head_sha': candidate['head_sha'], 'head_branch': 'main'}})
        def getter(path, binary=False):
            if binary:
                return archives[int(path.split('/')[2])]
            return {'artifacts': artifacts, 'total_count': len(artifacts)}
        return read_capture_evidence(getter, candidate, policy.due_slot('capture', AT), AT)

    def test_exact_current_attempt_name_wins_over_legacy_and_prior_attempt(self):
        candidate = run(kind='capture', run_attempt=2)
        previous = capture_document(run(kind='capture'))
        current = capture_document(candidate)
        records = [(71, 'melon-chart-capture', previous, False),
                   (72, 'melon-chart-capture-1-1', previous, False),
                   (73, 'melon-chart-capture-1-2', current, False)]
        self.assertTrue(self.read_artifacts(candidate, records)['currentComplete'])

    def test_exact_name_corrupt_or_duplicate_cannot_fall_back_to_valid_legacy(self):
        candidate = run(kind='capture', run_attempt=2)
        data = capture_document(candidate)
        legacy = (71, 'melon-chart-capture', data, False)
        for named in [[(72, 'melon-chart-capture-1-2', data, True)],
                      [(72, 'melon-chart-capture-1-2', data, False),
                       (73, 'melon-chart-capture-1-2', data, False)]]:
            with self.subTest(ids=[record[0] for record in named]), self.assertRaises(ValueError):
                self.read_artifacts(candidate, [legacy, *named])

    def test_named_and_legacy_json_attempt_must_equal_latest_attempt(self):
        candidate = run(kind='capture', run_attempt=2)
        old = capture_document(run(kind='capture'))
        for name in ('melon-chart-capture-1-2', 'melon-chart-capture'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.read_artifacts(candidate, [(71, name, old, False)])


class ProductionEvidence(unittest.TestCase):
    def test_current_sha_green_without_publication_proof_is_not_healthy(self):
        candidate = run(kind='production', conclusion='success')
        getter = Mock(return_value={'object': {'sha': 'a'*40}})
        with patch.object(policy, 'workflow_runs', return_value=[candidate]), patch.object(policy, 'read_production_evidence', side_effect=policy.EvidenceUnavailable('missing')):
            result = policy.inspect_batch('production', AT, getter)
        self.assertNotEqual(result['state'], 'healthy')
        self.assertFalse(result['publicationVerified'])

    def test_verified_deployment_survives_ancillary_failed_or_cancelled_job(self):
        for conclusion in ('failure', 'cancelled'):
            candidate = run(kind='production', conclusion=conclusion)
            getter = Mock(return_value={'object': {'sha': 'a'*40}})
            with patch.object(policy, 'workflow_runs', return_value=[candidate]), patch.object(policy, 'read_production_evidence', return_value=(publication(), candidate, {})):
                result = policy.inspect_batch('production', AT, getter)
            self.assertEqual(result['state'], 'healthy')
            self.assertTrue(result['ancillaryFailure'])
            self.assertTrue(production_evidence_ok(publication(), candidate, 'a'*40, AT))

    def test_lock_cleanup_and_readback_are_required_but_access_policy_is_preserved(self):
        candidate = run(kind='production', conclusion='success')
        self.assertTrue(production_evidence_ok(publication(), candidate, 'a'*40, AT))
        for key in ('lockRemoved', 'browserVerified', 'privatePathsBlocked', 'protectedFilesUnchanged'):
            value = publication(); value[key] = False
            self.assertFalse(production_evidence_ok(value, candidate, 'a'*40, AT))
        self.assertFalse(production_evidence_ok(publication(), candidate, 'b'*40, AT))


if __name__ == '__main__':
    unittest.main()
