"""Public policy routes, actual data disclosures and retained security boundaries."""
from pathlib import Path
from html.parser import HTMLParser
import re, unittest
R=Path(__file__).resolve().parents[1]
class LegalTests(unittest.TestCase):
 def test_complete_documents(self):
  for kind,n in [('terms',16),('privacy',13)]:
   with self.subTest(kind=kind):
    text=(R/'auth'/f'{kind}.html').read_text()
    self.assertEqual(len(re.findall(r'<h2 id="'+kind+r'-\d+">',text)),n)
    for i in range(1,n+1):
     self.assertIn(f'id="{kind}-{i:02}"',text);self.assertIn(f'href="#{kind}-{i:02}"',text)
    self.assertIn('2026년 10월 27일',text);self.assertIn('변경 이력',text)
    self.assertIn('<caption>',text);self.assertNotIn('<script',text)
 def test_reference_provider_not_copied_as_ours(self):
  text=''.join((R/'auth'/f'{x}.html').read_text() for x in ('terms','privacy'))
  for x in ('contact@viichan.kr','privacy@viichan.kr','V.LOG','Firebase UID','Neon, LLC','Vercel Inc.'):
   self.assertNotIn(x,text)
 def test_precise_minimal_storage(self):
  text=(R/'auth/privacy.html').read_text()
  for x in ('HMAC','12시간','30분','10분','원본 sub','회원 원장','세션','localStorage','Google Analytics','인아워넷'):
   self.assertIn(x,text)
 def test_disclosure_before_account_lookup(self):
  text=(R/'auth/Gateway.php').read_text()
  self.assertLess(text.index("$path === '/auth/terms' ? View::terms()"),text.index('$access = $this->store->access'))
  self.assertIn("if ($method === 'POST') { self::respond(405",text)
  self.assertIn("script-src 'none'",text)
 def test_bundle_includes_all_legal_files(self):
  text=(R/'scripts/build_auth_bundle.py').read_text()
  for x in ('terms.html','privacy.html','legal.css'):self.assertIn(x,text)
 def test_old_false_notice_removed(self):
  text=(R/'src/app.js').read_text()
  self.assertNotIn('회원 계정을 수집하는 기능은 없습니다',text)
  self.assertIn('https://isegye-idol.kr/auth/privacy',text)
  self.assertIn('https://isegye-idol.kr/auth/terms',text)
  self.assertIn('data-action="clear-data"',text)
 def test_footer_of_composed_site(self):
  text=(R/'second/compose.py').read_text()
  self.assertIn('https://isegye-idol.kr/auth/terms',text)
  self.assertIn('https://isegye-idol.kr/auth/privacy',text)
 def test_layout_accessibility(self):
  css=(R/'auth/legal.css').read_text()
  for x in ('@media print','max-width:680px','font-size:16px','scroll-margin-top'):self.assertIn(x,css)
if __name__=='__main__':unittest.main()
