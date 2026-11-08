#!/usr/bin/env python3
"""Read public Apple APIs and optional YouTube Data API into a preview-only snapshot.
No HTML scraping, auth bypass, inferred historical ranks, lyrics or promotional artwork.
"""
from pathlib import Path
from datetime import datetime, timezone, timedelta
from urllib.request import Request, urlopen
from urllib.parse import urlencode, urlparse
import json, os, re, time, unicodedata
ROOT = Path(__file__).resolve().parents[1]
CHART = 'https://rss.marketingtools.apple.com/api/v2/kr/music/most-played/100/songs.json'
ARTISTS = {'group': {'isegyeidol', '이세계아이돌'}, 'gosegu': {'gosegu', '고세구'}}

def norm(value):
    return re.sub(r'[^\w]', '', unicodedata.normalize('NFKC', str(value)).casefold()).replace('_', '')

def album_norm(value):
    return norm(re.sub(r'\s*-\s*(Single|EP)$', '', str(value), flags=re.I))

def fetch_json(url):
    if urlparse(url).hostname not in {'itunes.apple.com', 'rss.marketingtools.apple.com', 'www.googleapis.com'}:
        raise ValueError('Unapproved API host')
    with urlopen(Request(url, headers={'User-Agent': 'ISEGYE-Archive-Review/1.0', 'Accept': 'application/json'}), timeout=25) as response:
        if urlparse(response.url).hostname not in {'itunes.apple.com', 'rss.marketingtools.apple.com', 'www.googleapis.com'}:
            raise ValueError('Unexpected redirect')
        data = response.read(4 * 1024 * 1024 + 1)
        if len(data) > 4 * 1024 * 1024: raise ValueError('Oversized response')
        return json.loads(data)

def match_track(song, rows):
    artist = 'group' if len(song.get('members', [])) == 6 else 'gosegu' if song.get('members') == ['gosegu'] else None
    if not artist or song.get('dateKind') == '영상 공개일': return None, 'not_applicable'
    titles = {norm(v) for v in [song['title'], *song.get('aliases', [])]}
    candidates = {str(r['trackId']): r for r in rows if r.get('kind') == 'song' and r.get('trackId') and norm(r.get('artistName', '')) in ARTISTS[artist] and norm(r.get('trackName', '')) in titles}
    exact_album = {k: r for k, r in candidates.items() if album_norm(r.get('collectionName')) == album_norm(song.get('album'))}
    candidates = exact_album or candidates
    if len(candidates) != 1: return None, 'ambiguous' if candidates else 'unmatched'
    return next(iter(candidates.values())), 'matched'

def validate_chart(feed):
    rows = feed.get('feed', {}).get('results', [])
    country = feed.get('feed', {}).get('country', '').lower()
    updated = feed.get('feed', {}).get('updated', '')
    when = datetime.fromisoformat(updated.replace('Z', '+00:00'))
    now = datetime.now(timezone.utc)
    if when.tzinfo is None or when > now + timedelta(minutes=10) or when < now - timedelta(days=3):
        raise ValueError('Chart timestamp stale or invalid')
    if country != 'kr' or len(rows) != 100 or len({r.get('id') for r in rows}) != 100:
        raise ValueError('Incomplete chart; cannot infer out-of-chart')
    if any(not str(r.get('id', '')).isdigit() or not r.get('name') or r.get('kind') != 'songs' for r in rows):
        raise ValueError('Unexpected chart schema')
    return {str(r['id']): i + 1 for i, r in enumerate(rows)}, when.isoformat()

def merge_history(previous, point, now, identity):
    cutoff = now - timedelta(days=30)
    rows = {}
    for p in previous + [point]:
        try:
            t = datetime.fromisoformat(p['at'].replace('Z', '+00:00'))
            rank = p.get('rank')
            if t.tzinfo is None or not cutoff <= t <= now + timedelta(minutes=10): continue
            if p.get('trackId') != identity or p.get('status') not in {'ranked', 'out', 'error'}: continue
            if p['status'] == 'ranked' and (type(rank) is not int or not 1 <= rank <= 100): continue
            if p['status'] != 'ranked' and rank is not None: continue
            rows[p['at']] = {k: p.get(k) for k in ('at', 'rank', 'status', 'trackId')}
        except (KeyError, ValueError, TypeError): continue
    return sorted(rows.values(), key=lambda p: p['at'])[-1440:]

def collect(previous=None):
    now = datetime.now(timezone.utc); stamp = now.isoformat()
    source = json.loads((ROOT / 'catalog/music.json').read_text())['songs']
    result = {'schemaVersion': 1, 'generatedAt': stamp, 'scope': 'feature/albums review only', 'providers': {}, 'tracks': {}}
    rows = []; failures = []
    for term in ('ISEGYE IDOL', 'GOSEGU'):
        try:
            response = fetch_json('https://itunes.apple.com/search?' + urlencode({'term': term, 'country': 'KR', 'entity': 'song', 'attribute': 'artistTerm', 'limit': 200}))
            if not isinstance(response.get('results'), list): raise ValueError('Invalid catalog response')
            rows.extend(response['results'])
        except Exception as exc: failures.append(type(exc).__name__)
        time.sleep(3.1)
    result['providers']['itunes'] = {'state': 'partial' if failures and rows else 'error' if failures else 'ok', 'checkedAt': stamp, 'source': 'https://performance-partners.apple.com/search-api', 'errors': failures}
    ranks = {}; updated = stamp
    try:
        ranks, updated = validate_chart(fetch_json(CHART))
        result['providers']['apple_chart'] = {'state': 'ok', 'checkedAt': stamp, 'updatedAt': updated, 'source': CHART, 'storefront': 'KR', 'chart': 'most-played', 'limit': 100}
    except Exception as exc:
        result['providers']['apple_chart'] = {'state': 'error', 'checkedAt': stamp, 'source': CHART, 'error': type(exc).__name__}
    for s in source:
        row, state = match_track(s, rows)
        item = {'match': state, 'checkedAt': stamp, 'appleHistory': [], 'youtube': {'state': 'not_configured'}}
        if row:
            ident = str(row['trackId'])
            u = row.get('trackViewUrl', '')
            safe_url = u if urlparse(u).scheme == 'https' and urlparse(u).hostname in {'music.apple.com', 'itunes.apple.com'} else None
            duration = row.get('trackTimeMillis')
            item['metadata'] = {'trackId': ident, 'title': row['trackName'], 'artist': row['artistName'], 'album': row.get('collectionName'), 'durationMs': duration if type(duration) is int and 0 < duration < 3600000 else None, 'genre': row.get('primaryGenreName'), 'releaseDate': row.get('releaseDate'), 'url': safe_url, 'checkedAt': stamp, 'matchBasis': 'exact artist and title; exact album preferred; unique track ID only'}
            status = ('ranked' if ident in ranks else 'out') if result['providers']['apple_chart']['state'] == 'ok' else 'error'
            point = {'at': updated, 'rank': ranks.get(ident), 'status': status, 'trackId': ident}
            old = (previous or {}).get('tracks', {}).get(s['id'], {}).get('appleHistory', [])
            item['appleHistory'] = merge_history(old, point, now, ident)
        result['tracks'][s['id']] = item
    key = os.environ.get('ISEGYE_YOUTUBE_API_KEY', '')
    official = [s for s in source if s.get('videoId') and s.get('videoSource', {}).get('kind', '').startswith('official_')]
    if key and official:
        try:
            response = fetch_json('https://www.googleapis.com/youtube/v3/videos?' + urlencode({'part': 'statistics', 'id': ','.join(s['videoId'] for s in official), 'key': key}))
            stats = {r['id']: r.get('statistics', {}) for r in response['items']}
            for s in official:
                v = stats.get(s['videoId'])
                result['tracks'][s['id']]['youtube'] = {'state': 'ok' if v is not None else 'unavailable', 'checkedAt': stamp, 'videoId': s['videoId'], **({k: int(v[k]) for k in ('viewCount', 'likeCount') if str(v.get(k, '')).isdigit()} if v is not None else {})}
            result['providers']['youtube'] = {'state': 'ok', 'checkedAt': stamp}
        except Exception as exc:
            result['providers']['youtube'] = {'state': 'error', 'checkedAt': stamp, 'error': type(exc).__name__}
            for s in official: result['tracks'][s['id']]['youtube'] = {'state': 'error'}
    else: result['providers']['youtube'] = {'state': 'not_configured'}
    for name in ('melon', 'genie', 'bugs', 'flo', 'spotify'):
        result['providers'][name] = {'state': 'not_configured', 'reason': 'Verified provider access and exact track IDs required; no inferred rank.'}
    return result

if __name__ == '__main__':
    path = ROOT / 'albums/snapshot.json'
    try: previous = json.loads(path.read_text()) if path.exists() else {}
    except (ValueError, OSError): previous = {}
    data = collect(previous); path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'matched': sum(v['match'] == 'matched' for v in data['tracks'].values()), 'total': len(data['tracks']), 'providers': {k: v['state'] for k, v in data['providers'].items()}}, ensure_ascii=False))
