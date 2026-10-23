#!/usr/bin/env python3
"""Refresh known YouTube channels from their public Atom feeds at build time.
No API keys, browser cookies, third-party proxy, or writes outside catalog/videos.json.
A failed feed keeps its previous snapshot and original success timestamp.
"""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
import json,os,re,time,urllib.request,urllib.parse,xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
NS={'a':'http://www.w3.org/2005/Atom','yt':'http://www.youtube.com/xml/schemas/2015'}

def parse_feed(raw: bytes, expected: str, now: datetime) -> tuple[str,list]:
 if len(raw)>1024*1024 or b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():raise ValueError('Invalid XML size/declaration')
 tree=ET.fromstring(raw)
 if tree.findtext('yt:channelId',namespaces=NS) not in (expected,expected[2:]):raise ValueError('Channel identity mismatch')
 alternate=tree.find("a:link[@rel='alternate']",NS)
 if alternate is not None and alternate.get('href')!='https://www.youtube.com/channel/'+expected:raise ValueError('Channel URL mismatch')
 videos={}
 for entry in tree.findall('a:entry',NS):
  vid=entry.findtext('yt:videoId',namespaces=NS);title=entry.findtext('a:title',namespaces=NS);stamp=entry.findtext('a:published',namespaces=NS)
  if not re.fullmatch(r'[A-Za-z0-9_-]{11}',vid or '') or not title or not stamp:continue
  date=datetime.fromisoformat(stamp.replace('Z','+00:00'))
  if date.tzinfo is None or date>now:continue
  if entry.findtext('yt:channelId',namespaces=NS)!=expected:raise ValueError('Video channel mismatch')
  videos[vid]={'id':vid,'title':title[:300],'publishedAt':date.isoformat(),'url':'https://www.youtube.com/watch?v='+vid,'thumbnail':'https://i.ytimg.com/vi/'+vid+'/mqdefault.jpg'}
 return tree.findtext('a:title',default='',namespaces=NS),sorted(videos.values(),key=lambda v:v['publishedAt'],reverse=True)[:3]

class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,req,fp,code,msg,headers,newurl):return None

def main():
 now=datetime.now(timezone.utc);stamp=now.isoformat()
 profiles=json.loads((ROOT/'catalog/members.json').read_text());path=ROOT/'catalog/videos.json'
 old=json.loads(path.read_text());cached={x['key']:x for x in old['channels']}
 channels=[c for m in profiles['members'] for c in m['channels']]
 if len(channels)!=21 or len({c['channelId'] for c in channels})!=21:raise ValueError('Unexpected channel set')
 def refresh(c):
  cid=c['channelId'];assert re.fullmatch(r'UC[A-Za-z0-9_-]{22}',cid)
  url='https://www.youtube.com/feeds/videos.xml?channel_id='+cid
  for attempt in range(2):
   try:
    request=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 (compatible; IsegyeFanArchive/1.0)','Accept':'application/atom+xml'})
    with urllib.request.build_opener(NoRedirect).open(request,timeout=20) as r:raw=r.read(1024*1024+1)
    title,videos=parse_feed(raw,cid,now)
    return {'key':c['key'],'channelId':cid,'title':title,'feedUrl':url,'checkedAt':stamp,'attemptedAt':stamp,'status':'ok','videos':videos}
   except Exception:
    if attempt==0:time.sleep(.5)
  previous=cached.get(c['key'],{})
  if previous.get('channelId')!=cid:previous={}
  return {'key':c['key'],'channelId':cid,'title':c['name'],'feedUrl':url,'checkedAt':previous.get('checkedAt'),'attemptedAt':stamp,'status':'stale' if previous.get('videos') else 'unavailable','videos':previous.get('videos',[])}
 with ThreadPoolExecutor(max_workers=3) as pool:result=list(pool.map(refresh,channels))
 payload={'checkedAt':stamp,'channels':result}
 temp=path.with_suffix('.tmp');temp.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n');os.replace(temp,path)
 report={'attemptedAt':stamp,'freshChannels':sum(c['status']=='ok' for c in result),'preservedChannels':sum(c['status']!='ok' for c in result),'videoCount':sum(len(c['videos']) for c in result)}
 (ROOT/'test-results/catalog').mkdir(parents=True,exist_ok=True)
 (ROOT/'test-results/catalog/feeds.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
if __name__=='__main__':main()
