from urllib.parse import urlsplit,parse_qs,quote
import re

def search(page):
    page.goto('https://cafe.naver.com/steamindiegame',wait_until='domcontentloaded',timeout=25000);page.wait_for_timeout(1500)
    def fields():
        return [(f,n) for f in list(page.frames) for n in f.locator('input:not([type]),input[type=text],input[type=search]').all() if n.is_visible()]
    inputs=fields(); print('visible search field hints:',[(i.get_attribute('id'),i.get_attribute('placeholder')) for _,i in inputs][:8],flush=True)
    chosen=next(((f,n) for f,n in inputs if re.search('검색|query|search', ' '.join(str(n.get_attribute(k) or '') for k in ('title','name','placeholder','id','class')),re.I)),None)
    if not chosen:
        for f in page.frames:
            btn=f.locator('a[aria-label*=검색],button[aria-label*=검색],a[title*=검색],button[title*=검색]'); btn=next((b for b in btn.all() if b.is_visible()),None)
            if btn:btn.click();page.wait_for_timeout(750);break
        inputs=fields();chosen=next(iter(inputs),None)
    if not chosen:raise ValueError('public_search_control_not_found')
    _,inp=chosen;inp.fill('이세돌 뱅온정보');inp.press('Enter');page.wait_for_timeout(3000)
    pages=page.context.pages;view=pages[-1];print('search UI paths:',[urlsplit(f.url).path for f in view.frames],flush=True)
    return view
