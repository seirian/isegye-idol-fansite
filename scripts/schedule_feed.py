"""Approved sources only; publication dates are not inferred event dates.

The Cafe website AND its internal API disallow automated crawling. They are
therefore not fetched by this collector. Official Search API is optional;
its snippets are discovery, NOT verified member/agency announcements.
"""
from __future__ import annotations
from datetime import datetime, date, timedelta, timezone
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit, urljoin, urlencode
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.error import HTTPError
from urllib.robotparser import RobotFileParser
import hashlib, json, os, re, time, xml.etree.ElementTree as ET
import notice_policy

ROOT=Path(__file__).resolve().parents[1]
KST=timezone(timedelta(hours=9))
AGENT='IsegyeSchedule/1.0 (+https://isegye-idol.kr/auth/terms)'
LIMIT=2*1024*1024
# API Hub migration: credentials must never be sent to the legacy endpoint.
NAVER_SEARCH_URL='https://naverapihub.apigw.ntruss.com/search/v1/cafearticle'
NAVER_SEARCH_HEADER_NAMES=('X-NCP-APIGW-API-KEY-ID','X-NCP-APIGW-API-KEY')
MEMBERS={'ine':'아이네','jingburger':'징버거','lilpa':'릴파','jururu':'주르르','gosegu':'고세구','viichan':'비챤'}
SOURCES=[
 {'id':'cafe-members','label':'이세돌 멤버 공지','kind':'official','url':'https://cafe.naver.com/f-e/cafes/27842958/menus/345?viewType=L','mode':'reviewed_snapshot'},
 {'id':'cafe-agency','label':'패러블 카페 공지','kind':'official','url':'https://cafe.naver.com/f-e/cafes/27842958/menus/1250','mode':'reviewed_snapshot'},
 {'id':'fan-roundup','label':'팬 정리 · 뱅온정보','kind':'fan','url':'https://cafe.naver.com/steamindiegame/22137397','mode':'reviewed_snapshot'},
 {'id':'parable-web','label':'패러블 공식 뉴스룸','kind':'official','url':'https://parable-asia.com/newsroom/','mode':'automatic'},
 {'id':'naver-search','label':'왁물원 새 글 검색','kind':'unverified','url':'https://cafe.naver.com/steamindiegame','mode':'disabled_unverified'},
]
class FeedError(RuntimeError):pass
class NoRedirect(HTTPRedirectHandler):
 def redirect_request(self,*args):return None

def stamp():return datetime.now(timezone.utc).isoformat(timespec='seconds')
def text(value,limit=220):return re.sub(r'\s+',' ',unescape(re.sub('<[^>]+>',' ',str(value)))).strip()[:limit]
def iso(value):
 if not isinstance(value,str):return None
 try:
  dt=datetime.fromisoformat(value.replace('Z','+00:00'))
  return dt if dt.tzinfo else dt.replace(tzinfo=KST)
 except (ValueError,TypeError):return None

def members_in(title):
 if re.search(r'이세계\s*아이돌|이세돌|ISEGYE\s*IDOL',title,re.I):return list(MEMBERS)
 return [i for i,n in MEMBERS.items() if n in title]

def source_url(url):
 try:
  p=urlsplit(url)
  if p.scheme not in ('https','http') or p.username or p.password or p.port not in (None,443,80):return None
  if p.hostname in ('cafe.naver.com','m.cafe.naver.com'):
   match=re.fullmatch(r'/steamindiegame/(\d+)',p.path) or re.fullmatch(r'/(?:f-e|ca-fe)/cafes/27842958/articles/(\d+)',p.path)
   return 'https://cafe.naver.com/steamindiegame/'+match[1] if match else None
  if p.hostname=='parable-asia.com' and not p.fragment and not p.query:
   return 'https://parable-asia.com'+p.path
 except (ValueError,TypeError):pass
 return None

def request(url,headers=None):
 p=urlsplit(url)
 if p.scheme!='https' or p.hostname not in ('parable-asia.com','naverapihub.apigw.ntruss.com') or p.username or p.password or p.port not in (None,443) or p.fragment:raise FeedError('source_not_allowed')
 hub=p.hostname=='naverapihub.apigw.ntruss.com'
 if hub and p.path!='/search/v1/cafearticle':raise FeedError('source_not_allowed')
 # Parable is public and never receives API credentials. No redirects are followed.
 if headers and (not hub or set(k.lower() for k in headers)!={k.lower() for k in NAVER_SEARCH_HEADER_NAMES}):raise FeedError('credential_destination_not_allowed')
 req=Request(url,headers={'User-Agent':AGENT,'Accept':'application/json,application/rss+xml,text/html',**(headers or {})})
 try:
  with build_opener(NoRedirect).open(req,timeout=20) as response:
   raw=response.read(LIMIT+1)
   if len(raw)>LIMIT:raise FeedError('response_too_large')
   if response.status!=200:raise FeedError('http_'+str(response.status))
   return raw
 except HTTPError as err:
  reason='http_'+str(err.code)
  if hub:
   # Gateway errors are nested; Search errors are flat. Keep only safe codes.
   # Never persist response bodies, error messages, request headers or keys.
   try:
    payload=json.loads(err.read(16384))
    detail=payload.get('error',payload) if isinstance(payload,dict) else None
    code=str(detail.get('errorCode','')) if isinstance(detail,dict) else ''
    if re.fullmatch(r'(?:[0-9]{3}|SE[0-9]{2})',code):reason+='_api_'+code
   except Exception:pass
  raise FeedError(reason) from None

class HTML(HTMLParser):
 def __init__(self,content):
  super().__init__(convert_charrefs=True);self.parts=[];self.links=[];self.feeds=[];self.skip=0;self.anchor=None;self.published=None
  self.feed(content)
 def handle_starttag(self,tag,attrs):
  a=dict(attrs)
  if tag in ('script','style','noscript'):self.skip+=1
  if tag in ('p','div','br','li'):self.parts.append('\n')
  if tag=='a':self.anchor=[a.get('href',''),[]]
  if tag=='link' and a.get('type') in ('application/rss+xml','application/atom+xml'):self.feeds.append(a.get('href',''))
  if tag=='meta' and a.get('property')=='article:published_time':self.published=a.get('content')
 def handle_endtag(self,tag):
  if tag in ('script','style','noscript'):self.skip=max(0,self.skip-1)
  if tag=='a' and self.anchor:
   self.links.append((self.anchor[0],text(''.join(self.anchor[1]))));self.anchor=None
  if tag in ('p','div','li'):self.parts.append('\n')
 def handle_data(self,data):
  if not self.skip:
   self.parts.append(data)
   if self.anchor:self.anchor[1].append(data)
 @property
 def plain(self):return '\n'.join(text(s,2000) for s in ''.join(self.parts).splitlines() if text(s))

def explicit_date(value, published=None, relative=False):
 """Only one unambiguous date, optionally 'today/tomorrow' in a verified title."""
 value=text(value,10000); dates=[]; base=iso(published)
 # Ranges and undated day-of-month references are not silently reduced to one day.
 if re.search(r'(?:~|부터|까지|–|—)\s*\d{1,2}(?:일|월|[./])',value):return None
 for y,m,d in re.findall(r'(?<!\d)(20\d{2})\s*(?:[.\-/]|년)\s*(\d{1,2})\s*(?:[.\-/]|월)\s*(\d{1,2})(?:일)?(?!\d)',value):
  try:dates.append(date(int(y),int(m),int(d)))
  except ValueError:return None
 if not dates and base:
  for m,d in re.findall(r'(?<![\d.\-/])(\d{1,2})\s*(?:월|/)\s*(\d{1,2})(?:일)?(?!\d)',value):
   choices=[]
   for year in (base.year-1,base.year,base.year+1):
    try:choices.append(date(year,int(m),int(d)))
    except ValueError:pass
   if not choices:return None
   chosen=min(choices,key=lambda x:abs((x-base.date()).days))
   if abs((chosen-base.date()).days)>183:return None
   dates.append(chosen)
 if not dates and relative and base:
  relative_days=[n for k,n in [('오늘',0),('내일',1),('모레',2)] if k in value]
  if len(relative_days)==1:dates=[base.astimezone(KST).date()+timedelta(days=relative_days[0])]
 if len(set(dates))!=1:return None
 return dates[0].isoformat()

def explicit_time(value):
 matches=re.findall(r'(오전|오후)\s*(\d{1,2})\s*시(?:\s*(\d{1,2})\s*분)?',value)
 if len(matches)==1:
  mer,h,m=matches[0];h=int(h);m=int(m or 0)
  if not 1<=h<=12 or not 0<=m<=59:return None
  return f'{h%12+(12 if mer=="오후" else 0):02}:{m:02}'
 matches=re.findall(r'(?<!\d)([01]?\d|2[0-3]):([0-5]\d)(?!\d)',value)
 if len(matches)==1:return f'{int(matches[0][0]):02}:{matches[0][1]}'
 return None

def event_from_title(title,published,verified=False):
 """Never turn news about a past performance, winners or shipping into a show."""
 if re.search(r'당첨자|후기|성료|배송|결과|지난|어제',title):return None
 if not re.search(r'방송|뱅온|휴뱅|휴방|짧뱅|휴르르|발매|공연|콘서트|개최|팬사인회|생방송|팬미팅',title):return None
 d=explicit_date(title,published,relative=verified)
 if not d:return None
 if re.search(r'휴뱅|휴방|휴르르',title):kind='break'
 elif re.search(r'방송|뱅온|짧뱅|생방송',title):kind='broadcast'
 elif '발매' in title:kind='release'
 else:kind='event'
 status='cancelled' if re.search(r'취소|연기',title) else 'scheduled'
 uncertain=bool(re.search(r'예상|확률|미정|아마|\?|변경 가능',title))
 return {'date':d,'time':explicit_time(title),'type':kind,'certainty':'confirmed' if verified and not uncertain else 'tentative','status':status,'dateBasis':'title','detail':'제목에 명시된 날짜'+(' (작성일 기준 상대 날짜)' if re.search('오늘|내일|모레',title) else '')}

def public_item(source, url, title, published, checked, **extra):
 url=source_url(url)
 if not url:raise FeedError('invalid_source_url')
 members=extra.pop('members',members_in(title))
 return {'id':'post-'+hashlib.sha256(url.encode()).hexdigest()[:16], 'sourceId':source,'sourceUrl':url,
         'title':text(title), 'members':members,'publishedAt':published,'checkedAt':checked,**extra}

def validate(doc):
 if doc.get('schemaVersion')!=1 or doc.get('timezone')!='Asia/Seoul' or not iso(doc.get('generatedAt')):raise FeedError('invalid_snapshot')
 if len(json.dumps(doc).encode())>LIMIT:raise FeedError('snapshot_too_large')
 if not isinstance(doc.get('sources'),list) or {s.get('id') for s in doc['sources']}!={s['id'] for s in SOURCES}:raise FeedError('invalid_sources')
 for bucket in ('events','news','forecasts'):
  rows=doc.get(bucket)
  if not isinstance(rows,list) or len(rows)>700:raise FeedError('invalid_items')
  ids=set()
  for r in rows:
   if r.get('id') in ids or not isinstance(r.get('id'),str):raise FeedError('duplicate_id')
   ids.add(r['id'])
   if not source_url(r.get('sourceUrl','')) or not r.get('title') or len(r['title'])>240:raise FeedError('invalid_item')
   if r.get('sourceId') not in {s['id'] for s in SOURCES}:raise FeedError('unknown_source')
   if not isinstance(r.get('members'),list) or not set(r['members'])<=set(MEMBERS):raise FeedError('invalid_member')
   if not iso(r.get('checkedAt')):raise FeedError('invalid_check_time')
   if r.get('publishedAt') and not iso(r['publishedAt']):raise FeedError('invalid_published_time')
   if bucket!='news':
    try:date.fromisoformat(r.get('date',''))
    except (ValueError,TypeError):raise FeedError('invalid_event_date') from None
    if r.get('certainty') not in ('confirmed','tentative','unknown'):raise FeedError('invalid_certainty')
    if r['sourceId'] in ('fan-roundup','naver-search') and r['certainty']=='confirmed':raise FeedError('unverified_confirmation')
    if r.get('time') and not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d',r['time']):raise FeedError('invalid_time')
   if set(r)&{'body','html','email','memberKey','userId','cookie','token','comments'}:raise FeedError('unnecessary_data')
 return doc

def merge(previous,current):
 """Retain last good source data on failure; do not restamp old observations."""
 current=notice_policy.clean_snapshot(current)
 validate(current)
 if previous:
  previous=notice_policy.clean_snapshot(previous)
  validate(previous)
  for key in ('news','events','forecasts'):
   byid={r['id']:r for r in previous[key]}
   # A successfully re-read URL replaces its previous extracted dates as well.
   fresh_urls={r['sourceUrl'] for r in current['news'] if r['checkedAt']==current['generatedAt']}
   if key in ('events','forecasts'):
    byid={i:r for i,r in byid.items() if r['sourceUrl'] not in fresh_urls}
   for r in current[key]:
    old=byid.get(r['id'])
    if old is None or iso(r['checkedAt'])>=iso(old['checkedAt']):byid[r['id']]=r
   current[key]=sorted(byid.values(),key=lambda r:r.get('publishedAt') or r.get('checkedAt') or '',reverse=True)[:600]
  old={s['id']:s for s in previous['sources']}
  for s in current['sources']:
   if s['state'] not in ('ok','snapshot') and s['id'] in old:s['lastSuccessAt']=old[s['id']].get('lastSuccessAt')
 return validate(current)

def parable(fetch,now):
 robots=fetch('https://parable-asia.com/robots.txt').decode('utf-8',errors='replace')
 rp=RobotFileParser();rp.parse(robots.splitlines())
 def read(u):
  if not rp.can_fetch(AGENT,u):raise FeedError('robots_disallowed')
  return fetch(u)
 html=HTML(read('https://parable-asia.com/newsroom/').decode('utf-8',errors='replace'))
 feeds=[urljoin('https://parable-asia.com/',u) for u in html.feeds]
 feeds=[u for u in feeds if urlsplit(u).hostname=='parable-asia.com' and '/comments/' not in u]
 articles=[]
 if feeds:
  raw=read(feeds[0])
  if b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():raise FeedError('unsafe_xml')
  root=ET.fromstring(raw)
  if root.tag!='rss':raise FeedError('feed_schema_changed')
  from email.utils import parsedate_to_datetime
  for item in root.findall('./channel/item')[:40]:
   title=text(item.findtext('title',''));url=source_url(item.findtext('link',''));published=item.findtext('pubDate')
   if not members_in(title) or not url:continue
   try:published=parsedate_to_datetime(published).isoformat()
   except (ValueError,TypeError):published=None
   content=item.findtext('{http://purl.org/rss/1.0/modules/content/}encoded','') or item.findtext('description','')
   articles.append((title,url,published,HTML(content).plain))
 else:
  seen=set()
  for u,title in html.links:
   u=source_url(urljoin('https://parable-asia.com/',u))
   if not u or u in seen or not members_in(title) or '/category/' in u or '/tag/' in u:continue
   seen.add(u)
   detail=HTML(read(u).decode('utf-8',errors='replace'))
   articles.append((title,u,detail.published,''))
   if len(articles)>=8:break
 if not articles:raise FeedError('no_matching_items')
 news=[];events=[]
 for title,url,published,body in articles:
  n=public_item('parable-web',url,title,published,now,detail='패러블 공식 발표')
  news.append(n)
  event=event_from_title(title,published,True)
  # Body dates: only lines naming an event with explicit year and a single date.
  # Multiple dates / image-only posters stay news, requiring source review.
  if not event:
   candidates=[]
   for line in body.splitlines():
    if len(line)>1000 or not re.search(r'20\d{2}\s*년',line):continue
    candidate=event_from_title(line,published,True)
    if candidate:candidates.append(candidate)
   dates={x['date'] for x in candidates}
   if len(dates)==1:
    event=candidates[0];event['dateBasis']='explicit_body_date';event['detail']='공식 본문에 명시된 일정'
  if event:events.append({**n,**event,'id':n['id']+'-'+event['date']})
 return news,events

def naver_search(fetch,now):
 client=os.getenv('ISEGYE_NAVER_CLIENT_ID','').strip();secret=os.getenv('ISEGYE_NAVER_CLIENT_SECRET','').strip()
 if not client or not secret:raise FeedError('api_key_required')
 if not all(33<=ord(c)<=126 for c in client+secret):raise FeedError('invalid_api_key_format')
 headers=dict(zip(NAVER_SEARCH_HEADER_NAMES,(client,secret)))
 found={}
 for query in ['이세계아이돌 왁물원 공지','이세돌 뱅온정보']+[n+' 왁물원 방송' for n in MEMBERS.values()]:
  u=NAVER_SEARCH_URL+'?'+urlencode({'query':query,'display':20,'start':1,'sort':'date','format':'json'})
  data=json.loads(fetch(u,headers=headers))
  if not isinstance(data,dict) or not isinstance(data.get('items'),list) or len(data['items'])>100:raise FeedError('search_schema_changed')
  for x in data['items']:
   if not isinstance(x,dict):raise FeedError('search_schema_changed')
   url=source_url(x.get('link',''))
   if not url or urlsplit(url).hostname!='cafe.naver.com':continue
   # Search API has no trustworthy author/menu or item publication timestamps.
   title=text(x.get('title',''))
   if not members_in(title):continue
   n=public_item('naver-search',url,title,None,now,detail='검색으로 발견 · 작성자·일정 미검증')
   found[n['id']]=n
  time.sleep(.25)
 return list(found.values())

def collect(previous=None,fetch=request,now=None):
 now=now or stamp();seed=json.loads((ROOT/'schedule/seed.json').read_text());seed=validate(seed)
 data={'schemaVersion':1,'timezone':'Asia/Seoul','generatedAt':now,'sources':[], 'events':seed['events'][:],'news':seed['news'][:],'forecasts':seed['forecasts'][:]}
 for source in SOURCES:
  s={**source,'lastAttemptAt':now,'lastSuccessAt':None,'state':'pending'}
  if source['id']=='naver-search':
   s.update(state='restricted',lastAttemptAt=None,detail='작성자 미확인 검색글 수집·공개 중단')
  elif source['mode']=='reviewed_snapshot':
   s.update(state='snapshot',lastAttemptAt=None,lastSuccessAt=seed['generatedAt'],detail='초기 확인 자료 · 카페 자동 크롤링 미사용')
  else:
   try:
    if source['id']=='parable-web':
     news,events=parable(fetch,now);data['news']+=news;data['events']+=events
    else:data['news']+=naver_search(fetch,now)
    s.update(state='ok',lastSuccessAt=now,detail='자동 수집 완료')
   except Exception as err:
    reason=str(err) if isinstance(err,FeedError) else 'upstream_unavailable'
    s.update(state='needs_setup' if reason=='api_key_required' else 'error',detail='네이버 검색 API 설정 필요' if reason=='api_key_required' else '이번 수집 실패 · 이전 자료 유지',errorCode=reason)
  data['sources'].append(s)
 # Seed and search result for same URL must not overwrite inspected authorship
 # or claim the old calendar date was reverified via a short search snippet.
 reviewed={n['sourceUrl'] for n in seed['news']}
 data['news']=[n for n in data['news'] if n['sourceId']!='naver-search' or n['sourceUrl'] not in reviewed]
 return merge(previous,data)

if __name__=='__main__':
 import argparse
 parser=argparse.ArgumentParser();parser.add_argument('--output',default='schedule/snapshot.json');parser.add_argument('--previous');args=parser.parse_args()
 previous=json.loads(Path(args.previous).read_text()) if args.previous and Path(args.previous).exists() else None
 data=collect(previous);Path(args.output).parent.mkdir(parents=True,exist_ok=True);Path(args.output).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({'sourceStates':{s['id']:s['state'] for s in data['sources']},'events':len(data['events']),'news':len(data['news']),'forecasts':len(data['forecasts'])}))