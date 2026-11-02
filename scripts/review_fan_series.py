"""Operator-directed bounded review of a known daily roundup. Public visible UI only."""
import json,re,sys,time
from datetime import datetime,date,timedelta,timezone
from pathlib import Path
from urllib.parse import quote,quote_from_bytes,urljoin,urlsplit
from playwright.sync_api import sync_playwright
KST=timezone(timedelta(hours=9)); BASE='https://cafe.naver.com/steamindiegame/'; ORIGINAL=22137397
TITLE=re.compile(r'^\[\s*(\d{1,2})\s*/\s*(\d{1,2})\s*\([^)]{1,4}\)\s*\]\s*이세돌\s*뱅온정보\s*$')
MEMBERS={'아이네':'ine','징버거':'jingburger','릴파':'lilpa','주르르':'jururu','고세구':'gosegu','비챤':'viichan'}
def txt(frame,sel):
    nodes=frame.locator(sel)
    return ' '.join(nodes.first.inner_text(timeout=2000).split()) if nodes.count() else ''
def article(ctx,aid):
    page=ctx.new_page()
    try:
        page.goto(BASE+str(aid),wait_until='domcontentloaded',timeout=20000)
        f=None
        for _ in range(26):
            f=next((f for f in page.frames if f.locator('.ArticleTitle .title_text,.article_header .title_text').count()),None)
            if f:break
            page.wait_for_timeout(400)
        if not f:return None
        return {'title':txt(f,'.ArticleTitle .title_text,.article_header .title_text'), 'author':txt(f,'.WriterInfo .nickname,.writer_info .nickname,.WriterInfo .nick_name,.writer_info .nick_name'), 'board':txt(f,'.ArticleTitle .link_board,.article_header .link_board'), 'stamp':txt(f,'.article_info .date,.article_info .date_text')}
    finally:page.close()
def run(start):
    now=datetime.now(KST);lo=date.fromisoformat(start);out={'schemaVersion':1,'from':start,'checkedAt':now.isoformat(),'seriesReference':ORIGINAL,'verified':[],'state':'unverified','inspectedSearchPages':0}
    if not 0<=(now.date()-lo).days<15:raise ValueError('bounded date window')
    with sync_playwright() as p:
        b=p.chromium.launch();ctx=b.new_context(locale='ko-KR',timezone_id='Asia/Seoul'); ctx.route('**/*',lambda r:r.abort() if r.request.resource_type in ('image','media','font') else r.continue_());ref=article(ctx,ORIGINAL)
        out['referenceChecks']={k:bool(ref and ref[k]) for k in ('title','author','board','stamp')}
        if not ref or not all(ref.values()) or not TITLE.fullmatch(ref['title']):return out
        from fan_search_public_ui import search
        page=search(ctx.new_page())
        candidates={}
        for f in page.frames:
            # Only extract anchors whose visible title matches this exact series.
            anchors=f.locator('a').evaluate_all('(aa)=>aa.map(a=>[a.innerText,a.href,a.getAttribute("data-article-id"),a.closest("tr")?.innerText?.split("\\n")[0]]).filter(x=>x[0]&&x[0].includes("뱅온정보"))')
            for label,href,attr,rowid in anchors:
                label=' '.join(label.split());m=re.search(r'\[(\d{1,2})/(\d{1,2})\([^)]{1,4}\)\]\s*이세돌\s*뱅온정보',label)
                if not m:continue
                try:day=date(now.year,int(m[1]),int(m[2]))
                except ValueError:continue
                if not lo<=day<=now.date():continue
                ident=re.search(r'(?:/articles/|/steamindiegame/|articleid=)(\d+)',href,re.I); aid=ident[1] if ident else attr or rowid
                if aid and str(aid).strip().isdigit():candidates[int(aid)]=day
        out['inspectedSearchPages']=1;out['candidateCount']=len(candidates)
        out['pageShape']={'path':urlsplit(page.url).path,'frames':[urlsplit(f.url).path for f in page.frames][:3], 'visibleTextLength':sum(len(f.locator('body').inner_text()[:1500]) for f in page.frames if f.locator('body').count())}
        for aid,day in list(candidates.items())[:12]:
            d=article(ctx,aid)
            if not d or d['board']!=ref['board'] or d['author']!=ref['author'] or not TITLE.fullmatch(d['title']):continue
            dt=re.fullmatch(r'(\d{4})\.(\d{1,2})\.(\d{1,2})\.\s*(\d\d?):(\d\d)',d['stamp'])
            if not dt:continue
            stamp=datetime(*map(int,dt.groups()),tzinfo=KST)
            if stamp>now or stamp.date()!=day:continue
            out['verified'].append({'articleId':aid,'title':d['title'],'date':day.isoformat(),'publishedAt':stamp.isoformat(),'sameBoard':True,'sameAuthor':True,'public':True})
        if out['verified']:out['state']='verified_series_articles'
        b.close()
    return out
if __name__=='__main__':
    try:out=run(sys.argv[1])
    except Exception as exc:out={'state':'unverified','error':type(exc).__name__}
    Path('fan-review.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(json.dumps(out,ensure_ascii=False))
