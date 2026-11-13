import copy
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import batch_watchdog as w

class Watchdog(unittest.TestCase):
    def setUp(self):
        self.at=datetime(2026,11,13,14,22,tzinfo=w.KST)
        self.due=w.due_slot('albums',self.at)
    def test_album_quiet_window_boundaries(self):
        for hour in range(24):
            at=self.at.replace(hour=hour)
            self.assertEqual(w.due_slot('albums',at) is None, 1<=hour<7)
    def test_daily_and_previous_day(self):
        self.assertEqual(w.due_slot('music',self.at).astimezone(w.KST).hour,6)
        early=self.at.replace(hour=5)
        self.assertEqual(w.due_slot('music',early).astimezone(w.KST).day,12)
        self.assertEqual(w.due_slot('catalog',self.at).astimezone(w.KST).strftime('%H:%M'),'07:15')
    def test_schedule_before_five_uses_previous_hour(self):
        self.assertEqual(w.due_slot('schedule',self.at.replace(minute=4)).astimezone(w.KST).hour,13)
        self.assertEqual(w.due_slot('schedule',self.at.replace(minute=5)).astimezone(w.KST).hour,14)
    def test_history_not_due_until_first_new_sunday(self):
        self.assertIsNone(w.due_slot('history',self.at))
        self.assertEqual(w.due_slot('history',w.FIRST_WEEKLY).astimezone(w.KST),w.FIRST_WEEKLY)
    def test_future_and_naive_evidence_rejected(self):
        self.assertFalse(w.recent('2026-11-13T14:00:00',self.due,self.at))
        self.assertFalse(w.recent((self.at+timedelta(hours=1)).isoformat(),self.due,self.at))
    def test_green_without_evidence_is_not_success(self):
        for kind in ('music','schedule','history','albums'):
            self.assertFalse(w.evidence_ok(kind,{},self.due,self.at))
    def test_music_requires_all_channels_and_links_and_readback(self):
        pub={'status':'published','generatedAt':self.at.isoformat(),'verifiedReadback':True,
             'sourceStates':{str(i):'ok' for i in range(9)}}
        files={'music-publication.json':pub,'test-results/music-sources/source-audit.json':{'selected':151,'passed':151}}
        self.assertTrue(w.evidence_ok('music',files,self.due,self.at))
        pub['sourceStates']['0']='error'
        self.assertFalse(w.evidence_ok('music',files,self.due,self.at))
        pub['sourceStates']['0']='ok';pub['verifiedReadback']=False
        self.assertFalse(w.evidence_ok('music',files,self.due,self.at))
    def test_schedule_uses_source_clocks_not_stale_complete(self):
        sources={k:{'state':'complete','lastSuccessAt':self.at.isoformat()} for k in w.REQUIRED_SCHEDULE}
        pub={'status':'published','generatedAt':self.at.isoformat(),'collectionHealth':{'state':'complete','sources':sources}}
        files={'schedule-publication.json':pub,'schedule-health.json':{'verified':True}}
        self.assertTrue(w.evidence_ok('schedule',files,self.due,self.at))
        sources['cafe-members']['lastSuccessAt']=(self.at-timedelta(hours=4)).isoformat()
        self.assertFalse(w.evidence_ok('schedule',files,self.due,self.at))
    def test_albums_need_source_hour_and_real_published_restore(self):
        stamp=self.due.isoformat()
        data={'domesticCharts':{k:{'state':'ok','updatedAt':stamp} for k in ('melon_top100','melon_hot100')},
              'tracks':{'song':{'melon':{'trackId':'1'},'charts':{k:[{'at':stamp,'trackId':'1','rank':None,'status':'out'}] for k in ('melon_top100','melon_hot100')}}}}
        files={'albums/snapshot.json':data,'albums-restore.json':{'status':'restored','source':'cumulative-feed'}}
        self.assertTrue(w.evidence_ok('albums',files,self.due,self.at))
        files['albums-restore.json']['source']='seed'
        self.assertFalse(w.evidence_ok('albums',files,self.due,self.at))
    def test_active_jobs_never_dispatched_twice(self):
        for status in w.ACTIVE:
            self.assertEqual(w.recovery_action([{'status':status}],self.at,self.due,False),'active')
    def test_healthy_noop(self):
        self.assertEqual(w.recovery_action([],self.at,self.due,True),'healthy')
    def test_grace(self):
        self.assertEqual(w.recovery_action([],self.due+timedelta(minutes=3),self.due,False),'grace')
    def test_cooldown_uses_latest_attempt_time(self):
        run={'created_at':'2026-11-01T00:00:00Z','run_started_at':(self.at-timedelta(minutes=5)).isoformat(),'status':'completed'}
        self.assertEqual(w.recovery_action([run],self.at,self.due,False),'cooldown')
    def test_bounded_retry_budget(self):
        runs=[{'status':'completed','event':'workflow_dispatch','run_started_at':(self.at-timedelta(minutes=m)).isoformat()} for m in (20,40)]
        self.assertEqual(w.recovery_action(runs,self.at,self.due,False),'retry_budget')
    def test_missing_run_dispatch(self):
        self.assertEqual(w.recovery_action([],self.at,self.due,False),'dispatch')
    def test_manual_and_original_schedules_are_preserved(self):
        text=(ROOT/'.github/workflows/batch-watchdog.yml').read_text()
        self.assertNotIn('ISEGYE_SFTP_PASSWORD',text)
        self.assertIn('group: isegye-batch-watchdog',text)
        self.assertNotIn('group: isegye-inour-production',text)
        self.assertIn('with: {ref: main, persist-credentials: false}',text)
    def test_main_guard_rejects_branch_without_api(self):
        with patch.dict('os.environ',{'GITHUB_REPOSITORY':w.REPO,'GITHUB_REF':'refs/heads/other','GH_TOKEN':'test'}),patch.object(sys,'argv',['watchdog']),patch.object(w,'api') as api:
            with self.assertRaises(ValueError):w.main()
            api.assert_not_called()
    def test_artifact_current_attempt_digest_and_provenance(self):
        buff=io.BytesIO()
        with zipfile.ZipFile(buff,'w') as z:z.writestr('music-publication.json','{}')
        raw=buff.getvalue()
        run={'id':1,'run_attempt':2,'head_branch':'main','head_sha':'a'*40,'path':'.github/workflows/music-daily.yml','repository':{'full_name':w.REPO}}
        item={'id':7,'name':'daily-music-1-2','expired':False,'size_in_bytes':len(raw),'digest':'sha256:'+hashlib.sha256(raw).hexdigest(),'workflow_run':{'id':1,'head_sha':'a'*40}}
        def getter(path,**kwargs):return raw if kwargs.get('binary') else {'artifacts':[item]}
        self.assertEqual(w.artifact_files(run,'daily-music','music-daily.yml',getter),{'music-publication.json':{}})
        item['digest']='sha256:'+'0'*64
        with self.assertRaises(ValueError):w.artifact_files(run,'daily-music','music-daily.yml',getter)
    def test_api_endpoint_allowlist(self):
        with self.assertRaises(ValueError):w.api('https://other.invalid/secret')

if __name__=='__main__':unittest.main()
