"""Exact calendar bundle checks. Fixture replacement is browser-only, never production."""
from pathlib import Path
from playwright.sync_api import sync_playwright
import os,json,copy
ROOT=Path(__file__).resolve().parents[1];OUT=Path(os.getenv('SCHEDULE_OUT',str(ROOT/'test-results/schedule')));OUT.mkdir(parents=True,exist_ok=True)
URL=os.getenv('SCHEDULE_URL','http://127.0.0.1:4199/').rstrip('/')+'/'
seed=json.loads((ROOT/'schedule/snapshot.json').read_text());checks=[];errors=[]
def check(name,ok):
 checks.append({'name':name,'passed':bool(ok)})
 if not ok:raise AssertionError(name)
try:
 with sync_playwright() as p:
  b=p.chromium.launch();c=b.new_context(viewport={'width':1440,'height':1000},locale='ko-KR');page=c.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
  c.route('**/api/schedule',lambda r:r.fulfill(json=seed))
  page.goto(URL+'#/schedule?month=2026-10&date=2026-10-30',wait_until='networkidle')
  check('calendar first',page.locator('.sc-calendar').count()==1)
  check('announcement block removed','공식 발표 확인하기' not in page.locator('#main').inner_text())
  check('30 inspected announcements retained',page.locator('.sc-news-item').count()==8)
  check('six fan forecasts separate from events',page.locator('.sc-forecast-row').count()==6)
  check('fan forecast explicitly uncertain','팬 정리 · 미확정' in page.locator('.sc-forecast').inner_text())
  check('no body copies',page.locator('.sc-news-item').first.inner_text().find('본문 일정 미확인')>=0)
  check('calendar October days',page.locator('[data-action=date]').count()==31)
  page.locator('.sc-page').screenshot(path=str(OUT/'calendar-desktop.png'))
  page.screenshot(path=str(OUT/'calendar-desktop-top.png'),full_page=False)
  page.locator('#schedule-member').select_option('ine');page.wait_for_timeout(120)
  check('member filter forecast',page.locator('.sc-forecast-row').count()==1)
  page.locator('[data-filter=source]').select_option('official');page.wait_for_timeout(120)
  check('official filter excludes fan',page.locator('.sc-forecast-row').count()==0)
  page.goto(URL+'#/schedule?month=2026-10&date=2026-10-30',wait_until='networkidle')
  page.locator('[aria-label="다음 달"]').click();page.wait_for_timeout(120)
  check('next month works','2026년 11월' in page.locator('.calendar-header').inner_text())
  check('no forecast spills next day',page.locator('.sc-forecast-row').count()==0)
  page.goto(URL+'#/schedule?month=2026-09&date=2026-09-28',wait_until='networkidle')
  check('old verified release preserved','NO CAT, NO LIFE!' in page.locator('.calendar-layout').inner_text())
  page.goto(URL+'#/schedule?month=2026-10&date=2026-10-30',wait_until='networkidle')
  for width in (320,390,768,1440):
   page.set_viewport_size({'width':width,'height':900})
   if page.evaluate('document.documentElement.scrollWidth>innerWidth'):
    page.screenshot(path=str(OUT/('overflow-'+str(width)+'.png')),full_page=True)
    (OUT/('overflow-'+str(width)+'.json')).write_text(json.dumps(page.locator('body *').evaluate_all('(xs)=>xs.map(x=>({tag:x.tagName,cls:x.className,left:x.getBoundingClientRect().left,right:x.getBoundingClientRect().right})).filter(x=>x.right>innerWidth+1||x.left< -1)'),ensure_ascii=False))
   check('no overflow '+str(width),page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
  page.evaluate('document.documentElement.dataset.theme="dark"');page.screenshot(path=str(OUT/'calendar-dark.png'),full_page=True)
  page.set_viewport_size({'width':390,'height':844});page.evaluate('document.documentElement.dataset.theme="light"');page.screenshot(path=str(OUT/'calendar-mobile.png'),full_page=True)
  page.locator('.sc-page').evaluate("x=>x.style.fontSize='32px'");check('200 percent no overflow',page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
  c.unroute('**/api/schedule');c.route('**/api/schedule',lambda r:r.fulfill(status=503,body='unavailable'))
  page.locator('[data-schedule-refresh]').click();page.wait_for_timeout(200)
  check('failure preserves known news',page.locator('.sc-news-item').count()==8)
  check('failure is not false freshness','갱신 확인 실패' in page.locator('.sc-sync').inner_text())
  check('no exceptions',not errors);b.close()
finally:(OUT/'result.json').write_text(json.dumps({'url':URL,'passed':sum(x['passed'] for x in checks),'total':len(checks),'checks':checks,'browserErrors':errors},ensure_ascii=False,indent=2))
