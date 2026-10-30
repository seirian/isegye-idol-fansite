"""Read owner-selected public Berriz menus without login, bodies or fan posts."""
from datetime import datetime, timedelta, timezone, date
from urllib.parse import urlsplit, parse_qs
from urllib.robotparser import RobotFileParser
from urllib.request import Request, build_opener, HTTPRedirectHandler
import re
KST=timezone(timedelta(hours=9))
NOTICE='https://berriz.in/ko/isegyeidol/notice/'
CALENDAR='https://berriz.in/ko/isegyeidol/calendar/'
AGENT='IsegyeSchedule/1.0 (+https://isegye-idol.kr/auth/terms)'
NAMES={'아이네':'ine','징버거':'jingburger','릴파':'lilpa','주르르':'jururu','고세구':'gosegu','비챤':'viichan'}
ALL=list(NAMES.values())
SOURCES=[{'id':'berriz-notice','label':'베리즈 · 소속사 중요 공지','kind':'official','url':NOTICE,'mode':'public_browser'}, {'id':'berriz-calendar','label':'베리즈 · 공식 캘린더','kind':'official','url':CALENDAR,'mode':'public_browser'}]
class BerrizError(RuntimeError):pass
class NoRedirect(HTTPRedirectHandler):
 def redirect_request(self,*args):return None

def canonical(url,source=None):
 try:
  p=urlsplit(url)
  if p.scheme!='https' or p.hostname!='berriz.in' or p.username or p.password or p.port not in (None,443) or p.query or p.fragment:return None
  if re.fullmatch(r'/ko/isegyeidol/notice/[1-9]\d*/?',p.path) and source in (None,'berriz-notice'):return 'https://berriz.in'+p.path.rstrip('/')+'/'
  if p.path.rstrip('/')=='/ko/isegyeidol/calendar' and source in (None,'berriz-calendar'):return CALENDAR
 except (ValueError,TypeError):pass
 return None

def members(title,names=None):
 if names is not None:
  ids=[NAMES[n] for n in names if n in NAMES]
  if ids:return sorted(set(ids),key=ALL.index)
 ids=[v for k,v in NAMES.items() if k in title]
 for token,ident in [('JINGBURGER','jingburger'),('LILPA','lilpa'),('JURURU','jururu'),('GOSEGU','gosegu'),('VIICHAN','viichan'),('INE','ine')]:
  if re.search(r'\b'+token+r'\b',title,re.I) and ident not in ids:ids.append(ident)
 return ids or ALL[:]

def clean_title(title):
 title=re.sub(r'\s+',' ',str(title)).strip()
 if not 1<=len(title)<=240:raise BerrizError('invalid_title')
 if re.search(r'컨디션|건강|병원|수술|치료|진단',title):return '[안내] '+('·'.join(n for n in NAMES if n in title) or '아티스트')+' 활동·스케줄 관련 공식 안내'
 return title

def notice_row(link,now):
 url=canonical(link.get('url',''),'berriz-notice')
 if not url:return None
 text=str(link.get('text','')).strip();match=re.search(r'(20\d{2})[.]\s*(\d{1,2})[.]\s*(\d{1,2})\s*$',text)
 if not match:raise BerrizError('notice_date_missing')
 day=date(*map(int,match.groups())).isoformat();title=clean_title(text[:match.start()].strip())
 if re.search(r'팬클럽\s*전용|회원\s*전용|MEMBERS\s*ONLY',title,re.I):return None
 return {'id':'berriz-notice-'+url.rstrip('/').split('/')[-1],'sourceId':'berriz-notice','sourceUrl':url,'title':title,'members':members(title),'publishedAt':day+'T00:00:00+09:00','publicationPrecision':'day','checkedAt':now,'detail':'베리즈 공식 공지 · 게시일 기준 · 전문은 원문에서 확인'}

def aware(value):
 try:
  d=datetime.fromisoformat(value.replace('Z','+00:00'))
  if d.tzinfo is None:raise ValueError()
  return d.astimezone(KST)
 except (ValueError,TypeError,AttributeError):raise BerrizError('invalid_calendar_timestamp') from None

def calendar_rows(items,month,visible,now):
 if not isinstance(items,list) or len(items)>300:raise BerrizError('calendar_schema_changed')
 out=[];now_dt=aware(now)
 for row in items:
  if not isinstance(row,dict):raise BerrizError('calendar_schema_changed')
  vis=row.get('visibility') or {}
  if vis.get('status')!='PUBLISHED':continue
  if vis.get('publishAt') and aware(vis['publishAt'])>now_dt:continue
  title=str(row.get('title','')).strip()
  if title not in visible or re.search(r'팬클럽\s*전용|회원\s*전용|MEMBERS\s*ONLY',title,re.I):continue
  ident=str(row.get('id',''))
  if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',ident):raise BerrizError('invalid_calendar_id')
  start=aware(row.get('startDate'));end=aware(row['endDate']) if row.get('endDate') else start
  if end<start or (end-start).days>366:raise BerrizError('invalid_calendar_range')
  all_day=row.get('isAllDay')
  if type(all_day) is not bool:raise BerrizError('calendar_schema_changed')
  # No guessed recurrence or end-date inclusivity: explicit start and original end.
  if start.strftime('%Y-%m')!=month:continue
  kind={'RELEASE':'release','BIRTHDAY':'anniversary','CELEBRATION':'anniversary','BROADCAST':'broadcast','LIVE':'broadcast'}.get(row.get('type'),'event')
  out.append({'id':'berriz-calendar-'+ident,'calendarId':ident,'sourceId':'berriz-calendar','sourceUrl':CALENDAR,'title':clean_title(title),'members':members(title,[x.get('name') for x in row.get('members',[]) if isinstance(x,dict)]),'publishedAt':None,'checkedAt':now,'date':start.date().isoformat(),'time':None if all_day else start.strftime('%H:%M'),'type':kind,'certainty':'confirmed','status':'scheduled','allDay':all_day,'startAt':start.isoformat(),'endAt':end.isoformat() if row.get('endDate') else None,'dateBasis':'official_calendar','detail':'베리즈 공식 캘린더의 일정 · 한국 시간(KST)'+(' · 종일' if all_day else '')})
 return out

def month_shift(month,offset):
 y,m=map(int,month.split('-'));n=y*12+m-1+offset
 return f'{n//12:04}-{n%12+1:02}'

def robots_ok(read=None):
 if read is None:
  def read(url):
   with build_opener(NoRedirect).open(Request(url,headers={'User-Agent':AGENT}),timeout=20) as r:
    if r.status!=200:raise BerrizError('robots_unavailable')
    raw=r.read(100001)
    if len(raw)>100000:raise BerrizError('robots_too_large')
    return raw.decode('utf-8')
 rules=read('https://berriz.in/robots.txt');p=RobotFileParser();p.parse(rules.splitlines())
 if not all(p.can_fetch(AGENT,u) for u in (NOTICE,CALENDAR)):raise BerrizError('robots_disallowed')

def read_public(now):
 """One anonymous session. No direct service API calls or account credentials."""
 from playwright.sync_api import sync_playwright
 robots_ok();result={};today=aware(now).strftime('%Y-%m');target_months=[month_shift(today,i) for i in (-1,0,1,2)]
 with sync_playwright() as p:
  browser=p.chromium.launch();context=browser.new_context(locale='ko-KR',timezone_id='Asia/Seoul',user_agent=AGENT,viewport={'width':1440,'height':1000})
  def route(r):
   host=urlsplit(r.request.url).hostname or ''
   if (host not in ('berriz.in','svc-api.berriz.in') and not host.endswith('.berriz.in')) or r.request.resource_type in ('image','media','font'):r.abort()
   else:r.continue_()
  context.route('**/*',route);page=context.new_page()
  def visit(url):
   r=page.goto(url,wait_until='domcontentloaded',timeout=45000)
   if not r or r.status!=200:raise BerrizError('public_page_unavailable')
   page.wait_for_timeout(1800)
   if page.url.rstrip('/')!=url.rstrip('/'):raise BerrizError('public_page_redirected')
   if re.search(r'CAPTCHA|접근이 제한|Access Denied|Verify you are human',page.locator('body').inner_text(),re.I):raise BerrizError('public_page_restricted')
  try:
   try:
    visit(NOTICE)
    page.wait_for_function(r'''()=>[...document.querySelectorAll('a[href]')].some(a=>/\/isegyeidol\/notice\/\d+\/?$/.test(a.href))''',timeout=15000)
    previous=-1;stable=0
    for _ in range(8):
     count=page.locator('a[href*="/isegyeidol/notice/"]').count();stable=stable+1 if count==previous else 0
     if stable>=2:break
     previous=count;page.evaluate('window.scrollTo(0,document.body.scrollHeight)');page.wait_for_timeout(900)
    links=page.locator('a[href*="/isegyeidol/notice/"]').evaluate_all('(xs)=>xs.map(x=>({url:x.href,text:x.innerText}))');news={}
    for link in links:
     row=notice_row(link,now)
     if row:news[row['id']]=row
    if not news:raise BerrizError('no_public_notices')
    result['berriz-notice']={'news':list(news.values()),'events':[],'coverage':{'mode':'public_list','count':len(news),'complete':False},'detail':'공개 공식 공지 목록 확인 · 본문·팬 글 수집 안 함'}
   except Exception as e:result['berriz-notice']={'error':str(e) if isinstance(e,BerrizError) else 'public_browser_unavailable'}
   payloads={}
   def response(r):
    u=urlsplit(r.url);q=parse_qs(u.query)
    if u.hostname=='svc-api.berriz.in' and u.path=='/service/v1/calendar/schedule' and q.get('communityId')==['40'] and q.get('timeZone')==['Asia/Seoul'] and r.status==200:
     try:
      v=r.json()
      if v.get('code')=='0000':payloads[q.get('year',[''])[0]+'-'+q.get('month',[''])[0].zfill(2)]=v.get('data')
     except Exception:pass
   page.on('response',response)
   try:
    visit(CALENDAR);page.get_by_role('button',name='다음 달',exact=True).wait_for(timeout=15000);current=today;events={};done=[]
    for month in target_months:
     offset=(int(month[:4])-int(current[:4]))*12+int(month[5:])-int(current[5:])
     for _ in range(abs(offset)):
      page.get_by_role('button',name='다음 달' if offset>0 else '이전 달',exact=True).click();page.wait_for_timeout(900)
     current=month;page.wait_for_timeout(800);body=page.locator('body').inner_text()
     if not re.search(rf'{int(month[:4])}\.\s*0?{int(month[5:])}(?:\s|$)',body):raise BerrizError('calendar_month_not_displayed')
     page.wait_for_timeout(500)
     if month not in payloads:raise BerrizError('calendar_data_unavailable')
     data=payloads[month]
     visible={str(x.get('title','')) for x in data if isinstance(x,dict) and str(x.get('title','')) in body}
     for row in calendar_rows(data,month,visible,now):events[row['id']]=row
     done.append(month)
    result['berriz-calendar']={'news':[],'events':list(events.values()),'coverage':{'months':done,'complete':True},'detail':'공개 캘린더 확인 · '+done[0]+' ~ '+done[-1]+' · 한국 시간'}
   except Exception as e:result['berriz-calendar']={'error':str(e) if isinstance(e,BerrizError) else 'public_browser_unavailable'}
  finally:context.close();browser.close()
 return result
