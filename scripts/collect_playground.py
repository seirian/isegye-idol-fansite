#!/usr/bin/env python3
"""Bounded source checks without hosting credentials. No full quiz text is published."""
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlencode,unquote
import csv,hashlib,json,os,re,sys,urllib.request,urllib.error
import playground_bank as bank
import schedule_feed as source_api
ROOT=Path(__file__).resolve().parents[1];WORK=ROOT/'playground-state'
NAMES=bank.NAMES

def read(url,headers=None):
    # Public oEmbed reader. API credentials belong only to source_api.request.
    if headers:raise ValueError('Public source reader refuses credentials')
    from schedule_feed import NoRedirect
    req=urllib.request.Request(url,headers={'User-Agent':'IsegyeFanArchive/1.0',**(headers or {})})
    with urllib.request.build_opener(NoRedirect).open(req,timeout=18) as response:
        raw=response.read(1048577)
    if len(raw)>1048576:raise ValueError('Response size')
    return json.loads(raw)

def rows(diagnostics=None):
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
    stats=diagnostics if diagnostics is not None else {}
    stats.update(inputRows=len(choices),unsupportedChannel=0,unsupportedFact=0,duplicateInput=0,eligibleRows=0)
    seen=set();result=[]
    for r in choices:
        k=r['channelKey'];owner=CHANNELS.get(k,(None,None))[1]
        if owner is None or channels.get(k,{}).get('role')!='official':
            stats['unsupportedChannel']+=1;continue
        if r['members']!=[owner] or r['type'] not in ('cover','original','remake','official_track'):
            stats['unsupportedFact']+=1;continue
        key=bank.digest([bank.norm(r['title']),owner,r['type']])
        if key in seen:
            stats['duplicateInput']+=1;continue
        seen.add(key);result.append({**r,'factKey':key,'channelUrl':channels[k]['url'],'owner':owner})
    stats['eligibleRows']=len(result)
    return result

def verify(row,fetch=read):
    u='https://www.youtube.com/watch?v='+row['videoId']
    d=fetch('https://www.youtube.com/oembed?'+urlencode({'url':u,'format':'json'}))
    def canon(s):return unquote(s).rstrip('/').casefold()
    if d.get('type')!='video' or canon(d.get('author_url',''))!=canon(row['channelUrl']):raise ValueError('Original channel mismatch')
    if len(bank.norm(row['title']))<2 or bank.norm(row['title']) not in bank.norm(d.get('title','')):raise ValueError('Title mismatch')
    return {'member':row['owner']}

def search_json(url,headers=None):
    # Reuse the site's migrated API HUB transport: fixed host/path, no redirects,
    # NCP header allowlist and sanitized HTTP error codes. Never use legacy OpenAPI.
    return json.loads(source_api.request(url,headers=headers))

def discover_references(fetch=search_json,env=None):
    seeds=['21721901','21741748'];found={i:{'url':'https://cafe.naver.com/steamindiegame/'+i,'title':'기존 참고 글'} for i in seeds};errors=[]
    env=os.environ if env is None else env
    keys=[env.get(k,'').strip() for k in ('ISEGYE_NAVER_CLIENT_ID','ISEGYE_NAVER_CLIENT_SECRET')]
    if not all(keys):return found,['naver_search_not_configured']
    if not all(33<=ord(char)<=126 for char in ''.join(keys)):
        return found,['naver_search_invalid_key_format']
    for query in ('왁물원 이세돌 퀴즈 정답','이세계아이돌 문제 답안'):
        try:
            url=source_api.NAVER_SEARCH_URL+'?'+urlencode({'query':query,'display':10,'start':1,'sort':'date','format':'json'})
            data=fetch(url,dict(zip(source_api.NAVER_SEARCH_HEADER_NAMES,keys)))
            if not isinstance(data,dict) or not isinstance(data.get('items'),list) or len(data['items'])>10:raise ValueError('Search schema')
            for item in data['items']:
                if not isinstance(item,dict):raise ValueError('Search item schema')
                canonical=source_api.source_url(item.get('link',''))
                match=re.fullmatch(r'https://cafe\.naver\.com/steamindiegame/(\d{1,12})',canonical or '')
                if match:found.setdefault(match[1],{'url':canonical,'title':source_api.text(item.get('title',''),140)})
        except Exception as e:
            # Persist bounded diagnostic codes, never bodies, headers or key values.
            reason=str(e) if isinstance(e,source_api.FeedError) and re.fullmatch(r'http_\d{3}(?:_api_[a-zA-Z0-9]+)?',str(e)) else type(e).__name__
            errors.append('naver_search_'+reason)
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
    from playground_pipeline import DAILY_TARGET, reserve_proposals, growth_report, editorial_manifest
    now=now or datetime.now(timezone.utc);WORK.mkdir(exist_ok=True)
    previous=json.loads((WORK/'previous.json').read_text()) if (WORK/'previous.json').exists() else None
    if previous:bank.validate_stored_feed(previous)
    catalog=(previous['catalog'] if previous else bank.seed())
    today=now.astimezone(bank.KST).date().isoformat()
    used=previous.get('addedToday',0) if previous and previous.get('batchDate')==today else 0
    budget=max(0,min(DAILY_TARGET,bank.MAX_DAILY)-used)
    existing={q.get('provenance',{}).get('factKey') for q in catalog['questions']}
    diagnostics={};eligible=rows(diagnostics)
    pending=[r for r in eligible if r['factKey'] not in existing]
    diagnostics.update(alreadyUsed=len(eligible)-len(pending),unusedOfficial=len(pending))
    # Change the starting point daily so permanently failing candidates do not
    # starve all later candidates. At most 20 public source reads per run.
    if pending:
        offset=now.astimezone(bank.KST).date().toordinal()%len(pending)
        pending=pending[offset:]+pending[:offset]
    proposals=[];checks=[]
    for row in pending[:20] if budget else []:
        if len(proposals)>=budget:break
        try:
            verified=verify(row);item=bank.auto_question(row,verified,now)
            if item:proposals.append(item)
            checks.append({'videoId':row['videoId'],'state':'verified' if item else 'excluded'})
        except Exception as e:checks.append({'videoId':row['videoId'],'state':'deferred','errorType':type(e).__name__})
    selection_catalog={**catalog,'questions':catalog['questions']+[q for q,_,_ in proposals]}
    reserved,reserve_stats=reserve_proposals(selection_catalog,now,max(0,budget-len(proposals)))
    # Live verified facts and exact reviewed reserve items share one daily cap.
    proposals+=reserved
    oldrefs=json.loads((WORK/'references-before.json').read_text()) if (WORK/'references-before.json').exists() else {}
    if budget:
        found,search_errors=discover_references()
        references,reference_checks=check_reference_bodies(found,oldrefs,now)
    else:
        references,reference_checks,search_errors=oldrefs,[],[]
    value,added=bank.assemble(previous,proposals,now)
    _,after=reserve_proposals(value['catalog'],now,0)
    reserve_added=sum(ident.startswith('reserve-') for ident in added)
    diagnostics.update(verified=sum(c['state']=='verified' for c in checks),
        deferred=sum(c['state']=='deferred' for c in checks),dailyBudget=budget,
        reserveTotal=reserve_stats['reviewedTotal'],reserveUsedOrDuplicate=reserve_stats['duplicateOrUsed'])
    value['growth']=growth_report(previous,value,added,after['readyBefore'],now,diagnostics)
    value['editorialRevision']=editorial_manifest()['revision']
    # External outages do not discard already reviewed questions; outages remain
    # visible separately. A zero-change execution is never called growth success.
    essential_ok=not checks or any(c['state']=='verified' for c in checks) or bool(reserve_added)
    report={'schemaVersion':1,'generatedAt':now.isoformat(),'status':'checked' if essential_ok else 'sources_unavailable',
        'reviewedAdded':value.get('reviewedAdded',0),'automaticAdded':len(added)-reserve_added,
        'reserveAdded':reserve_added,'totalAdded':len(added),'addedIds':added,
        'questionCount':len(value['catalog']['questions']),'sourceChecks':checks,
        'candidateCounts':diagnostics,'growth':value['growth'],'referenceChecks':reference_checks,
        'referenceWarnings':search_errors,'communityAutoPublished':False,
        'previousSha256':previous['sha256'] if previous else None}
    (WORK/'candidate.json').write_bytes(bank.encoded(value));(WORK/'references.json').write_bytes(bank.encoded(references));(ROOT/'playground-discovery.json').write_bytes(bank.encoded(report))
    # References remain a review inbox, never unverified automatic answers.
    inbox={'schemaVersion':1,'generatedAt':now.isoformat(),'automaticPublication':False,
        'references':reference_checks,'readyByCategory':after['readyByCategory']}
    (ROOT/'playground-review-inbox.json').write_bytes(bank.encoded(inbox))
    print(json.dumps({k:v for k,v in report.items() if k not in ('sourceChecks','referenceChecks')},ensure_ascii=False))
    return 0 if essential_ok else 1
if __name__=='__main__':sys.exit(collect())
