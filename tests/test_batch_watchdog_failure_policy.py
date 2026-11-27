"""Bounded deterministic-failure circuit and idempotent incident reconciliation."""
from datetime import timedelta
from pathlib import Path
import copy
import json
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import batch_failure_evidence as failure
import batch_watchdog as policy
from test_batch_watchdog_reliability import AT, run

IDENTITIES = {'codeIdentity': 'b'*64, 'inputIdentity': 'c'*64}


def proof(candidate, reason='production_directory_conflict'):
    retry, stage = failure.REASONS[reason]
    return {'schemaVersion': 1, 'kind': 'batch_failure', 'repository': policy.REPO,
        'workflow': 'production.yml', 'stage': stage, 'commit': candidate['head_sha'],
        'runId': candidate['id'], 'runAttempt': candidate['run_attempt'],
        'checkedAt': (policy.started(candidate)+timedelta(minutes=1)).isoformat(),
        'reasonCode': reason, 'retryClass': retry, **IDENTITIES}


class FailureCircuit(unittest.TestCase):
    def candidates(self):
        return [run(2, kind='production', minutes=30), run(1, kind='production', minutes=90, head_sha='d'*40)]

    def evaluate(self, candidates=None, reason='production_directory_conflict', mutate=None):
        candidates = candidates or self.candidates()
        def read(getter, candidate, prefix, name):
            result = proof(candidate, reason)
            if mutate: mutate(result)
            return result
        with patch.object(policy, 'read_json_artifact', side_effect=read), patch.object(failure, 'identities', return_value=IDENTITIES):
            return policy.production_failure_block(candidates, AT, Mock())

    def test_two_exact_failures_block_even_after_unrelated_commit(self):
        result = self.evaluate()
        self.assertEqual(result['state'], 'blocked_permanent')
        self.assertEqual([item['runId'] for item in result['failureEvidence']], [2, 1])
        self.assertTrue(result['requiresResolutionEvidence'])

    def test_single_failure_or_recent_success_does_not_claim_repetition(self):
        self.assertIsNone(self.evaluate(self.candidates()[:1]))
        values = self.candidates(); values[1]['conclusion'] = 'success'
        self.assertIsNone(self.evaluate(values))

    def test_related_code_or_input_change_invalidates_previous_block(self):
        for key in IDENTITIES:
            self.assertIsNone(self.evaluate(mutate=lambda value: value.update({key: '0'*64})))

    def test_unverified_provenance_never_authorizes_a_block(self):
        for field, value in [('runAttempt', 99), ('commit', 'f'*40), ('repository', 'other/repo'),
                             ('reasonCode', 'UNREVIEWED_RAW_ERROR'), ('retryClass', 'ignore')]:
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.evaluate(mutate=lambda doc: doc.update({field: value}))

    def test_missing_failure_report_is_not_invented(self):
        with patch.object(policy, 'read_json_artifact', side_effect=policy.EvidenceUnavailable('missing')):
            self.assertIsNone(policy.production_failure_block(self.candidates(), AT, Mock()))

    def test_unknown_mutation_is_distinct_from_source_inspection(self):
        self.assertEqual(self.evaluate(reason='production_lock_request_unknown')['state'], 'request_unknown')
        self.assertEqual(self.evaluate(reason='music_source_inspection_unknown')['state'], 'inspection_failed')
        self.assertEqual(self.evaluate(reason='production_lock_busy')['state'], 'blocked_dependency')
        self.assertIsNone(self.evaluate(reason='music_source_transport_failed'))

    def test_block_is_attention_not_healthy_or_user_pause(self):
        self.assertEqual(policy.report_state([self.evaluate()]), 'attention')

    def test_failure_producer_has_fixed_bounded_identity_only(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in failure.DEPLOY_CODE:
                path = root/name; path.parent.mkdir(parents=True, exist_ok=True); path.write_text(name)
            (root/'auth-deployment.json').write_text(json.dumps({'status': 'failed', 'reason': 'Refusing existing directory', 'secret': 'DO-NOT-COPY'}))
            env = {'GITHUB_REPOSITORY': policy.REPO, 'GITHUB_REF': 'refs/heads/main', 'GITHUB_SHA': 'a'*40,
                   'GITHUB_RUN_ID': '42', 'GITHUB_RUN_ATTEMPT': '2'}
            result = failure.build(root, 'deploy', env, AT)
            self.assertEqual(result['reasonCode'], 'production_directory_conflict')
            self.assertNotIn('DO-NOT-COPY', json.dumps(result))
            before = result['codeIdentity']; (root/failure.DEPLOY_CODE[0]).write_text('reviewed fix')
            self.assertNotEqual(failure.identities(result['reasonCode'], root)['codeIdentity'], before)


class ReportingRetry(unittest.TestCase):
    def error(self, code=502):
        return policy.GitHubAPIError('github_http_error', api_diagnostics={'httpStatus': code, 'rateLimitRemaining': 4996})

    def test_read_502_has_one_bounded_retry(self):
        get = Mock(side_effect=[self.error(), []]); sleep = Mock()
        result = policy.update_incident(get, 'title', 'body', False, False, sleep)
        self.assertEqual(result['reportRetries'], 1)
        self.assertEqual(get.call_count, 2)

    def test_patch_unknown_is_reconciled_without_dispatch_or_second_write(self):
        get = Mock(side_effect=[[{'number': 12, 'title': 'title'}], self.error(), {'body': 'body'}])
        result = policy.update_incident(get, 'title', 'body', True, False, Mock())
        self.assertTrue(result['reconciled'])
        writes = [call for call in get.call_args_list if len(call.args) > 1]
        self.assertEqual(len(writes), 1)
        self.assertEqual(writes[0].args[:2], ('issues/12', 'PATCH'))

    def test_create_unknown_never_blindly_reposts(self):
        get = Mock(side_effect=[[], self.error(), []])
        with self.assertRaises(policy.GitHubAPIError):
            policy.update_incident(get, 'title', 'body', True, False, Mock())
        self.assertEqual(sum(len(call.args)>1 and call.args[1]=='POST' for call in get.call_args_list), 1)

    def test_access_denial_is_not_retried(self):
        get = Mock(side_effect=self.error(403))
        with self.assertRaises(policy.GitHubAPIError):
            policy.update_incident(get, 'title', 'body', True, False, Mock())
        self.assertEqual(get.call_count, 1)

    def test_cache_only_reuses_immutable_archive_bytes(self):
        get = Mock(side_effect=lambda path, **kwargs: b'archive' if kwargs.get('binary') else {})
        client = policy.EvidenceCache(get)
        for _ in range(2):
            client('actions/artifacts/42/zip', binary=True)
            client('git/ref/heads/main')
            client('actions/workflows/albums-daily.yml/runs?per_page=100&page=1')
        self.assertEqual(client.calls, 5)
        self.assertEqual(client.cacheHits, 1)

    def test_shared_budget_cannot_be_bypassed_by_a_new_batch(self):
        get = Mock(return_value={})
        client = policy.EvidenceCache(get, max_calls=2)
        client('git/ref/heads/main'); client('actions/workflows/albums-daily.yml/runs?per_page=100&page=1')
        with self.assertRaises(policy.InspectionError):
            client('actions/workflows/schedule-refresh.yml/runs?per_page=100&page=1')
        self.assertEqual(get.call_count, 2)


if __name__ == '__main__':
    unittest.main()
