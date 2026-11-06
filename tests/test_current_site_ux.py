"""Regression guards for simplified schedule and current about page."""
from pathlib import Path
import sys,unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import build_review_2nd as review
import review_2nd_polish as polish

class CurrentSiteUX(unittest.TestCase):
 def test_schedule_filters_and_confirmed_status(self):
  src=(ROOT/'review-1st/app.js').read_text()
  app=review.adapt_app(src)
  schedule=app[app.index('function scheduleView(p)'):app.index('function sourceBox(')]
  self.assertNotIn("choose('종류'",schedule)
  self.assertNotIn("choose('멤버 조건'",schedule)
  self.assertNotIn('>오늘</a>',schedule)
  self.assertIn("choose('출처'",schedule)
  self.assertIn('memberChips(p)',schedule)
  self.assertIn("p.delete('kind');p.delete('match')",schedule)
  self.assertIn("badge(r.status==='cancelled'?'취소':'미확정','warning')",app)
  self.assertNotIn("'확정 일정'",app[app.index('function eventView(id)'):app.index('function albumCard(')])
 def test_about_page_is_current_not_preview_copy(self):
  about=(ROOT/'site/about-current.js').read_text()
  for item in ('오늘의 이세돌','멤버 소개','소식·일정','음악','LIVE','콘텐츠','활동 기록','자동 수집','비공식'):
   self.assertIn(item,about)
  for old in ('8개 메뉴','미구현입니다','관리자 CMS는 없습니다','운영 도메인과 호스팅 연결'):
   self.assertNotIn(old,about)
  adapter=(ROOT/'scripts/promote_review_2nd.py').read_text()
  self.assertIn("site/about-current.js",adapter)
 def test_approved_base_is_not_modified(self):
  self.assertIn("reviewed_data.pop('videos')",(ROOT/'scripts/promote_review_2nd.py').read_text())
  self.assertIn("ProductionUI.about()",polish.app(review.adapt_app((ROOT/'review-1st/app.js').read_text())))
if __name__=='__main__':unittest.main()
