import base64,json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import auth_routing as a
import inour_sftp as d
class AuthRoutingTests(unittest.TestCase):
    def test_gate_is_exact(self):
        r=a.router('r123456abcdef');self.assertEqual(a.release_of(r),('r123456abcdef',True))
    def test_old_router_accepted_only_for_migration(self):self.assertEqual(a.release_of(d.router('r123456abcdef')),('r123456abcdef',False))
    def test_recovery_keeps_gate_for_first_activation(self):self.assertEqual(a.recovery_router(d.router('r123456abcdef')),a.router('r123456abcdef'))
    def test_recovery_keeps_gate_for_updates(self):self.assertEqual(a.recovery_router(a.router('r123456abcdef')),a.router('r123456abcdef'))
    def test_public_release_bypass_not_present(self):
        r=a.router('r123456abcdef');self.assertNotIn(b'RewriteRule ^_isegye_releases',r);self.assertIn(b'RewriteRule ^ access.php [END]',r)
    def test_unknown_router_rejected(self):
        for r in (b'',b'# forged',a.router('r123456abcdef')+b'Allow from all\n'):
            with self.subTest(r=r),self.assertRaises(d.Stop):a.release_of(r)
    def test_bad_release_rejected(self):
        for r in ('../main','r123','main','r'+'0'*13):
            with self.subTest(r=r),self.assertRaises(d.Stop):a.router(r)
    def test_unpublished_not_activated(self):
        with self.assertRaises(d.Stop):a.release_of(d.router())
    def config(self):return {'origin':d.ORIGIN,'clientId':'','siteKey':base64.b64encode(b'x'*32).decode(),'adminEmailDigest':'a'*64}
    def test_client_only_added_without_changing_identity(self):
        c=self.config();out,changed=a.configured(json.dumps(c).encode(),'123456-example.apps.googleusercontent.com');c['clientId']='123456-example.apps.googleusercontent.com';self.assertTrue(changed);self.assertEqual(json.loads(out),c)
    def test_same_client_is_idempotent(self):
        c=self.config();c['clientId']='123456-example.apps.googleusercontent.com';data=json.dumps(c).encode();self.assertEqual(a.configured(data,c['clientId']),(data,False))
    def test_replacing_client_is_rejected(self):
        c=self.config();c['clientId']='123456-example.apps.googleusercontent.com'
        with self.assertRaises(d.Stop):a.configured(json.dumps(c).encode(),'999999-different.apps.googleusercontent.com')
    def test_empty_fake_client_rejected(self):
        for value in ('','wrong','123.apps.googleusercontent.com','https://accounts.google.com'):
            with self.subTest(value=value),self.assertRaises(d.Stop):a.configured(json.dumps(self.config()).encode(),value)
    def test_account_counts_only(self):
        self.assertEqual(a.account_state(b'{"schema":1,"administrator":null,"accounts":{}}'),{'accountCount':0,'administratorRegistered':False})
    def test_admin_state_report_never_contains_identity(self):
        data={'schema':1,'administrator':'b'*64,'accounts':{'b'*64:'admin','c'*64:'member'}};report=a.account_state(json.dumps(data).encode());self.assertEqual(report,{'accountCount':2,'administratorRegistered':True});self.assertNotIn('b'*64,str(report))
    def test_bad_privilege_rejected(self):
        for data in ({'schema':1,'administrator':None,'accounts':{'b'*64:'admin'}},{'schema':1,'administrator':'b'*64,'accounts':{}},{'schema':1,'administrator':None,'accounts':{'email':'member'}}):
            with self.subTest(data=data),self.assertRaises(d.Stop):a.account_state(json.dumps(data).encode())
    def test_missing_store_not_reset(self):
        with self.assertRaises(d.Stop):a.account_state(None)
    def test_gateway_injected_only_in_document(self):
        data=b'<head></head><body></body>';self.assertIn(a.INJECTION.encode(),a.public_html(data));self.assertEqual(data,b'<head></head><body></body>')
    def test_template_runtime_must_be_unique(self):
        with self.assertRaises(d.Stop):a.entry(b'RUNTIME_ID RUNTIME_ID','g123456abcdef')
if __name__=='__main__':unittest.main()
