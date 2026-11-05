from pathlib import Path
import sys,unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from build_review_2nd import adapt_app,one
from build_review_2nd_host import patched,HOOK
from build_review_host import HOOK as FIRST_HOOK
class SecondReview(unittest.TestCase):
 def test_all_requested_choices(self):
  a=adapt_app((ROOT/'review-1st/app.js').read_text())
  for item in ("['content','콘텐츠'","ProductionUI.live()","ProductionUI.members()","ProductionUI.member(id)",'OUR STORY','SINCE 2021','차곡차곡, 우리의 발자취.','오디션의 첫 시작부터 음악과 무대, 함께 만든 순간까지.','data-member-tone','data-agency','★ 소속사 공지'):self.assertIn(item,a)
  for item in ('OUR TIMELINE','기록과 기록 사이의 이야기','LIVE·방송',"['now','방송 중']","const tab=p.get('tab')||'intro'"):self.assertNotIn(item,a)
  self.assertIn('isegye:review2:prefs',a);self.assertNotIn('isegye:review1:prefs',a)
 def test_music_source_is_unchanged(self):
  before=(ROOT/'review-1st/app.js').read_text();after=adapt_app(before)
  a,b='function musicView(p)','function liveCardsHtml('
  self.assertEqual(before[before.index(a):before.index(b)],after[after.index(a):after.index('function contentView(')])
 def test_patches_fail_when_source_moves(self):
  with self.assertRaises(ValueError):one('x','y','z')
 def test_gate_order_and_preservation(self):
  original=(ROOT/'auth/Gateway.php').read_text();s=patched(original)
  self.assertEqual(s.replace(HOOK,'').replace(FIRST_HOOK,''),original)
  self.assertLess(s.index("if (!$access['allowed'])"),s.index(HOOK))
  self.assertIn('/review-1st/',s);self.assertIn('/review-2nd/',s)
 def test_handler_separate_and_read_only(self):
  a=(ROOT/'review-1st/hosting/ReviewPreview.php').read_text();b=(ROOT/'review-2nd/hosting/Review2Preview.php').read_text()
  self.assertEqual(b,a.replace('ReviewPreview','Review2Preview').replace('review-1st','review-2nd').replace('isegye-first-review','isegye-second-review'))
  for x in ('file_put_contents','accounts.json','config.json','exec('):self.assertNotIn(x,b)
 def test_hosting_preserves_first_and_production(self):
  s=(ROOT/'scripts/deploy_review_2nd.py').read_text()
  for x in ('firstReviewUnchanged=True','first_html_hash','rollbackRestoredPreviousEntry','refs/heads/feature/review-2nd','productionUIUnchanged=True'):self.assertIn(x,s)
  self.assertNotIn("remote.replace(d.ROOT+'/.htaccess'",s)
if __name__=='__main__':unittest.main()
