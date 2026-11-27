"""A monitor-only retry may retain exactly its deployed dependency's proof."""
from datetime import datetime, timezone
from pathlib import Path
import copy
import hashlib
import io
import json
import os
import sys
import unittest
import zipfile
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import batch_publication_evidence as evidence
import batch_publication_reference as reference
import batch_watchdog as watchdog
import batch_monitor_snapshot as monitor

AT = datetime(2026, 11, 27, 3, 55, tzinfo=timezone.utc)
SHA = 'a'*40


class ReferenceFixture(unittest.TestCase):
    def setUp(self):
        self.source = {'id': 42, 'run_attempt': 1, 'head_sha': SHA, 'head_branch': 'main',
            'status': 'completed', 'conclusion': 'failure', 'event': 'workflow_dispatch',
            'repository': {'full_name': evidence.REPO}, 'head_repository': {'full_name': evidence.REPO},
            'path': '.github/workflows/production.yml', 'workflow_id': 51,
            'created_at': '2026-11-27T03:00:00Z', 'run_started_at': '2026-11-27T03:00:00Z'}
        self.current = dict(self.source, run_attempt=2, run_started_at='2026-11-27T03:35:00Z')
        self.env = {'GITHUB_REPOSITORY': evidence.REPO, 'GITHUB_REF': 'refs/heads/main',
                    'GITHUB_SHA': SHA, 'GITHUB_RUN_ID': '42', 'GITHUB_RUN_ATTEMPT': '2'}
        self.auth = {'status': 'deployed_and_verified', 'commit': SHA, 'browserVerified': True,
            'privatePathsBlocked': True, 'protectedFilesUnchanged': True, 'lockRemoved': True,
            'checkedAt': '2026-11-27T03:05:00Z', 'verifiedAt': '2026-11-27T03:20:00Z'}
        self.candidate = {'status': 'candidate_verified', 'repository': evidence.REPO,
            'commit': SHA, 'runId': 42, 'prepareAttempt': 1, 'consumerAttempt': 1,
            'archiveSha256': 'f'*64, 'files': 350}
        self.artifacts, self.archives, self.calls = [], {}, []
        source = self.add(700, 'isegye-production-evidence-42-1',
                        {'auth-deployment.json': self.auth, 'production-candidate-verified.json': self.candidate})
        self.ref = reference.build(700, source['digest'], 1, 1, 1, environ=self.env, at=AT)
        self.write_reference()

    def add(self, identity, name, members):
        output = io.BytesIO()
        with zipfile.ZipFile(output, 'w') as archive:
            for member, data in members.items():
                archive.writestr(member, json.dumps(data))
        raw = output.getvalue()
        artifact = {'id': identity, 'name': name, 'size_in_bytes': len(raw),
            'digest': 'sha256:'+hashlib.sha256(raw).hexdigest(),
            'workflow_run': {'id': 42, 'head_sha': SHA, 'head_branch': 'main'}}
        self.artifacts = [old for old in self.artifacts if old['id'] != identity]+[artifact]
        self.archives[identity] = raw
        return artifact

    def write_reference(self):
        self.add(701, 'isegye-production-monitor-evidence-42-2',
                 {'production-publication-reference.json': self.ref})

    def get(self, path, binary=False):
        self.calls.append(path)
        if path == 'actions/runs/42/artifacts?per_page=100':
            return {'total_count': len(self.artifacts), 'artifacts': copy.deepcopy(self.artifacts)}
        if path == 'actions/runs/42/attempts/1':
            return copy.deepcopy(self.source)
        if binary and path.startswith('actions/artifacts/'):
            return self.archives[int(path.split('/')[2])]
        if path == 'git/ref/heads/main':
            return {'object': {'sha': SHA}}
        if path.endswith('/jobs?per_page=100'):
            return {'total_count': 0, 'jobs': []}
        raise AssertionError('Unexpected endpoint: '+path)

    def read(self):
        return evidence.read_production_evidence(self.get, self.current, AT)

    def test_monitor_only_rerun_preserves_original_verified_time(self):
        auth, run, lineage = self.read()
        self.assertEqual(auth['verifiedAt'], self.auth['verifiedAt'])
        self.assertEqual(run['run_attempt'], 1)
        self.assertTrue(lineage['viaReference'])
        self.assertEqual((lineage['executionAttempt'], lineage['sourceAttempt']), (2, 1))
        self.assertTrue(evidence.production_evidence_ok(auth, run, SHA, AT))
        self.assertFalse(evidence.production_evidence_ok(auth, self.current, SHA, AT))

    def test_watchdog_and_monitor_share_original_attempt(self):
        with patch.dict(os.environ, {'PRODUCTION_PAUSED': ''}), \
             patch.object(watchdog, 'workflow_runs', return_value=[self.current]), \
             patch.object(monitor, 'listing', return_value=([self.current], True)):
            recovery = watchdog.inspect_batch('production', AT, self.get)
            row = monitor.inspect('production', AT, SHA, self.get)
        self.assertEqual(recovery['state'], 'healthy')
        self.assertEqual(recovery['evidenceAttempt'], 1)
        self.assertEqual((row['state'], row['dataState']), ('healthy', 'healthy'))
        self.assertEqual(row['run']['attempt'], 2)
        self.assertEqual(row['evidenceRun']['attempt'], 1)
        self.assertEqual(row['lastVerifiedAt'], '2026-11-27T03:20:00+00:00')
        self.assertTrue(row['ancillaryFailure'])

    def test_missing_reference_never_searches_an_older_success(self):
        self.artifacts = self.artifacts[:1]
        with self.assertRaises(evidence.EvidenceUnavailable):
            self.read()
        self.assertNotIn('actions/runs/42/attempts/1', self.calls)

    def test_reference_other_run_or_commit_is_rejected(self):
        for name, value in [('runId', 43), ('commit', 'b'*40), ('runAttempt', 1)]:
            with self.subTest(name=name):
                original = self.ref[name]; self.ref[name] = value; self.write_reference()
                with self.assertRaises(ValueError):
                    self.read()
                self.ref[name] = original

    def test_reference_different_artifact_or_digest_is_rejected(self):
        for name, value in [('sourceArtifactId', 702), ('sourceArtifactDigest', 'sha256:'+'0'*64)]:
            with self.subTest(name=name):
                original = self.ref[name]; self.ref[name] = value; self.write_reference()
                with self.assertRaisesRegex(ValueError, 'artifact identity'):
                    self.read()
                self.ref[name] = original

    def test_new_prepare_attempt_cannot_reuse_old_deployment(self):
        self.ref['currentPrepareAttempt'] = 2; self.write_reference()
        with self.assertRaises(ValueError):
            self.read()
        with self.assertRaises(ValueError):
            reference.build(700, self.ref['sourceArtifactDigest'], 1, 1, 2, environ=self.env, at=AT)

    def test_original_attempt_provenance_is_required(self):
        for name, value in [('id', 43), ('head_sha', 'b'*40), ('run_attempt', 2),
                            ('status', 'in_progress'), ('path', '.github/workflows/other.yml'),
                            ('head_repository', {'full_name': 'untrusted/fork'})]:
            with self.subTest(name=name):
                original = self.source[name]; self.source[name] = value
                with self.assertRaises(ValueError):
                    self.read()
                self.source[name] = original

    def test_original_candidate_consumer_is_required(self):
        self.candidate['consumerAttempt'] = 2
        source = self.add(700, 'isegye-production-evidence-42-1',
                        {'auth-deployment.json': self.auth, 'production-candidate-verified.json': self.candidate})
        self.ref['sourceArtifactDigest'] = source['digest']; self.write_reference()
        with self.assertRaisesRegex(ValueError, 'candidate lineage'):
            self.read()

    def test_current_incomplete_or_expired_evidence_cannot_fallback(self):
        artifact = self.add(702, 'isegye-production-evidence-42-2', {'batch-failure.json': {'status': 'failed'}})
        with self.assertRaises(evidence.EvidenceUnavailable):
            self.read()
        self.assertNotIn('actions/runs/42/attempts/1', self.calls)
        artifact['expired'] = True
        with self.assertRaises(evidence.EvidenceUnavailable):
            self.read()
        self.assertNotIn('actions/runs/42/attempts/1', self.calls)

    def test_current_unverified_publication_is_not_replaced(self):
        self.add(702, 'isegye-production-evidence-42-2', {'auth-deployment.json': {'status': 'failed'}})
        report, run, lineage = self.read()
        self.assertFalse(evidence.production_evidence_ok(report, run, SHA, AT))
        self.assertFalse(lineage['viaReference'])
        self.assertNotIn('actions/runs/42/attempts/1', self.calls)

    def test_reference_clock_and_current_main_identity_required(self):
        self.ref['createdAt'] = '2026-11-27T03:00:00Z'; self.write_reference()
        with self.assertRaises(ValueError):
            self.read()
        for change in [{'GITHUB_REF': 'refs/heads/feature'}, {'GITHUB_REPOSITORY': 'other/repo'}]:
            with self.subTest(change=change), self.assertRaises(ValueError):
                reference.build(700, self.ref['sourceArtifactDigest'], 1, 1, 1,
                                environ=dict(self.env, **change), at=AT)

    def test_capture_does_not_expand_manual_capabilities(self):
        import batch_manual_worker as manual
        self.assertEqual(len(manual.TARGETS), 8)
        self.assertNotIn('capture', manual.TARGETS)
        self.assertNotIn('capture', manual.PAUSES)
        with self.assertRaises(ValueError):
            manual.GitHub()('actions/workflows/melon-chart-capture.yml/dispatches',
                           method='POST', payload={'ref': 'main'})


if __name__ == '__main__':
    unittest.main()
