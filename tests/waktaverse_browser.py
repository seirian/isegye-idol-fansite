"""Actual catalog renderer with reviewed rows; no external writes or user sessions."""
from pathlib import Path
import json,os,sys
from datetime import datetime,timezone
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import daily_music as m,waktaverse_history as history
url=os.environ['WAKTA_TEST_URL'];out=Path(os.environ['WAKTA_OUT']);out.mkdir(parents=True,exist_ok=True)
now=datetime.now(timezone.utc).isoformat();rows=[dict(m.classify('c1',r['sourceTitle'],m.baseline()[1]),videoId=r['videoId'],channelKey='c1',publishedAt=r['publishedDate'],datePrecision='day',checkedAt=now) for r in history.records()];checks=[]
def check(label,ok):
 checks.append({'name':label,'passed':bool(ok)})
 if not ok:raise AssertionError(label)
with sync_playwright() as p:
 b=p.chromium.launch(executable_path=os.getenv('BROWSER_EXECUTABLE') or None)
 for width in (390,1440):
  c=b.new_context(viewport={'width':width,'height':1000},locale='ko-KR');page=c.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  page.route('**/api/music',lambda r:r.fulfill(json={'schemaVersion':1,'feed':'daily-music','generatedAt':now,'rows':rows}))
  for query in ('리와인드','REWIND','RE:WIND'):
   page.goto(url+'#/music?q='+query);card=page.locator('[data-song="rewind"]');card.wait_for(timeout=15000);check(f'{width} {query} finds original MV',card.count()==1)
  page.goto(url+'#/music?type=official_track&q=리와인드');card=page.locator('[data-song="rewind"]');card.wait_for();check('original MV in official filter',card.count()==1);card.locator('a').first.click();page.locator('.catalog-song-detail').wait_for();check('original MV preserved',page.locator('.catalog-song-detail a.button.primary').get_attribute('href')=='https://www.youtube.com/watch?v=fgSXAKsq-Vo')
  page.goto(url+'#/music?type=performance');page.locator('[data-song="daily-plO-C9aSwxs"]').wait_for(timeout=15000);check('six performance versions',page.locator('.catalog-song').count()==6)
  page.locator('[data-song="daily-plO-C9aSwxs"] a').first.click();page.locator('.catalog-song-detail').wait_for();check('jazz version source',page.locator('.catalog-song-detail a.button.primary').get_attribute('href')=='https://www.youtube.com/watch?v=plO-C9aSwxs' and '공연·편곡' in page.locator('.catalog-song-detail').inner_text());check('day precision explained','시간대는 추정하지 않습니다' in page.locator('.music-source-info').inner_text())
  page.goto(url+'#/music?context=collab&q=고속도로');card=page.locator('[data-song="daily-7XFJ4s0j9z0"]');card.wait_for();card.locator('a').first.click();page.locator('.catalog-song-detail').wait_for();check('joint artists preserved','숲튽훈 & 주르르' in page.locator('.music-source-info').inner_text());check('video date not album date','영상 공개일' in page.locator('.catalog-facts').inner_text())
  page.goto(url+'#/music?q=왁타버스');page.locator('[data-song^="daily-"]').first.wait_for();check('no overflow',page.evaluate('document.documentElement.scrollWidth<=innerWidth+1'));page.screenshot(path=str(out/f'music-{width}.png'),full_page=True);check('no JS errors',not errors);c.close()
 b.close()
(out/'result.json').write_text(json.dumps({'passed':sum(x['passed'] for x in checks),'total':len(checks),'checks':checks},ensure_ascii=False,indent=2))
