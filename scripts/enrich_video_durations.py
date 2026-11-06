#!/usr/bin/env python3
"""Add conservative, public YouTube duration metadata to the video catalog.

YouTube Data API does not expose a definitive Shorts flag or aspect ratio.
A short duration is a candidate only; #shorts in a title is explicit evidence.
Never fabricate a Shorts classification from duration alone.
"""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
import json, os, re, sys
from backfill_channel_videos import request, APIError
from refresh_catalog_videos import VIDEO_ID

ROOT=Path(__file__).resolve().parents[1]
CACHE=ROOT/'catalog/video-durations.json'
DURATION=re.compile(r'^P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?$')
LIMIT=700

def parse_duration(value):
    if not isinstance(value,str):return None
    match=DURATION.fullmatch(value)
    if not match or not any(v is not None for v in match.groups()):return None
    days,hours,minutes,seconds=(int(x or 0) for x in match.groups())
    total=days*86400+hours*3600+minutes*60+seconds
    return total if 0<=total<=86400*30 else None

def collect(catalog,previous,key,fetch=None):
    ids={row['id'] for channel in catalog['channels'] for row in channel['videos']}
    if not all(VIDEO_ID.fullmatch(id) for id in ids):raise APIError('invalid_catalog_video_id')
    existing={k:v for k,v in previous.get('seconds',{}).items() if k in ids and type(v) is int and 0<=v<=2592000}
    pending=sorted(ids-set(existing))
    if (len(pending)+49)//50>LIMIT:raise APIError('duration_batch_budget_exceeded')
    for start in range(0,len(pending),50):
        batch=pending[start:start+50]
        doc=request('videos',{'part':'contentDetails,status','id':','.join(batch),'maxResults':50},key,fetch)
        items=doc.get('items')
        if not isinstance(items,list):raise APIError('duration_response_invalid')
        for item in items:
            if not isinstance(item,dict) or item.get('id') not in batch:continue
            if item.get('status',{}).get('privacyStatus')!='public':continue
            seconds=parse_duration((item.get('contentDetails') or {}).get('duration'))
            if seconds is not None:existing[item['id']]=seconds
    return {'schemaVersion':1,'checkedAt':datetime.now(timezone.utc).isoformat(),'seconds':existing},len(pending)

def main():
    key=os.environ.pop('ISEGYE_YOUTUBE_API_KEY','')
    if not key:
        print('Short-video duration enrichment skipped: server-side YouTube API key missing')
        return 0
    catalog=json.loads((ROOT/'catalog/videos.json').read_text())
    old=json.loads(CACHE.read_text()) if CACHE.exists() else {}
    try:result,attempted=collect(catalog,old,key)
    except APIError as exc:
        print('Short-video duration enrichment failed: '+str(exc),file=sys.stderr)
        return 1
    tmp=CACHE.with_suffix('.tmp')
    tmp.write_text(json.dumps(result,ensure_ascii=False,separators=(',',':'))+'\n')
    tmp.replace(CACHE)
    short=sum(s<=180 for s in result['seconds'].values())
    print(json.dumps({'durationChecked':len(result['seconds']),'requested':attempted,'shortDurationCandidates':short,'totalCatalogVideos':sum(len(c['videos']) for c in catalog['channels'])}))
    return 0

if __name__=='__main__':sys.exit(main())
