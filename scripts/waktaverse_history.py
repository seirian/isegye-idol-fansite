"""Recheck the bounded, reviewed historical queue on every music daily run."""
from pathlib import Path
import json
from concurrent.futures import ThreadPoolExecutor
from music_public_metadata import public_watch_date
ROOT=Path(__file__).resolve().parents[1]
def records():
    import daily_music as m
    data=json.loads((ROOT/'catalog/waktaverse-history.json').read_text())
    if data.get('channelId')!=m.CHANNELS['c1'][0] or data.get('schemaVersion')!=1 or len(data['videos'])>200:raise ValueError('history scope')
    ids=set()
    for r in data['videos']:
        if set(r)!={'videoId','sourceTitle','publishedDate'} or not m.VID.fullmatch(r['videoId']) or r['videoId'] in ids:raise ValueError('history row')
        ids.add(r['videoId']);m.publication_clock(r['publishedDate'])
        if not m.classify('c1',r['sourceTitle'],m.baseline()[1]):raise ValueError('unclassified historical music')
    return data['videos']
def collect(now):
    import daily_music as m
    expected=m.selections()[0]['channels']['c1']['url'];evidence=m.baseline()[1];cid=m.CHANNELS['c1'][0]
    def check(r):
        try:
            m.verify_video(r['videoId'],expected,r['sourceTitle'])
            body=m.read('https://www.youtube.com/watch?v='+r['videoId']+'&hl=ko',6500000).decode()
            day=public_watch_date(body,cid,r['videoId'],r['sourceTitle'])
            if day!=r['publishedDate']:raise ValueError('historical publication date changed')
            parsed=m.classify('c1',r['sourceTitle'],evidence)
            row=dict(parsed,channelKey='c1',videoId=r['videoId'],publishedAt=day,datePrecision='day',checkedAt=now.isoformat())
            m.validate([row]);return row,None
        except Exception as e:return None,{'videoId':r['videoId'],'reason':type(e).__name__}
    reviewed=records()
    with ThreadPoolExecutor(max_workers=3) as ex:checked=list(ex.map(check,reviewed))
    rows=[r for r,e in checked if r];errors=[e for r,e in checked if e]
    return rows,{'checked':len(reviewed),'verified':len(rows),'errors':errors,'range':'reviewed historical uploads; no 30-day cutoff'}
