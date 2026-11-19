"""No live identities, queue, network or batch mutations in these tests."""
from pathlib import Path
from datetime import datetime,timedelta,timezone
import json,os,subprocess,sys,tempfile,unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import batch_manual_worker as worker

class QueueTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.folder=self.root/'.batch-monitoring/control';self.folder.mkdir(parents=True)
        (self.folder/'.owner').write_bytes(worker.MARKER);(self.folder/'.htaccess').write_text('Require all denied\n')
    def php(self,code,*args):
        prefix='require $argv[1];require $argv[2];$_SESSION=["csrf"=>str_repeat("c",64),"account"=>str_repeat("a",64)];'
        out=subprocess.check_output(['php','-r',prefix+code,str(ROOT/'monitoring/BatchManual.php'),str(ROOT/'auth/Session.php'),str(self.root),*[json.dumps(a) for a in args]])
        return json.loads(out)
    def submit(self,action='enqueue',batch='music',ident='1'*32):
        return self.php('echo json_encode(Isegye\\Access\\BatchManual::submit($argv[3],json_decode($argv[4],true),str_repeat("a",64)));',{'action':action,'id':ident,'batch':batch,'confirm':batch})
    def work(self,action,**kwargs):
        role=kwargs.pop('role','admin');allowed=kwargs.pop('allowed',True)
        return self.php('echo json_encode(Isegye\\Access\\BatchManual::work($argv[3],json_decode($argv[4],true),"123",fn($id)=>json_decode($argv[5],true)));',{'action':action,**kwargs},{'role':role,'allowed':allowed})
    def saved(self):return json.loads((self.folder/'queue.json').read_text())
    def test_idempotency(self):
        self.assertEqual(self.submit()['code'],202);self.assertEqual(self.submit()['code'],200);self.assertEqual(len(self.saved()['requests']),1)
    def test_duplicate_pending_blocked(self):
        self.submit();self.assertEqual(self.submit(ident='2'*32)['code'],409)
    def test_cancel_does_not_execute(self):
        self.submit();self.assertEqual(self.submit('cancel')['request']['state'],'cancelled');self.assertFalse(self.work('claim')['pending'])
    def test_begin_requires_live_admin(self):
        self.submit();self.work('claim');self.assertFalse(self.work('begin',id='1'*32,role='member')['allowed'])
    def test_revoked_before_claim(self):
        self.submit();self.assertFalse(self.work('claim',allowed=False)['pending']);self.assertEqual(self.saved()['requests']['1'*32]['reason'],'administrator_revoked')
    def test_single_attempt(self):
        self.submit();self.assertEqual(len(self.work('claim')['pending']),1);self.assertFalse(self.work('claim')['pending']);self.assertTrue(self.work('begin',id='1'*32)['allowed']);self.assertFalse(self.work('claim')['pending'])
    def test_ambiguous_not_retried(self):
        self.submit();self.work('claim');self.work('begin',id='1'*32);self.work('settle',id='1'*32,state='unknown',reason='dispatch_unconfirmed')
        self.assertEqual(self.submit(ident='2'*32)['code'],409);self.assertFalse(self.work('claim')['pending'])
    def test_tracking_exact_run(self):
        self.submit();self.work('claim');self.work('begin',id='1'*32);self.work('settle',id='1'*32,state='accepted',reason='accepted',runId=77)
        self.assertEqual(self.work('claim')['tracking'][0]['runId'],77);self.work('status',id='1'*32,runId=77,conclusion='success')
        self.assertEqual(self.saved()['requests']['1'*32]['state'],'completed')
    def test_queue_expiry(self):
        self.submit();db=self.saved();db['requests']['1'*32]['at']-=1201;(self.folder/'queue.json').write_text(json.dumps(db))
        self.assertFalse(self.work('claim')['pending']);self.assertEqual(self.saved()['requests']['1'*32]['state'],'expired')
    def test_cooldown(self):
        self.submit();self.submit('cancel');self.assertEqual(self.submit(ident='2'*32)['code'],429)
    def test_unknown_explicit_resolution(self):
        self.submit();self.work('claim');self.work('begin',id='1'*32);self.work('settle',id='1'*32,state='unknown',reason='dispatch_unconfirmed')
        self.assertEqual(self.submit('resolve')['request']['state'],'resolved')
    def test_status_never_exposes_actor(self):
        self.submit();data=self.work('claim');self.assertNotIn('actor',json.dumps(data));self.assertNotIn('a'*64,json.dumps(data))
    def test_access_boundary(self):
        for role,allowed,expected in [(None,False,401),('member',True,403),('admin',False,403),('admin',True,200)]:
            result=self.php('$_SERVER["REQUEST_METHOD"]="GET";ob_start();Isegye\\Access\\BatchManual::serve($argv[3],"/ops/batches/control",json_decode($argv[4],true),"https://isegye-idol.kr");$v=ob_get_clean();echo json_encode([http_response_code(),$v]);',{'role':role,'allowed':allowed})
            self.assertEqual(result[0],expected)
            if expected!=200:self.assertNotIn('csrf',result[1])
    def test_csrf_required(self):
        result=self.php('$_SERVER["REQUEST_METHOD"]="POST";$_SERVER["HTTP_ORIGIN"]="https://evil.test";ob_start();Isegye\\Access\\BatchManual::serve($argv[3],"/ops/batches/control",["role"=>"admin","allowed"=>true],"https://isegye-idol.kr");$v=ob_get_clean();echo json_encode([http_response_code(),$v]);')
        self.assertEqual(result[0],403);self.assertFalse((self.folder/'queue.json').exists())
    def test_private_symlink_denied(self):
        target=self.root/'foreign';target.write_text('{}');(self.folder/'queue.json').symlink_to(target)
        result=self.php('$_SERVER["REQUEST_METHOD"]="GET";ob_start();Isegye\\Access\\BatchManual::serve($argv[3],"/ops/batches/control",["role"=>"admin","allowed"=>true],"https://isegye-idol.kr");ob_end_clean();echo json_encode(http_response_code());')
        self.assertEqual(result,503);self.assertEqual(target.read_text(),'{}')
    def test_worker_unauthenticated(self):
        result=self.php('$_SERVER["REQUEST_METHOD"]="POST";ob_start();Isegye\\Access\\BatchManual::agent($argv[3],fn($id)=>["role"=>"admin","allowed"=>true]);ob_end_clean();echo json_encode(http_response_code());')
        self.assertEqual(result,404)

class WorkerPolicy(unittest.TestCase):
    at=datetime(2026,11,17,4,0,tzinfo=timezone.utc)
    def api(self,path,**kwargs):
        if path=='git/ref/heads/main':return {'object':{'sha':'a'*40}}
        if '/runs?' in path:return {'total_count':0,'workflow_runs':[]}
        return {'state':'active','path':'.github/workflows/music-daily.yml'}
    def run_fixture(self,**changes):
        return {'id':2,'head_branch':'main','head_sha':'a'*40,'path':'.github/workflows/music-daily.yml','repository':{'full_name':worker.REPO},'head_repository':{'full_name':worker.REPO},'status':'completed','event':'workflow_dispatch','created_at':(self.at-timedelta(minutes=20)).isoformat(),**changes}
    def test_allowed(self):self.assertEqual(worker.decision(self.api,'music',self.at,{}),'allowed')
    def test_global_and_individual_pause(self):
        for name in ('PRODUCTION_PAUSED','ISEGYE_MANUAL_PAUSED','ISEGYE_MUSIC_PAUSED'):
            self.assertEqual(worker.decision(lambda *a: self.fail('must not read'), 'music',self.at,{name:'true'}),'paused')
    def test_night_pause(self):self.assertEqual(worker.decision(self.api,'albums',self.at.replace(hour=19),{}),'night_pause')
    def test_active_before_mutation(self):
        def api(path,**kw):return {'total_count':1,'workflow_runs':[self.run_fixture(status='in_progress')]} if '/runs?' in path else self.api(path)
        self.assertEqual(worker.decision(api,'music',self.at,{}),'existing_run')
    def test_incomplete_history_fails_closed(self):
        with self.assertRaises(ValueError):worker.runs(lambda *a:{'total_count':2,'workflow_runs':[self.run_fixture()]},'music-daily.yml',{})
    def test_fork_run_rejected(self):
        with self.assertRaises(ValueError):worker.trusted_run(self.run_fixture(head_repository={'full_name':'other/fork'}),'music-daily.yml')
    def test_actual_transport_allows_only_bound_endpoints(self):
        from unittest.mock import MagicMock
        response=MagicMock();response.__enter__.return_value.read.return_value=b'{}'
        opener=MagicMock();opener.open.return_value=response
        with patch.dict(os.environ,{'GH_TOKEN':'synthetic-only'}), patch.object(worker.urllib.request,'build_opener',return_value=opener):
            api=worker.GitHub()
            for path in ['git/ref/heads/main','actions/runs/123','actions/workflows/music-daily.yml','actions/workflows/music-daily.yml/runs?branch=main&status=pending']:
                self.assertEqual(api(path),{})
            self.assertEqual(api('actions/workflows/music-daily.yml/dispatches',method='POST',payload={'ref':'main'}),{})
            self.assertEqual(opener.open.call_count,5)
            req=opener.open.call_args.args[0]
            self.assertEqual(req.method,'POST');self.assertEqual(json.loads(req.data),{'ref':'main'})
            self.assertEqual(req.get_header('X-github-api-version'),worker.API_VERSION)
    def test_target_and_branch_allowlist(self):
        for path,payload in [('issues',{}),('actions/workflows/music-daily.yml/dispatches',{'ref':'feature/other'}),('actions/workflows/unknown.yml/dispatches',{'ref':'main'})]:
            with self.assertRaises(ValueError):worker.GitHub()(path,method='POST',payload=payload)
    def process(self,api=None,decision='allowed'):
        calls=[]
        def agent(value):
            calls.append(value)
            if value['action']=='claim':return {'version':1,'pending':[{'id':'1'*32,'batch':'music'}],'tracking':[]}
            return {'allowed':True}
        with patch.object(worker,'decision',return_value=decision):
            result=worker.process(api or self.api,agent,'a'*40,{},now=lambda:self.at)
        return result,calls
    def test_no_retry_on_ambiguous_dispatch(self):
        posts=[]
        def api(path,**kw):
            if kw.get('method')=='POST':posts.append(path);raise TimeoutError()
            return self.api(path)
        result,calls=self.process(api);self.assertEqual(len(posts),1);self.assertEqual(result['unconfirmed'],1);self.assertEqual(calls[-1]['state'],'unknown')
    def test_mark_before_post_and_validate_id(self):
        posts=[]
        def api(path,**kw):
            if kw.get('method')=='POST':posts.append(path);return {'workflow_run_id':2}
            if path=='actions/runs/2':return self.run_fixture()
            return self.api(path)
        result,calls=self.process(api);self.assertEqual(result['accepted'],1);self.assertEqual([v['action'] for v in calls],['claim','begin','settle']);self.assertEqual(calls[-1]['runId'],2);self.assertEqual(len(posts),1)
    def test_block_does_not_dispatch(self):
        result,calls=self.process(decision='existing_run');self.assertEqual(result['blocked'],1);self.assertNotIn('begin',[v['action'] for v in calls])
    def test_legacy_204_does_not_fabricate_run(self):
        def api(path,**kw):return {} if kw.get('method')=='POST' else self.api(path)
        result,calls=self.process(api);self.assertEqual(result['unconfirmed'],1);self.assertNotIn('runId',calls[-1])

    def test_superseded_main_is_safe_noop(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(worker,'ROOT',Path(tmp)),\
             patch.dict(os.environ,{'GITHUB_REPOSITORY':worker.REPO,'GITHUB_REF':'refs/heads/main',
                                   'GITHUB_SHA':'a'*40,'ISEGYE_SFTP_PASSWORD':'synthetic','GITHUB_EVENT_NAME':'schedule'}),\
             patch.object(worker,'GitHub',return_value=lambda _: {'object':{'sha':'b'*40}}),\
             patch.object(worker.subprocess,'check_output',return_value='a'*40+'\n'),\
             patch.object(worker.socket,'create_connection',side_effect=AssertionError('never connect')):
            self.assertEqual(worker.main(),0)
            report=json.loads((Path(tmp)/'batch-manual-worker.json').read_text())
        self.assertEqual(report['status'],'superseded')
        self.assertFalse(report['realUserRequestCreated'])
        self.assertNotIn('runtime',report)
    def test_stale_event_sha_is_safe_noop(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(worker,'ROOT',Path(tmp)),\
             patch.dict(os.environ,{'GITHUB_REPOSITORY':worker.REPO,'GITHUB_REF':'refs/heads/main',
                                   'GITHUB_SHA':'b'*40,'ISEGYE_SFTP_PASSWORD':'synthetic','GITHUB_EVENT_NAME':'schedule'}),\
             patch.object(worker,'GitHub',return_value=lambda _: {'object':{'sha':'a'*40}}),\
             patch.object(worker.subprocess,'check_output',return_value='a'*40+'\n'),\
             patch.object(worker.socket,'create_connection',side_effect=AssertionError('never connect')):
            self.assertEqual(worker.main(),0)
            report=json.loads((Path(tmp)/'batch-manual-worker.json').read_text())
        self.assertEqual(report['reason'],'main_changed_before_processing')
    def test_no_completed_workflow_wakes_the_manual_worker(self):
        config=(ROOT/'.github/workflows/batch-manual.yml').read_text()
        self.assertNotIn('workflow_run:',config)
        self.assertIn("cron: '2,7,12,17,22,27,32,37,42,47,52,57 * * * *'",config)
        self.assertIn('workflow_dispatch:',config)

    def test_unexpected_completion_event_cannot_contact_control_queue(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(worker,'ROOT',Path(tmp)),\
             patch.dict(os.environ,{'GITHUB_REPOSITORY':worker.REPO,'GITHUB_REF':'refs/heads/main',
                                    'GITHUB_EVENT_NAME':'workflow_run','ISEGYE_SFTP_PASSWORD':'synthetic'}),\
             patch.object(worker,'GitHub',side_effect=AssertionError('never inspect')) as github,\
             patch.object(worker.socket,'create_connection',side_effect=AssertionError('never connect')):
            self.assertEqual(worker.main(),1)
            report=json.loads((Path(tmp)/'batch-manual-worker.json').read_text())
        self.assertEqual(report['errorCode'],'ValueError')
        self.assertFalse(report['realUserRequestCreated'])
        github.assert_not_called()

    def test_invalid_main_identity_is_real_failure(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(worker,'ROOT',Path(tmp)),\
             patch.dict(os.environ,{'GITHUB_REPOSITORY':worker.REPO,'GITHUB_REF':'refs/heads/main',
                                   'GITHUB_SHA':'a'*40,'ISEGYE_SFTP_PASSWORD':'synthetic','GITHUB_EVENT_NAME':'schedule'}),\
             patch.object(worker,'GitHub',return_value=lambda _: {'object':{'sha':'invalid'}}),\
             patch.object(worker.subprocess,'check_output',return_value='a'*40+'\n'),\
             patch.object(worker.socket,'create_connection',side_effect=AssertionError('never connect')):
            self.assertEqual(worker.main(),1)
            report=json.loads((Path(tmp)/'batch-manual-worker.json').read_text())
        self.assertEqual(report['status'],'failed')
        self.assertEqual(report['errorCode'],'ValueError')

if __name__=='__main__':unittest.main()
