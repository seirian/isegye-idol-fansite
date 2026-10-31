"""Exercise the home spacing, actual snapshot, disclosure and empty-feed transition."""
from datetime import datetime,timezone,timedelta
from pathlib import Path
import json,os
from playwright.sync_api import sync_playwright,expect
root=Path(__file__).resolve().parents[1]
snapshot=json.loads((root/'schedule/snapshot.json').read_text())
out=Path(os.environ['BRIEF_OUT']);out.mkdir(exist_ok=True,parents=True)
url=os.environ['HOME_URL'];checks=[]
def check(name,ok):
    checks.append({'name':name,'passed':bool(ok)})
    assert ok,name
try:
    with sync_playwright() as pw:
        b=pw.chromium.launch();c=b.new_context(locale='ko-KR',timezone_id='Asia/Seoul',viewport={'width':1440,'height':1000},reduced_motion='reduce')
        p=c.new_page();errors=[];p.on('pageerror',lambda e:errors.append(str(e)));p.route('**/api/schedule',lambda r:r.fulfill(json=snapshot))
        p.goto(url,wait_until='networkidle');brief=p.locator('.hm-brief');expect(brief).to_be_visible()
        check('LIVE precedes the bulletin',p.locator('#main > section').first.get_attribute('class')=='live-home' and p.locator('.live-mini').count()==6)
        check('no duplicate membership navigation or old introductory copy',brief.locator('nav,a[href="#/members"]').count()==0 and '방송부터 새 영상' not in brief.inner_text())
        check('bulletin has two labelled rows',brief.locator('.hm-brief-label').all_text_contents()==['최근 공지','다음 일정'])
        for width,theme in ((1440,'dark'),(390,'light'),(320,'dark')):
            p.set_viewport_size({'width':width,'height':1000});p.evaluate('(t)=>{document.documentElement.dataset.theme=t;scrollTo(0,0)}',theme)
            gap=p.evaluate("document.querySelector('.live-home').getBoundingClientRect().top-document.querySelector('.site-header').getBoundingClientRect().bottom")
            check('navigation gap '+str(width),gap>=(32 if width>640 else 20)-1)
            check('page fits '+str(width),p.evaluate('document.documentElement.scrollWidth<=innerWidth'))
            if width!=320:
                p.screenshot(path=str(out/f'home-{width}.png'));brief.screenshot(path=str(out/f'bulletin-{width}.png'))
        details=p.locator('.hm-channel-links');check('channel directory starts closed',not details.evaluate('e=>e.open'));details.locator('summary').click()
        check('six links available on demand',len([a for a in details.locator('nav a').all() if a.is_visible()])==6)
        link=brief.locator('a[href^="#/schedule?"]')
        if link.count():
            href=link.get_attribute('href');date=href.split('&date=')[1].split('&')[0];link.click();expect(p.locator('.sc-page')).to_have_attribute('data-selected-date',date)
        empty={**snapshot,'news':[],'events':[],'generatedAt':(datetime.now(timezone.utc)+timedelta(minutes=5)).isoformat()}
        p.unroute('**/api/schedule');p.route('**/api/schedule',lambda r:r.fulfill(json=empty));p.goto(url+'#/home');p.reload(wait_until='networkidle')
        expect(brief.locator('.hm-brief-empty')).to_have_count(2);check('new empty snapshot clears both stale links',brief.locator('a').count()==0)
        check('no browser exceptions',not errors);b.close()
finally:
    (out/'result.json').write_text(json.dumps({'passed':sum(x['passed'] for x in checks),'total':len(checks),'checks':checks},ensure_ascii=False,indent=2))
