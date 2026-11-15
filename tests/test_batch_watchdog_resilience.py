"""Regression coverage for missed triggers, completion provenance and dispatch races."""
import copy
from datetime import datetime, timedelta
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import batch_watchdog as w


class Resilience(unittest.TestCase):
    def setUp(self):
        self.at = datetime(2026, 11, 15, 14, 22, tzinfo=w.KST)
        self.due = w.due_slot('albums', self.at)

    def run_row(self, ident=1, minutes=25, **kw):
        row = {'id': ident, 'run_attempt': 1, 'head_branch': 'main',
               'repository': {'full_name': w.REPO}, 'head_repository': {'full_name': w.REPO},
               'path': '.github/workflows/albums-daily.yml', 'event': 'schedule',
               'status': 'completed', 'conclusion': 'failure',
               'created_at': '2026-11-01T00:00:00Z',
               'run_started_at': (self.at-timedelta(minutes=minutes)).isoformat()}
        row.update(kw)
        return row

    def event(self):
        return {'action': 'completed', 'repository': {'full_name': w.REPO},
                'workflow_run': self.run_row()}

    def test_completion_requires_fixed_main_source(self):
        getter = Mock(return_value=self.run_row())
        self.assertEqual(w.trusted_completion(self.event(), getter)['runId'], 1)
        getter.assert_called_once_with('actions/runs/1')

    def test_fork_pull_request_and_wrong_branch_are_rejected_before_lookup(self):
        for key, value in [('head_repository', {'full_name': 'fork/repo'}),
                           ('head_branch', 'topic'), ('event', 'pull_request'), ('id', '../other')]:
            event = self.event(); event['workflow_run'][key] = value
            getter = Mock()
            with self.assertRaises(ValueError): w.trusted_completion(event, getter)
            getter.assert_not_called()

    def test_unapproved_workflow_cannot_self_trigger_or_dispatch(self):
        for path in ('.github/workflows/batch-watchdog.yml', '.github/workflows/ci.yml'):
            with self.assertRaises(ValueError):
                w.trusted_completion(self.event(), Mock(return_value=self.run_row(path=path)))

    def test_completion_api_provenance_must_match(self):
        for changes in ({'repository': {'full_name': 'other/repo'}},
                        {'head_repository': {'full_name': 'other/repo'}},
                        {'head_branch': 'other'}, {'id': 2}, {'event': 'pull_request'}):
            with self.assertRaises(ValueError):
                w.trusted_completion(self.event(), Mock(return_value=self.run_row(**changes)))

    def test_rerun_is_sorted_by_latest_attempt_not_creation(self):
        new = self.run_row(2, 5, run_attempt=3)
        old = self.run_row(1, 30)
        getter = Mock(return_value={'workflow_runs': [old, new]})
        self.assertEqual(w.list_runs('albums-daily.yml', getter)[0]['id'], 2)
        self.assertIn('per_page=100', getter.call_args.args[0])

    def test_listing_refuses_wrong_path(self):
        with self.assertRaises(ValueError):
            w.list_runs('albums-daily.yml', Mock(return_value={'workflow_runs': [self.run_row(path='wrong')]}))

    def recheck(self, original, latest, at=None):
        return w.dispatch_recheck('albums', 'albums-daily.yml', at or self.at, self.due,
                                  original, False, Mock(return_value={'workflow_runs': latest}))

    def test_dispatch_rechecks_active_race(self):
        self.assertEqual(self.recheck([], [self.run_row(status='pending')]), 'active')

    def test_dispatch_rechecks_cooldown_race(self):
        self.assertEqual(self.recheck([], [self.run_row(minutes=3)]), 'cooldown')

    def test_dispatch_rechecks_rolling_hour_budget_race(self):
        rows = [self.run_row(i, m, event='workflow_dispatch') for i, m in ((1, 20), (2, 40))]
        self.assertEqual(self.recheck([], rows), 'retry_budget')

    def test_dispatch_refuses_new_completed_evidence(self):
        self.assertEqual(self.recheck([], [self.run_row(conclusion='success')]), 'evidence_changed')

    def test_dispatch_refuses_changed_attempt(self):
        self.assertEqual(self.recheck([self.run_row()], [self.run_row(run_attempt=2)]), 'evidence_changed')

    def test_next_slot_and_night_pause_do_not_use_stale_decision(self):
        self.assertEqual(self.recheck([], [], self.at.replace(hour=15)), 'slot_changed')
        self.assertEqual(self.recheck([], [], self.at.replace(hour=1)), 'night_pause')

    def test_grace_and_unchanged_overdue_work(self):
        self.assertEqual(self.recheck([], [], self.at.replace(minute=3)), 'grace')
        self.assertEqual(self.recheck([], []), 'dispatch')

    def test_completion_trigger_never_changes_primary_collection_schedules_or_lock(self):
        text = (ROOT/'.github/workflows/batch-watchdog.yml').read_text()
        self.assertIn('types: [completed]', text)
        self.assertIn('branches: [main]', text)
        self.assertIn("cron: '2,12,22,32,42,52 * * * *'", text)
        self.assertNotIn('ISEGYE_SFTP_PASSWORD', text)
        self.assertNotIn('group: isegye-inour-production', text)
        self.assertIn('with: {ref: main, persist-credentials: false}', text)
        for filename in ('albums-daily.yml','schedule-refresh.yml','music-daily.yml','history-monthly.yml','production.yml'):
            source = (ROOT/'.github/workflows'/filename).read_text()
            self.assertIn('group: isegye-inour-production', source)
            self.assertIn('queue: max', source)
            self.assertIn('cancel-in-progress: false', source)

    def test_timing_distinguishes_created_and_attempt_clock(self):
        result = w.timing_evidence([self.run_row()], self.due, self.at)
        self.assertEqual(result['slotAgeSeconds'], 22*60)
        self.assertNotEqual(result['latestRun']['created_at'], result['latestRun']['run_started_at'])

    def schedule_files(self):
        sources = {s: {'state':'complete','lastSuccessAt':self.at.isoformat()} for s in w.REQUIRED_SCHEDULE}
        return {'schedule-publication.json': {'status':'already_current','evidenceVersion':2,
            'verifiedReadback':True,'generatedAt':self.at.isoformat(),
            'collectionHealth': {'state':'complete','sources':sources}},
            'schedule-health.json': {'verified':True}}

    def test_same_slot_readback_is_valid_evidence_not_a_new_publication(self):
        files = self.schedule_files()
        self.assertTrue(w.evidence_ok('schedule', files, self.due, self.at))
        files['schedule-publication.json']['verifiedReadback'] = False
        self.assertFalse(w.evidence_ok('schedule', files, self.due, self.at))

    def test_new_publication_report_requires_readback_and_current_sources(self):
        files = self.schedule_files(); pub = files['schedule-publication.json']
        pub['status'] = 'published'; pub.pop('verifiedReadback')
        self.assertFalse(w.evidence_ok('schedule', files, self.due, self.at))
        pub['verifiedReadback'] = True
        pub['collectionHealth']['sources']['cafe-members']['lastSuccessAt'] = (self.at-timedelta(hours=1)).isoformat()
        self.assertFalse(w.evidence_ok('schedule', files, self.due, self.at))

    def test_global_pause_performs_no_lookup_or_dispatch(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(w,'ROOT',Path(tmp)), \
             patch.dict('os.environ', {'GITHUB_REPOSITORY':w.REPO,'GITHUB_REF':'refs/heads/main',
                                       'GH_TOKEN':'fixture','PRODUCTION_PAUSED':'true','GITHUB_EVENT_NAME':'schedule'}), \
             patch.object(sys,'argv',['watchdog','--apply']), patch.object(w,'api') as api:
            self.assertEqual(w.main(),0); api.assert_not_called()
            self.assertEqual(json.loads((Path(tmp)/'batch-watchdog.json').read_text())['state'],'paused')


if __name__ == '__main__': unittest.main()
