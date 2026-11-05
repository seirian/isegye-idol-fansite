"""Test accepted UI on the final production bundle, with synthetic public feeds.

CI: exact multi-file bundle over loopback HTTP. Container: an offline composition
of the same JS/CSS, no network or authentication. No production login/write.
"""
from pathlib import Path
from datetime import datetime,timezone,timedelta
import base64,hashlib,json,os,re
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'test-results/promoted-review';OUT.mkdir(parents=True,exist_ok=True)
URL=os.getenv('PROMOTED_URL');checks=[];errors=[]

def check(name,ok):
 checks.append({'name':name,'passed':bool(ok)});assert ok,name

def offline():
 dist=ROOT/'dist';html=(dist/'index.html').read_text();data=(dist/'src/data.js').read_text()
 def embed(m):
  path=dist/m.group(1).split('?')[0]
  return json.dumps('data:image/webp;base64,'+base64.b64encode(path.read_bytes()).decode())
 data=re.sub(r'"(assets/[^"]+\.webp(?:\?[^\"]*)?)"',embed,data)
 # All asset references present in data; other failed thumbnails remain readable.
 parts=[]
 for rel in re.findall(r'<script src="([^"]+)"></script>',html):
  parts.append(data if rel=='src/data.js' else (dist/rel).read_text())
 code='\n'.join(parts);css=(dist/'src/styles.css').read_text()
 sha=lambda s:base64.b64encode(hashlib.sha256(s.encode()).digest()).decode()
 html=re.sub(r'<script src="[^"]+"></script>','',html).replace('<link rel="stylesheet" href="src/styles.css">','<style>'+css+'</style>')
 html=re.sub(r'<link rel="icon"[^>]+>','',html)
 html=html.replace("script-src 'self'", "script-src 'sha256-"+sha(code)+"'").replace("style-src 'self'", "style-src 'sha256-"+sha(css)+"'")
 return html.replace('</body>','<script>'+code+'</script></body>')

try:
 with sync_playwright() as pw:
  opts={'executable_path':os.environ['CHROMIUM_PATH']} if os.getenv('CHROMIUM_PATH') else {}
  b=pw.chromium.launch(**opts);p=b.new_page(viewport={'width':1440,'height':1000},locale='ko-KR')
  p.on('pageerror',lambda e:errors.append(str(e)));p.route('https://**/*',lambda r:r.abort())
  if URL:
   p.route('**/api/*',lambda r:r.fulfill(status=503,content_type='application/json',body='{}'))
   p.goto(URL,wait_until='load')
  else:
   p.evaluate("""()=>{const data=new Map([['isegye:theme:v1','light'],['isegye:bookmarks:v1','[\"ine\",\"rewind\"]']]);Object.defineProperty(window,'localStorage',{value:{getItem:k=>data.get(k)||null,setItem:(k,v)=>data.set(k,String(v)),removeItem:k=>data.delete(k)},configurable:true})}""")
   p.set_content(offline(),wait_until='load')
  def go(route):
   p.evaluate('(r)=>{location.hash="#/"+r;render()}',route);p.wait_for_timeout(35)
  go('home')
  check('accepted seven menus',p.locator('.desktop-nav>a').all_text_contents()==['오늘의 이세돌','멤버 소개','소식·일정','음악','LIVE','콘텐츠','활동 기록'])
  check('no preview banner or settings shortcut',not p.locator('a[href="#/settings"],a[href="#/review"]').count() and '2차 검토' not in p.locator('.review-bar').inner_text())
  if not URL:
   check('legacy theme retained',p.evaluate('prefs.theme==="light"'))
   check('legacy bookmarks imported',p.evaluate('prefs.favorites.includes("member:ine")&&prefs.favorites.includes("song:rewind")'))
   check('legacy values never removed',p.evaluate('localStorage.getItem("isegye:bookmarks:v1")!==null'))
  for theme in ('dark','light'):
   for width in (320,390,768,1440):
    p.set_viewport_size({'width':width,'height':1000});p.evaluate('(t)=>{prefs.theme=t}',theme)
    for route,title in [('home','오늘의 이세돌'),('members','멤버 소개'),('live','지금, 우리와 함께 LIVE'),('content','콘텐츠'),('music','한 곡에서 시작되는 이야기'),('history','차곡차곡, 우리의 발자취.'),('schedule?month=2026-11&view=calendar','소식·일정'),('guide','좋아하는 마음이 오래 가도록')]:
     go(route);check(f'{theme}/{width}/{route} title',p.locator('h1').first.inner_text()==title)
     check(f'{theme}/{width}/{route} no overflow',p.evaluate('document.documentElement.scrollWidth<=innerWidth'))
     check(f'{theme}/{width}/{route} operating footer',p.locator('.footer-links a').all_text_contents()==['이용약관','개인정보처리방침','팬가이드','사이트소개'])
     if width in (390,1440) and theme=='dark':p.screenshot(path=str(OUT/(route.split('?')[0]+'-'+str(width)+'.png')),full_page=True)
  p.set_viewport_size({'width':1440,'height':1000});go('guide')
  links=p.locator('a[href^="/#/record/"]').evaluate_all('(xs)=>xs.map(x=>x.getAttribute("href").split("#/")[1])')
  for link in links:
   go(link);check('operating guide detail '+link,p.locator('.article').count()>0)
  go('report?record=fan-policy');check('existing report handoff retained',p.locator('#report-form').count()==1)
  go('content?tab=series');check('removed multiview absent','같은 합방, 다른 시점' not in p.locator('#main').inner_text())
  for s in ('festival-2025','music-beginning'):
   go('series/'+s);check('removed context heading '+s,'맥락을 더 살펴보기' not in p.locator('#main').inner_text())
  # Validated test data tests new records absent from the compiled catalog.
  now=datetime.now(timezone.utc);gen=(now-timedelta(seconds=1)).isoformat();pub=(now-timedelta(hours=1)).isoformat()
  feed=json.loads((ROOT/'dist/src/schedule.json').read_text());feed['generatedAt']=gen
  row={'articleId':99990001,'menuId':345,'author':'lilpa','members':['lilpa'],'title':'[릴파] 런타임 검증용 공지','publishedAt':pub,'verifiedRole':'staff','public':True,'titleGeneralized':False,'checkedAt':gen}
  feed.setdefault('cafeEvidence',{'schemaVersion':1,'notices':[],'fanSeries':[]})['notices'].append(row)
  feed['news'].append({'id':'cafe-test-99990001','sourceId':'cafe-members','sourceUrl':'https://cafe.naver.com/steamindiegame/99990001','title':row['title'],'members':['lilpa'],'publishedAt':pub,'checkedAt':gen,'detail':'합성 회귀검사 자료'})
  p.evaluate('(f)=>ProductionFeeds.applySchedule(f)',feed)
  check('new approved cafe URL accepted',p.evaluate('notices.has("99990001")'))
  go('search?q=런타임+검증용');check('new cafe appears in global search','런타임 검증용 공지' in p.locator('#main').inner_text())
  go('notice/99990001');p.locator('[data-save="notice:99990001"]').click();go('saved');check('new cafe can be saved',p.locator('[data-item-key="notice:99990001"]').count()==1)
  rejected=json.loads(json.dumps(feed));rejected['news'][-1]['title']='[릴파] 검증 근거와 다른 제목'
  p.evaluate('(f)=>ProductionFeeds.applySchedule(f)',rejected);check('mismatched new URL not published',p.evaluate('!notices.has("99990001")'))
  p.evaluate('(f)=>ProductionFeeds.applySchedule(f)',feed)
  invalid=json.loads(json.dumps(feed));invalid['cafeEvidence']['notices'][-1]['verifiedRole']='ordinary'
  check('bad evidence rejected atomically',p.evaluate('(f)=>{const old=D.notices;try{ProductionFeeds.applySchedule(f);return false}catch{return D.notices===old}}',invalid))
  music={'schemaVersion':1,'feed':'daily-music','generatedAt':gen,'rows':[{'videoId':'testvid0001','channelKey':'c2','title':'자동 갱신 검증곡','members':['ine','jingburger','lilpa','jururu','gosegu','viichan'],'type':'official_track','kind':'official_mv','publishedAt':pub,'checkedAt':gen}]}
  p.evaluate('(f)=>ProductionFeeds.applyMusic(f)',music);check('new daily song indexed',p.evaluate('songs.has("daily-testvid0001")'))
  go('song/daily-testvid0001');check('new song detail renders',p.locator('h1').inner_text()=='자동 갱신 검증곡')
  go('search?q=자동+갱신+검증곡');check('new music searchable',p.locator('[data-item-key="song:daily-testvid0001"]').count()>0)
  bad=json.loads(json.dumps(music));bad['rows'][0]['channelKey']='unreviewed'
  check('invalid music cannot change current data',p.evaluate('(f)=>{const old=D.songs;try{ProductionFeeds.applyMusic(f);return false}catch{return D.songs===old}}',bad))
  key='mh-'+'a'*24;hid='monthly-'+'b'*24
  hist={'schemaVersion':1,'feed':'monthly-history','generatedAt':gen,'windowStart':'2026-10-01','through':((now+timedelta(hours=9)).date().replace(day=1)-timedelta(days=1)).isoformat(),'events':[{'id':hid,'date':'2026-10-15','title':'월간 기록 검증 항목','type':'content','members':['lilpa'],'sources':[key],'summary':'합성 회귀검사 기록','note':'실제 활동이 아닌 검사 데이터','dateBasis':'video_published'}],'sources':{key:{'title':'검사 원본','url':'https://www.youtube.com/watch?v=testvid0001','basis':'official','checkedAt':gen}}}
  p.evaluate('(f)=>ProductionFeeds.applyHistory(f)',hist);check('monthly record indexed',p.evaluate('(id)=>histories.has(id)',hid))
  go('history/'+hid);check('new history detail renders',p.locator('h1').inner_text()=='월간 기록 검증 항목')
  old=json.loads(json.dumps(feed));old['generatedAt']=(now-timedelta(days=1)).isoformat()
  check('older server response rejected',p.evaluate('(f)=>{try{ProductionFeeds.applySchedule(f);return false}catch{return true}}',old))
  # Source observations and missing values must not become a made-up current date.
  check('notice publication time preserved',p.evaluate('(v)=>notices.get("99990001").publishedAt===v',pub))
  if URL:
   p.unroute('**/api/*')
   fixtures={'schedule':feed,'music':music,'history':hist}
   p.route('**/api/*',lambda r:r.fulfill(status=200,content_type='application/json',body=json.dumps(fixtures[r.request.url.rsplit('/',1)[-1]])))
   p.evaluate('async()=>{await ProductionFeeds.refresh(true)}')
   check('operating API refresh preserves verified notice',p.evaluate('notices.has("99990001")'))
   check('operating API refresh preserves music/history',p.evaluate('(id)=>songs.has("daily-testvid0001")&&histories.has(id)',hid))
   p.unroute('**/api/*');p.route('**/api/*',lambda r:r.fulfill(status=503,content_type='application/json',body='{}'))
   p.evaluate('async()=>{await ProductionFeeds.refresh(true)}')
   check('outage retains last verified data',p.evaluate('notices.has("99990001")&&songs.has("daily-testvid0001")'))
   check('outage reported without fake zero','갱신 확인 실패' in p.evaluate('ProductionFeeds.scheduleMessage()'))
  check('no JavaScript errors',not errors)
  b.close()
finally:
 (OUT/'result.json').write_text(json.dumps({'passed':sum(c['passed'] for c in checks),'total':len(checks),'checks':checks,'browserErrors':errors,'scope':'exact multi-file production bundle; synthetic API records' if URL else 'offline composition of production code; no network; synthetic records'},ensure_ascii=False,indent=2)+'\n')
print('Production promotion checks:',len(checks))
