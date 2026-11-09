#!/usr/bin/env python3
"""Official API observations for feature/albums only; never infer historical data."""
from pathlib import Path
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from urllib.request import Request, urlopen
from urllib.parse import urlencode, urlparse
import json, os, re, time, unicodedata
ROOT = Path(__file__).resolve().parents[1]
CHART = 'https://rss.marketingtools.apple.com/api/v2/kr/music/most-played/100/songs.json'
ARTISTS = {'group': {'isegyeidol', '이세계아이돌'}, 'gosegu': {'gosegu', '고세구'}}
# Exact provider titles, reviewed against artist/album/track and distributor pages.
ALIASES = {'winter-spring': ['Winter Spring'], 'white': ['White'], 'cat-save-world': ['NO CAT, NO LIFE!']}
HOSTS = {'itunes.apple.com', 'rss.marketingtools.apple.com', 'www.googleapis.com'}

def norm(value):
    return re.sub(r'[^\w]', '', unicodedata.normalize('NFKC', str(value)).casefold()).replace('_', '')

def album_norm(value):
    return norm(re.sub(r'\s*-\s*(Single|EP)$', '', str(value), flags=re.I))

def fetch_json(url):
    u = urlparse(url)
    if u.scheme != 'https' or u.hostname not in HOSTS or u.username or u.password: raise ValueError('Unapproved API URL')
    with urlopen(Request(url, headers={'User-Agent': 'ISEGYE-Archive-Review/1.0', 'Accept': 'application/json'}), timeout=25) as response:
        final = urlparse(response.url)
        if final.scheme != 'https' or final.hostname != u.hostname: raise ValueError('Unexpected redirect')
        data = response.read(4 * 1024 * 1024 + 1)
        if len(data) > 4 * 1024 * 1024: raise ValueError('Oversized response')
        return json.loads(data)

def match_track(song, rows):
    artist = 'group' if len(song.get('members', [])) == 6 else 'gosegu' if song.get('members') == ['gosegu'] else None
    if not artist or song.get('dateKind') == '영상 공개일': return None, 'not_applicable'
    titles = {norm(v) for v in [song['title'], *song.get('aliases', []), *ALIASES.get(song.get('id'), [])]}
    candidates = {str(r['trackId']): r for r in rows if r.get('kind') == 'song' and r.get('trackId') and norm(r.get('artistName', '')) in ARTISTS[artist] and norm(r.get('trackName', '')) in titles}
    exact = {k: r for k, r in candidates.items() if album_norm(r.get('collectionName')) == album_norm(song.get('album'))}
    candidates = exact or candidates
    if len(candidates) != 1: return None, 'ambiguous' if candidates else 'unmatched'
    return next(iter(candidates.values())), 'matched'

def validate_chart(feed):
    info = feed.get('feed', {}); rows = info.get('results', [])
    updated = info.get('updated', '')
    try: when = datetime.fromisoformat(updated.replace('Z', '+00:00'))
    except ValueError: when = parsedate_to_datetime(updated)
    now = datetime.now(timezone.utc)
    if when.tzinfo is None or when > now + timedelta(minutes=10) or when < now - timedelta(days=3): raise ValueError('Chart timestamp invalid')
    if info.get('country', '').lower() != 'kr' or len(rows) != 100 or len({r.get('id') for r in rows}) != 100: raise ValueError('Incomplete chart')
    if any(not str(r.get('id', '')).isdigit() or not r.get('name') or r.get('kind') != 'songs' for r in rows): raise ValueError('Unexpected chart schema')
    return {str(r['id']): i + 1 for i, r in enumerate(rows)}, when.isoformat()

def merge_history(previous, point, now, identity):
    cutoff = now - timedelta(days=30); rows = {}
    for p in previous + ([point] if point else []):
        try:
            t = datetime.fromisoformat(p['at'].replace('Z', '+00:00')); rank = p.get('rank')
            if t.tzinfo is None or not cutoff <= t <= now + timedelta(minutes=10): continue
            if p.get('trackId') != identity or p.get('status') not in {'ranked', 'out', 'error'}: continue
            if p['status'] == 'ranked' and (type(rank) is not int or not 1 <= rank <= 100): continue
            if p['status'] != 'ranked' and rank is not None: continue
            rows[p['at']] = {k: p.get(k) for k in ('at', 'rank', 'status', 'trackId')}
        except (KeyError, ValueError, TypeError): continue
    return sorted(rows.values(), key=lambda p: p['at'])[-1440:]

def official_bindings(source):
    approved = {}
    for line in (ROOT/'catalog/video-sources.tsv').read_text().splitlines():
        if line.startswith('#') or not line.strip(): continue
        sid, vid, kind, channel = line.split('\t')
        if kind.startswith('official_') and re.fullmatch(r'[\w-]{11}', vid): approved[sid] = vid
    from album_releases import video_bindings
    approved.update({sid: row['videoId'] for sid, row in video_bindings(ROOT).items()})
    return {s['id']: approved[s['id']] for s in source if s['id'] in approved}

def video_history(previous, point, now, ident):
    rows = {}
    for p in previous + [point]:
        try:
            t = datetime.fromisoformat(p['at'])
            if t.tzinfo is None or not now-timedelta(days=30) <= t <= now or p.get('videoId') != ident: continue
            if type(p.get('viewCount')) is not int or p['viewCount'] < 0: continue
            rows[t.replace(minute=0, second=0, microsecond=0).isoformat()] = {k:p[k] for k in ('at','videoId','viewCount','likeCount') if k in p}
        except (KeyError, ValueError, TypeError): continue
    return sorted(rows.values(),key=lambda p:p['at'])[-720:]

def collect(previous=None, include_apple_chart=True):
    now = datetime.now(timezone.utc); stamp = now.isoformat(); previous = previous or {}
    from album_releases import load_catalog
    source = load_catalog(ROOT)['songs']
    result = {'schemaVersion':1,'generatedAt':stamp,'scope':'feature/albums review only','providers':{},'tracks':{}}
    rows = []; failures = []
    for term in ('ISEGYE IDOL', 'GOSEGU'):
        try:
            response = fetch_json('https://itunes.apple.com/search?' + urlencode({'term':term,'country':'US','entity':'song','limit':200}))
            if not isinstance(response.get('results'),list): raise ValueError('Invalid catalog response')
            rows.extend(response['results'])
        except Exception as exc: failures.append(type(exc).__name__)
        time.sleep(3.1)
    result['providers']['itunes'] = {'state':'partial' if failures and rows else 'error' if failures else 'ok','storefront':'US','checkedAt':stamp,'source':'https://performance-partners.apple.com/search-api','errors':failures}
    ranks = {}; updated = stamp
    if include_apple_chart:
        try:
            feed = fetch_json(CHART)
            probe = ROOT/'test-results/albums-api-probe'; probe.mkdir(parents=True,exist_ok=True)
            (probe/'apple-chart.json').write_text(json.dumps(feed,ensure_ascii=False))
            ranks, updated = validate_chart(feed)
            result['providers']['apple_chart'] = {'state':'ok','checkedAt':stamp,'updatedAt':updated,'source':CHART,'storefront':'KR','limit':100}
        except Exception as exc:
            result['providers']['apple_chart'] = {'state':'error','checkedAt':stamp,'source':CHART,'error':type(exc).__name__}
    else:
        result['providers']['apple_chart']={'state':'excluded','reason':'Melon-only flow; free Apple metadata remains enabled.'}
    for s in source:
        row, state = match_track(s,rows); old = previous.get('tracks',{}).get(s['id'],{})
        item = {'match':state,'checkedAt':stamp,'appleHistory':[],'appleChartMatch':'unverified_storefront','youtube':{'state':'not_configured'}}
        if row:
            ident = str(row['trackId']); u = row.get('trackViewUrl',''); duration = row.get('trackTimeMillis')
            safe = u if urlparse(u).scheme=='https' and urlparse(u).hostname in {'music.apple.com','itunes.apple.com'} else None
            item['metadata'] = {'trackId':ident,'storefront':'US','title':row['trackName'],'artist':row['artistName'],'album':row.get('collectionName'),'durationMs':duration if type(duration) is int and 0<duration<3600000 else None,'genre':row.get('primaryGenreName'),'releaseDate':row.get('releaseDate'),'url':safe,'checkedAt':stamp,'matchBasis':'exact reviewed title/artist; exact album preferred; unique ID only'}
            # US metadata absent from a KR chart is NOT evidence of being chart-out.
            mapped = include_apple_chart and (ident in ranks or (old.get('metadata',{}).get('trackId')==ident and old.get('appleChartMatch')=='observed_kr_feed'))
            if mapped:
                item['appleChartMatch']='observed_kr_feed'
                status = ('ranked' if ident in ranks else 'out') if result['providers']['apple_chart']['state']=='ok' else 'error'
                point={'at':updated,'rank':ranks.get(ident),'status':status,'trackId':ident}
                item['appleHistory']=merge_history(old.get('appleHistory',[]),point,now,ident)
        result['tracks'][s['id']]=item
    key=os.environ.get('ISEGYE_YOUTUBE_API_KEY',''); official=official_bindings(source)
    if key and official:
        try:
            response=fetch_json('https://www.googleapis.com/youtube/v3/videos?'+urlencode({'part':'statistics','id':','.join(dict.fromkeys(official.values())),'key':key}))
            stats={r['id']:r.get('statistics',{}) for r in response['items']}
            for sid,vid in official.items():
                v=stats.get(vid); counts={k:int(v[k]) for k in ('viewCount','likeCount') if str((v or {}).get(k,'')).isdigit()}
                result['tracks'][sid]['youtube']={'state':'ok' if v is not None else 'unavailable','checkedAt':stamp,'videoId':vid,**counts}
                if 'viewCount' in counts:
                    old=previous.get('tracks',{}).get(sid,{}).get('youtubeHistory',[])
                    result['tracks'][sid]['youtubeHistory']=video_history(old,{'at':stamp,'videoId':vid,**counts},now,vid)
            result['providers']['youtube']={'state':'ok','checkedAt':stamp,'source':'https://developers.google.com/youtube/v3/docs/videos/list'}
        except Exception as exc:
            result['providers']['youtube']={'state':'error','checkedAt':stamp,'error':type(exc).__name__}
            for sid in official: result['tracks'][sid]['youtube']={'state':'error'}
    else: result['providers']['youtube']={'state':'not_configured'}
    for name in ('melon','genie','bugs'):
        result['providers'][name]={'state':'not_configured','reason':'Verified provider access and exact track IDs required; no inferred rank.'}
    return result

if __name__=='__main__':
    path=ROOT/'albums/snapshot.json'
    try: previous=json.loads(path.read_text()) if path.exists() else {}
    except (ValueError,OSError): previous={}
    data=collect(previous);path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'matched':sum(v['match']=='matched' for v in data['tracks'].values()),'total':len(data['tracks']),'providers':{k:v['state'] for k,v in data['providers'].items()}},ensure_ascii=False))
