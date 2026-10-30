"""Exact-build Berriz calendar checks; synthetic public metadata only, no accounts."""
from pathlib import Path
from playwright.sync_api import sync_playwright
import os,json,copy
ROOT=Path(__file__).resolve().parents[1];OUT=Path(os.getenv('BERRIZ_OUT',str(ROOT/'test-results/berriz')));OUT.mkdir(parents=True,exist_ok=True)
URL=os.getenv('BERRIZ_URL','http://127.0.0.1:4199/').rstrip('/')+'/'
checks=[];errors=[]
def check(name,ok):
 checks.append({'name':name,'passed':bool(ok)})
 if not ok:raise AssertionError(name)
seed=json.loads((ROOT/'schedule/seed.json').read_text());now='2026-10-30T12:28:17Z'
for id,label,path in [('berriz-notice','베리즈 · 소속사 중요 공지','notice'),('berriz-calendar','베리즈 · 공식 캘린더','calendar')]:
 seed['sources'].append({'id':id,'label':label,'url':'https://berriz.in/ko/isegyeidol/'+path+'/','kind':'official','mode':'public_browser','state':'ok','lastSuccessAt':now,'detail':'공개 메뉴 확인'})
seed['generatedAt']='2099-01-01T00:00:00Z'
seed['news'].append({'id':'berriz-notice-2673','sourceId':'berriz-notice','sourceUrl':'https://berriz.in/ko/isegyeidol/notice/2673/','title':'[안내] 아이네 활동·스케줄 관련 공식 안내','members':['ine'],'publishedAt':'2026-10-27T00:00:00+09:00','checkedAt':now})
for ident,title,date,time,ids,kind in [('birthday','HAPPY JINGBURGER DAY','2026-10-08',None,['jingburger'],'anniversary'),('release','Across Dimensions ALBUM RELEASE','2026-11-09','18:00',['ine','jingburger','lilpa','jururu','gosegu','viichan'],'release'),('one','공식 일정 A','2026-10-27','18:00',['ine'],'event'),('two','공식 일정 B','2026-10-27','19:00',['ine'],'event')]:
 seed['events'].append({'id':'berriz-calendar-'+ident,'calendarId':ident,'sourceId':'berriz-calendar','sourceUrl':'https://berriz.in/ko/isegyeidol/calendar/','title':title,'members':ids,'publishedAt':None,'checkedAt':now,'date':date,'time':time,'type':kind,'certainty':'confirmed','status':'scheduled','allDay':time is None,'dateBasis':'official_calendar','detail':'공식 캘린더의 한국 시간'})
try:
 with sync_playwright() as p:
  b=p.chromium.launch();c=b.new_context(viewport={'width':1440,'height':1000},locale='ko-KR');page=c.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
  c.route('**/api/schedule',lambda r:r.fulfill(json=seed))
  page.goto(URL+'#/schedule?month=2026-10&date=2026-10-27',wait_until='networkidle');page.wait_for_timeout(300)
  check('Berriz notice is highest-priority first day entry',page.locator('[data-date="2026-10-27"] .sc-chip').first.get_attribute('data-priority')=='0')
  check('highest-priority notice visible without expanding',page.locator('[data-date="2026-10-27"] .sc-chip').first.inner_text().startswith('★'))
  check('selected day first item is agency notice',page.locator('.sc-day-list .sc-event').first.get_attribute('data-schedule-source')=='https://berriz.in/ko/isegyeidol/notice/2673/')
  check('explicit agency badge',page.locator('.sc-day-list .sc-important').inner_text()=='★ 소속사 공지')
  check('two separate official calendar events retained',page.locator('.sc-day-list a[href="https://berriz.in/ko/isegyeidol/calendar/"]').count()==2)
  check('existing same-day Jururu is still one notice',page.locator('.sc-day-list a[href$="/22131584"]').count()==1)
  check('no restored recent-news panel',page.locator('.sc-news').count()==0)
  check('four-entry layout kept',page.locator('[data-date="2026-10-27"] .sc-chip').count()==4)
  day=page.locator('[data-date="2026-10-26"]');day.scroll_into_view_if_needed();y=page.evaluate('scrollY');day.click();page.wait_for_timeout(150)
  check('date scroll position preserved',abs(page.evaluate('scrollY')-y)<=2)
  page.locator('[data-filter=source]').select_option('berriz');page.wait_for_timeout(200)
  check('Berriz source filter',page.locator('[data-filter=source]').input_value()=='berriz')
  page.locator('[data-date="2026-10-27"]').click();page.wait_for_timeout(150)
  check('Berriz filter excludes cafe rows',all('berriz.in' in u for u in page.locator('.sc-day-list .sc-event').evaluate_all('(xs)=>xs.map(x=>x.dataset.scheduleSource)')))
  page.locator('.sc-calendar').screenshot(path=str(OUT/'berriz-priority-calendar.png'))
  page.locator('.sc-agenda').screenshot(path=str(OUT/'berriz-priority-detail.png'))
  page.goto(URL+'#/schedule?month=2026-11&date=2026-11-09&source=berriz',wait_until='networkidle')
  check('official November release shown','Across Dimensions' in page.locator('.sc-agenda').inner_text())
  check('release actual time in KST','18:00' in page.locator('.sc-agenda').inner_text())
  check('release not a publication record',page.locator('.sc-day-list .sc-event').first.get_attribute('data-schedule-record-type')=='release')
  page.locator('.sc-calendar').screenshot(path=str(OUT/'berriz-november-calendar.png'))
  page.goto(URL+'#/schedule?month=2026-10&date=2026-10-08&source=berriz',wait_until='networkidle')
  check('birthday is October 8 KST','HAPPY JINGBURGER DAY' in page.locator('.sc-agenda').inner_text())
  check('birthday no midnight appointment','종일' in page.locator('.sc-agenda').inner_text() and '00:00' not in page.locator('.sc-agenda').inner_text())
  check('birthday member color retained',page.locator('.sc-day-list .sc-event').first.get_attribute('data-member-tone')=='jingburger')
  for width in (320,390,768,1440):
   page.set_viewport_size({'width':width,'height':900});check('no page overflow '+str(width),page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
  page.set_viewport_size({'width':390,'height':844});page.goto(URL+'#/schedule?month=2026-10&date=2026-10-27&source=berriz',wait_until='networkidle')
  page.locator('.sc-agenda').screenshot(path=str(OUT/'berriz-detail-mobile.png'))
  page.evaluate('document.documentElement.dataset.theme="dark"');check('dark priority badge visible',page.locator('.sc-day-list .sc-important').is_visible());page.locator('.sc-agenda').screenshot(path=str(OUT/'berriz-detail-dark.png'))
  bad=copy.deepcopy(seed);bad['news'].append({'id':'berriz-notice-999','sourceId':'berriz-notice','sourceUrl':'https://berriz.in/ko/isegyeidol/board/999/','title':'DO NOT PUBLISH','members':['ine'],'publishedAt':now,'checkedAt':now})
  c.unroute('**/api/schedule');c.route('**/api/schedule',lambda r:r.fulfill(json=bad));page.locator('.sc-sources').evaluate('(x)=>x.open=true');page.locator('[data-schedule-refresh]').click();page.wait_for_timeout(200)
  check('fan board masquerading as official rejected','DO NOT PUBLISH' not in page.locator('#main').inner_text())
  check('bad feed retains last known official notices','아이네 활동' in page.locator('.sc-agenda').inner_text())
  check('bad feed not false success','갱신 확인 실패' in page.locator('.sc-refresh-status').inner_text())
  check('no browser exceptions',not errors);b.close()
finally:
 (OUT/'result.json').write_text(json.dumps({'url':URL,'passed':sum(x['passed'] for x in checks),'total':len(checks),'checks':checks,'browserErrors':errors},ensure_ascii=False,indent=2))
