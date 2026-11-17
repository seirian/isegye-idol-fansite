"""Monitoring regression tests: schedules, incomplete evidence, history, access."""
from pathlib import Path
from datetime import datetime, timedelta, timezone
import hashlib, io, json, os, subprocess, sys, tempfile, unittest, zipfile
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import batch_monitor_snapshot as m


def fixture_snapshot(at=None):
    at=at or datetime.now(timezone.utc)
    states=['healthy','running','attention','unknown','healthy','paused','healthy','healthy']
    rows=[]
    for i,(key,(name,schedule)) in enumerate(m.META.items()):
        due=m.policy.due_slot(key,at) if key not in ('production','watchdog') else None
        run={'id':1000+i,'attempt':1,'status':'in_progress' if states[i]=='running' else 'completed',
             'conclusion':None if states[i]=='running' else 'failure' if states[i]=='attention' else 'success',
             'createdAt':m.iso(at-timedelta(minutes=4)),'startedAt':m.iso(at-timedelta(minutes=3)),
             'jobStartedAt':m.iso(at-timedelta(minutes=2)),'durationSeconds':95,'queueSeconds':60,
             'url':f'https://github.com/{m.REPO}/actions/runs/{1000+i}/attempts/1'}
        row={'key':key,'name':name,'schedule':schedule,'state':states[i],'dataState':states[i],
             'dueAt':m.iso(due),'nextDueAt':m.next_due(key,at),'checkedAt':m.iso(at),
             'listingComplete':True,'run':run,'evidenceRun':run,'history':[run],
             'evidence':{'verifiedReadback':states[i]=='healthy','readbackAt':m.iso(at-timedelta(minutes=1))},
             'sources':[{'name':'SYNTHETIC_TEST_SOURCE','state':'ok','lastSuccessAt':m.iso(at)}],
             'steps':[{'name':'Synthetic test verification','status':'completed','conclusion':'success'}],
             'note':'SYNTHETIC TEST ONLY — 운영 자료가 아닙니다.'}
        if key=='albums':
            row['chartSlots']=[{'at':m.iso(at.replace(minute=0,second=0,microsecond=0)-timedelta(hours=x)),
                               'state':['healthy','partial','missing','paused','unknown'][x%5]} for x in reversed(range(168))]
            row['historicalGapCount']=5
        rows.append(row)
    return m.merge_observations({}, {'schemaVersion':1,'mode':'fixture','source':'SYNTHETIC TEST ONLY',
        'checkedAt':m.iso(at),'staleAfterSeconds':2700,'readOnly':True,'scheduledRefreshEnabled':False,
        'mainCommit':'a'*40,'batches':rows})


class MonitorPolicyTests(unittest.TestCase):
    def at(self,value):return m.stamp(value)
    def test_read_only_api_rejects_write(self):
        with patch.object(subprocess,'run') as run:
            for method in ('POST','PATCH','DELETE','PUT'):
                with self.assertRaises(ValueError):m.ReadOnlyGitHub()('git/ref/heads/main',method)
            run.assert_not_called()
    def test_allowlist_rejects_arbitrary_paths(self):
        with patch.object(subprocess,'run') as run:
            for path in ('actions/runs/12/rerun','issues','contents/auth/config.json','https://evil.test/','actions/workflows/evil.yml/runs?per_page=100'):
                with self.assertRaises(ValueError):m.ReadOnlyGitHub()(path)
            run.assert_not_called()
    def test_schedule_two_hour_boundary(self):
        at=self.at('2026-11-17T09:30:00+09:00')
        self.assertEqual(m.policy.due_slot('schedule',at),self.at('2026-11-17T08:05:00+09:00'))
        self.assertEqual(m.next_due('schedule',at),m.iso(self.at('2026-11-17T10:05:00+09:00')))
    def test_notice_before_midnight_slot(self):
        self.assertEqual(m.policy.due_slot('schedule',self.at('2026-11-17T00:04:00+09:00')),self.at('2026-11-16T22:05:00+09:00'))
    def test_album_night_pause_and_next(self):
        at=self.at('2026-11-17T01:00:00+09:00')
        self.assertIsNone(m.policy.due_slot('albums',at))
        self.assertEqual(m.next_due('albums',at),m.iso(self.at('2026-11-17T07:00:00+09:00')))
    def test_playground_previous_day(self):
        self.assertEqual(m.policy.due_slot('playground',self.at('2026-11-17T07:59:00+09:00')),self.at('2026-11-16T08:00:00+09:00'))
    def test_weekly_boundary(self):
        self.assertEqual(m.next_due('history',self.at('2026-11-17T10:00:00+09:00')),m.iso(self.at('2026-11-22T00:00:00+09:00')))
    def test_attempt_start_required(self):
        with self.assertRaises(ValueError):m.run_start({'run_attempt':2,'created_at':'2026-11-01T00:00:00Z'})
    def test_failed_execution_not_green(self):
        row={'listingComplete':True,'run':{'status':'completed','conclusion':'failure'},'dataState':'healthy'}
        self.assertEqual(m.row_state(row),'attention')
    def test_partial_listing_not_green(self):
        self.assertEqual(m.row_state({'listingComplete':False,'dataState':'healthy'}),'unknown')
    def test_paused_not_failure(self):
        self.assertEqual(m.row_state({'paused':True,'run':{'conclusion':'failure'}}),'paused')
    def test_latest_attempt_order(self):
        def run(rid,started):return {'id':rid,'run_attempt':2,'status':'completed','created_at':'2026-01-01T00:00:00Z','run_started_at':started,'head_branch':'main','path':'.github/workflows/music-daily.yml','repository':{'full_name':m.REPO},'head_repository':{'full_name':m.REPO}}
        entries=[run(2,'2026-11-17T01:00:00Z'),run(1,'2026-11-17T02:00:00Z')]
        rows,complete=m.listing(lambda p:{'total_count':2,'workflow_runs':entries},'music-daily.yml')
        self.assertTrue(complete);self.assertEqual(rows[0]['id'],1)
    def test_duplicate_listing_incomplete(self):
        row={'id':1,'head_branch':'other'}
        _,complete=m.listing(lambda p:{'total_count':2,'workflow_runs':[row,row]},'music-daily.yml')
        self.assertFalse(complete)
    def test_history_preserves_without_backfill(self):
        at=self.at('2026-11-17T03:00:00Z');old=fixture_snapshot(at-timedelta(days=1));new=fixture_snapshot(at)
        merged=m.merge_observations(old,new)
        self.assertGreater(len(merged['observations']),len(new['batches'])-2)
        self.assertTrue(all('batch' in i and 'dueAt' in i for i in merged['observations']))
    def test_history_excludes_secret_fields(self):
        doc=fixture_snapshot();old=json.loads(json.dumps(doc));old['observations'][0]['token']='DO_NOT_COPY'
        self.assertNotIn('DO_NOT_COPY',json.dumps(m.merge_observations(old,doc)))
    def test_history_excludes_future_and_expired(self):
        at=self.at('2026-11-17T03:00:00Z');new=fixture_snapshot(at)
        old={'schemaVersion':1,'observations':[{'batch':'music','dueAt':'2027-01-01T00:00:00Z','checkedAt':'2027-01-01T00:00:00Z','state':'healthy'}, {'batch':'music','dueAt':'2025-01-01T00:00:00Z','checkedAt':'2025-01-01T00:00:00Z','state':'healthy'}]}
        self.assertEqual(m.merge_observations(old,new)['observations'],fixture_snapshot(at)['observations'])
    def test_artifact_digest_and_attempt(self):
        raw=io.BytesIO()
        with zipfile.ZipFile(raw,'w') as z:z.writestr('batch-watchdog.json',json.dumps({'checkedAt':'2026-11-17T00:00:00Z'}))
        data=raw.getvalue();run={'id':42,'run_attempt':2,'head_sha':'a'*40}
        artifact={'id':7,'name':'batch-watchdog-42-2','size_in_bytes':len(data),'digest':'sha256:'+hashlib.sha256(data).hexdigest(),'workflow_run':{'id':42,'head_sha':'a'*40,'head_branch':'main'}}
        def get(path,binary=False):return data if binary else {'total_count':1,'artifacts':[artifact]}
        self.assertIn('checkedAt',m.extra_artifact(get,run,'batch-watchdog','batch-watchdog.json'))
        artifact['digest']='sha256:'+'0'*64
        with self.assertRaises(ValueError):m.extra_artifact(get,run,'batch-watchdog','batch-watchdog.json')
    def test_artifact_different_attempt_unavailable(self):
        run={'id':42,'run_attempt':2,'head_sha':'a'*40}
        with self.assertRaises(ValueError):m.extra_artifact(lambda p:{'total_count':1,'artifacts':[{'id':1,'name':'batch-watchdog-42-1'}]},run,'batch-watchdog','batch-watchdog.json')
    def test_naive_time_rejected(self):
        with self.assertRaises(ValueError):m.stamp('2026-11-17T01:00:00')
    def test_no_browser_token_or_mutation(self):
        source=(ROOT/'monitoring/monitor.js').read_text()
        for forbidden in ('innerHTML','Bearer','workflow_dispatch','method:'):
            self.assertNotIn(forbidden,source)
        self.assertIn('AbortController',source);self.assertIn('textContent',source)
        self.assertEqual(source.count('localStorage.setItem('),1)
        self.assertIn('localStorage.setItem(themeKey, theme)',source)
        self.assertIn("const themeKey = 'isegye:monitor-theme:v1'",source)


class MonitorAccessTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name).resolve()
        from deploy_batch_monitor import release_payload
        self.release,self.files,self.pointer=release_payload(fixture_snapshot())
        self.directory=self.root/'.batch-monitoring'/'releases'/self.release;self.directory.mkdir(parents=True)
        for name,data in self.files.items():(self.directory/name).write_bytes(data)
        (self.root/'.batch-monitoring/active.json').write_bytes(self.pointer)
    def tearDown(self):self.tmp.cleanup()
    def request(self,role=None,allowed=False,path='/ops/batches/data.json',method='GET'):
        code='require $argv[1]; require $argv[6]; $_SERVER["REQUEST_METHOD"]=$argv[5]; ob_start(); Isegye\\Access\\BatchMonitor::serve($argv[2],$argv[3],json_decode($argv[4],true)); $body=ob_get_clean(); echo json_encode([http_response_code(),$body]);'
        out=subprocess.check_output(['php','-r',code,str(ROOT/'monitoring/BatchMonitor.php'),str(self.root),path,json.dumps({'role':role,'allowed':allowed}),method,str(ROOT/'auth/View.php')])
        return json.loads(out)
    def test_guest_denied(self):self.assertEqual(self.request()[0],401)
    def test_member_denied(self):self.assertEqual(self.request('member',True)[0],403)
    def test_admin_denied_without_access(self):self.assertEqual(self.request('admin',False)[0],403)
    def test_admin_data_verified(self):
        code,body=self.request('admin',True);self.assertEqual(code,200);self.assertTrue(json.loads(body)['readOnly'])
    def test_all_assets_protected(self):
        for name in ('','monitor.js','monitor.css','data.json'):
            self.assertEqual(self.request(path='/ops/batches/'+name)[0],303 if name=='' else 401)
    def test_post_denied(self):self.assertEqual(self.request('admin',True,method='POST')[0],405)
    def test_head_empty(self):self.assertEqual(self.request('admin',True,method='HEAD'),[200,''])
    def test_unknown_route(self):self.assertEqual(self.request('admin',True,path='/ops/batches/config.json')[0],404)
    def test_corrupt_snapshot_denied(self):
        (self.directory/'data.json').write_text('{');self.assertEqual(self.request('admin',True)[0],503)
    def test_symlink_denied(self):
        (self.directory/'data.json').unlink();(self.directory/'data.json').symlink_to(self.root/'.batch-monitoring/active.json')
        self.assertEqual(self.request('admin',True)[0],503)
    def test_corrupt_manifest_denied(self):
        (self.directory/'manifest.json').write_text('{}');self.assertEqual(self.request('admin',True)[0],503)

if __name__=='__main__':unittest.main()
