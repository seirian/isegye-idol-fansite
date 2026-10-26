"""In-memory deployment transactions; no network, users, credentials or production writes."""
import base64,json,os,stat,sys,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import auth_routing as a
import deploy_google_access as m
import inour_sftp as d
CLIENT='123456-fixture.apps.googleusercontent.com'
OLD='r123456abcdef'
TEMPLATE=b"<?php // fixture\n$runtime=$root.'/.auth-runtime/RUNTIME_ID';"
class Remote:
    def __init__(self,gated=False):
        self.files={d.ROOT+'/.isegye-owner':d.OWNER,d.ROOT+'/.htaccess':a.router(OLD) if gated else d.router(OLD),a.PRIVATE+'/.owner':a.PRIVATE_OWNER,a.PRIVATE+'/config.json':json.dumps({'origin':d.ORIGIN,'clientId':CLIENT if gated else '', 'siteKey':base64.b64encode(b'x'*32).decode(),'adminEmailDigest':'a'*64}).encode(),a.PRIVATE+'/accounts.lock':b'',a.PRIVATE+'/accounts.json':b'{"schema":1,"administrator":null,"accounts":{}}'}
        self.dirs={'/web',d.ROOT,a.PRIVATE,a.PRIVATE+'/sessions',d.ROOT+'/.auth-runtime',d.ROOT+'/_isegye_releases',d.ROOT+'/.release-backups'}
        self.mode={p:0o600 for p in self.files};self.mode.update({p:0o700 for p in self.dirs});self.s=self;self.writes=[]
        if gated:
            self.files[d.ROOT+'/access.php']=a.entry(TEMPLATE,'g000000000001');self.files[d.ROOT+'/.auth-runtime/g000000000001/access.php.template']=TEMPLATE
    def info(self,p):
        if p not in self.files and p not in self.dirs:return None
        return SimpleNamespace(st_mode=(stat.S_IFDIR if p in self.dirs else stat.S_IFREG)|self.mode.get(p,0o600))
    def directory(self,p):d.require(p in self.dirs,'Missing directory')
    def read(self,p):return self.files.get(p)
    def mkdir(self,p):d.write_path(p);d.require(self.info(p) is None,'Existing lock or folder');self.dirs.add(p);self.mode[p]=0o755
    def chmod(self,p,mode):self.mode[p]=mode
    def new(self,p,b):d.write_path(p);d.require(p not in self.files,'Existing file');self.files[p]=b;self.mode[p]=0o644;self.writes.append(p)
    def replace(self,p,b,expected):d.write_path(p);d.require(self.files.get(p)==expected,'Concurrent change');self.files[p]=b;self.writes.append(p)
    def snapshot(self):return {'shared':'unchanged','mir':'unchanged'}
    def prove_mapping(self):pass
    def parents(self,p):d.write_path(p)
    def rmdir(self,p):self.dirs.remove(p)
class AccessDeployTests(unittest.TestCase):
    def run_deploy(self,r,fail=False):
        report={};payload={'index.html':b'<head></head>APP','src/app.js':b'APP_DATA'}
        def http(url):return (200,b'EXISTING') if url in m.EXISTING else (404,b'NOT_FOUND')
        browser={'googleButtonRendered':True,'googleAccountChooserReached':True}
        with patch.dict(os.environ,GITHUB_RUN_ID='test',GITHUB_RUN_ATTEMPT='1'),patch.object(a,'bundle',return_value=('g000000000002',{'access.php.template':TEMPLATE})),patch.object(d,'http',side_effect=http),patch.object(m,'verify_public'),patch.object(m,'verify_browser',side_effect=RuntimeError('Synthetic failure') if fail else None,return_value=browser),patch.object(m,'status',return_value={'maintenance':False}):
            if fail:
                with self.assertRaises(RuntimeError):m.deploy(r,payload,'a'*40,CLIENT,report)
            else:m.deploy(r,payload,'a'*40,CLIENT,report)
        return report
    def test_first_activation_never_writes_accounts(self):
        r=Remote();before=r.files[a.PRIVATE+'/accounts.json'];result=self.run_deploy(r)
        self.assertEqual(result['status'],'deployed_and_verified');self.assertEqual(before,r.files[a.PRIVATE+'/accounts.json']);self.assertNotIn(a.PRIVATE+'/accounts.json',r.writes)
        self.assertTrue(a.release_of(r.files[d.ROOT+'/.htaccess'])[1]);self.assertTrue(result['lockRemoved'])
    def test_first_failure_keeps_gate_and_previous_release(self):
        r=Remote();result=self.run_deploy(r,True);self.assertEqual(a.release_of(r.files[d.ROOT+'/.htaccess']),(OLD,True));self.assertTrue(result['rollbackKeptAccessGate']);self.assertIn(d.ROOT+'/access.php',r.files)
    def test_update_failure_restores_previous_gateway(self):
        r=Remote(True);entry=r.files[d.ROOT+'/access.php'];result=self.run_deploy(r,True);self.assertEqual(r.files[d.ROOT+'/access.php'],entry);self.assertEqual(a.release_of(r.files[d.ROOT+'/.htaccess']),(OLD,True))
    def test_update_does_not_change_client_configuration(self):
        r=Remote(True);cfg=r.files[a.PRIVATE+'/config.json'];self.run_deploy(r);self.assertEqual(r.files[a.PRIVATE+'/config.json'],cfg);self.assertNotIn(a.PRIVATE+'/config.json',r.writes)
    def test_missing_private_store_fails_without_reinitialization(self):
        r=Remote();del r.files[a.PRIVATE+'/accounts.json']
        with self.assertRaises(d.Stop):self.run_deploy(r)
        self.assertNotIn(a.PRIVATE+'/accounts.json',r.files)
    def test_existing_lock_is_preserved(self):
        r=Remote();r.dirs.add(d.ROOT+'/.deploy-lock')
        with self.assertRaises(d.Stop):self.run_deploy(r)
        self.assertIn(d.ROOT+'/.deploy-lock',r.dirs)
    def test_auth_runtime_paths_remain_inside_root(self):
        r=Remote();self.run_deploy(r);self.assertTrue(all(p.startswith(d.ROOT+'/') for p in r.writes));self.assertNotIn('/web/.htaccess',r.writes)
if __name__=='__main__':unittest.main()
