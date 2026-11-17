"""Shared access UI, document redirects and strict resource denial."""
from pathlib import Path
import json, subprocess, unittest
from test_batch_monitor import MonitorAccessTests, ROOT


class RedirectAccess(MonitorAccessTests):
    def test_document_notice_uses_shared_shell(self):
        for role,allowed in [(None,False),('member',True),('member',False),('admin',False)]:
            for path in ('/ops/batches','/ops/batches/'):
                status,html=self.request(role,allowed,path)
                self.assertEqual(status,303)
                self.assertIn('관리자 계정만 해당 사이트에 접근이 가능합니다.',html)
                self.assertIn('/auth/style.css',html)
                self.assertIn('/auth/login?notice=batch-admin',html)
                self.assertNotIn('id="rows"',html)
    def test_document_head_does_not_expose_body(self):
        self.assertEqual(self.request(path='/ops/batches/',method='HEAD'),[303,''])
    def test_post_is_not_login_redirect(self):
        self.assertEqual(self.request(path='/ops/batches/',method='POST')[0],401)
        self.assertEqual(self.request('member',True,path='/ops/batches/',method='POST')[0],403)
    def test_resources_keep_original_denial(self):
        for role,code in [(None,401),('member',403)]:
            for resource in ('data.json','monitor.js','monitor.css','other'):
                self.assertEqual(self.request(role,True,'/ops/batches/'+resource),[code,'Administrator access required'])
    def test_contextual_login_message_without_elevation(self):
        code='require $argv[1];require $argv[2];$_SERVER["REQUEST_METHOD"]="GET";ob_start();Isegye\\Access\\BatchMonitor::login(json_decode($argv[3],true),"test","nonce","csrf");$body=ob_get_clean();echo json_encode([http_response_code(),$body]);'
        for role in (None,'member'):
            result=json.loads(subprocess.check_output(['php','-r',code,str(ROOT/'monitoring/BatchMonitor.php'),str(ROOT/'auth/View.php'),json.dumps({'role':role,'allowed':False})]))
            self.assertEqual(result[0],200)
            self.assertIn('data-batch-access="required"',result[1])
            self.assertNotIn('http-equiv="refresh"',result[1])
            self.assertIn('data-intent="batch-monitor"' if role is None else 'action="/auth/logout?notice=batch-admin"',result[1])

if __name__=='__main__':unittest.main()
