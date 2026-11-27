"""Inspect selected links, explicit attribution and real preview images without mocking media."""
from datetime import datetime,timezone
import json,os,re,subprocess,time
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
  catalog_match=re.search(r'^const CATALOG=(.+);$',c.request.get(URL+'src/app.js').text(),re.M)
  check('public bundle includes reviewed catalogue data',catalog_match is not None)
  catalog_songs=json.loads(catalog_match.group(1))['music']['songs']
  check('selected commit matches',info['commit']==os.environ.get('GITHUB_SHA',info['commit']))
  music_audit=info['musicVideoAudit'];availability=music_audit.get('availability')
  check('all 154 reviewed; 151 selections retained',music_audit['songs']==154 and music_audit.get('selected',music_audit['linked'])==151)
  if availability:
   check('unavailable sources remain partial and inactive',availability['available']==music_audit['linked'] and availability['available']+availability['unavailable']==151 and availability['blocked']==0 and availability['state']==('partial' if availability['unavailable'] else 'complete'))
  examples=[('rewind','fgSXAKsq-Vo','official_mv'),('be-my-light','3cEUPoPXz7E','official_mv'),('your-turn','8e1Npb3wKyY','official_audio'),('cat-save-world','zGOzGcEbd-s','official_mv'),('cover-TYB9ScXvq34','IajO_xnbyFE','fan_backup'),('cover-buJjUHSalVA','BD6RZwsTvcs','karaoke_tj')]
  for sid,vid,kind in examples:
   page.goto(URL+'#/song/'+sid,wait_until='networkidle');page.locator('.catalog-song-detail').wait_for()
   unavailable=page.locator('.music-source-info').get_attribute('data-video-availability')=='unavailable'
   if unavailable:
    check(sid+' unavailable playback disabled',page.locator('.catalog-song-detail button.button.primary[disabled]').count()==1 and page.locator('.catalog-song-detail-visual .music-video-art').count()==0)
    check(sid+' failed selection has no active playback link',page.locator('a[href="https://www.youtube.com/watch?v='+vid+'"]').count()==0)
    continue
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
  unavailable_examples=[{'id':s['id'],'videoId':s['videoSource']['reviewedVideoId']} for s in catalog_songs if s.get('videoSource',{}).get('availability')=='unavailable'][:3]
  for row in unavailable_examples:
   page.goto(URL+'#/song/'+row['id'],wait_until='networkidle')
   check(row['id']+' unavailable record remains readable',page.locator('.catalog-song-detail h1').count()==1 and page.locator('.music-source-info[data-video-availability=unavailable]').count()==1)
   check(row['id']+' known failed playback and thumbnail disabled',page.locator('.catalog-song-detail button[disabled]').count()==1 and page.locator('.catalog-song-detail-visual .music-video-art').count()==0 and page.locator('a[href="https://www.youtube.com/watch?v='+row['videoId']+'"]').count()==0)
  page.goto(URL+'#/music?type=original',wait_until='networkidle');page.screenshot(path=str(OUT/'originals-desktop.png'),full_page=True)
  expected_originals=sum(s['type']=='original' and bool(s.get('videoId')) for s in catalog_songs)
  check('available originals linked; unavailable records retained',page.locator('.music-video-art').count()==expected_originals and page.locator('.catalog-song').count()==20)
  expected_backups=sum(s['type']=='original' and bool(s.get('videoId')) and s.get('videoSource',{}).get('kind')=='fan_backup' for s in catalog_songs)
  check('available unofficial originals labelled',page.locator('.music-video-label').filter(has_text='팬 백업').count()==expected_backups)
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
