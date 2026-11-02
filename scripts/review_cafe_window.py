"""One-time public review. Not an hourly Cafe crawler. No credentials or direct API calls."""
import argparse, collections, json, re, time
from datetime import date, datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urlsplit, parse_qs
import notice_policy as policy
KST=timezone(timedelta(hours=9))
NAMES={'아이네':'ine','아이네 INE':'ine','징버거':'jingburger','릴파 LILPA':'lilpa','릴파':'lilpa','주르르':'jururu','고세구':'gosegu','비챤':'viichan'}
GROUP=re.compile('이세계|이세돌|ISEGYE',re.I)
HEALTH=re.compile('병원|진단|우울증|공황|코로나|독감|장염|생리|수술|치료|건강검진')

def approved(x, menu, lo, until):
    if x.get('cafeId')!=27842958 or x.get('menuId')!=menu or x.get('openArticle') is not True or x.get('restrictMenu') is True: return
    w=x.get('writerInfo') or {}; name=str(w.get('nickName','')).strip(); member=NAMES.get(name)
    if menu==345 and not (member and w.get('staff') is True): return
    if menu==1250 and not (name=='parable' and (w.get('staff') is True or w.get('manager') is True)): return
    aid=x.get('articleId'); title=' '.join(str(x.get('subject') or '').split())[:220]
    if type(aid) is not int or not title or f'https://cafe.naver.com/steamindiegame/{aid}' in policy.EXCLUDED_URLS: return
    published=datetime.fromtimestamp(x['writeDateTimestamp']/1000,timezone.utc)
    if not lo<=published<=until: return
    group=GROUP.search(title); members=list(dict.fromkeys(v for k,v in NAMES.items() if k.split()[0] in title))
    if menu==1250 and not (group or members): return
    generalized=bool(HEALTH.search(title))
    if generalized: title='휴방 관련 공지' if re.search('휴뱅|휴방|휴르르',title) else '멤버 공지 (세부 내용은 원문 확인)'
    return dict(articleId=aid,menuId=menu,author=member or 'parable',members=[member] if member else list(dict.fromkeys(NAMES.values())) if group else members,title=title,publishedAt=published.isoformat(timespec='milliseconds'),verifiedRole='manager' if menu==1250 and w.get('manager') is True else 'staff',public=True,titleGeneralized=generalized)

def board(page,menu,lo,until):
    output={}; seen=set(); pages=0
    for n in range(1,9):
        path=f'/cafes/27842958/menus/{menu}/articles'
        def listing(r):
            u=urlsplit(r.url); q=parse_qs(u.query)
            return u.scheme=='https' and (u.hostname or '').endswith('.naver.com') and u.path.endswith(path) and q.get('page',['1'])==[str(n)]
        url=f'https://cafe.naver.com/f-e/cafes/27842958/menus/{menu}?page={n}&viewType=L'
        with page.expect_response(listing,timeout=25000) as response:
            nav=page.goto(url,wait_until='domcontentloaded',timeout=25000)
            if not nav or nav.status!=200: raise ValueError('board_unavailable')
        r=response.value
        if r.status!=200: raise ValueError('board_unavailable')
        result=r.json().get('result') or {}; entries=result.get('articleList')
        if not isinstance(entries,list): raise ValueError('listing_schema')
        rows=[e.get('item') or {} for e in entries if isinstance(e,dict)]; rows=[x for x in rows if x.get('cafeId')==27842958 and x.get('menuId')==menu and x.get('articleId')]
        if not rows: raise ValueError('empty_or_ambiguous_board')
        sig=tuple(x['articleId'] for x in rows)
        if sig in seen: raise ValueError('repeated_page')
        seen.add(sig); pages+=1
        for x in rows:
            row=approved(x,menu,lo,until)
            if row: output[row['articleId']]=row
        # One old pinned notice does not prove that the boundary was crossed.
        regular=[x for x in rows if x.get('noticeArticle') is not True and x.get('notice') is not True]
        regular_times=[datetime.fromtimestamp(x['writeDateTimestamp']/1000,timezone.utc) for x in regular]
        if regular_times and all(t<lo for t in regular_times[-min(3,len(regular_times)):] ) and len(regular_times)>=3:
            return list(output.values()),pages
        time.sleep(1.5)
    raise ValueError('window_boundary_not_reached')

def run(start):
    from playwright.sync_api import sync_playwright
    until=datetime.now(timezone.utc); lo=datetime.fromisoformat(start).replace(tzinfo=KST)
    if not 0<=(until-lo).days<=14: raise ValueError('bounded review expects a recent start')
    out={'schemaVersion':1,'from':start,'checkedAt':until.isoformat(),'boards':{},'notices':[],'fan':{}}
    with sync_playwright() as p:
        b=p.chromium.launch(); ctx=b.new_context(locale='ko-KR',timezone_id='Asia/Seoul'); page=ctx.new_page()
        page.route('**/*',lambda r:r.abort() if r.request.resource_type in ('image','media','font') else r.continue_())
        for menu in (345,1250):
            try:
                items,pages=board(page,menu,lo,until);out['notices']+=items;out['boards'][str(menu)]={'state':'reviewed','count':len(items),'pages':pages}
            except Exception as e: out['boards'][str(menu)]={'state':'unverified','reason':str(e) if type(e) is ValueError and str(e) in ('board_unavailable','listing_schema','empty_or_ambiguous_board','repeated_page','window_boundary_not_reached') else type(e).__name__}
        # Only the approved article. Its title/date are evidence about this post,
        # not about other fan posts or the six members' actual stream starts.
        try:
            page=ctx.new_page();page.goto(policy.FAN_URL,wait_until='domcontentloaded',timeout=25000)
            target=None
            for _ in range(24):
                for frame in page.frames:
                    title=frame.locator('.ArticleTitle .title_text, .article_header .title_text')
                    if title.count() and title.first.is_visible(): target=frame;break
                if target:break
                page.wait_for_timeout(400)
            if not target: raise ValueError('approved_article_not_visible')
            title=' '.join(target.locator('.ArticleTitle .title_text, .article_header .title_text').first.inner_text().split())[:220]
            dl=target.locator('.article_info .date, .article_info .date_text'); ds=dl.first.inner_text().strip() if dl.count() else ''
            out['fan']={'state':'article_observed','articleId':22137397,'title':title,'displayDate':ds if re.fullmatch(r'[0-9.: /-]{8,30}',ds) else None,'forecastCoverage':'not_verified'}
        except Exception:out['fan']={'state':'unverified','articleId':22137397,'forecastCoverage':'not_verified'}
        b.close()
    policy.validate_archive({'schemaVersion':1,'rangeStart':'2021-08-26','rangeEnd':until.astimezone(KST).date().isoformat(),'checkedAt':out['checkedAt'],'notices':out['notices']})
    return out
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('start',type=lambda s:date.fromisoformat(s).isoformat());args=p.parse_args();data=run(args.start);Path('cafe-review.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'boards':data['boards'],'fan':data['fan'],'from':data['from'],'checkedAt':data['checkedAt'],'byDay':dict(collections.Counter(datetime.fromisoformat(x['publishedAt']).astimezone(KST).date().isoformat() for x in data['notices']))},ensure_ascii=False))
