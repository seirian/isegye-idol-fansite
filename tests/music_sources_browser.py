"""Inspect selected links, explicit attribution and real preview images without mocking media."""
from datetime import datetime,timezone
import json,os,subprocess,time
from pathlib import Path
from urllib.request import urlopen
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
URL=os.getenv('MUSIC_URL','http://127.0.0.1:4197/').rstrip('/')+'/'
OUT=ROOT/os.getenv('MUSIC_OUT','test-results/music-sources');OUT.mkdir(parents=True,exist_ok=True)
checks=[];errors=[];server=None

def check(name,ok):
 checks.append({'name':name,'passed':bool(ok)})
 if not ok:raise AssertionError(name)
try:
 if 'MUSIC_URL' not in os.environ:
  server=subprocess.Popen(['python','-m','http.server','4197','--bind','127.0.0.1','--directory','live-dist'],cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  for _ in range(30):
   try:urlopen(URL,timeout=1).close();break
   except Exception:time.sleep(.1)
 with sync_playwright() as p:
  opts={'headless':True}
  if os.getenv('CHROMIUM_PATH'):opts['executable_path']=os.environ['CHROMIUM_PATH']
  b=p.chromium.launch(**opts);c=b.new_context(viewport={'width':1440,'height':1000},locale='ko-KR',timezone_id='Asia/Seoul',reduced_motion='reduce');page=c.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
  info=c.request.get(URL+'build-info.json').json()
  check('selected commit matches',info['commit']==os.environ.get('GITHUB_SHA',info['commit']))
  check('all 154 reviewed; 151 connected',info['musicVideoAudit']['songs']==154 and info['musicVideoAudit']['linked']==151)
  examples=[('rewind','fgSXAKsq-Vo','official_mv'),('be-my-light','3cEUPoPXz7E','official_mv'),('your-turn','8e1Npb3wKyY','official_audio'),('cat-save-world','zGOzGcEbd-s','official_mv'),('cover-TYB9ScXvq34','IajO_xnbyFE','fan_backup'),('cover-buJjUHSalVA','BD6RZwsTvcs','karaoke_tj')]
  for sid,vid,kind in examples:
   page.goto(URL+'#/song/'+sid,wait_until='networkidle');page.locator('.catalog-song-detail').wait_for()
   image=page.locator('.catalog-song-detail-visual .music-video-art>img');image.scroll_into_view_if_needed();image.wait_for()
   page.wait_for_function('(id)=>{const x=document.querySelector(".catalog-song-detail-visual .music-video-art>img");return x&&x.complete&&x.naturalWidth>=320&&!x.hidden;}',arg=vid)
   check(sid+' selected thumbnail',('/vi/'+vid+'/') in image.get_attribute('src'))
   check(sid+' matching selected CTA',page.locator('.catalog-song-detail a.button.primary').get_attribute('href')=='https://www.youtube.com/watch?v='+vid)
   check(sid+' source classification',page.locator('.music-source-info').get_attribute('data-video-kind')==kind)
   if kind=='fan_backup':check('backup explicit and original retained','비공식' in page.locator('.music-source-info').inner_text() and page.locator('a[href="https://www.youtube.com/watch?v=TYB9ScXvq34"]').count()==1)
   if kind=='karaoke_tj':check('karaoke is not member vocals','멤버 가창 영상이 아닌' in page.locator('.music-source-info').inner_text())
   if sid in ('rewind','cover-TYB9ScXvq34','cover-buJjUHSalVA'):page.screenshot(path=str(OUT/(kind+'-desktop.png')),full_page=True)
  for sid in ('cover-WItY2T5zz1A','cover-7E_cZ9eU3ZE','cover-q8iiUYJsOUM'):
   page.goto(URL+'#/song/'+sid,wait_until='networkidle');check(sid+' no wrong substitution',page.locator('.catalog-song-detail-visual .music-video-art').count()==0 and page.locator('.music-source-info[data-video-kind=unavailable]').count()==1)
  page.goto(URL+'#/music?type=original',wait_until='networkidle');page.screenshot(path=str(OUT/'originals-desktop.png'),full_page=True)
  check('every original linked',page.locator('.music-video-art').count()==20)
  check('unofficial original labelled',page.locator('.music-video-label').filter(has_text='팬 백업').count()==1)
  for theme in ('light','dark'):
   page.evaluate('(t)=>document.documentElement.dataset.theme=t',theme)
   for width in (320,390,768,1440):
    page.set_viewport_size({'width':width,'height':900})
    for route in ('music?type=original','song/cover-TYB9ScXvq34','song/cover-buJjUHSalVA','song/cover-q8iiUYJsOUM'):
     page.goto(URL+'#/'+route,wait_until='networkidle');check(f'{theme}/{width}/{route} no overflow',page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
  page.evaluate("document.documentElement.dataset.theme='light'");page.set_viewport_size({'width':390,'height':844});page.goto(URL+'#/music?type=original',wait_until='networkidle');page.screenshot(path=str(OUT/'originals-mobile.png'),full_page=True)
  check('no uncaught exceptions',not errors);b.close()
finally:
 (OUT/'result.json').write_text(json.dumps({'checkedAt':datetime.now(timezone.utc).isoformat(),'url':URL,'intercepted':False,'commit':os.getenv('GITHUB_SHA'),'passed':sum(x['passed'] for x in checks),'total':len(checks),'checks':checks,'browserErrors':errors},ensure_ascii=False,indent=2))
 if server:server.terminate();server.wait(timeout=5)
print('Music source browser checks:',len(checks))
