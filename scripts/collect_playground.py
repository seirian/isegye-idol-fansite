#!/usr/bin/env python3
"""Bounded source checks without hosting credentials. No full quiz text is published."""
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlencode,unquote
import csv,hashlib,json,os,re,sys,urllib.request,urllib.error
import playground_bank as bank
ROOT=Path(__file__).resolve().parents[1];WORK=ROOT/'playground-state'
NAMES=bank.NAMES

def read(url,headers=None):
    # Fixed API endpoints only; redirects are not followed with API credentials.
    from schedule_feed import NoRedirect
    req=urllib.request.Request(url,headers={'User-Agent':'IsegyeFanArchive/1.0',**(headers or {})})
    with urllib.request.build_opener(NoRedirect).open(req,timeout=18) as response:
        raw=response.read(1048577)
    if len(raw)>1048576:raise ValueError('Response size')
    return json.loads(raw)

def rows():
    from enhance_catalog import load_music
    from daily_music import validate,CHANNELS
    channels=json.loads((ROOT/'catalog/video-sources.json').read_text())['channels']
    choices=[]
    feed=WORK/'music.json'
    if feed.exists():
        data=json.loads(feed.read_text())
        if data.get('schemaVersion')!=1 or data.get('feed')!='daily-music':raise ValueError('Music snapshot identity')
        choices+=validate(data['rows'])
    for r in load_music()['songs']:
        k=r.get('videoChannel') or r.get('channelKey')
        # The explicit selected source table, never a fan mirror, supplies identity.
        binding=next((v for v in csv.reader((ROOT/'catalog/video-sources.tsv').read_text().splitlines(),delimiter='\t') if len(v)==4 and v[0]==r['id'] and v[2].startswith('official_')),None)
        if binding:k=binding[3]
        if k not in CHANNELS:continue
        choices.append({'videoId':binding[1] if binding else r.get('videoId'),'channelKey':k,'title':r['title'],'type':r['type'],'members':r['members']})
    seen=set();result=[]
    for r in choices:
        k=r['channelKey'];owner=CHANNELS.get(k,(None,None))[1]
        if owner is None or r['members']!=[owner] or r['type'] not in ('cover','original','remake','official_track') or channels.get(k,{}).get('role')!='official':continue
        key=bank.digest([bank.norm(r['title']),owner,r['type']])
        if key in seen:continue
        seen.add(key);result.append({**r,'factKey':key,'channelUrl':channels[k]['url'],'owner':owner})
    return result

def verify(row,fetch=read):
    u='https://www.youtube.com/watch?v='+row['videoId']
    d=fetch('https://www.youtube.com/oembed?'+urlencode({'url':u,'format':'json'}))
    def canon(s):return unquote(s).rstrip('/').casefold()
    if d.get('type')!='video' or canon(d.get('author_url',''))!=canon(row['channelUrl']):raise ValueError('Original channel mismatch')
    if len(bank.norm(row['title']))<2 or bank.norm(row['title']) not in bank.norm(d.get('title','')):raise ValueError('Title mismatch')
    return {'member':row['owner']}

def discover_references(fetch=read):
    seeds=['21721901','21741748'];found={i:{'url':'https://cafe.naver.com/steamindiegame/'+i,'title':'기존 참고 글'} for i in seeds};errors=[]
    keys=[os.getenv(k,'') for k in ('ISEGYE_NAVER_CLIENT_ID','ISEGYE_NAVER_CLIENT_SECRET')]
    if not all(keys):return found,['naver_search_not_configured']
    for query in ('왁물원 이세돌 퀴즈 정답','이세계아이돌 문제 답안'):
        try:
            data=fetch('https://openapi.naver.com/v1/search/cafearticle.json?'+urlencode({'query':query,'display':10,'start':1,'sort':'date'}),dict(zip(('X-Naver-Client-Id','X-Naver-Client-Secret'),keys)))
            if not isinstance(data.get('items'),list):raise ValueError('Search schema')
            for item in data['items']:
                match=re.fullmatch(r'https://(?:m\.)?cafe\.naver\.com/steamindiegame/(\d+)',item.get('link',''))
                if match:found.setdefault(match[1],{'url':'https://cafe.naver.com/steamindiegame/'+match[1],'title':re.sub('<[^>]*>','',item.get('title',''))[:140]})
        except Exception as e:errors.append('naver_search_'+type(e).__name__)
    return found,errors

def check_reference_bodies(found,previous,now):
    """Read normal public rendered pages, not search snippets; no account/cookie import."""
    results=dict(previous or {});states=[]
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            opt={'headless':True}
            if os.getenv('CHROMIUM_PATH'):opt['executable_path']=os.environ['CHROMIUM_PATH']
            b=p.chromium.launch(**opt);context=b.new_context(locale='ko-KR');page=context.new_page()
            # Prioritize newly discovered posts, then re-check the two owner references.
            picks=sorted(found,key=lambda key:(key in results,key in ('21721901','21741748'),-int(key)))[:5]
            for ident in picks:
                item=found[ident];row={**item,'checkedAt':now.isoformat(),'state':'unread'}
                try:
                    page.goto('https://cafe.naver.com/ca-fe/cafes/27842958/articles/'+ident,wait_until='domcontentloaded',timeout=30000)
                    locator=page.locator('.se-main-container, .ContentRenderer, .article_viewer').first
                    locator.wait_for(timeout=12000);body=locator.inner_text(timeout=3000)
                    if len(body)<80 or re.search('가입한 멤버만|로그인 후 이용|접근 권한이 없',body):raise ValueError('Public body unavailable')
                    digest=hashlib.sha256(body.encode()).hexdigest();nums=set(re.findall(r'(?m)^\s*(\d{1,3})\s*[.、)번]',body))
                    row.update(state='body_checked',bodySha256=digest,questionMarkers=len(nums),answerSection=bool(re.search('정답|답안',body)),changed=bool(results.get(ident,{}).get('bodySha256') and results[ident]['bodySha256']!=digest),publication='candidate_only')
                except Exception as e:row.update(state='unread',errorType=type(e).__name__)
                # An outage never replaces the last successful body checksum.
                if row['state']=='body_checked':results[ident]=row
                states.append(row)
            context.close();b.close()
    except Exception as e:states.append({'state':'browser_unavailable','errorType':type(e).__name__})
    return dict(list(results.items())[-200:]),states

def collect(now=None):
    now=now or datetime.now(timezone.utc);WORK.mkdir(exist_ok=True)
    previous=json.loads((WORK/'previous.json').read_text()) if (WORK/'previous.json').exists() else None
    if previous:bank.validate_feed(previous)
    existing={q.get('provenance',{}).get('factKey') for q in (previous['catalog'] if previous else bank.seed())['questions']}
    proposals=[];checks=[]
    for row in [r for r in rows() if r['factKey'] not in existing][:20]:
        if len(proposals)>=bank.MAX_DAILY:break
        try:
            verified=verify(row);item=bank.auto_question(row,verified,now)
            if item:proposals.append(item)
            checks.append({'videoId':row['videoId'],'state':'verified' if item else 'excluded'})
        except Exception as e:checks.append({'videoId':row['videoId'],'state':'deferred','errorType':type(e).__name__})
    found,search_errors=discover_references()
    oldrefs=json.loads((WORK/'references-before.json').read_text()) if (WORK/'references-before.json').exists() else {}
    references,reference_checks=check_reference_bodies(found,oldrefs,now)
    value,added=bank.assemble(previous,proposals,now)
    # Meaningful failure is reported instead of marking complete when every new source failed.
    essential_ok=not checks or any(c['state']=='verified' for c in checks)
    report={'schemaVersion':1,'generatedAt':now.isoformat(),'status':'checked' if essential_ok else 'sources_unavailable','automaticAdded':len(added),'addedIds':added,'questionCount':len(value['catalog']['questions']),'sourceChecks':checks,'referenceChecks':reference_checks,'referenceWarnings':search_errors,'communityAutoPublished':False,'previousSha256':previous['sha256'] if previous else None}
    (WORK/'candidate.json').write_bytes(bank.encoded(value));(WORK/'references.json').write_bytes(bank.encoded(references));(ROOT/'playground-discovery.json').write_bytes(bank.encoded(report))
    print(json.dumps({k:v for k,v in report.items() if k not in ('sourceChecks','referenceChecks')},ensure_ascii=False))
    return 0 if essential_ok else 1
if __name__=='__main__':sys.exit(collect())
