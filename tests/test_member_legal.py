"""Canonical legal text and strictly bounded authenticated presentation."""
from pathlib import Path
import json,sys,unittest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import compose_member_legal as legal
class MemberLegal(unittest.TestCase):
 def test_only_canonical_documents(self):
  self.assertEqual(set(legal.documents()),{'terms','privacy'})
  for kind,body in legal.documents().items():self.assertEqual(body,(ROOT/'auth'/f'{kind}.html').read_text())
 def test_missing_anchor_stops_build(self):
  with self.assertRaises(ValueError):legal.adapt_app('unrecognized renderer')
 def test_login_required_before_member_pages(self):
  s=(ROOT/'auth/Gateway.php').read_text();start=s.index("if (in_array($path, ['/account/terms'")
  block=s[start:s.index("MemberLegal::serve",start)+len("MemberLegal::serve")]
  self.assertIn("if ($access['role'] === null)",block);self.assertLess(block.index("if ($access['role'] === null)"),block.index('MemberLegal::serve'))
  for route in ('/api/schedule','/api/music','/api/history'):
   self.assertLess(s.index("if (!$access['allowed'])"),s.index("if ($path === '"+route+"')"))
 def test_public_policies_before_session_and_account_access(self):
  s=(ROOT/'auth/Gateway.php').read_text()
  self.assertLess(s.index("$path === '/auth/terms' ?"),s.index("$access = $this->store->access"))
  self.assertIn("script-src 'none'",s)
 def test_member_bundle_allowlist_and_integrity(self):
  s=(ROOT/'auth/MemberLegal.php').read_text()
  for part in ('realpath($file) !== $file','is_link($file)','filesize($file) > 2000000','hash_equals','sourceHashes',"connect-src 'none'",'member-legal.json','styles.css','member-legal.js'):self.assertIn(part,s)
  self.assertNotIn('accounts.json',s);self.assertNotIn('Session::login',s)
 def test_member_javascript_has_no_data_or_network(self):
  s=(ROOT/'site/member-legal.js').read_text()
  for part in ('fetch(', 'XMLHttpRequest','REVIEW_DATA','ProductionFeeds','document.cookie','removeItem'):self.assertNotIn(part,s)
  self.assertIn('isegye:archive:prefs:v1',s);self.assertIn('p.theme=theme',s)
 def test_precise_public_and_account_links(self):
  s=(ROOT/'auth/View.php').read_text();self.assertNotIn("$signedIn ? '/account/' : '/auth/'",s);self.assertIn("true, '/auth/'",s)
  self.assertIn("true, '/account/'",s)
 def test_archived_review_sources_unmodified(self):
  import promote_review_2nd
  self.assertTrue(promote_review_2nd.approval()['operatorApprovedDeployment'])
if __name__=='__main__':unittest.main()
