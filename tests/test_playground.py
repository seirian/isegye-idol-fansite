import copy,hashlib,json,os,re,sys,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import build_playground as b
import build_playground_host as h
class PlaygroundTests(unittest.TestCase):
 def setUp(self):self.data=json.loads((ROOT/'playground/catalog.json').read_text())
 def test_valid_real_bank(self):self.assertEqual(len(b.validate(self.data)['questions']),32)
 def test_duplicate_choices_refused(self):
  self.data['questions'][0]['choices']=['a']*4
  with self.assertRaises(ValueError):b.validate(self.data)
 def test_unknown_source_refused(self):
  self.data['questions'][0]['sources']=['missing']
  with self.assertRaises(ValueError):b.validate(self.data)
 def test_unread_page_not_answer_evidence(self):
  self.data['questions'][0]['sources']=['namu-group']
  with self.assertRaises(ValueError):b.validate(self.data)
 def test_insecure_url_refused(self):
  self.data['sources']['winter']['url']='javascript:alert(1)'
  with self.assertRaises(ValueError):b.validate(self.data)
 def test_no_inline_injection(self):
  self.data['questions'][0]['stem']='</script>'
  with self.assertRaises(ValueError):b.validate(self.data)
 def test_main_develop_refused(self):
  for name in ('main','develop'):
   with patch.dict(os.environ,{'GITHUB_REF':'refs/heads/'+name}):
    with self.assertRaises(ValueError):b.build()
 def test_exact_artifact_hash(self):
  meta=json.loads((ROOT/'playground-dist/build-info.json').read_text());raw=(ROOT/'playground-dist/review.html').read_bytes();self.assertEqual(meta['htmlSha256'],hashlib.sha256(raw).hexdigest());self.assertTrue(meta['realQuestionBank']);self.assertFalse(meta['sampleOnly'])
 def test_auth_gate_unchanged(self):
  source=(ROOT/'auth/Gateway.php').read_text();out=h.patched(source);self.assertLess(out.index("if (!$access['allowed'])"),out.index('ISEGYE-PLAYGROUND'));self.assertEqual(out.replace(h.HOOK,''),h.baseline_patched(source));self.assertIn('ISEGYE-FANMADE',out)
 def test_preview_handler_is_read_only(self):
  t=(ROOT/'playground/hosting/PlaygroundPreview.php').read_text();self.assertIn("$role !== 'admin'",t);self.assertIn('hash_equals',t);self.assertNotIn('file_put_contents',t)
 def test_isolated_storage_and_no_network(self):
  js=(ROOT/'playground/app.js').read_text()+(ROOT/'playground/core.js').read_text();self.assertNotIn('fetch(',js);self.assertNotIn('isegye:archive:',js);self.assertNotIn('localStorage.clear',js)
 def test_deployer_preserves_fanmade_and_operating_ui(self):
  t=(ROOT/'scripts/deploy_playground.py').read_text();self.assertIn("'review-fanmade'",t);self.assertIn('production_hashes',t);self.assertIn('rollbackRestoredPreviousEntry',t);self.assertIn('Host key mismatch; credential not sent',t)
if __name__=='__main__':unittest.main()
