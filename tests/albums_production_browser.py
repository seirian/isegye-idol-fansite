"""Validate the exact promoted full-catalog bundle, not the sampled preview."""
from pathlib import Path
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
from functools import partial
from playwright.sync_api import sync_playwright,expect
import threading,json,os
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'test-results/albums-production';OUT.mkdir(parents=True,exist_ok=True)
class Handler(SimpleHTTPRequestHandler):
 def log_message(self,*args):pass
server=ThreadingHTTPServer(('127.0.0.1',0),partial(Handler,directory=str(ROOT/'dist')))
threading.Thread(target=server.serve_forever,daemon=True).start();url=f'http://127.0.0.1:{server.server_port}/';checks=[]
def check(name,value):
 checks.append({'name':name,'passed':bool(value)})
 if not value:raise AssertionError(name)
try:
 with sync_playwright() as pw:
  browser=pw.chromium.launch(headless=True,executable_path=os.getenv("BROWSER_PATH") or None);ctx=browser.new_context(viewport={'width':1440,'height':1000});page=ctx.new_page();errors=[]
  page.on('pageerror',lambda e:errors.append(str(e)))
  ctx.route('**/*',lambda r:r.continue_() if r.request.url.startswith(url) else r.abort())
  for path in ('schedule','music','history','albums'):ctx.route('**/api/'+path,lambda r:r.fulfill(status=503,content_type='application/json',body='{}'))
  page.goto(url,wait_until='domcontentloaded');expect(page.locator('#main h1')).to_be_visible()
  check('home remains default',page.url.endswith('#/home'))
  page.goto(url+'#/music?tab=albums',wait_until='domcontentloaded');expect(page.locator('#main h1')).to_have_text('한 곡에서 시작되는 이야기')
  check('existing fifteen plus new album',page.locator('.ai-card').count()==16)
  new_album=page.evaluate("D.albums.find(a=>a.title==='Across Dimensions')")
  check('new album has five registered tracks',len(new_album['songIds'])==5)
  page.goto(url+'#/album/'+new_album['id'],wait_until='domcontentloaded')
  expect(page.locator('#main h1')).to_have_text('Across Dimensions')
  check('new album ordered track links',page.locator('.ai-track h3 a').count()==5)
  check('no preview banner',page.locator('.ai-review').count()==0)
  check('no removed filters or reset',page.locator('[data-filter=coverage]').count()==0 and '초기화' not in page.locator('#main').inner_text())
  snap=json.loads((ROOT/'dist/src/albums-insights.json').read_text());keys=['top100','hot100','realtime','hot100_30','daily','new_week','new_month']
  for sid in json.loads((ROOT/'albums/record-sources.json').read_text())['tracks']:
   page.goto(url+'#/song/'+sid,wait_until='domcontentloaded');expect(page.locator('.ai-peaks')).to_be_visible();item=snap['tracks'].get(sid,{})
   values=[]
   for key in keys:
    rank=item.get('melonPeaks',{}).get('dailyBestRank') if key=='daily' else None
    if type(rank) is not int:rank=item.get('melonPeakFallback',{}).get('records',{}).get(key,{}).get('rank')
    values.append(str(rank)+'위' if type(rank) is int else '—')
   check(sid+' seven peaks match snapshot',page.locator('.ai-peak strong').all_text_contents()==values)
  page.goto(url+'#/song/cat-save-world',wait_until='domcontentloaded')
  check('Melon-only graph',page.locator('select[data-filter=metric] option').evaluate_all('(xs)=>xs.map(x=>x.value)')==['melon_top100','melon_hot100'])
  check('six service logos',page.locator('.ai-platform-logo').count()==6)
  expect(page.locator('.ai-hero .ai-cover img')).to_be_visible()
  check('cover loaded',page.locator('.ai-hero .ai-cover img').evaluate('(e)=>e.complete&&e.naturalWidth>0'))
  check('new same-origin data readable',page.request.get(url+'src/albums-insights.json').status==200)
  check('no review endpoint in app','/review-albums/api' not in (ROOT/'dist/src/app.js').read_text())
  for width in (320,390,768,1440):
   page.set_viewport_size({'width':width,'height':1000})
   for name,route in [('list','music?tab=albums'),('detail','song/cat-save-world')]:
    page.goto(url+'#/'+route,wait_until='domcontentloaded');expect(page.locator('#main h1')).to_be_visible()
    check(name+' no overflow '+str(width),page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
    if width in (390,1440):page.screenshot(path=str(OUT/f'{name}-{width}.png'),full_page=True)
  page.goto(url+'#/song/cat-save-world?demo=1',wait_until='domcontentloaded')
  check('approved curve and gradient',page.locator('.ai-flow-line').count()>0 and page.locator('.ai-flow-area').count()>0)
  check('explicit example label retained',page.locator('.ai-demo').count()==1)
  page.goto(url+'#/music?tab=albums&view=list',wait_until='domcontentloaded');check('list view',page.locator('.ai-list-view').count()==1)
  meta=json.loads((ROOT/'dist/build-info.json').read_text())
  check('approved commit recorded',meta['albumPromotion']['acceptedCommit']=='f2c00e2bb1f4a762e8ff1578f540584652d8053b')
  check('existing feeds unchanged',meta['runtimeFeeds']==['/api/schedule','/api/music','/api/history'])
  check('complete video catalog not sampled',page.evaluate('D.videos.length')>10000 and not page.evaluate('D.scope.offlineSample||false'))
  from datetime import datetime,timezone
  from copy import deepcopy
  from PIL import Image
  import io,hashlib
  fresh=deepcopy(snap);fresh.update(generatedAt=datetime.now(timezone.utc).isoformat(),feed='daily-albums')
  buf=io.BytesIO();Image.new('RGB',(2,2)).save(buf,format='WEBP');image=buf.getvalue();sha=hashlib.sha256(image).hexdigest()
  fresh.setdefault('assets',{}).setdefault('covers',{})[sha]={'sha256':sha,'path':'albums/asset-cache/'+sha+'.webp'}
  fresh['tracks']['rebels']={'match':'unmatched','artwork':{'asset':sha,'provider':'melon'},'melon':{'state':'ok','title':'REBELS','album':'Across Dimensions','trackId':'test-fixture','albumId':'15120216','checkedAt':fresh['generatedAt']}}
  ctx.route('**/api/albums',lambda r:r.fulfill(status=200,content_type='application/json',body=json.dumps(fresh)))
  ctx.route('**/api/albums/assets/'+sha+'.webp',lambda r:r.fulfill(status=200,content_type='image/webp',body=image))
  page.goto(url+'#/song/rebels');page.reload(wait_until='domcontentloaded')
  expect(page.locator('.ai-hero .ai-cover img')).to_be_visible()
  check('newer feed accepted',page.evaluate('albumInsights.generatedAt')==fresh['generatedAt'])
  expect(page.locator('.ai-hero .ai-cover img')).to_have_attribute('src','/api/albums/assets/'+sha+'.webp')
  check('dynamic cover bytes loaded',page.locator('.ai-hero .ai-cover img').evaluate('(e)=>e.complete&&e.naturalWidth>0'))
  check('existing and new songs survive music feed refresh',page.evaluate("D.songs.filter(s=>s.videoId==='y-klhPVFblg').length") == 1)
  check('no JavaScript exceptions',not errors)
  browser.close()
finally:
 server.shutdown();(OUT/'report.json').write_text(json.dumps({'checks':checks},ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'passed':len(checks)}))
