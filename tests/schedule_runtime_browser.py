"""Real built UI: recovered dates plus synthetic post-build source IDs. No writes."""
from datetime import datetime, timezone
from pathlib import Path
import copy, json, os, sys
from playwright.sync_api import sync_playwright, expect
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import schedule_feed as feed
import schedule_health
URL=os.getenv('CAFE_RUNTIME_URL','http://127.0.0.1:4199/').rstrip('/')+'/'
OUT=Path(os.getenv('CAFE_RUNTIME_OUT',ROOT/'test-results/cafe-runtime'));OUT.mkdir(parents=True,exist_ok=True)
checks=[];errors=[]
def check(name,ok):
    checks.append({'name':name,'passed':bool(ok)})
    assert ok,name
now=datetime.now(timezone.utc).isoformat()
seed=json.loads((ROOT/'schedule/snapshot.json').read_text())
packet=json.loads((ROOT/'schedule/cafe-batches/2026-11-04-recovery.json').read_text())
# Preserve the fixed observation window so this fixture remains valid in later CI runs.
# This synthetic ID is intentionally absent from the bundled real notice archive.
packet['notices']=[{**packet['notices'][0],'articleId':99911111,'author':'ine','members':['ine'],
                    'title':'[테스트 전용] 재배포 없는 새 공지','publishedAt':'2026-11-04T07:30:00+00:00'}]
packet['boards']['345']['count']=1
value=feed.collect(previous=seed,fetch=lambda u:(_ for _ in ()).throw(feed.FeedError('fixture')),now=now,cafe_review=packet)
value['collectionHealth']=schedule_health.assess(value)
current={'value':seed}
with sync_playwright() as pw:
    b=pw.chromium.launch(**({'executable_path':os.environ['CHROMIUM_PATH']} if os.getenv('CHROMIUM_PATH') else {}))
    try:
        c=b.new_context(viewport={'width':1440,'height':1000},locale='ko-KR',timezone_id='Asia/Seoul',reduced_motion='reduce')
        page=c.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
        page.route('**/api/schedule',lambda r:r.fulfill(json=current['value']))
        page.route('https://chapi.sooplive.co.kr/**',lambda r:r.fulfill(status=503,body='fixture offline'))
        page.goto(URL+'#/schedule?month=2026-11&date=2026-11-03',wait_until='networkidle')
        for aid,member in ((22160518,'jingburger'),(22160543,'viichan'),(22160973,'lilpa')):
            item=page.locator('.sc-day-list [data-schedule-source="https://cafe.naver.com/steamindiegame/'+str(aid)+'"]')
            expect(item).to_have_count(1)
            check('November 3 '+member+' recovered once',item.get_attribute('data-member-tone')==member)
        check('November 3 has six separate uncertain fan references',page.locator('.sc-forecast-row').count()==6)
        for width in (1440,390):
            page.set_viewport_size({'width':width,'height':1000})
            page.locator('.sc-agenda').screenshot(path=str(OUT/f'november-3-{width}.png'))
        current['value']=value
        page.goto(URL+'#/schedule?month=2026-11&date=2026-11-04',wait_until='networkidle');page.reload(wait_until='networkidle')
        item=page.locator('.sc-day-list [data-schedule-source="https://cafe.naver.com/steamindiegame/99911111"]')
        expect(item).to_have_count(1)
        check('new runtime ID absent from build is visible', '재배포 없는 새 공지' in item.inner_text())
        page.locator('#schedule-member').select_option('ine')
        expect(item).to_have_count(1);check('runtime notice follows member filter',item.get_attribute('data-member-tone')=='ine')
        page.locator('#schedule-source').select_option('official')
        expect(item).to_have_count(1);check('runtime official notice survives official filter',page.locator('.sc-forecast-row').count()==0)
        page.locator('.sc-sources summary').click()
        check('source failure is disclosed without clearing valid notices','수집 지연' in page.locator('.sc-refresh-status').inner_text())
        for theme in ('light','dark'):
            page.evaluate('(t)=>document.documentElement.dataset.theme=t',theme)
            for width in (320,390,768,1440):
                page.set_viewport_size({'width':width,'height':1000})
                check(f'{theme}/{width} no overflow',page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
        # HTTP 200 is not sufficient: reject invalid proof and retain the last good UI.
        bad=copy.deepcopy(value);bad['cafeEvidence']['notices'][0]['verifiedRole']='member'
        current['value']=bad
        page.locator('[data-schedule-refresh]').click()
        expect(page.locator('.sc-refresh-status')).to_contain_text('갱신 확인 실패')
        expect(item).to_have_count(1)
        check('invalid proof never evicts last good notice', '재배포 없는 새 공지' in item.inner_text())
        check('no JavaScript exceptions',not errors)
    finally:
        (OUT/'result.json').write_text(json.dumps({'passed':sum(c['passed'] for c in checks),'total':len(checks),'checks':checks,'errors':errors,'scope':'recovered real notices and separate synthetic post-build fixture'},ensure_ascii=False,indent=2)+'\n')
        b.close()
print('Cafe runtime browser checks passed:',len(checks))
