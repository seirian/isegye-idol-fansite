"""Rendered application regression using clearly synthetic monthly-feed records."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json, os
from playwright.sync_api import sync_playwright
URL=os.environ['HISTORY_TEST_URL'];OUT=Path(os.environ['HISTORY_TEST_OUT']);OUT.mkdir(parents=True,exist_ok=True)
NOW=datetime.now(timezone.utc);KST=timezone(timedelta(hours=9));through=(NOW.astimezone(KST).date().replace(day=1)-timedelta(days=1)).isoformat()
key='mh-'+'a'*24;source={'title':'월간 갱신 검증용 공식 소식','url':'https://berriz.in/ko/isegyeidol/notice/999001/','basis':'official','checkedAt':NOW.isoformat()}
row={'id':'monthly-'+'a'*24,'title':'월간 갱신 검증용 앨범 소식','date':'2026-10-12','type':'release','members':['ine'],'sources':[key],'summary':'공식 소식 게시일 검증','note':'실제 행사일이 아닌 게시일 기준입니다.','dateBasis':'notice_published','announced':True}
feed={'feed':'monthly-history','schemaVersion':1,'generatedAt':NOW.isoformat(),'windowStart':'2026-10-01','through':through,'sources':{key:source},'events':[row],'coverage':{'partial':False}}
checks=[]
def check(name,value):
 checks.append({'name':name,'passed':bool(value)})
 if not value:raise AssertionError(name)
with sync_playwright() as p:
 b=p.chromium.launch(executable_path=os.getenv('CHROMIUM_PATH') or None)
 try:
  for width in (390,1440):
   c=b.new_context(viewport={'width':width,'height':950},locale='ko-KR',timezone_id='Asia/Seoul');page=c.new_page();errors=[];requests=[]
   page.on('pageerror',lambda e:errors.append(str(e)))
   page.route('**/api/history',lambda r:(requests.append(r.request.url),r.fulfill(json=feed)))
   page.route('**/api/music',lambda r:r.fulfill(status=503,body='fixture unavailable'))
   page.goto(URL+'#/music',wait_until='networkidle');check(f'{width}: no history requests on other pages',not requests)
   page.goto(URL+'#/history?order=new',wait_until='networkidle');page.get_by_role('heading',name=row['title'],exact=True).wait_for()
   check(f'{width}: original 55 plus monthly record',page.locator('[data-history-event]').count()==56)
   check(f'{width}: publication basis displayed',page.locator('[data-history-event="'+row['id']+'"] .history-event-tags').inner_text().find('공식 소식 게시일')>=0)
   check(f'{width}: through-month displayed',through.replace('-','.') in page.locator('.history-monthly-status').inner_text())
   page.locator('[data-history-filter="member"]').select_option('ine');page.wait_for_timeout(150)
   check(f'{width}: member filter includes addition',page.locator('[data-history-event="'+row['id']+'"]').count()==1)
   page.locator('#history-query').fill('월간 갱신 검증용');page.locator('#history-search button').click();page.wait_for_timeout(150)
   check(f'{width}: monthly entry searchable',page.locator('[data-history-event]').count()==1)
   page.locator('.history-sources summary').click()
   check(f'{width}: canonical source link',page.locator('.history-source a').get_attribute('href')==source['url'])
   check(f'{width}: no horizontal overflow',page.evaluate('document.documentElement.scrollWidth<=window.innerWidth+1'))
   check(f'{width}: no JS errors',not errors)
   page.screenshot(path=str(OUT/f'fixture-history-{width}.png'),full_page=True);c.close()
  c=b.new_context();page=c.new_page();bad={**feed,'events':[{**row,'date':'2099-01-01'}]}
  page.route('**/api/history',lambda r:r.fulfill(json=bad));page.goto(URL+'#/history',wait_until='networkidle')
  check('malformed API keeps curated records',page.locator('[data-history-event]').count()==55)
  check('future events never shown',page.locator('[data-history-date="2099-01-01"]').count()==0);c.close()
 finally:
  b.close();(OUT/'result.json').write_text(json.dumps({'fixture':True,'passed':sum(c['passed'] for c in checks),'total':len(checks),'checks':checks},ensure_ascii=False,indent=2))
