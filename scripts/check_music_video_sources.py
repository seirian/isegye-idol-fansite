#!/usr/bin/env python3
"""Read-only metadata/thumbnail audit of the fixed, reviewed video list.
No YouTube search, credentials, playback, arbitrary URLs or media rehosting.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
import io,json,os,time
from pathlib import Path
import urllib.request,urllib.parse,urllib.error
from music_video_sources import selections
ROOT=Path(__file__).resolve().parents[1]
def get(url,limit):
 request=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0','Accept-Language':'ko-KR,ko;q=0.9'})
 with urllib.request.urlopen(request,timeout=15) as r:
  data=r.read(limit+1)
  if len(data)>limit:raise ValueError('Response limit exceeded')
  return data

def main():
 config,rows=selections();jobs=[(sid,r) for sid,r in rows.items() if r['videoId']]
 def inspect(job):
  sid,row=job;vid=row['videoId'];result={'songId':sid,'videoId':vid,'kind':row['kind'],'ok':False}
  try:
   url='https://www.youtube.com/watch?v='+vid
   d=json.loads(get('https://www.youtube.com/oembed?'+urllib.parse.urlencode({'url':url,'format':'json'}),128000))
   expected=config['channels'][row['channelKey']]
   result.update(title=d.get('title'),author=d.get('author_name'),authorUrl=d.get('author_url'),metadataStatus=200)
   if d.get('author_url','').rstrip('/').lower()!=expected['url'].rstrip('/').lower():raise ValueError('Uploader identity changed')
   from PIL import Image
   raw=get('https://i.ytimg.com/vi/'+vid+'/hqdefault.jpg',1500000)
   with Image.open(io.BytesIO(raw)) as im:
    result.update(thumbnailWidth=im.width,thumbnailHeight=im.height)
    if im.width<320 or im.height<180:raise ValueError('Generic/unavailable thumbnail')
   result['ok']=True
  except urllib.error.HTTPError as ex:result.update(error='HTTP '+str(ex.code))
  except Exception as ex:result.update(error=type(ex).__name__+': '+str(ex))
  return result
 with ThreadPoolExecutor(max_workers=3) as pool:results=list(pool.map(inspect,jobs))
 out=ROOT/'test-results/music-sources';out.mkdir(parents=True,exist_ok=True)
 report={'checkedAt':datetime.now(timezone.utc).isoformat(),'commit':os.getenv('GITHUB_SHA','local'),'scope':'public metadata, uploader identity and thumbnail dimensions; not full video playback','catalogue':len(rows),'selected':len(jobs),'passed':sum(r['ok'] for r in results),'unresolved':[sid for sid,r in rows.items() if not r['videoId']],'results':results}
 (out/'source-audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({k:v for k,v in report.items() if k!='results'},ensure_ascii=False))
 failed=[r for r in results if not r['ok']]
 if failed:print(json.dumps(failed,ensure_ascii=False,indent=2));raise SystemExit(1)
if __name__=='__main__':main()
