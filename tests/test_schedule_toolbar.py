"""Final-shell presentation tests. No source/ingestion/auth state mutations."""
from pathlib import Path
import sys,unittest
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'scripts'))
import compose_footer_navigation as nav
class Toolbar(unittest.TestCase):
 def test_footer_navigation_transformation(self):
  old='<nav>${NAV.map(n=>`link`)}</nav><div class="footer-links"><a href="https://isegye-idol.kr/auth/terms">이용약관</a><a href="https://isegye-idol.kr/auth/privacy"><strong>개인정보처리방침</strong></a></div>function guideView(){return "retained";}'
  meta={};app,css=nav.compose(old,'base',meta)
  self.assertIn("NAV.filter(n=>n.id!=='guide').map",app)
  self.assertIn('<a href="#/guide">팬가이드</a>',app)
  self.assertLess(app.index('이용약관'),app.index('개인정보처리방침'));self.assertLess(app.index('개인정보처리방침'),app.index('팬가이드'))
  self.assertIn('function guideView(){return "retained";}',app)
  self.assertEqual(meta['navigationPresentation']['primaryCount'],6)
 def test_unknown_shell_fails_closed(self):
  with self.assertRaises(ValueError):nav.compose('changed shell','',{})
 def test_status_banner_absent_not_data_collection(self):
  text=(R/'schedule/ui.js').read_text()
  self.assertNotIn('공식 소식 확인 현황',text);self.assertNotIn('sc-sync',text)
  self.assertIn('수집 상태와 표시 기준</summary>${scheduleRefreshControl()}',text)
  self.assertIn("fetch('/api/schedule'",text)
 def test_uniform_toolbar_has_named_controls(self):
  text=(R/'schedule/ui.js').read_text()
  for name in ('month','member','source','kind'):self.assertIn('id="schedule-'+name+'"',text)
  self.assertIn('aria-label="일정 필터"',text)
 def test_short_label_and_existing_priority(self):
  text=(R/'schedule/ui.js').read_text()
  self.assertNotIn('소속사 중요 공지',text);self.assertIn('★ 소속사 공지',text)
  self.assertIn('schedulePriority(x)',text)
if __name__=='__main__':unittest.main()
