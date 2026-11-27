"""Cancellation, lost-response and foreign-owner lock safety, without a host."""
import copy
import json
import os
from pathlib import Path
import signal
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import inour_sftp as d
import production_lock as locks
import recover_production_lock as recover
from test_batch_monitor_production import MemoryRemote


class ProductionLockTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {'GITHUB_ACTIONS': 'false'})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.remote = MemoryRemote()
        self.report = {}

    def acquire(self):
        return locks.acquire(self.remote, purpose='test_writer', report=self.report, commit='a' * 40)

    def test_actions_main_identity_and_pull_ref_denial_remain_enforced(self):
        env = {'GITHUB_ACTIONS': 'true', 'GITHUB_REPOSITORY': locks.REPO,
               'GITHUB_REF': 'refs/heads/main', 'GITHUB_RUN_ID': '123456',
               'GITHUB_RUN_ATTEMPT': '2', 'GITHUB_SHA': 'a' * 40,
               'GITHUB_WORKFLOW_REF': locks.REPO + '/.github/workflows/production.yml@refs/heads/main'}
        with patch.dict(os.environ, env):
            owner = locks.owner_identity('test_writer')
            self.assertEqual((owner['runId'], owner['runAttempt']), (123456, 2))
            with patch.dict(os.environ, GITHUB_REF='refs/pull/999/merge'):
                before = copy.deepcopy((self.remote.files, self.remote.dirs, self.remote.writes))
                with self.assertRaisesRegex(d.Stop, 'Verified Actions identity required'):
                    self.acquire()
                self.assertEqual(before, (self.remote.files, self.remote.dirs, self.remote.writes))

    def test_owned_lock_is_exclusive_and_released_with_no_nonce_disclosure(self):
        held = self.acquire()
        self.assertEqual(locks.decode_owner(self.remote.read(locks.LOCK + '/owner.json'))['nonce'], held.owner['nonce'])
        self.assertNotIn(held.owner['nonce'], json.dumps(self.report))
        with self.assertRaises(d.Stop): self.acquire()
        locks.release(self.remote, held)
        self.assertIsNone(self.remote.info(locks.LOCK))
        self.assertEqual(self.report['productionLock']['state'], 'released')

    def test_legacy_empty_or_foreign_lock_never_deleted(self):
        self.remote.mkdir(locks.LOCK)
        with self.assertRaises(d.Stop): self.acquire()
        self.assertIsNotNone(self.remote.info(locks.LOCK))
        self.assertEqual(self.remote.s.listdir_attr(locks.LOCK), [])

    def test_lost_mkdir_reply_is_unknown_and_preserved(self):
        create = self.remote.mkdir
        def ambiguous(path, mode=0o755):
            create(path, mode)
            raise ConnectionResetError('simulated lost mkdir response')
        with patch.object(self.remote, 'mkdir', side_effect=ambiguous), self.assertRaises(ConnectionResetError):
            self.acquire()
        self.assertIsNotNone(self.remote.info(locks.LOCK))
        self.assertEqual(self.report['productionLock']['state'], 'acquire_unknown')

    def test_owned_upload_lost_reply_can_clean_only_matching_random_owner(self):
        create = self.remote.new
        def interrupted(path, raw):
            create(path, raw)
            raise ConnectionResetError('simulated reply loss after complete owner write')
        with patch.object(self.remote, 'new', side_effect=interrupted), self.assertRaises(ConnectionResetError):
            self.acquire()
        self.assertIsNone(self.remote.info(locks.LOCK))

    def test_foreign_owner_change_blocks_cleanup(self):
        held = self.acquire()
        self.remote.files[locks.LOCK + '/owner.json'] = b'foreign'
        with self.assertRaises(d.Stop): locks.release(self.remote, held)
        self.assertEqual(self.remote.read(locks.LOCK + '/owner.json'), b'foreign')
        self.assertIsNotNone(self.remote.info(locks.LOCK))

    def test_recovery_guard_blocks_new_writer(self):
        guard = locks.acquire(self.remote, purpose='test_recovery', recovery=True)
        try:
            with self.assertRaises(d.Stop): self.acquire()
            self.assertIsNone(self.remote.info(locks.LOCK))
        finally:
            locks.release(self.remote, guard)

    def test_sigterm_enters_owned_cleanup_and_restores_previous_handler(self):
        before = signal.getsignal(signal.SIGTERM)
        held = self.acquire()
        with self.assertRaises(locks.Interrupted):
            try:
                os.kill(os.getpid(), signal.SIGTERM)
            finally:
                locks.release(self.remote, held)
        self.assertIsNone(self.remote.info(locks.LOCK))
        self.assertEqual(signal.getsignal(signal.SIGTERM), before)

    def test_cleanup_failure_after_retirement_does_not_create_anonymous_busy_lock(self):
        held = self.acquire()
        with patch.object(self.remote, 'remove_own', side_effect=ConnectionResetError), self.assertRaises(ConnectionResetError):
            locks.release(self.remote, held)
        self.assertIsNone(self.remote.info(locks.LOCK))
        self.assertTrue(held.released)
        self.assertEqual(self.report['productionLock']['state'], 'released_cleanup_pending')
        self.assertEqual(self.remote.read(locks.LOCK + '.released-' + held.owner['nonce'] + '/owner.json'), held.raw)

    def test_checkpoint_preserves_owner_and_refuses_foreign_mutation(self):
        held = self.acquire()
        locks.checkpoint(self.remote, held, 'activation')
        self.assertEqual(locks.decode_owner(self.remote.read(locks.LOCK + '/owner.json'))['phase'], 'activation')
        locks.release(self.remote, held)


class LockRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {'GITHUB_ACTIONS': 'false'})
        self.env.start(); self.addCleanup(self.env.stop)
        self.remote = MemoryRemote(); self.remote.mkdir(locks.LOCK)
        self.api = SimpleNamespace(calls=0)
        self.args = SimpleNamespace(expected_main='a' * 40, allow_legacy_empty=True,
            legacy_owner_run_id=123, legacy_owner_attempt=1, audit_sha256=None)
        self.incident = {'id': 123, 'run_attempt': 1, 'path': '.github/workflows/production.yml',
            'head_sha': 'b' * 40, 'head_branch': 'main', 'status': 'completed', 'conclusion': 'cancelled'}
        self.inspect = {'complete': True, 'executingWriters': 0, 'waitingWriters': [], 'checkedAt': 'test'}

    def snapshot(self, remote, guard=None):
        return {'lock': recover.lock_state(remote), 'hashes': {'router': 'unchanged'},
                'protected': {'mir': 'unchanged'}, 'accountStoreAccessed': False}

    def context(self):
        return (patch.object(recover, 'snapshot', side_effect=self.snapshot),
                patch.object(recover, 'active_writers', return_value=self.inspect),
                patch.object(recover, 'terminal_run', return_value=self.incident))

    def audit(self):
        return recover.evidence(self.remote, self.api, 'a' * 40, 456,
            legacy_run_id=123, legacy_attempt=1, allow_legacy=True)

    def test_default_audit_has_no_remote_writes_and_does_not_claim_legacy_ownership(self):
        before = copy.deepcopy((self.remote.files, self.remote.dirs, self.remote.writes))
        a, b, c = self.context()
        with a, b as inspections, c:
            result = self.audit()
        self.assertEqual(before, (self.remote.files, self.remote.dirs, self.remote.writes))
        self.assertEqual(inspections.call_count, 2)
        self.assertFalse(result['evidence']['ownerConfirmed'])
        self.assertFalse(result['remoteWrites'])

    def test_legacy_without_explicit_opt_in_is_not_recovery_candidate(self):
        a, b, c = self.context()
        with a, b, c, self.assertRaises(d.Stop):
            recover.evidence(self.remote, self.api, 'a' * 40, 456)

    def test_audited_legacy_recovery_preserves_router_and_removes_only_empty_lock(self):
        a, b, c = self.context()
        with a, b, c:
            audit = self.audit(); self.args.audit_sha256 = audit['diagnosticSha256']
            report = {}
            recover.apply_recovery(self.remote, self.api, self.args, audit, 456, report)
        self.assertEqual(report['status'], 'recovered_and_verified')
        self.assertFalse(report['ownerConfirmed'])
        self.assertIsNone(self.remote.info(locks.LOCK))
        self.assertIsNone(self.remote.info(locks.RECOVERY_LOCK))
        self.assertTrue(report['routingAndPointersUnchanged'])

    def test_unknown_or_active_writer_prevents_lock_removal(self):
        a, b, c = self.context()
        with a, b, c:
            audit = self.audit(); self.args.audit_sha256 = audit['diagnosticSha256']
        with patch.object(recover, 'active_writers', side_effect=d.Stop('writer active')), self.assertRaises(d.Stop):
            recover.apply_recovery(self.remote, self.api, self.args, audit, 456, {})
        self.assertIsNotNone(self.remote.info(locks.LOCK))
        self.assertIsNone(self.remote.info(locks.RECOVERY_LOCK))

    def test_hash_mismatch_never_acquires_guard_or_changes_legacy_lock(self):
        a, b, c = self.context()
        with a, b, c:
            audit = self.audit()
        self.args.audit_sha256 = '0' * 64
        before = list(self.remote.writes)
        with self.assertRaises(d.Stop):
            recover.apply_recovery(self.remote, self.api, self.args, audit, 456, {})
        self.assertEqual(before, self.remote.writes)

    def test_foreign_file_is_not_legacy_empty_lock(self):
        self.remote.new(locks.LOCK + '/foreign', b'keep')
        with self.assertRaises(d.Stop): recover.lock_state(self.remote)
        self.assertEqual(self.remote.read(locks.LOCK + '/foreign'), b'keep')

    def test_terminal_status_must_be_exact_attempt_and_real_owner(self):
        run = dict(self.incident, repository={'full_name': locks.REPO}, head_repository={'full_name': locks.REPO})
        api = SimpleNamespace(get=lambda endpoint: run)
        recover.terminal_run(api, 123, 1)
        for change in ({'status': 'in_progress'}, {'run_attempt': 2}, {'head_branch': 'develop'}):
            modified = dict(run, **change)
            with self.subTest(change=change), self.assertRaises(d.Stop):
                recover.terminal_run(SimpleNamespace(get=lambda endpoint: modified), 123, 1)


class ActiveWriterInspectionTests(unittest.TestCase):
    def make_api(self, writer_status='queued', *, broken_queue=False, truncated=False):
        main = 'a' * 40
        own = {'id': 456, 'run_attempt': 1, 'path': recover.SELF_WORKFLOW,
               'head_sha': main, 'head_branch': 'main', 'status': 'in_progress',
               'repository': {'full_name': locks.REPO}, 'head_repository': {'full_name': locks.REPO}}
        production = dict(own, id=789, path='.github/workflows/production.yml')
        queue = {'group': 'wrong' if broken_queue else recover.SHARED_GROUP, 'cancel-in-progress': False}
        definitions = {
            recover.SELF_WORKFLOW: {'jobs': {'recover': {'name': 'Audit or recover owned production lock',
                'concurrency': {'group': recover.SHARED_GROUP, 'cancel-in-progress': False}}}},
            '.github/workflows/production.yml': {'jobs': {
                'prepare': {'name': 'Prepare verified production candidate', 'steps': [{'run': 'npm test'}]},
                'deploy': {'name': 'Publish verified production candidate', 'concurrency': queue,
                    'env': {'ISEGYE_SFTP_PASSWORD': '${{ secrets.ISEGYE_SFTP_PASSWORD }}'}}}}}
        def get(endpoint):
            if endpoint == 'git/ref/heads/main': return {'object': {'sha': main}}
            if endpoint == 'actions/runs/456': return own
            if endpoint.startswith('actions/runs/456/jobs'):
                return {'total_count': 1, 'jobs': [{'id': 1, 'run_id': 456,
                    'name': 'Audit or recover owned production lock', 'status': 'in_progress'}]}
            if endpoint.startswith('actions/runs/789/jobs'):
                return {'total_count': 2, 'jobs': [
                    {'id': 2, 'run_id': 789, 'name': 'Prepare verified production candidate', 'status': 'in_progress'},
                    {'id': 3, 'run_id': 789, 'name': 'Publish verified production candidate', 'status': writer_status}]}
            if endpoint.startswith('actions/runs?'):
                from urllib.parse import parse_qs
                status = parse_qs(endpoint.partition('?')[2])['status'][0]
                rows = [own, production] if status == 'in_progress' else []
                return {'total_count': len(rows) + int(truncated), 'workflow_runs': rows}
            raise AssertionError('Unexpected API endpoint ' + endpoint)
        return SimpleNamespace(get=get, source=lambda path, sha: definitions[path])

    def test_readonly_prepare_and_serialized_queued_writer_do_not_block_recovery(self):
        result = recover.active_writers(self.make_api(), 456, 'a' * 40)
        self.assertEqual(result['executingWriters'], 0)
        self.assertEqual(result['waitingWriters'], [{'runId': 789, 'jobId': 3, 'state': 'queued_common_group'}])

    def test_running_remote_writer_blocks_even_when_build_is_readonly(self):
        with self.assertRaisesRegex(d.Stop, 'still executing'):
            recover.active_writers(self.make_api('in_progress'), 456, 'a' * 40)

    def test_queued_writer_without_the_shared_queue_is_not_safe(self):
        with self.assertRaisesRegex(d.Stop, 'common production queue'):
            recover.active_writers(self.make_api(broken_queue=True), 456, 'a' * 40)

    def test_incomplete_active_listing_is_never_absence_evidence(self):
        with self.assertRaisesRegex(d.Stop, 'truncated'):
            recover.active_writers(self.make_api(truncated=True), 456, 'a' * 40)

    def test_current_main_change_is_not_ignored(self):
        with self.assertRaisesRegex(d.Stop, 'Main changed'):
            recover.active_writers(self.make_api(), 456, 'b' * 40)

    def test_real_actions_yaml_trigger_keys_do_not_break_credential_scan(self):
        import yaml
        parsed = yaml.safe_load('name: Example\non:\n  push:\n  workflow_dispatch:\njobs:\n  deploy:\n    env:\n      ISEGYE_SFTP_PASSWORD: placeholder\n')
        self.assertTrue(recover.credential_bearing(parsed))

    def test_workflow_queued_before_job_creation_uses_each_actual_writer_queue(self):
        api = self.make_api()
        original = api.get
        def get(endpoint):
            result = original(endpoint)
            if endpoint.startswith('actions/runs?'):
                from urllib.parse import parse_qs
                status = parse_qs(endpoint.partition('?')[2])['status'][0]
                if status == 'in_progress':
                    result = {'total_count': 1, 'workflow_runs': result['workflow_runs'][:1]}
                elif status == 'queued':
                    row = original('actions/runs?status=in_progress&per_page=100&page=1')['workflow_runs'][1]
                    result = {'total_count': 1, 'workflow_runs': [dict(row, status='queued')]}
            elif endpoint.startswith('actions/runs/789/jobs'):
                result = {'total_count': 0, 'jobs': []}
            return result
        api.get = get
        result = recover.active_writers(api, 456, 'a' * 40)
        self.assertEqual(result['waitingWriters'], [{'runId': 789, 'state': 'queued_common_group'}])

    def test_in_progress_writer_without_job_evidence_remains_blocked(self):
        api = self.make_api(); original = api.get
        api.get = lambda endpoint: {'total_count': 0, 'jobs': []} if endpoint.startswith('actions/runs/789/jobs') else original(endpoint)
        with self.assertRaisesRegex(d.Stop, 'queue cannot be verified'):
            recover.active_writers(api, 456, 'a' * 40)


if __name__ == '__main__':
    unittest.main()
