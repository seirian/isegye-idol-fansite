"""Local browser proof for every reviewed song, rank and collected date; no live accounts."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from playwright.sync_api import sync_playwright, expect
import json, os, threading
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'test-results/guyso-peaks';OUT.mkdir(parents=True,exist_ok=True)
class Handler(SimpleHTTPRequestHandler):
 def log_message(self,*args):pass
server=ThreadingHTTPServer(('127.0.0.1',0),partial(Handler,directory=str(ROOT/'dist')))
threading.Thread(target=server.serve_forever,daemon=True).start();url=f'http://127.0.0.1:{server.server_port}/'
data=json.loads((ROOT/'albums/peak-reference/guyso-20261118.json').read_text())
dates=json.loads((ROOT/'albums/peak-reference/guyso-dates-20261118.json').read_text())
keys=['top100','hot100','realtime','hot100_30','daily','new_week','new_month'];checks=[]
def check(name,value):
 checks.append({'name':name,'passed':bool(value)})
 if not value:raise AssertionError(name)
def expected_dates(sid):
 return [dates['tracks'][sid]['records'][k]['date']+' 기록' if k in dates['tracks'][sid]['records'] else '확인된 최고 기록 없음' if data['tracks'][sid]['reference']['records'][k]['rank'] is None else '기록일 미확인' for k in keys]
def kst_date(value):
 return datetime.fromisoformat(value.replace('Z','+00:00')).astimezone(timezone(timedelta(hours=9))).date().isoformat()
try:
 check('all 24 linked songs reviewed',len(data['tracks'])==24 and set(dates['tracks'])==set(data['tracks']))
 check('all 164 numeric peaks have verified dates',sum(len(t['records']) for t in dates['tracks'].values())==164 and not dates['unresolved'])
 with sync_playwright() as p:
  browser=p.chromium.launch(headless=True,executable_path=os.getenv('BROWSER_PATH') or None)
  ctx=browser.new_context(viewport={'width':1440,'height':1000});page=ctx.new_page();errors=[]
  page.on('pageerror',lambda e:errors.append(str(e)))
  ctx.route('**/*',lambda r:r.continue_() if r.request.url.startswith(url) else r.abort())
  for endpoint in ('schedule','music','history','albums'):ctx.route('**/api/'+endpoint,lambda r:r.fulfill(status=503,content_type='application/json',body='{}'))
  page.goto(url,wait_until='domcontentloaded');expect(page.locator('#main h1')).to_be_visible()
  page.evaluate("""({rows,dates})=>{for(const [sid,e] of Object.entries(rows)){const t=albumInsights.tracks[sid]||={};t.melon={...(t.melon||{}),...e.identity,state:'ok'};t.melonPeakFallback=e.reference;t.melonPeakDates=dates[sid];}}""",{'rows':data['tracks'],'dates':dates['tracks']})
  for sid,entry in data['tracks'].items():
   page.goto(url+'#/song/'+sid,wait_until='domcontentloaded');expect(page.locator('.ai-peaks')).to_be_visible()
   panel=page.locator('.ai-peaks');values=[str(entry['reference']['records'][k]['rank'])+'위' if entry['reference']['records'][k]['rank'] is not None else '—' for k in keys]
   check(sid+' exact seven source ranks',panel.locator('.ai-peak strong').all_text_contents()==values)
   check(sid+' exact seven verified date states',panel.locator('[data-peak-date]').all_text_contents()==expected_dates(sid))
   check(sid+' no card attribution',panel.locator('.ai-peak a, .ai-peak-source').count()==0)
   check(sid+' no legacy provider text','이세계차트' not in panel.inner_text())
   details=panel.locator('details');expect(details.locator('summary')).to_have_text('최고 성적 출처와 확인 시각')
   check(sid+' details closed by default',details.get_attribute('open') is None)
   details.locator('summary').click()
   evidence=dates['tracks'][sid]['records'];matched=[k for k in keys if k in evidence]
   check(sid+' seven original provenance links retained',details.locator('[data-peak-rank-source]').evaluate_all('(xs)=>xs.map(a=>a.href)')==[entry['reference']['source']]*7)
   check(sid+' exact date source links',details.locator('[data-peak-date-source]').evaluate_all('(xs)=>xs.map(a=>a.href)')==[evidence[k]['source'] for k in matched])
   check(sid+' only reviewed evidence links',details.locator('tbody a').count()==7+len(matched))
   for k in matched:
    row=details.locator('[data-peak-evidence="'+k+'"]');e=evidence[k]
    formatted=page.evaluate("s=>new Intl.DateTimeFormat('ko-KR',{timeZone:'Asia/Seoul',dateStyle:'medium',timeStyle:'short'}).format(Date.parse(s))+' KST'",e['checkedAt'])
    check(sid+' '+k+' actual date confirmation and range',row.locator('[data-peak-date-checked]').inner_text()=='기록일 확인 · '+formatted and kst_date(e['rangeStart'])+' ~ '+kst_date(e['rangeEnd']) in row.inner_text())
   check(sid+' confirmation timestamp retained',details.locator('tbody tr').count()==7 and '가이섬' in details.inner_text())
   check(sid+' bounded date explanation','최초 달성일을 보증하지 않습니다' in details.inner_text() and '기록일 미제공' not in details.inner_text())
   details.locator('summary').click()
  check('four absent HOT100 ranks remain unrecorded',sum(e['reference']['records'][k]['rank'] is None for e in data['tracks'].values() for k in keys)==4)
  for width in (320,390):
   page.set_viewport_size({'width':width,'height':1000})
   for sid in data['tracks']:
    page.goto(url+'#/song/'+sid,wait_until='domcontentloaded')
    check(sid+' '+str(width)+' mobile dates intact',page.locator('[data-peak-date]').all_text_contents()==expected_dates(sid))
    check(sid+' '+str(width)+' no horizontal overflow',page.evaluate('document.documentElement.scrollWidth<=innerWidth+1'))
    page.locator('.ai-peaks summary').click()
    check(sid+' '+str(width)+' expanded details no page overflow',page.evaluate('document.documentElement.scrollWidth<=innerWidth+1'))
    page.locator('.ai-peaks summary').click()
  page.goto(url+'#/song/love-cells',wait_until='domcontentloaded')
  for width in (320,390,1440):
   page.set_viewport_size({'width':width,'height':1000});page.wait_for_timeout(100)
   check(str(width)+' no horizontal overflow',page.evaluate('document.documentElement.scrollWidth<=innerWidth+1'))
   if width in (390,1440):page.locator('.ai-peaks').screenshot(path=str(OUT/f'peaks-{width}.png'))
  page.locator('.ai-peaks summary').click();page.locator('.ai-peaks').screenshot(path=str(OUT/'peaks-details.png'))
  target='kidding';page.goto(url+'#/song/'+target,wait_until='domcontentloaded')
  for name,patch,all_dates in (
   ('wrong rank',{'rank':dates['tracks'][target]['records']['top100']['rank']+1},False),
   ('wrong chart',{'source':dates['tracks'][target]['records']['hot100']['source']},False),
   ('wrong date',{'date':'1900-01-01'},False),
   ('timezone omitted',{'observedAt':'2023-08-19T00:00:00'},False),
   ('wrong identity',{'albumId':'1'},True),
  ):
   bad=deepcopy(dates['tracks'][target]);bad.update(patch) if all_dates else bad['records']['top100'].update(patch)
   page.evaluate("({sid,evidence})=>{albumInsights.tracks[sid].melonPeakDates=evidence;render();}",{'sid':target,'evidence':bad})
   expected=expected_dates(target);expected=['기록일 미확인']*7 if all_dates else ['기록일 미확인']+expected[1:]
   check(name+' tampered evidence ignored',page.locator('[data-peak-date]').all_text_contents()==expected)
   check(name+' ranks preserved',page.locator('.ai-peak strong').all_text_contents()==[str(data['tracks'][target]['reference']['records'][k]['rank'])+'위' for k in keys])
  page.evaluate("({sid,evidence})=>{albumInsights.tracks[sid].melonPeakDates=evidence;render();}",{'sid':target,'evidence':dates['tracks'][target]})
  for sid in ('but-you-want-more','isegye-cypher'):
   page.goto(url+'#/song/'+sid,wait_until='domcontentloaded');check(sid+' no invented ranking',page.locator('.ai-peak strong').all_text_contents()==['—']*7)
   check(sid+' no invented dates',page.locator('[data-peak-date]').all_text_contents()==['확인된 최고 기록 없음']*7)
  check('no page exceptions',not errors);browser.close()
finally:
 server.shutdown();(OUT/'report.json').write_text(json.dumps({'checks':checks,'passed':sum(c['passed'] for c in checks),'sourceEvidence':'actual 24-song reviewed ranks and separately collected Guyso date dataset injected locally, not a live account session'},ensure_ascii=False,indent=2))
print(json.dumps({'passed':len(checks)}))
