"""Regression guards for simplified schedule and current about page."""
from pathlib import Path
import sys,unittest,subprocess,json
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
 def test_dedupe_suppresses_only_identical_day_member_title(self):
  app=review.adapt_app((ROOT/'review-1st/app.js').read_text())
  self.assertIn("scheduleUniqueRows(rows)",app)
  sched=app[app.index('function scheduleView(p)'):app.index('function sourceBox(')]
  self.assertIn('rows=scheduleUniqueRows(rows);',sched)
  self.assertIn('${memberChips(p)}</div><form class="search-form"',sched)
  self.assertNotIn('</div>${memberChips(p)}<form class="search-form"',sched)
  script=app[app.index('function scheduleUniqueRows(rows)'):app.index('function scheduleView(p)')]
  samples=[
   dict(kind='notice',date='2026-11-06',title='[징버거] 오늘 뱅온',members=['jingburger'],id='notice'),
   dict(kind='event',date='2026-11-06',title='[징버거] 오늘 뱅온',members=['jingburger'],id='event'),
   dict(kind='notice',date='2026-11-07',title='[징버거] 오늘 뱅온',members=['jingburger'],id='tomorrow'),
   dict(kind='notice',date='2026-11-06',title='[비챤] 오늘 뱅온',members=['viichan'],id='other-member')]
  program=script+'console.log(JSON.stringify(scheduleUniqueRows('+json.dumps(samples,ensure_ascii=False)+').map(x=>x.id)))'
  result=subprocess.run(['node','-e',program],capture_output=True,text=True,check=True)
  self.assertEqual(json.loads(result.stdout),['event','tomorrow','other-member'])
 def test_schedule_filter_row_css(self):
  css=(ROOT/'site/schedule-filter-layout.css').read_text()
  self.assertIn('.filter-row>.chips',css)
  self.assertIn('margin-left:auto',css)
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
