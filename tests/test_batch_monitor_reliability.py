"""Inspection outage, history preservation, trusted events and recovery regressions."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import copy, json, os, sys, tempfile, unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'));sys.path.insert(0,str(ROOT/'tests'))
import batch_monitor_snapshot as m
import batch_monitor_health as h
import batch_monitor_trigger as t
import batch_monitor_recovery as r
from test_batch_monitor import fixture_snapshot
from test_batch_monitor_production import MemoryRemote, StorageTransactions, document


class HistoryAndHealth(unittest.TestCase):
    def test_outage_keeps_last_verified_without_claiming_new_success(self):
        at=datetime.now(timezone.utc);old=fixture_snapshot(at-timedelta(minutes=50))
        current=fixture_snapshot(at)
        for row in current['batches']:row.update(dataState='unknown',state='unknown',inspectionError='execution_query_failed',listingComplete=False,lastVerifiedResult=None)
        current['collectorHealth']=h.inspection_health(current)
        m.merge_observations(old,current)
        self.assertEqual(current['collectorHealth']['state'],'failed')
        self.assertTrue(all(row['dataState']=='unknown' for row in current['batches']))
        self.assertIsNotNone(current['batches'][0]['lastVerifiedResult'])
        self.assertEqual(current['batches'][0]['lastVerifiedResult']['observedAt'],old['checkedAt'])
        self.assertIsNone(current['batches'][2]['lastVerifiedResult'])
    def test_complete_check_timestamp_not_reset_by_failed_attempt(self):
        at=datetime.now(timezone.utc);old=fixture_snapshot(at-timedelta(minutes=50))
        old['lastCompleteInspectionAt']=old['checkedAt']
        current=fixture_snapshot(at)
        for row in current['batches']:row.update(dataState='unknown',state='unknown',listingComplete=False)
        current['collectorHealth']=h.inspection_health(current)
        h.preserve_verified(old,current)
        self.assertEqual(current['lastCompleteInspectionAt'],old['checkedAt'])
    def test_batch_failure_is_not_inspector_failure(self):
        doc=fixture_snapshot()
        for row in doc['batches']:row.update(dataState='attention',listingComplete=True)
        self.assertEqual(h.inspection_health(doc)['state'],'ok')
    def test_unknown_publication_does_not_count_as_failed_read(self):
        doc=fixture_snapshot()
        for row in doc['batches']:
            row.update(dataState='healthy',listingComplete=True)
            row.pop('inspectionError',None)
        doc['batches'][3]['dataState']='unknown'
        result=h.inspection_health(doc)
        self.assertEqual((result['state'],result['inspected'],result['failed'],result['unresolved']),('ok',8,0,1))
        self.assertIsNone(h.verified_summary(doc['batches'][3],h.clock(doc['checkedAt'])))
    def test_partial_api_failure_is_degraded(self):
        doc=fixture_snapshot()
        for row in doc['batches']:row.update(dataState='healthy',listingComplete=True)
        doc['batches'][0].update(dataState='unknown',inspectionError='execution_query_failed',listingComplete=False)
        quality=h.inspection_health(doc)
        self.assertEqual((quality['state'],quality['failed'],quality['inspected']),('degraded',1,7))
    def test_current_main_deployment_is_pending_without_old_artifact(self):
        at=datetime.now(timezone.utc);head='a'*40
        current={'id':123,'run_attempt':1,'head_sha':head,'status':'in_progress',
                 'created_at':at.isoformat(),'run_started_at':at.isoformat()}
        previous={**current,'id':122,'head_sha':'b'*40,'status':'completed','conclusion':'success'}
        with patch.dict(os.environ,{'PRODUCTION_PAUSED':''}),patch.object(m,'listing',return_value=([current,previous],True)),\
             patch.object(m,'extra_artifact',side_effect=AssertionError('no old artifact reads')):
            row=m.inspect('production',at,head,lambda _: {'jobs':[],'total_count':0})
        self.assertEqual((row['state'],row['dataState'],row['listingComplete']),('running','running',True))
        self.assertNotIn('inspectionError',row)
        self.assertNotIn('evidenceRun',row)
    def test_catalog_waits_for_current_main_deployment(self):
        at=datetime.now(timezone.utc);doc=fixture_snapshot(at)
        production=next(row for row in doc['batches'] if row['key']=='production')
        production['dataState']='running'
        production['run']={'status':'in_progress','commit':doc['mainCommit']}
        catalog=next(row for row in doc['batches'] if row['key']=='catalog')
        catalog.update(paused=False,listingComplete=True,dataState='unknown')
        with patch.object(m,'extra_artifact',side_effect=AssertionError('no release verification yet')):
            m.attach_catalog_publication(doc,at,None)
        self.assertEqual(catalog['dataState'],'running')
        self.assertIn('배포가 진행 중',catalog['note'])
        self.assertNotIn('inspectionError',catalog)
    def test_history_does_not_copy_arbitrary_fields(self):
        at=datetime.now(timezone.utc)
        record={'observedAt':at.isoformat(),'kind':'publication','token':'must-not-copy','privateUser':'must-not-copy'}
        self.assertNotIn('token',h.clean_summary(record,at));self.assertNotIn('privateUser',h.clean_summary(record,at))
    def test_invalid_history_clocks_rejected(self):
        at=datetime.now(timezone.utc)
        for observed in (at+timedelta(seconds=1),at-timedelta(days=91)):
            self.assertIsNone(h.clean_summary({'observedAt':observed.isoformat(),'kind':'publication'},at))
    def test_same_slot_verified_observation_survives_query_failure(self):
        at=datetime.now(timezone.utc).replace(hour=4,minute=30,second=0,microsecond=0)
        old=fixture_snapshot(at-timedelta(minutes=1));new=fixture_snapshot(at)
        for row in new['batches']:row['dataState']='unknown'
        original=next(v for v in old['observations'] if v['batch']=='albums')
        m.merge_observations(old,new)
        self.assertEqual(next(v for v in new['observations'] if v['batch']=='albums'),original)
    def test_all_api_failure_records_failed_quality(self):
        with patch.dict(os.environ,{'MONITOR_COMMIT':'a'*40}):
            doc=m.collect(lambda *a,**kw:(_ for _ in ()).throw(RuntimeError('private failure')))
        self.assertEqual(doc['collectorHealth']['state'],'failed')
        self.assertEqual(doc['collectorHealth']['failed'],8)
        self.assertNotIn('private failure',json.dumps(doc))
    def test_main_reports_failure_after_writing_diagnostics(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(m,'ROOT',Path(folder)),patch.dict(os.environ,{'GITHUB_REPOSITORY':m.REPO,'GITHUB_REF':'refs/heads/main','MONITOR_COMMIT':'a'*40}):
            with patch.object(m,'ReadOnlyGitHub',return_value=lambda *a,**kw:(_ for _ in ()).throw(RuntimeError('fixture'))):
                self.assertEqual(m.main(),1)
            public=json.loads((Path(folder)/'batch-monitor-inspection.json').read_text())
            self.assertNotIn('batches',public)
            self.assertTrue((Path(folder)/'monitoring-dist/data.json').exists())
    def test_atomic_publication_preserves_history_on_failed_inspection(self):
        remote=MemoryRemote();old=document(datetime.now(timezone.utc)-timedelta(minutes=5))
        for row in old['batches']:row.update(checkedAt=old['checkedAt'],dataState='healthy',listingComplete=True)
        h.preserve_verified({},old)
        _,point=remote.install(old);remote.files[r_store.FOLDER+'/active.json']=point
        current=document()
        for row in current['batches']:row.update(dataState='unknown',state='unknown',listingComplete=False,inspectionError='execution_query_failed')
        current['collectorHealth']=h.inspection_health(current)
        report=StorageTransactions().run_refresh(remote,current)
        self.assertEqual(report['collectorHealth']['state'],'failed')
        self.assertEqual(report['preservedVerifiedResults'],8)


# Import only the existing storage test adapter; never a real server identity.
import batch_monitor_storage as r_store


class CompletionTrust(unittest.TestCase):
    def event(self,name=None):
        name=name or next(iter(t.COMPLETIONS))
        source={'id':42,'name':name,'head_branch':'main','head_repository':{'full_name':m.REPO}}
        run=dict(source,repository={'full_name':m.REPO},path='.github/workflows/'+t.COMPLETIONS[name],status='completed',event='schedule',conclusion='failure')
        return {'action':'completed','workflow_run':source},run
    def test_all_eight_completed_workflows_including_failure_and_cancel(self):
        for name in t.COMPLETIONS:
            event,run=self.event(name)
            for conclusion in ('success','failure','cancelled','timed_out','skipped'):
                run['conclusion']=conclusion;self.assertTrue(t.validate(event,lambda _:run))
    def test_monitor_self_and_untrusted_forks_rejected(self):
        event,run=self.event()
        event['workflow_run']['name']='Batch monitoring - administrator-only production status'
        with self.assertRaises(ValueError):t.validate(event,lambda _:run)
        event,run=self.event();event['workflow_run']['head_repository']={'full_name':'other/repo'}
        with self.assertRaises(ValueError):t.validate(event,lambda _:run)
    def test_authoritative_pr_run_or_path_mismatch_rejected(self):
        for key,val in [('event','pull_request'),('path','.github/workflows/wrong.yml'),('head_branch','feature/test')]:
            event,run=self.event();run[key]=val
            with self.assertRaises(ValueError):t.validate(event,lambda _:run)


class Recovery(unittest.TestCase):
    def test_fixed_dispatch_target_only(self):
        with patch.object(r.subprocess,'run') as call:
            for path,payload in [('actions/workflows/albums-daily.yml/dispatches',{'ref':'main'}),(r.PREFIX+'/dispatches',{'ref':'feature/test'}),('issues',{})]:
                with self.assertRaises(ValueError):r.API()(path,method='POST',payload=payload)
            call.assert_not_called()
    def test_active_old_rerun_blocks_recovery(self):
        with patch.object(r,'read_runs',return_value=[{'id':1}]):
            self.assertEqual(r.inspect(None,datetime.now(timezone.utc))['state'],'active')
    def test_race_prevents_second_dispatch(self):
        with patch.object(r,'inspect',side_effect=[{'state':'dispatch'},{'state':'active'}]),patch.object(r,'API') as api:
            self.assertEqual(r.recover(api,datetime.now(timezone.utc),True)['state'],'active');api.assert_not_called()
    def test_only_one_fixed_dispatch(self):
        with patch.object(r,'inspect',return_value={'state':'dispatch'}),patch.object(r,'API') as api:
            self.assertEqual(r.recover(api,datetime.now(timezone.utc),True)['state'],'dispatched')
            api.assert_called_once_with(r.PREFIX+'/dispatches',method='POST',payload={'ref':'main'})
    def test_dispatch_succeeds_as_request_but_not_verified_monitor(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(r,'ROOT',Path(tmp)),\
             patch.dict(os.environ,{'GITHUB_REPOSITORY':m.REPO,'GITHUB_REF':'refs/heads/main'}),\
             patch.object(r,'recover',return_value={'state':'dispatched','reason':'monitor_only_recovery_requested'}):
            self.assertEqual(r.main(),0)
            result=json.loads((Path(tmp)/'batch-monitor-recovery.json').read_text())
        self.assertEqual(result['state'],'dispatched')
        self.assertTrue(result['recoveryRequestSent'])
        self.assertFalse(result['monitorVerified'])
    def test_exhausted_recovery_budget_still_fails(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(r,'ROOT',Path(tmp)),\
             patch.dict(os.environ,{'GITHUB_REPOSITORY':m.REPO,'GITHUB_REF':'refs/heads/main'}),\
             patch.object(r,'recover',return_value={'state':'retry_budget','reason':'two_monitor_dispatches_per_hour'}):
            self.assertEqual(r.main(),1)
            result=json.loads((Path(tmp)/'batch-monitor-recovery.json').read_text())
        self.assertFalse(result['recoveryRequestSent'])
        self.assertFalse(result['monitorVerified'])
    def test_partial_or_corrupt_read_never_dispatches(self):
        with patch.object(r,'inspect',side_effect=ValueError('incomplete')),patch.object(r,'API') as api:
            with self.assertRaises(ValueError):r.recover(api,datetime.now(timezone.utc),True)
            api.assert_not_called()
    def recent_run(self,at,minutes):
        return {'id':minutes,'run_attempt':1,'head_sha':'a'*40,'status':'completed','conclusion':'failure','event':'workflow_dispatch',
                'created_at':(at-timedelta(minutes=minutes)).isoformat(),'run_started_at':(at-timedelta(minutes=minutes)).isoformat()}
    def inspect_runs(self,runs,at):
        with patch.object(r,'read_runs',side_effect=[[] for _ in r.ACTIVE]+[runs]),patch.object(r,'extra_artifact',side_effect=m.policy.EvidenceUnavailable('missing')):
            return r.inspect(None,at)
    def test_cooldown_and_two_requests_per_hour(self):
        at=datetime.now(timezone.utc)
        self.assertEqual(self.inspect_runs([self.recent_run(at,10)],at)['state'],'cooldown')
        self.assertEqual(self.inspect_runs([self.recent_run(at,20),self.recent_run(at,40)],at)['state'],'retry_budget')
        self.assertEqual(self.inspect_runs([self.recent_run(at,20)],at)['state'],'dispatch')
    def test_integrity_error_fails_closed_instead_of_recovering(self):
        at=datetime.now(timezone.utc)
        with patch.object(r,'read_runs',side_effect=[[] for _ in r.ACTIVE]+[[self.recent_run(at,20)]]),patch.object(r,'extra_artifact',side_effect=ValueError('digest mismatch')):
            with self.assertRaises(ValueError):r.inspect(None,at)
    def test_recovery_workflow_no_sftp_and_no_self_loop(self):
        text=(ROOT/'.github/workflows/batch-monitoring-health.yml').read_text()
        self.assertNotIn('ISEGYE_SFTP_PASSWORD',text);self.assertNotIn('workflow_run:',text)
        self.assertIn('cancel-in-progress: false',text)
        monitor=(ROOT/'.github/workflows/batch-monitoring.yml').read_text()
        for name in t.COMPLETIONS:self.assertIn(name,monitor)
        self.assertNotIn("conclusion == 'success'",monitor)
        self.assertIn('continue-on-error: true',monitor)
        self.assertIn("collectorHealth']['state']=='ok'",monitor)

if __name__=='__main__':unittest.main()
