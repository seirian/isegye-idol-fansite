#!/usr/bin/env python3
"""Complete upload history through the official YouTube Data API, when configured.

Requires a server-side ISEGYE_YOUTUBE_API_KEY. Never access non-public video,
account data, internal YouTube endpoints, or credentials in frontend code.
"""
from __future__ import annotations
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request,build_opener
import json,os,re,sys
import refresh_catalog_videos as catalog
ROOT=Path(__file__).resolve().parents[1]
API='https://www.googleapis.com/youtube/v3/'
MAX_PAGES=450
MAX_BYTES=8_000_000
class APIError(RuntimeError):pass
def request(resource,params,key,fetch=None):
 if resource not in ('channels','playlistItems','videos'):raise APIError('endpoint_not_allowed')
 if not isinstance(key,str) or len(key)<16 or not re.fullmatch(r'[A-Za-z0-9_-]+',key):raise APIError('api_key_missing_or_invalid')
 url=API+resource+'?'+urlencode({**params,'key':key})
 if fetch is None:
  def fetch(url):
   with build_opener(catalog.NoRedirect).open(Request(url,headers={'Accept':'application/json','User-Agent':'ISEGYE-Verified-Video-Archive/1.0'}),timeout=25) as response:
    if response.status!=200:raise APIError('api_http_failure')
    return response.read(2_000_001)
 try:
  raw=fetch(url)
  if len(raw)>2_000_000:raise APIError('api_response_too_large')
  doc=json.loads(raw)
  if not isinstance(doc,dict) or 'error' in doc:raise APIError('api_response_error')
  return doc
 except APIError:raise
 except Exception:raise APIError('api_request_failed') from None  # Do not log key-bearing URLs.
def collect_channel(channel,uploads,key,now,fetch=None):
 seen=set();rows=[];pages=0;token=''
 while True:
  if pages>=MAX_PAGES:raise APIError('channel_exceeds_page_budget')
  params={'part':'snippet,contentDetails,status','playlistId':uploads,'maxResults':50}
  if token:params['pageToken']=token
  doc=request('playlistItems',params,key,fetch);pages+=1
  if not isinstance(doc.get('items'),list):raise APIError('playlist_schema_changed')
  for item in doc['items']:
   if item.get('status',{}).get('privacyStatus')!='public':continue
   sn=item.get('snippet') or {};cd=item.get('contentDetails') or {}
   owner=sn.get('videoOwnerChannelId')
   vid=cd.get('videoId') or (sn.get('resourceId') or {}).get('videoId')
   stamp=cd.get('videoPublishedAt');title=sn.get('title','')
   if owner!=channel['channelId'] or not catalog.VIDEO_ID.fullmatch(vid or '') or not isinstance(title,str) or title.strip() in ('Private video','Deleted video'):continue
   try:published=datetime.fromisoformat(stamp.replace('Z','+00:00'))
   except (AttributeError,ValueError):continue
   if published.tzinfo is None or published>now:continue
   if vid in seen:raise APIError('duplicate_upload_id')
   seen.add(vid)
   rows.append({'id':vid,'title':title.strip()[:300],'publishedAt':published.isoformat(),
    'url':'https://www.youtube.com/watch?v='+vid,'thumbnail':'https://i.ytimg.com/vi/'+vid+'/mqdefault.jpg'})
  nxt=doc.get('nextPageToken')
  if nxt is None:break
  if not isinstance(nxt,str) or not re.fullmatch(r'[A-Za-z0-9_.=-]{1,300}',nxt) or nxt==token:raise APIError('invalid_pagination')
  token=nxt
 return rows,pages
def backfill(data,key,now=None,fetch=None):
 now=now or datetime.now(timezone.utc)
 expected=catalog.channels();ids=','.join(c['channelId'] for c in expected)
 doc=request('channels',{'part':'contentDetails','id':ids,'maxResults':50},key,fetch)
 items=doc.get('items')
 if not isinstance(items,list) or len(items)!=len(expected):raise APIError('channels_missing')
 uploads={}
 for row in items:
  ident=row.get('id');playlist=(row.get('contentDetails') or {}).get('relatedPlaylists',{}).get('uploads')
  if ident in uploads or ident not in ids.split(',') or not re.fullmatch(r'UU[A-Za-z0-9_-]{22}',playlist or ''):raise APIError('channel_identity_or_playlist')
  uploads[ident]=playlist
 saved={c['key']:c for c in data['channels']};out=[];report=[]
 for c in expected:
  current=saved.get(c['key'],{})
  if current.get('channelId')!=c['channelId']:raise APIError('local_channel_identity')
  if current.get('coverageComplete'):
   out.append(current);report.append({'key':c['key'],'state':'preserved_complete','count':len(current['videos'])});continue
  rows,pages=collect_channel(c,uploads[c['channelId']],key,now,fetch)
  merged=catalog.merge_rows(current.get('videos',[]),rows,now.isoformat())
  out.append({**current,'checkedAt':now.isoformat(),'status':'ok','coverageComplete':True,'coverageMode':'official_api_full',
   'lastFullSyncAt':now.isoformat(),'fullPages':pages,'videos':merged})
  report.append({'key':c['key'],'state':'complete','count':len(merged),'pages':pages})
 result={'schemaVersion':2,'checkedAt':now.isoformat(),'channels':out}
 if len(json.dumps(result,ensure_ascii=False).encode())>MAX_BYTES:raise APIError('catalog_too_large_requires_sharding')
 return result,report
def main():
 key=os.environ.pop('ISEGYE_YOUTUBE_API_KEY','')
 if not key:
  print('Full-history backfill NOT run: official YouTube Data API key is not configured. Recent Atom snapshots remain partial.')
  return 0
 path=ROOT/'catalog/videos.json';current=json.loads(path.read_text())
 try:
  result,report=backfill(current,key)
  temp=path.with_suffix('.tmp');temp.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');os.replace(temp,path)
  print(json.dumps({'status':'full_history_verified','channels':len(report),'complete':sum(c['coverageComplete'] for c in result['channels']),
   'total':sum(len(c['videos']) for c in result['channels'])}))
  return 0
 except APIError as ex:
  print('Full-history backfill not published: '+str(ex),file=sys.stderr)
  return 1
if __name__=='__main__':sys.exit(main())
