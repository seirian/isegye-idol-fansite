"""One-time reading of visible lines for approved roundup IDs; retain no full text."""
from datetime import datetime,timezone,timedelta
from pathlib import Path
from urllib.parse import urlsplit
import json,re,sys,unicodedata
from playwright.sync_api import sync_playwright
M={'아이네':'ine','징버거':'jingburger','릴파':'lilpa','주르르':'jururu','고세구':'gosegu','비챤':'viichan'}
STATUS={'rest':r'휴뱅|휴방|휴르르|방송\s*(?:없|안\s*함)|방송\s*쉬', 'unknown':r'미정|모르|미확|불확실|정보\s*없|몰루|애매', 'expected':r'뱅온|방송\s*(?:예정|시작)|생방\s*예정|방송\s*(?:켤|킵|킬)|합방\s*예정'}
HOURS=re.compile(r'(오전|오후)\s*(1[0-2]|[1-9])\s*시(?:\s*([0-5]?\d)\s*분|\s*(반))?')

def classify(lines):
    groups={}; current=None
    for line in lines:
        line=' '.join(unicodedata.normalize('NFKC',line).split()).strip(); line=line.strip(' \t\u200b')
        if not line:continue
        matches=[(n,m) for n,m in M.items() if re.search(re.escape(n),line)]
        if len(matches)>1:current=None;continue
        if matches:
            name,member=matches[0]; head=re.sub(r'[^가-힣A-Za-z0-9]','',line.split(name,1)[0]);current=member if len(head)<=2 else None
            if current:groups.setdefault(current,[]).append(line)
        elif current and len(groups[current])<4 and len(line)<150:
            if re.search('안내사항|링크|댓글|어제|지난 방송|유튜브|다시보기|다른 멤버',line):current=None
            else:groups[current].append(line)
    rows={}
    for member,section in groups.items():
        # Only compact member-specific entries; ambiguous/mixed wording remains unknown.
        text=' '.join(section);signals={k for k,p in STATUS.items() if re.search(p,text)}; times={x.group(0) for x in HOURS.finditer(text)}
        st=next(iter(signals)) if len(signals)==1 else 'unknown';tm=None
        hrs=HOURS.search(text)
        if len(times)==1 and hrs and st=='expected' and not re.search('아마|전후|사이|부터|까지|예전|어제|[~∼]',text):
            ap,h,mi,half=hrs.groups();tm=f'{int(h)%12+(12 if ap=="오후" else 0):02}:{30 if half else int(mi or 0):02}'
        rows[member]={'status':st,'time':tm}
    return rows

def read(series):
    result={}; now=datetime.now(timezone(timedelta(hours=9))).isoformat()
    with sync_playwright() as p:
        b=p.chromium.launch();ctx=b.new_context(locale='ko-KR');ctx.route('**/*',lambda r:r.abort() if r.request.resource_type in ('image','media','font') else r.continue_());pg=ctx.new_page()
        for r in series:
            if not all(r.get(k) is True for k in ('public','sameBoard','sameAuthor')):continue
            aid=r['articleId']; url='https://cafe.naver.com/steamindiegame/'+str(aid)
            try:
                pg.goto(url,wait_until='domcontentloaded',timeout=20000); f=None
                for _ in range(24):
                    f=next((f for f in pg.frames if f.locator('.ArticleTitle .title_text,.article_header .title_text').count()),None)
                    if f:break
                    pg.wait_for_timeout(400)
                if not f or f.locator('.ArticleTitle .title_text,.article_header .title_text').first.inner_text().strip()!=r['title']:continue
                el=f.locator('.se-main-container,.ContentRenderer .content_viewer,.article_viewer');
                if not el.count():continue
                sections=classify(el.first.inner_text(timeout=3000).splitlines());result[str(aid)]=sections
            except Exception:continue
        b.close()
    return {'checkedAt':now,'cards':result}
if __name__=='__main__':
    data=read(json.loads(Path(sys.argv[1]).read_text())['verified']);Path('fan-cards.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n');print(json.dumps(data))
