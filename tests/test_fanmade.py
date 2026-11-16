import copy,hashlib,json,os,sys,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import build_fanmade as b
import build_fanmade_host as h
import deploy_fanmade as d
class FanmadeTests(unittest.TestCase):
 def setUp(self):self.data=json.loads((ROOT/'fanmade/catalog.json').read_text())
 def test_valid_sample_catalog(self):self.assertEqual(len(b.validate(self.data)['works']),12)
 def test_unapproved_real_work_refused(self):
  for k,v in [('sample',False),('originalUrl','https://example.org/art'),('publishedAt','2026-11-16'),('permission',{'status':'granted'})]:
   data=copy.deepcopy(self.data);data['works'][0][k]=v
   with self.assertRaises(ValueError):b.validate(data)
 def test_broken_relationship_refused(self):
  self.data['works'][0]['creatorId']='missing'
  with self.assertRaises(ValueError):b.validate(self.data)
 def test_bad_gallery_refused(self):
  self.data['works'][0]['frames']=[]
  with self.assertRaises(ValueError):b.validate(self.data)
 def test_main_and_production_refused(self):
  for env in ({'GITHUB_REF':'refs/heads/main'},{'GITHUB_REF':'refs/heads/develop'},{'DEPLOY_ENV':'production'}):
   with patch.dict(os.environ,env):
    with self.assertRaises(ValueError):b.build()
 def test_gateway_after_access_gate(self):
  source=(ROOT/'auth/Gateway.php').read_text();out=h.patched(source)
  self.assertLess(out.index("if (!$access['allowed'])"),out.index('ISEGYE-FANMADE'))
  self.assertEqual(out.replace(h.HOOK,''),h.previous.patched(source))
  self.assertNotIn('/review-fanmade',source)
 def test_storage_and_requests_isolated(self):
  app=(ROOT/'fanmade/app.js').read_text();core=(ROOT/'fanmade/core.js').read_text()
  for token in ('fetch(', 'XMLHttpRequest','sendBeacon','isegye:prefs','isegye:bookmarks'):
   self.assertNotIn(token,app+core)
  self.assertIn('isegye:fanmade:review:v1',core)
 def test_exact_payload_hash(self):
  meta=json.loads((ROOT/'fanmade-dist/build-info.json').read_text());raw=(ROOT/'fanmade-dist/review.html').read_bytes()
  self.assertEqual(meta['htmlSha256'],hashlib.sha256(raw).hexdigest())
  if meta['commit']!='local':
   release,html,metadata,pointer=d.payload(ROOT/'fanmade-dist',meta['commit']);self.assertEqual(html,raw)
 def test_handler_is_read_only_and_fail_closed(self):
  s=(ROOT/'fanmade/hosting/FanmadePreview.php').read_text()
  for token in ("$role !== 'admin'",'hash_equals','realpath','is_link','Session::touch()'):self.assertIn(token,s)
  for token in ('file_put_contents','unlink(','registerVerified'):self.assertNotIn(token,s)
 def test_deployer_preserves_operating_runtime(self):
  s=(ROOT/'scripts/deploy_fanmade.py').read_text()
  for token in ('Current auth source changed','Concurrent gateway change','Production UI files changed','Host key mismatch','entry_changed','refs/heads/feature/fanmade'):self.assertIn(token,s)
if __name__=='__main__':unittest.main()
