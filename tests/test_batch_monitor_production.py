"""Main production integration, bounded retention and fail-closed refresh tests."""
from pathlib import Path
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch
import copy, hashlib, json, os, stat, sys, unittest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import batch_monitor_storage as store
import batch_monitor_snapshot as snapshot
import deploy_batch_monitor as deploy
import auth_routing as routing
from test_batch_monitor import fixture_snapshot


def document(at=None):
    v=fixture_snapshot(at);v.update(mode='production',repository=snapshot.REPO,collectorCommit='a'*40,
        scheduledRefreshEnabled=True,refreshEverySeconds=600)
    return v


class MemoryRemote:
    def __init__(self):
        self.s=self;self.tick=1000;self.times={};self.writes=[]
        self.dirs={'/web',store.d.ROOT,store.FOLDER,store.FOLDER+'/releases'}
        self.files={store.d.ROOT+'/.isegye-owner':store.d.OWNER,
            store.d.ROOT+'/.htaccess':routing.router('r123456abcdef'),store.d.ROOT+'/access.php':b'fixture-entry',
            store.FOLDER+'/.owner':store.MARKER,store.FOLDER+'/.htaccess':b'Require all denied\n'}
    def info(self,p):
        if p not in self.files and p not in self.dirs:return None
        return SimpleNamespace(st_mode=(stat.S_IFDIR|0o700) if p in self.dirs else (stat.S_IFREG|0o600),
            st_uid=store.d.UID,st_size=len(self.files.get(p,b'')),st_mtime=self.times.get(p,1))
    def directory(self,p):store.d.require(p in self.dirs,'Missing directory')
    def read(self,p):return self.files.get(p)
    def parents(self,p):store.d.write_path(p)
    def mkdir(self,p):
        self.parents(p);store.d.require(self.info(p) is None,'Existing directory');self.dirs.add(p);self.tick+=1;self.times[p]=self.tick
    def new(self,p,raw):
        self.parents(p);store.d.require(p not in self.files,'Existing file');self.files[p]=raw;self.writes.append(p)
    def replace(self,p,raw,expected):
        self.parents(p);store.d.require(self.read(p)==expected,'Concurrent write');self.files[p]=raw;self.writes.append(p)
    def chmod(self,*args):pass
    def remove_own(self,p,raw):
        self.parents(p);store.d.require(self.read(p)==raw,'Concurrent write');del self.files[p];self.writes.append(p)
    def rmdir(self,p):
        store.d.require(not any(x.startswith(p+'/') for x in self.files),'Directory not empty');self.dirs.remove(p)
    def listdir_attr(self,p):
        names={x[len(p)+1:] for x in self.files.keys()|self.dirs if x.startswith(p+'/') and '/' not in x[len(p)+1:]}
        return [SimpleNamespace(filename=name,**vars(self.info(p+'/'+name))) for name in names]
    def install(self,doc):
        from deploy_google_access import upload_tree
        name,files,point=deploy.release_payload(doc);upload_tree(self,store.FOLDER+'/releases/'+name,files,private=True)
        return name,point


class ProductionPolicy(unittest.TestCase):
    def test_production_snapshot_bound_to_current_main(self):
        v=document();store.validate_snapshot(v,'a'*40)
        for key,value in [('mode','review-snapshot'),('mainCommit','b'*40),('collectorCommit','b'*40),('readOnly',False),('scheduledRefreshEnabled',False),('refreshEverySeconds',60)]:
            changed=copy.deepcopy(v);changed[key]=value
            with self.subTest(key=key),self.assertRaises(store.d.Stop):store.validate_snapshot(changed,'a'*40)
    def test_stale_snapshot_not_newly_published(self):
        with self.assertRaises(store.d.Stop):store.validate_snapshot(document(datetime.now(timezone.utc)-timedelta(minutes=16)),'a'*40)
    def test_future_snapshot_not_published(self):
        with self.assertRaises(store.d.Stop):store.validate_snapshot(document(datetime.now(timezone.utc)+timedelta(minutes=3)),'a'*40)
    def test_missing_duplicate_categories_rejected(self):
        v=document();v['batches'][1]=v['batches'][0]
        with self.assertRaises(store.d.Stop):store.validate_snapshot(v,'a'*40)
    def test_main_workflow_preserves_read_only_and_shared_lock(self):
        text=(ROOT/'.github/workflows/batch-monitoring.yml').read_text()
        self.assertIn('permissions:\n  contents: read\n  actions: read',text)
        self.assertIn("cron: '7,17,27,37,47,57 * * * *'",text)
        self.assertIn('group: isegye-inour-production',text)
        self.assertIn('cancel-in-progress: false',text)
        self.assertIn("github.ref == 'refs/heads/main'",text)
        self.assertIn('with: {ref: main, persist-credentials: false}',text)
        self.assertNotIn('actions: write',text);self.assertNotIn('--method POST',text)
        self.assertIn('--refresh-only',text)
        self.assertNotIn('path: monitoring-dist',text)
    def test_full_deployment_permanently_keeps_route(self):
        text=(ROOT/'.github/workflows/production.yml').read_text()
        self.assertLess(text.index('python scripts/build_batch_monitor_host.py'),text.index('python -u scripts/deploy_verified_albums.py'))
        self.assertLess(text.index('tests/batch_monitor_host_browser.py'),text.index('python -u scripts/deploy_verified_albums.py'))
        self.assertIn('isegye-production-evidence-',text)
        self.assertIn('scripts/deploy_batch_monitor.py',text)
    def test_no_feature_production_publisher(self):
        text=(ROOT/'.github/workflows/batch-monitoring-preview.yml').read_text()
        self.assertNotIn('  publish:',text)
        self.assertNotIn('ISEGYE_SFTP_PASSWORD',text)
    def test_source_guards_no_private_identity_reads(self):
        text=(ROOT/'scripts/batch_monitor_storage.py').read_text()
        self.assertNotIn("read(d.ROOT+'/.auth-private",text)
        self.assertNotIn('auth_password',text)
        self.assertIn('Unknown object in monitoring releases',text)
    def test_anonymous_denial_requires_status_body_and_destination(self):
        def response(path):
            headers={'cache-control':'private, no-store'}
            if path in store.DOCUMENT_ROUTES:
                return 303, (store.MESSAGE+' /auth/style.css').encode(),dict(headers,location=store.LOGIN)
            if path == store.LOGIN:
                return 200, (store.MESSAGE+' /auth/style.css data-batch-access="required" data-intent="batch-monitor"').encode(),headers
            return 401,b'Administrator access required',headers
        with patch.object(store,'access_http',side_effect=response):store.verify_anonymous()
        for bad in [(200,b'Administrator access required',{}),(303,b'notice',{'location':'https://evil.test/'}),(401,b'dashboard',{})]:
            with patch.object(store,'access_http',return_value=bad),self.assertRaises(store.d.Stop):store.verify_anonymous()
        def data_redirect(path):
            return response(path) if path in store.DOCUMENT_ROUTES else (303,b'',{'cache-control':'no-store','location':store.LOGIN})
        with patch.object(store,'access_http',side_effect=data_redirect),self.assertRaises(store.d.Stop):store.verify_anonymous()


class StorageTransactions(unittest.TestCase):
    def run_refresh(self,r,v,report=None,gate=None):
        report={} if report is None else report
        with patch.object(store,'current_runtime',return_value=('g123456abcdef',b'fixture-entry')),patch.object(store,'verify_anonymous',side_effect=gate),patch.object(store.d,'http',return_value=(403,b'Forbidden')):
            store.refresh(r,v,'a'*40,report,ROOT)
        return report
    def test_refresh_writes_only_owned_snapshot_paths(self):
        r=MemoryRemote();before=dict(r.files);report=self.run_refresh(r,document())
        self.assertEqual(report['status'],'monitor_snapshot_verified')
        self.assertTrue(all(p.startswith(store.FOLDER+'/') for p in r.writes))
        self.assertTrue(all(r.files[p]==raw for p,raw in before.items()))
        self.assertNotIn(store.d.ROOT+'/.deploy-lock',r.dirs)
        self.assertTrue(report['authenticationRuntimeUnchanged'])
    def test_history_survives_atomic_refresh(self):
        r=MemoryRemote();v=document();old=document(datetime.now(timezone.utc)-timedelta(days=1))
        _,point=r.install(old);r.files[store.FOLDER+'/active.json']=point
        initial_count=len(v['observations'])
        self.run_refresh(r,v)
        got=deploy.old_snapshot(r,r.read(store.FOLDER+'/active.json'))
        self.assertGreater(len(got['observations']),initial_count)
        self.assertEqual(r.read(store.FOLDER+'/previous.json'),point)
    def test_post_activation_failure_restores_pointer(self):
        r=MemoryRemote();_,point=r.install(document(datetime.now(timezone.utc)-timedelta(minutes=2)))
        r.files[store.FOLDER+'/active.json']=point;report={}
        with self.assertRaises(RuntimeError):self.run_refresh(r,document(),report,[None,RuntimeError('test rejection')])
        self.assertEqual(r.read(store.FOLDER+'/active.json'),point);self.assertTrue(report['previousPointerRestored'])
    def test_existing_writer_lock_not_removed(self):
        r=MemoryRemote();lock=store.d.ROOT+'/.deploy-lock';r.dirs.add(lock)
        with self.assertRaises(store.d.Stop):self.run_refresh(r,document())
        self.assertIn(lock,r.dirs);self.assertEqual(r.writes,[])
    def test_old_snapshot_cannot_replace_newer_snapshot(self):
        r=MemoryRemote();_,point=r.install(document());r.files[store.FOLDER+'/active.json']=point
        with self.assertRaises(store.d.Stop):self.run_refresh(r,document(datetime.now(timezone.utc)-timedelta(minutes=1)))
        self.assertEqual(r.read(store.FOLDER+'/active.json'),point)
    def test_retention_preserves_active_rollback_and_ninety_day_summary(self):
        r=MemoryRemote();at=datetime.now(timezone.utc);items=[]
        for i in range(27):items.append(r.install(document(at-timedelta(minutes=i))))
        active,point=items[0];previous=items[1][0];r.files[store.FOLDER+'/active.json']=point
        removed=store.prune(r,active,previous)
        self.assertEqual(removed,3);self.assertEqual(len(r.listdir_attr(store.FOLDER+'/releases')),24)
        self.assertIn(store.FOLDER+'/releases/'+active,r.dirs);self.assertIn(store.FOLDER+'/releases/'+previous,r.dirs)
    def test_unknown_release_prevents_deletion(self):
        r=MemoryRemote();r.dirs.add(store.FOLDER+'/releases/unrelated');before=set(r.dirs)
        with self.assertRaises(store.d.Stop):store.prune(r,'m'+'a'*12,None)
        self.assertEqual(before,r.dirs)
    def test_cleanup_rejects_symlink_or_foreign_owner(self):
        for mode,uid in [(stat.S_IFLNK|0o777,store.d.UID),(stat.S_IFDIR|0o700,0)]:
            entry=SimpleNamespace(filename='m'+'a'*12,st_mode=mode,st_uid=uid,st_mtime=1)
            with self.assertRaises(store.d.Stop):store.prune_candidates([entry],None,None)
    def test_cleanup_bounded(self):
        with self.assertRaises(store.d.Stop):store.prune_candidates([None]*251,None,None)
    def test_cleanup_tamper_stops_before_any_deletion(self):
        r=MemoryRemote();at=datetime.now(timezone.utc);items=[r.install(document(at-timedelta(minutes=i))) for i in range(25)]
        active,point=items[-1];r.files[store.FOLDER+'/active.json']=point
        doomed=store.prune_candidates(r.listdir_attr(store.FOLDER+'/releases'),active,None)
        r.files[store.FOLDER+'/releases/'+doomed[0]+'/data.json']=b'tampered'
        before=set(r.files)
        with self.assertRaises(store.d.Stop):store.prune(r,active,None)
        self.assertEqual(set(r.files),before)

if __name__=='__main__':unittest.main()
