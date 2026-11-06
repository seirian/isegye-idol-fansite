#!/usr/bin/env python3
"""Accumulate verified public channel upload metadata; Atom is recent-only.

A separate official YouTube Data API job can backfill full historical uploads.
Never claim recent Atom coverage is a complete history.
"""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
from pathlib import Path
import json,os,re,time,urllib.request,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]
NS={'a':'http://www.w3.org/2005/Atom','yt':'http://www.youtube.com/xml/schemas/2015'}
CHANNEL_ID=re.compile(r'UC[A-Za-z0-9_-]{22}')
VIDEO_ID=re.compile(r'[A-Za-z0-9_-]{11}')
GROUP={'key':'isegye-official','name':'ISEGYE IDOL 공식 채널','kind':'단체 공식','url':'https://www.youtube.com/channel/UCmblbE_WxTaFWcMEGFJ_97w','channelId':'UCmblbE_WxTaFWcMEGFJ_97w'}
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args):return None
def channels():
 profiles=json.loads((ROOT/'catalog/members.json').read_text())
 selected=[c for m in profiles['members'] for c in m['channels']]+[GROUP]
 if len(selected)!=22 or len({c['channelId'] for c in selected})!=22 or not all(CHANNEL_ID.fullmatch(c['channelId']) for c in selected):raise ValueError('Unexpected channel set')
 return selected
def parse_feed(raw,expected,now):
 if len(raw)>1024*1024 or b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():raise ValueError('Invalid XML size/declaration')
 tree=ET.fromstring(raw)
 if tree.findtext('yt:channelId',namespaces=NS) not in (expected,expected[2:]):raise ValueError('Channel identity mismatch')
 alternate=tree.find("a:link[@rel='alternate']",NS)
 if alternate is not None and alternate.get('href')!='https://www.youtube.com/channel/'+expected:raise ValueError('Channel URL mismatch')
 videos={}
 for entry in tree.findall('a:entry',NS):
  vid=entry.findtext('yt:videoId',namespaces=NS);title=entry.findtext('a:title',namespaces=NS);stamp=entry.findtext('a:published',namespaces=NS)
  if not VIDEO_ID.fullmatch(vid or '') or not title or not stamp:continue
  dt=datetime.fromisoformat(stamp.replace('Z','+00:00'))
  if dt.tzinfo is None or dt>now:continue
  if entry.findtext('yt:channelId',namespaces=NS)!=expected:raise ValueError('Video channel mismatch')
  videos[vid]={'id':vid,'title':title[:300],'publishedAt':dt.isoformat(),'url':'https://www.youtube.com/watch?v='+vid,'thumbnail':'https://i.ytimg.com/vi/'+vid+'/mqdefault.jpg'}
 return tree.findtext('a:title',default='',namespaces=NS),sorted(videos.values(),key=lambda v:v['publishedAt'],reverse=True)
def merge_rows(old,new,now):
 previous={r['id']:r for r in old if isinstance(r,dict) and VIDEO_ID.fullmatch(str(r.get('id','')))}
 for row in new:
  prior=previous.get(row['id'],{})
  previous[row['id']]={**prior,**row,'firstSeenAt':prior.get('firstSeenAt') or prior.get('checkedAt') or now}
 return sorted(previous.values(),key=lambda r:(r['publishedAt'],r['id']),reverse=True)
def collect(previous,now=None,fetch=None):
 now=now or datetime.now(timezone.utc);stamp=now.isoformat()
 if fetch is None:
  def fetch(url):
   req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 (compatible; IsegyeFanArchive/1.0)','Accept':'application/atom+xml'})
   with urllib.request.build_opener(NoRedirect).open(req,timeout=20) as response:return response.read(1024*1024+1)
 saved={x['key']:x for x in previous.get('channels',[])}
 def refresh(c):
  cid=c['channelId'];url='https://www.youtube.com/feeds/videos.xml?channel_id='+cid
  old=saved.get(c['key'],{})
  if old.get('channelId')!=cid:old={}
  for attempt in range(2):
   try:
    title,videos=parse_feed(fetch(url),cid,now)
    return {**old,'key':c['key'],'channelId':cid,'title':title,'feedUrl':url,'checkedAt':stamp,'attemptedAt':stamp,'status':'ok',
      'coverageComplete':bool(old.get('coverageComplete',False)),'coverageMode':old.get('coverageMode','recent_atom'),'videos':merge_rows(old.get('videos',[]),videos,stamp)}
   except Exception:
    if attempt==0:time.sleep(.2)
  return {**old,'key':c['key'],'channelId':cid,'title':old.get('title',c['name']),'feedUrl':url,'checkedAt':old.get('checkedAt'),
    'attemptedAt':stamp,'status':'stale' if old.get('videos') else 'unavailable','coverageComplete':bool(old.get('coverageComplete',False)),
    'coverageMode':old.get('coverageMode','recent_atom'),'videos':old.get('videos',[])}
 with ThreadPoolExecutor(max_workers=3) as pool:results=list(pool.map(refresh,channels()))
 return {'schemaVersion':2,'checkedAt':stamp,'channels':results}
def main():
 path=ROOT/'catalog/videos.json';old=json.loads(path.read_text());value=collect(old)
 temp=path.with_suffix('.tmp');temp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n');os.replace(temp,path)
 report={'checkedAt':value['checkedAt'],'channels':len(value['channels']),'complete':sum(bool(c.get('coverageComplete')) for c in value['channels']),
  'fresh':sum(c['status']=='ok' for c in value['channels']),'videos':sum(len(c['videos']) for c in value['channels'])}
 (ROOT/'test-results/catalog').mkdir(parents=True,exist_ok=True)
 (ROOT/'test-results/catalog/feeds.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps(report))
if __name__=='__main__':main()
