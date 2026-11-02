"""Hourly official API discovery. Unknown-author rows are counted, never logged, saved or published."""
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlencode
import json,os,re
import schedule_feed as f,cafe_batch as cb,notice_policy as policy
QUERIES={'cafe-members':'왁물원 이세돌 멤버 공지','cafe-agency':'왁물원 패러블 이세계아이돌 공지','fan-roundup':'이세돌 뱅온정보'}

def discover(fetch=f.request,env=None):
    env=os.environ if env is None else env; keys=[env.get(v,'').strip() for v in ('ISEGYE_NAVER_CLIENT_ID','ISEGYE_NAVER_CLIENT_SECRET')]
    out={}; ref=policy.reviewed_sources(); fanids=set(cb.fans())|{22137397}; mx={sid:max((int(u.rsplit('/',1)[1]) for u,s in ref.items() if s==sid),default=0) for sid in ('cafe-members','cafe-agency')};mx['fan-roundup']=max(fanids)
    for sid,q in QUERIES.items():
        if not all(keys):out[sid]={'state':'needs_setup'};continue
        try:
            raw=json.loads(fetch(f.NAVER_SEARCH_URL+'?'+urlencode({'query':q,'display':30,'start':1,'sort':'date','format':'json'}),headers=dict(zip(f.NAVER_SEARCH_HEADER_NAMES,keys)))); items=raw.get('items')
            if not isinstance(items,list) or len(items)>30:raise ValueError('schema_changed')
            seen=set();count=0; reviewed=0
            for row in items:
                u=f.source_url(row.get('link',''))
                if not u or not u.startswith(cb.PREFIX) or u in policy.EXCLUDED_URLS or u in seen:continue
                seen.add(u);aid=int(u.rsplit('/',1)[1]);title=f.text(row.get('title',''))
                if (sid=='fan-roundup' and aid in fanids) or ref.get(u)==sid: reviewed+=1;continue
                if aid<=mx[sid] or u in ref or aid in fanids:continue
                # Hints, never proof of date, board, or author. Do not retain candidates.
                hit=(re.fullmatch(r'\[\s*\d{1,2}/\d{1,2}\([^)]{1,4}\)\s*\]\s*이세돌\s*뱅온정보',title) if sid=='fan-roundup' else re.match(r'^\[(아이네|징버거|릴파|주르르|고세구|비챤)\]',title) if sid=='cafe-members' else re.search(r'(이세계아이돌|이세돌|아이네|징버거|릴파|주르르|고세구|비챤)',title) and re.search(r'안내|공개|발매|공지|예약',title))
                if hit:count+=1
            out[sid]={'state':'needs_review' if count else 'searched','unverifiedHints':count,'knownMatches':reviewed}
        except Exception as e:
            reason=str(e) if isinstance(e,f.FeedError) and re.fullmatch(r'http_\d{3}(?:_api_[a-zA-Z0-9]+)?',str(e)) else 'api_unavailable_or_schema_changed'
            out[sid]={'state':'not_checked','reason':reason}
    return out
if __name__=='__main__':
    result=discover();print(json.dumps(result,ensure_ascii=False));file=os.getenv('GITHUB_STEP_SUMMARY');
    if file:
        with open(file,'a') as s:
            print('### 카페 새 글 신호 (공식 검색 API)\n검색은 작성자 검증·게시판 전수 대조가 아닙니다. 일반 검색글은 저장·공개하지 않습니다.\n',file=s)
            for sid,v in result.items():print('- '+sid+': '+v['state']+' · '+str(v.get('unverifiedHints','—'))+'개 미검증 신호',file=s)
    for sid,v in result.items():
        if v['state']!='searched':print('::warning::'+sid+' — '+v['state']+' (not a verified zero)')
