"""Owner-requested presentation cleanup; never modifies authorization."""
from pathlib import Path
import re, subprocess, unittest
R=Path(__file__).resolve().parents[1]
class PresentationTests(unittest.TestCase):
    def render(self, call):
        return subprocess.check_output(['php','-r', "require 'auth/View.php'; echo Isegye\\Access\\View::"+call+';'],cwd=R).decode()
    def test_maintenance_has_no_policy_links(self):
        for arg in ('true','false'):
            html=self.render('maintenance('+arg+')')
            self.assertNotIn('href="/auth/terms"',html)
            self.assertNotIn('href="/auth/privacy"',html)
            self.assertIn('href="/auth/login"',html)
            self.assertIn('access-backdrop',html)
            self.assertIn('현재 사이트는 <br>공사중입니다.',html)
    def test_login_and_account_disclosures_remain(self):
        for call in ("login('client','nonce','csrf')", "account('admin','csrf')", "account('member','csrf')"):
            html=self.render(call)
            self.assertIn('href="/auth/terms"',html)
            self.assertIn('href="/auth/privacy"',html)
    def test_policy_navigation_and_generic_operator(self):
        for kind in ('terms','privacy'):
            html=self.render(kind+'()')
            nav=re.search(r'<div class="legal-navigation">(.*?)</div>',html).group(1)
            self.assertNotIn('/auth/login',nav)
            self.assertIn('href="/"',nav)
            self.assertNotIn('seirian',html.replace('seirian@gmail.com',''))
            self.assertIn('<dt>운영자</dt><dd>운영자</dd>',html)
            self.assertIn('mailto:seirian@gmail.com',html)
    def test_both_shells_have_exactly_two_footer_links(self):
        for name in ('src/app.js','second/compose.py'):
            html=(R/name).read_text()
            footer=re.search(r'<div class="footer-links">(.*?)</div>',html).group(1)
            self.assertEqual(re.findall(r'href="([^"]+)"',footer),['https://isegye-idol.kr/auth/terms','https://isegye-idol.kr/auth/privacy'])
            for label in ('사이트 소개','운영 원칙','권리·정정 요청'):self.assertNotIn(label,footer)
    def test_public_policy_notice_matches_navigation(self):
        text=(R/'auth/privacy.html').read_text()
        self.assertNotIn('로그인·공사중 화면과 사이트 하단',text)
        self.assertIn('공사중에도 로그인 화면이나 문서 주소',text)
if __name__=='__main__':unittest.main()
