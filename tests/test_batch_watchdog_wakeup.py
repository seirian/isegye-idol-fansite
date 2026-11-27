"""No live credentials or writes: exercise the external wake-up safety boundary."""
from datetime import datetime, timedelta
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import batch_watchdog as policy
import batch_watchdog_wakeup as wake

SHA = 'a'*40
AT = datetime(2026, 11, 24, 18, 22, tzinfo=policy.KST)
ENV = {'GITHUB_REPOSITORY': policy.REPO, 'GITHUB_REF': 'refs/heads/main',
       'GH_TOKEN': 'test-placeholder', 'GITHUB_EVENT_NAME': 'workflow_dispatch',
       'GITHUB_SHA': SHA, 'GITHUB_RUN_ID': '10000', 'GITHUB_RUN_ATTEMPT': '1'}


def run(ident=1, minutes=30, **changes):
    value = {'id': ident, 'run_attempt': 1, 'status': 'completed', 'conclusion': 'success',
             'event': 'schedule', 'head_branch': 'main', 'head_sha': SHA,
             'path': '.github/workflows/batch-watchdog.yml',
             'repository': {'full_name': policy.REPO}, 'head_repository': {'full_name': policy.REPO},
             'created_at': (AT-timedelta(days=10)).isoformat(),
             'run_started_at': (AT-timedelta(minutes=minutes)).isoformat()}
    value.update(changes)
    return value


def report(checked=None):
    checked = checked or AT-timedelta(minutes=2)
    rows = []
    for kind, (filename, _, _) in policy.SPECS.items():
        row = {'batch': kind, 'workflow': filename, 'state': 'healthy', 'checkedAt': checked.isoformat()}
        if kind == 'production':
            row['expectedHead'] = SHA
        else:
            due = policy.due_slot(kind, AT)
            row['dueAt'] = due.isoformat() if due else None
        rows.append(row)
    return {'checkedAt': checked.isoformat(), 'mode': 'apply', 'batches': rows, 'state': 'checked'}


class Fake:
    def __init__(self, runs=None, report_doc=None):
        self.runs = runs if runs is not None else [run()]
        self.report = report_doc
        self.calls = []
        self.posts = []
        self.history_passes = 0
        self.on_pass = None
        self.head = SHA

    def __call__(self, path, method='GET', payload=None, binary=False):
        self.calls.append((path, method))
        if method == 'POST':
            self.posts.append((path, payload))
            return {}
        if path == 'git/ref/heads/main':
            return {'object': {'sha': self.head}}
        if path.startswith(wake.PREFIX+'/runs?'):
            page = int(path.rsplit('page=', 1)[1])
            if page == 1:
                self.history_passes += 1
                if self.on_pass:
                    self.on_pass(self.history_passes)
            return {'total_count': len(self.runs), 'workflow_runs': copy.deepcopy(self.runs[(page-1)*100:page*100])}
        if '/artifacts?' in path:
            if self.report is None:
                return {'total_count': 0, 'artifacts': []}
            ident = int(path.split('/')[2])
            source = next(r for r in self.runs if r['id'] == ident)
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, 'w') as archive:
                archive.writestr('batch-watchdog.json', json.dumps(self.report))
            self.archive = buffer.getvalue()
            return {'total_count': 1, 'artifacts': [{
                'id': 900, 'name': f"batch-watchdog-{ident}-{source['run_attempt']}", 'expired': False,
                'size_in_bytes': len(self.archive), 'digest': 'sha256:'+hashlib.sha256(self.archive).hexdigest(),
                'workflow_run': {'id': ident, 'head_sha': source['head_sha'], 'head_branch': 'main'}}]}
        if path == 'actions/artifacts/900/zip' and binary:
            return self.archive
        raise AssertionError('Unexpected fake endpoint '+path)


class Wakeup(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, ENV, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def recover(self, fake, apply=True):
        return wake.recover(fake, SHA, apply=apply, now=lambda: AT)

    def test_scoped_history_never_queries_repository_wide_runs(self):
        fake = Fake([run(i) for i in range(1, 150)])
        result = self.recover(fake)
        self.assertEqual(result['state'], 'dispatched')
        self.assertEqual(result['inspection']['observedRuns'], 149)
        self.assertEqual(fake.posts, [(wake.PREFIX+'/dispatches', {'ref': 'main'})])
        self.assertFalse(any(path.startswith('actions/runs?') for path, _ in fake.calls))

    def test_old_created_recent_completed_attempt_on_second_page_blocks(self):
        rows = [run(i, minutes=120) for i in range(1, 101)]
        rows.append(run(101, minutes=3, run_attempt=12))
        fake = Fake(rows)
        self.assertEqual(self.recover(fake)['state'], 'cooldown')
        self.assertEqual(fake.posts, [])

    def test_all_active_states_block_including_old_runs(self):
        for status in policy.ACTIVE:
            with self.subTest(status=status):
                fake = Fake([run(status=status)])
                self.assertEqual(self.recover(fake)['state'], 'active')
                self.assertEqual(fake.posts, [])

    def test_current_verified_report_suppresses_wakeup(self):
        fake = Fake(report_doc=report())
        self.assertEqual(self.recover(fake)['state'], 'healthy')
        self.assertEqual(fake.posts, [])

    def test_failed_controller_or_incident_error_is_never_healthy(self):
        for problem in ('conclusion', 'incident', 'state'):
            doc = report()
            source = run()
            if problem == 'conclusion':
                source['conclusion'] = 'failure'
            elif problem == 'incident':
                doc['incidentError'] = 'GitHubAPIError'
            else:
                doc['state'] = 'inspection_failed'
            fake = Fake([source], doc)
            with self.subTest(problem=problem):
                self.assertEqual(self.recover(fake)['state'], 'dispatched')

    def test_new_slot_grace_is_preserved(self):
        at = AT.replace(minute=7)
        source = run(minutes=45)
        checked = at-timedelta(minutes=3)
        doc = report(checked)
        schedule = next(row for row in doc['batches'] if row['batch'] == 'schedule')
        schedule.update(state='healthy', dueAt=(policy.due_slot('schedule', at)-timedelta(hours=2)).isoformat())
        albums = next(row for row in doc['batches'] if row['batch'] == 'albums')
        albums['checkedAt'] = (at-timedelta(minutes=1)).isoformat()
        self.assertTrue(wake.report_is_current(doc, source, at, SHA, wake.slots(at)))
        self.assertFalse(wake.report_is_current(doc, source, at+timedelta(minutes=3), SHA, wake.slots(at+timedelta(minutes=3))))

    def test_old_report_and_wrong_slot_cannot_establish_current_success(self):
        for change in ('age', 'slot', 'pending', 'head'):
            doc = report()
            if change == 'age':
                doc['checkedAt'] = (AT-timedelta(minutes=50)).isoformat()
            elif change == 'slot':
                doc['batches'][1]['dueAt'] = (policy.due_slot('schedule', AT)-timedelta(hours=2)).isoformat()
            elif change == 'pending':
                doc['batches'][1]['state'] = 'cooldown'
            else:
                doc['batches'][-1]['expectedHead'] = 'b'*40
            fake = Fake([run(minutes=80)], doc)
            with self.subTest(change=change):
                self.assertEqual(self.recover(fake)['state'], 'dispatched')

    def test_missing_evidence_is_not_success_and_corrupt_evidence_blocks(self):
        fake = Fake()
        self.assertEqual(self.recover(fake)['controllerEvidence'], 'unavailable')
        fake = Fake(report_doc=report())
        delegate = fake.__call__
        def corrupt(path, **kwargs):
            value = delegate(path, **kwargs)
            return value+b'corrupt' if kwargs.get('binary') else value
        with self.assertRaisesRegex(ValueError, 'digest'):
            wake.recover(corrupt, SHA, apply=True, now=lambda: AT)
        self.assertEqual(fake.posts, [])

    def test_complete_history_required_even_if_repo_counts_are_large(self):
        fake = Fake([run(i) for i in range(1, 2283)])
        with self.assertRaises(policy.InspectionError) as caught:
            self.recover(fake)
        self.assertEqual(caught.exception.reason_code, 'run_history_budget_exceeded')
        self.assertEqual(fake.posts, [])

    def test_second_pass_observes_old_attempt_with_unchanged_total(self):
        fake = Fake()
        def change(number):
            if number == 2:
                fake.runs[0].update(run_attempt=2, run_started_at=(AT-timedelta(minutes=1)).isoformat())
        fake.on_pass = change
        result = self.recover(fake)
        self.assertEqual(result['state'], 'cooldown')
        self.assertTrue(result['recheckedBeforeDispatch'])
        self.assertEqual(fake.posts, [])

    def test_second_pass_success_prevents_dispatch(self):
        fake = Fake()
        fake.on_pass = lambda number: setattr(fake, 'report', report()) if number == 2 else None
        self.assertEqual(self.recover(fake)['state'], 'healthy')
        self.assertEqual(fake.posts, [])

    def test_pause_and_main_change_prevent_dispatch(self):
        fake = Fake()
        with patch.dict(os.environ, {'PRODUCTION_PAUSED': 'true'}):
            self.assertEqual(self.recover(fake)['state'], 'paused')
        self.assertEqual(fake.calls, [])
        fake = Fake()
        fake.on_pass = lambda number: setattr(fake, 'head', 'b'*40) if number == 2 else None
        self.assertEqual(self.recover(fake)['state'], 'policy_changed')
        self.assertEqual(fake.posts, [])

    def test_slot_boundary_invalidates_decision(self):
        fake = Fake()
        instants = iter([AT, AT, AT+timedelta(hours=1)])
        result = wake.recover(fake, SHA, apply=True, now=lambda: next(instants))
        self.assertEqual(result['state'], 'slot_changed')
        self.assertEqual(fake.posts, [])

    def test_final_head_read_crossing_slot_boundary_blocks(self):
        fake = Fake()
        current = [AT]
        head_reads = [0]
        def getter(path, **kwargs):
            value = fake(path, **kwargs)
            if path == 'git/ref/heads/main':
                head_reads[0] += 1
                if head_reads[0] == 3:
                    current[0] = AT+timedelta(hours=1)
            return value
        result = wake.recover(getter, SHA, apply=True, now=lambda: current[0])
        self.assertEqual(result['state'], 'slot_changed')
        self.assertEqual(fake.posts, [])

    def test_controller_cap_counts_created_requests_and_old_recent_attempts(self):
        rows = [run(1, minutes=25, event='workflow_dispatch'),
                run(2, minutes=35, event='workflow_dispatch')]
        fake = Fake(rows)
        self.assertEqual(self.recover(fake)['state'], 'retry_budget')
        self.assertEqual(fake.posts, [])

    def test_audit_runs_never_post(self):
        fake = Fake()
        self.assertEqual(self.recover(fake, apply=False)['state'], 'dispatch')
        self.assertEqual(fake.posts, [])

    def test_post_timeout_is_unknown_without_retry(self):
        fake = Fake()
        delegate = fake.__call__
        def uncertain(path, **kwargs):
            value = delegate(path, **kwargs)
            if kwargs.get('method') == 'POST':
                raise RuntimeError('private transport details')
            return value
        result = wake.recover(uncertain, SHA, apply=True, now=lambda: AT)
        self.assertEqual(result['state'], 'request_unknown')
        self.assertEqual(len(fake.posts), 1)
        self.assertNotIn('private transport', json.dumps(result))

    def test_api_blocks_other_targets_audit_writes_and_second_attempt(self):
        getter = Mock(return_value={})
        for target in ('actions/workflows/production.yml/dispatches', 'issues', 'https://other.invalid'):
            with self.assertRaises(wake.WakeupError):
                wake.API(apply=True, getter=getter)(target, method='POST', payload={'ref': 'main'})
        with self.assertRaises(wake.WakeupError):
            wake.API(getter=getter)(wake.PREFIX+'/dispatches', method='POST', payload={'ref': 'main'})
        getter.assert_not_called()
        api = wake.API(apply=True, getter=getter)
        api(wake.PREFIX+'/dispatches', method='POST', payload={'ref': 'main'})
        with self.assertRaises(wake.WakeupError):
            api(wake.PREFIX+'/dispatches', method='POST', payload={'ref': 'main'})
        self.assertEqual(getter.call_count, 1)

    def test_api_has_no_cache_and_enforces_budget(self):
        getter = Mock(return_value={'object': {'sha': SHA}})
        api = wake.API(getter=getter)
        api('git/ref/heads/main')
        api('git/ref/heads/main')
        self.assertEqual(getter.call_count, 2)
        api.calls = wake.MAX_CALLS
        with self.assertRaises(wake.WakeupError):
            api('git/ref/heads/main')

    def test_partition_queries_are_audit_only(self):
        path = wake.PREFIX+'/runs?branch=main&created=2026-11-01T00%3A00%3A00Z..2026-11-24T00%3A00%3A00Z&per_page=100&page=1'
        getter = Mock(return_value={'total_count': 0, 'workflow_runs': []})
        wake.API(getter=getter)(path)
        self.assertEqual(getter.call_count, 1)
        with self.assertRaises(wake.WakeupError):
            wake.API(apply=True, getter=getter)(path)
        self.assertEqual(getter.call_count, 1)

    def test_fork_and_missing_attempt_clock_block(self):
        for changes in ({'head_repository': {'full_name': 'other/repo'}},
                        {'run_attempt': 2, 'run_started_at': None}):
            fake = Fake([run(**changes)])
            with self.assertRaises(ValueError):
                self.recover(fake)
            self.assertEqual(fake.posts, [])

    def test_automatic_seed_cannot_enable_apply(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {'GITHUB_EVENT_NAME': 'push'}), \
                patch.object(wake, 'ROOT', Path(directory)), patch.object(sys, 'argv', ['wakeup', '--apply']), \
                patch.object(wake.policy, 'api') as api, patch('builtins.print'):
            self.assertEqual(wake.main(), 1)
            result = json.loads((Path(directory)/'batch-watchdog-wakeup.json').read_text())
            self.assertEqual(result['reasonCode'], 'seed_is_audit_only')
            self.assertFalse(result['requestAttempted'])
            api.assert_not_called()

    def test_workflow_is_isolated_without_new_cron_or_credentials(self):
        text = (ROOT/'.github/workflows/batch-watchdog-wakeup.yml').read_text()
        self.assertNotIn('cron:', text)
        self.assertNotIn('needs:', text)
        self.assertNotIn('SFTP', text)
        self.assertIn('group: isegye-watchdog-wakeup', text)
        self.assertNotIn('group: isegye-batch-watchdog\n', text)
        self.assertIn('with: {ref: main, persist-credentials: false}', text)


if __name__ == '__main__':
    unittest.main()
