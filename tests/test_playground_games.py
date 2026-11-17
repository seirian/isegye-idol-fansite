"""Preview artifact, unchanged PHP gate, and tightly scoped publication safeguards."""
from pathlib import Path
import base64,copy,hashlib,json,os,re,subprocess,sys,tempfile,unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import build_playground_games as b
import deploy_playground_games as deploy

class Games(unittest.TestCase):
 def test_catalog_only_selected_official_minimal_metadata(self):
  d=b.catalog();self.assertGreaterEqual(len(d['songs']),8);self.assertEqual(len({s['id'] for s in d['songs']}),len(d['songs']))
  for s in d['songs']:
   self.assertEqual(set(s),{'id','title','members','album','aliases','url','checkedAt'});self.assertRegex(s['url'],r'^https://www.youtube.com/watch\?v=[A-Za-z0-9_-]{11}$')
 def test_main_and_develop_build_refused(self):
  for ref in ('refs/heads/main','refs/heads/develop'):
   with patch.dict(os.environ,{'GITHUB_REF':ref}),self.assertRaises(ValueError):b.build()
 def test_only_existing_review_writable(self):
  for p in (deploy.FOLDER+'/active.json',deploy.FOLDER+'/releases/p123456789012/review.html',deploy.d.ROOT+'/.deploy-lock'):self.assertEqual(deploy.allowed_write(p),p)
  for p in (deploy.d.ROOT+'/access.php',deploy.d.ROOT+'/.htaccess',deploy.d.ROOT+'/.auth-private/accounts.json',deploy.d.ROOT+'/.playground-bank/current.json',deploy.d.ROOT+'/.review-fanmade/active.json','/web/.htaccess',deploy.FOLDER+'/../access.php'):
   with self.assertRaises(deploy.d.Stop):deploy.allowed_write(p)
 def test_exact_hash_csp_and_payload(self):
  with patch.dict(os.environ,{'GITHUB_REF':'refs/heads/feature/playground-games','GITHUB_SHA':'a'*40,'DEPLOY_ENV':'preview'}):b.build()
  r,html,meta,ptr=deploy.payload(ROOT/'playground-games-dist','a'*40);self.assertRegex(r,'^p[0-9a-f]{12}$');self.assertEqual(json.loads(ptr)['sha256'],hashlib.sha256(html).hexdigest());self.assertTrue(json.loads(meta)['counts']['games']==3)
  with tempfile.TemporaryDirectory() as t:
   f=Path(t);(f/'review.html').write_bytes(html+b'bad');(f/'build-info.json').write_bytes((ROOT/'playground-games-dist/build-info.json').read_bytes())
   with self.assertRaises(deploy.d.Stop):deploy.payload(f,'a'*40)
 def test_wrong_commit_and_untested_bytes_refused(self):
  with self.assertRaises(deploy.d.Stop):deploy.payload(ROOT/'playground-games-dist','b'*40)
  with patch.dict(os.environ,{'VERIFIED_HTML_SHA256':'0'*64}),self.assertRaises(deploy.d.Stop):deploy.payload(ROOT/'playground-games-dist','a'*40)
 def test_existing_preview_handler_is_admin_only(self):
  handler=ROOT/'playground/hosting/PlaygroundPreview.php'
  with tempfile.TemporaryDirectory() as t:
   tmp=Path(t);base=tmp/'.review-playground';base.mkdir();(base/'.owner').write_bytes(deploy.MARKER)
   html=b'<!doctype html><h1>three-content-fixture</h1>';rid='p'+'1'*12;dest=base/'releases'/rid;dest.mkdir(parents=True);(dest/'review.html').write_bytes(html);meta=b'{}';(dest/'build-info.json').write_bytes(meta)
   pointer={'release':rid,'sha256':hashlib.sha256(html).hexdigest(),'metadataSha256':hashlib.sha256(meta).hexdigest()};(base/'active.json').write_text(json.dumps(pointer))
   def invoke(role,path='/review-playground/',method='GET'):
    code="namespace Isegye\\Access; class Session{static function touch(){}} require "+json.dumps(str(handler))+"; $_SERVER['REQUEST_METHOD']="+json.dumps(method)+"; ob_start(); PlaygroundPreview::serve("+json.dumps(str(tmp))+","+json.dumps(path)+","+('null' if role is None else json.dumps(role))+"); $body=ob_get_clean(); echo json_encode(['status'=>http_response_code(),'body'=>$body]);"
    return json.loads(subprocess.check_output(['php','-r',code]))
   for role in (None,'member','administrator','ADMIN'):
    v=invoke(role);self.assertEqual(v['status'],403);self.assertNotIn('three-content-fixture',v['body'])
   self.assertEqual(invoke('admin')['body'],html.decode());self.assertEqual(invoke('admin',method='HEAD')['body'],'');self.assertEqual(invoke('admin',method='POST')['status'],405)
   for path in ('/review-playground/private','/review-playground/../active.json','/review-playground/%2e%2e/active.json'):self.assertEqual(invoke('admin',path)['status'],404)
   (dest/'review.html').write_bytes(html+b'tampered');self.assertEqual(invoke('admin')['status'],503)
 def test_no_auth_account_or_production_write_calls(self):
  src=(ROOT/'scripts/deploy_playground_games.py').read_text();self.assertNotIn('a.entry(',src);self.assertNotIn('a.bundle(',src);self.assertNotIn('auth-private/',src);self.assertIn('rollbackRestoredPreviousPreview',src);self.assertIn('Previous preview lost',src)
 def test_shared_heading_rules_are_imported_not_reinvented(self):
  self.assertIn("ROOT/'review-2nd/polish.css'",(ROOT/'scripts/build_playground_games.py').read_text())
 def test_no_external_artwork_or_audio_in_assets(self):
  files=list((ROOT/'playground-games').iterdir());self.assertEqual({p.suffix for p in files},{'.js','.html','.css'})
if __name__=='__main__':unittest.main()
