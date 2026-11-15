"""Regression tests; all GitHub calls are fakes and never use live credentials."""
from contextlib import redirect_stdout
from datetime import datetime, timedelta
import copy
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import batch_watchdog as w

AT = datetime(2026, 11, 15, 14, 22, tzinfo=w.KST)
ENV = {'GITHUB_REPOSITORY':w.REPO, 'GITHUB_REF':'refs/heads/main', 'GH_TOKEN':'test-placeholder'}


def run(ident=1, kind='schedule', minutes=30, **changes):
    value = {'id':ident, 'run_attempt':1, 'status':'completed', 'conclusion':'failure',
             'event':'workflow_dispatch', 'head_branch':'main', 'head_sha':'a'*40,
             'path':'.github/workflows/'+w.SPECS[kind][0],
             'repository':{'full_name':w.REPO}, 'head_repository':{'full_name':w.REPO},
             'created_at':(AT-timedelta(days=1)).isoformat(),
             'run_started_at':(AT-timedelta(minutes=minutes)).isoformat()}
    value.update(changes)
    return value


def decision(state, kind='schedule', at=AT):
    return {'batch':kind, 'workflow':w.SPECS[kind][0], 'state':state,
            'dueAt':w.due_slot(kind, at).isoformat() if kind != 'production' else at.isoformat()}


class Reliability(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, ENV, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def test_second_page_old_run_recent_attempt_is_not_missed(self):
        first = [run(i, minutes=120) for i in range(1,101)]
        old = run(101, minutes=3, run_attempt=12, created_at='2026-10-01T00:00:00Z')
        getter = Mock(side_effect=[{'total_count':101,'workflow_runs':first},
                                   {'total_count':101,'workflow_runs':[old]}])
        runs = w.workflow_runs('schedule-refresh.yml', getter)
        self.assertEqual(runs[0]['id'], 101)
        self.assertEqual(w.recovery_action(runs, AT, w.due_slot('schedule',AT), False), 'cooldown')
        self.assertIn('per_page=100&page=2', getter.call_args_list[1].args[0])

    def test_older_page_active_run_blocks_duplicate(self):
        first = [run(i, minutes=120) for i in range(1,101)]
        getter = Mock(side_effect=[{'total_count':101,'workflow_runs':first},
                                   {'total_count':101,'workflow_runs':[run(101,status='waiting')]}])
        result = w.inspect_batch('schedule', AT, getter)
        self.assertEqual(result['state'], 'active')
        self.assertEqual(result['activeRuns'], [101])

    def test_incomplete_page_fails_closed(self):
        getter = Mock(return_value={'total_count':2,'workflow_runs':[run()]})
        with self.assertRaisesRegex(ValueError,'Incomplete'):
            w.workflow_runs('schedule-refresh.yml', getter)

    def test_history_limit_fails_closed(self):
        getter = Mock(return_value={'total_count':101,'workflow_runs':[run(i) for i in range(1,101)]})
        with self.assertRaisesRegex(ValueError,'budget'):
            w.workflow_runs('schedule-refresh.yml', getter, max_pages=1)

    def test_exact_limit_is_complete_when_total_count_matches(self):
        getter = Mock(return_value={'total_count':100,'workflow_runs':[run(i) for i in range(1,101)]})
        self.assertEqual(len(w.workflow_runs('schedule-refresh.yml',getter,max_pages=1)),100)

    def test_listing_provenance_is_required(self):
        for changes in ({'repository':{'full_name':'fork/other'}},
                        {'path':'.github/workflows/production.yml'}, {'id':'1'}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                w.workflow_runs('schedule-refresh.yml',
                    lambda *a, **kw: {'total_count':1,'workflow_runs':[run(**changes)]})

    def test_unapproved_workflow_is_never_requested(self):
        getter = Mock()
        with self.assertRaises(ValueError):w.workflow_runs('untrusted.yml', getter)
        getter.assert_not_called()

    def test_completion_between_reads_prevents_dispatch(self):
        getter = Mock()
        with patch.object(w,'inspect_batch',side_effect=[decision('dispatch'),decision('healthy')]):
            result = w.recover_batch('schedule', True, getter, lambda:AT)
        self.assertEqual(result['state'],'healthy')
        getter.assert_not_called()

    def test_recheck_honors_all_non_dispatch_states(self):
        for state in ('active','cooldown','retry_budget','grace','paused','healthy'):
            getter=Mock()
            with self.subTest(state=state), patch.object(w,'inspect_batch',
                    side_effect=[decision('dispatch'),decision(state)]):
                self.assertEqual(w.recover_batch('schedule',True,getter,lambda:AT)['state'],state)
                getter.assert_not_called()

    def test_only_one_fixed_main_dispatch_after_two_checks(self):
        getter=Mock(return_value={})
        with patch.object(w,'inspect_batch',side_effect=[decision('dispatch'),decision('dispatch')]) as inspect:
            result=w.recover_batch('schedule',True,getter,lambda:AT)
        self.assertEqual(inspect.call_count,2)
        getter.assert_called_once_with('actions/workflows/schedule-refresh.yml/dispatches','POST',{'ref':'main'})
        self.assertEqual(result['state'],'dispatched')
        self.assertNotEqual(result['state'],'healthy')

    def test_audit_mode_never_dispatches(self):
        getter=Mock()
        with patch.object(w,'inspect_batch',return_value=decision('dispatch')):
            self.assertEqual(w.recover_batch('schedule',False,getter,lambda:AT)['state'],'dispatch')
        getter.assert_not_called()

    def test_recheck_api_failure_never_dispatches(self):
        getter=Mock()
        with patch.object(w,'inspect_batch',side_effect=[decision('dispatch'),ValueError('incomplete')]):
            with self.assertRaises(ValueError):w.recover_batch('schedule',True,getter,lambda:AT)
        getter.assert_not_called()

    def test_mid_inspection_hour_boundary_does_not_reuse_old_decision(self):
        at=AT.replace(minute=59,second=59)
        getter=Mock()
        with patch.object(w,'inspect_batch',return_value=decision('dispatch','albums',at)):
            result=w.recover_batch('albums',True,getter,Mock(side_effect=[at,at,at+timedelta(seconds=1)]))
        self.assertEqual(result['state'],'slot_changed')
        getter.assert_not_called()

    def test_mid_inspection_night_boundary_never_dispatches(self):
        at=AT.replace(hour=0,minute=59,second=59)
        getter=Mock()
        with patch.object(w,'inspect_batch',return_value=decision('dispatch','albums',at)):
            result=w.recover_batch('albums',True,getter,Mock(side_effect=[at,at,at+timedelta(seconds=1)]))
        self.assertEqual(result['state'],'night_pause')
        getter.assert_not_called()

    def test_pause_controls_stop_before_api_reads(self):
        for kind,(_,_,pause) in w.SPECS.items():
            getter=Mock()
            with self.subTest(kind=kind), patch.dict(os.environ,{pause:'true'}):
                self.assertEqual(w.inspect_batch(kind,AT,getter)['state'],'paused')
                getter.assert_not_called()

    def test_new_attempt_after_inspection_clock_still_enters_cooldown(self):
        value=run(run_started_at=(AT+timedelta(seconds=1)).isoformat())
        self.assertEqual(w.recovery_action([value],AT,w.due_slot('schedule',AT),False),'cooldown')

    def test_implausible_future_attempt_fails_closed(self):
        value=run(run_started_at=(AT+timedelta(hours=1)).isoformat())
        with self.assertRaises(ValueError):w.recovery_action([value],AT,w.due_slot('schedule',AT),False)

    def test_current_healthy_past_gaps_not_live_incident(self):
        rows=[{'batch':'albums','state':'healthy','missingHours':{'melon_top100':4},'historicalGapsOnly':True}]
        self.assertEqual(w.report_state(rows),'checked')
        rows[0]['state']='dispatch'
        self.assertEqual(w.report_state(rows),'attention')

    def test_unfinished_states_are_pending_not_checked(self):
        for state in ('active','grace','cooldown','slot_changed'):
            with self.subTest(state=state):
                self.assertEqual(w.report_state([{'state':state}]),'pending')

    def test_schedule_explicit_failed_readback_is_rejected(self):
        sources={k:{'state':'complete','lastSuccessAt':AT.isoformat()} for k in w.REQUIRED_SCHEDULE}
        pub={'status':'published','generatedAt':AT.isoformat(),
             'collectionHealth':{'state':'complete','sources':sources}}
        files={'schedule-publication.json':pub,'schedule-health.json':{'verified':True}}
        due=w.due_slot('schedule',AT)
        self.assertTrue(w.evidence_ok('schedule',files,due,AT)) # historical reports have no flag
        pub['verifiedReadback']=False
        self.assertFalse(w.evidence_ok('schedule',files,due,AT))
        pub['verifiedReadback']=True
        self.assertTrue(w.evidence_ok('schedule',files,due,AT))

    def test_current_main_is_fetched_for_production_evidence(self):
        getter=Mock(return_value={'object':{'sha':'b'*40}})
        with patch.object(w,'workflow_runs',return_value=[run(kind='production',conclusion='success')]):
            result=w.inspect_batch('production',AT,getter)
        self.assertEqual(result['expectedHead'],'b'*40)
        self.assertEqual(result['state'],'dispatch')
        getter.assert_called_once_with('git/ref/heads/main')

    def test_global_pause_makes_main_a_noop(self):
        with tempfile.TemporaryDirectory() as d, patch.object(w,'ROOT',Path(d)), \
                patch.dict(os.environ,{'PRODUCTION_PAUSED':'true'}), \
                patch.object(sys,'argv',['watchdog','--apply']), patch.object(w,'api') as api, redirect_stdout(io.StringIO()):
            self.assertEqual(w.main(),0)
            self.assertEqual(json.loads((Path(d)/'batch-watchdog.json').read_text())['state'],'paused')
            api.assert_not_called()

    def test_workflow_keeps_cron_lock_main_checkout_and_no_secrets(self):
        text=(ROOT/'.github/workflows/batch-watchdog.yml').read_text()
        self.assertIn("cron: '12,32,52 * * * *'",text)
        self.assertIn('workflow_run:',text)
        self.assertIn('types: [completed]',text)
        self.assertIn('branches: [main]',text)
        self.assertIn('group: isegye-batch-watchdog',text)
        self.assertNotIn('group: isegye-inour-production',text)
        self.assertNotIn('secrets.',text)
        self.assertIn('with: {ref: main, persist-credentials: false}',text)
        triggers=text.split('  workflow_run:',1)[1].split('  push:',1)[0]
        self.assertNotIn('Batches - verified outcome recovery watchdog',triggers)
        self.assertNotIn('pull_request',triggers)


class CompletionTrust(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.file=Path(self.tmp.name)/'event.json'
        name=next(iter(w.COMPLETION_WORKFLOWS))
        self.source={'id':42,'name':name,'head_branch':'main','head_repository':{'full_name':w.REPO}}
        self.metadata=run(42,kind='albums',name=name,status='completed',event='workflow_dispatch')
        self.event={'action':'completed','workflow_run':self.source}
        self.env=patch.dict(os.environ,{**ENV,'GITHUB_EVENT_NAME':'workflow_run','GITHUB_EVENT_PATH':str(self.file)},clear=True)
        self.env.start();self.addCleanup(self.env.stop)

    def check(self,getter):
        self.file.write_text(json.dumps(self.event))
        return w.require_trusted_completion(getter)

    def test_allowed_same_repository_completion(self):
        getter=Mock(return_value=self.metadata)
        self.check(getter)
        getter.assert_called_once_with('actions/runs/42')

    def test_fork_or_non_main_event_is_rejected_without_lookup(self):
        for changes in ({'head_branch':'feature'}, {'head_repository':{'full_name':'someone/fork'}},
                        {'name':'Batches - verified outcome recovery watchdog'}, {'id':'42'}):
            with self.subTest(changes=changes):
                original=copy.deepcopy(self.source)
                self.source.update(changes)
                getter=Mock()
                with self.assertRaises(ValueError):self.check(getter)
                getter.assert_not_called()
                self.source.clear();self.source.update(original)

    def test_pr_or_mismatched_authoritative_run_is_rejected(self):
        for changes in ({'event':'pull_request'}, {'head_branch':'other'},
                        {'path':'.github/workflows/unknown.yml'},
                        {'repository':{'full_name':'someone/fork'}}, {'status':'in_progress'}):
            with self.subTest(changes=changes),self.assertRaises(ValueError):
                self.check(Mock(return_value={**self.metadata,**changes}))

    def test_ordinary_manual_or_schedule_trigger_needs_no_event_lookup(self):
        getter=Mock()
        with patch.dict(os.environ,{'GITHUB_EVENT_NAME':'workflow_dispatch'}):w.require_trusted_completion(getter)
        getter.assert_not_called()


if __name__=='__main__':unittest.main()
