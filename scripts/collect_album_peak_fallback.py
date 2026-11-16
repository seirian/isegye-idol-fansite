#!/usr/bin/env python3
"""User-approved secondary historical peaks; never relabel these as Melon originals.
Only bounded factual peak fields are retained. No lyrics, UI, or time-series copying.
"""
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urlparse
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[1]
TYPE = 'isegyechart_observed_peaks'
SELECTOR = 'https://isegyechart.com/api/song-selector-list'
LABELS = {
    'TOP100': ('top100', 100), 'HOT100 (100일)': ('hot100', 100),
    '실시간차트': ('realtime', 100), 'HOT100 (30일)': ('hot100_30', 100),
    '일간차트': ('daily', 1000), '최신발매 (1주)': ('new_week', 100),
    '최신발매 (4주)': ('new_month', 100),
}
LIMITS = dict(LABELS.values())

def source_url(record_id):
    if type(record_id) is not int or not 0 < record_id < 1000000:
        raise ValueError('Invalid secondary page ID')
    return f'https://isegyechart.com/song/{record_id}'

def allowed_source(url):
    try:
        u = urlparse(url)
        return (u.scheme == 'https' and u.netloc == 'isegyechart.com'
                and re.fullmatch(r'/song/[1-9]\d{0,5}', u.path) is not None
                and not u.query and not u.fragment)
    except (TypeError, ValueError):
        return False

def unastro(value):
    if isinstance(value, list) and len(value) == 2 and type(value[0]) is int:
        return unastro(value[1])
    if isinstance(value, list): return [unastro(v) for v in value]
    if isinstance(value, dict): return {k: unastro(v) for k, v in value.items() if k != 'lyrics'}
    return value

def discover_ids(raw, tracks):
    """One bounded public index request; candidate pages still require exact Melon IDs."""
    from collect_album_domestic import norm
    rows = json.loads(raw)
    if not isinstance(rows, list) or len(rows) > 2000:
        raise ValueError('Invalid public selector index')
    index = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('Invalid selector entry')
        ident = row.get('id')
        if type(ident) is not int or not 0 < ident < 1000000:
            continue
        key = (norm(row.get('name') or ''), norm(row.get('albumName') or ''),
               norm(row.get('artistName') or ''))
        index.setdefault(key, set()).add(ident)
    found = {}
    for sid, item in tracks.items():
        melon = item.get('melon', {})
        if melon.get('state') != 'ok':
            continue
        artist = norm(melon.get('artist') or '')
        group = {'이세계아이돌', '이세계아이돌isegyeidol', 'isegyeidol'}
        artists = group if artist in group else {artist}
        candidates = set()
        for name in {norm(melon.get('title') or '')}:
            for candidate_artist in artists:
                candidates.update(index.get((name, norm(melon.get('album') or ''), candidate_artist), set()))
        if len(candidates) == 1:
            found[sid] = next(iter(candidates))
    return found


def parse_reference(html, melon, record_id, checked_at):
    # Build-time validation uses only the standard library; parsing needs these.
    from bs4 import BeautifulSoup
    from collect_album_domestic import norm, text
    soup = BeautifulSoup(html, 'html.parser')
    info = None
    for el in soup.select('astro-island[props]'):
        if 'FeaturedSongSelector' in el.get('component-url', ''):
            candidate = unastro(json.loads(el['props'])).get('songInfo')
            if info is not None: raise ValueError('Ambiguous song identity')
            info = candidate
    if not isinstance(info, dict) or str(info.get('id')) != str(record_id):
        raise ValueError('Missing secondary song identity')
    if (str(info.get('idMap', {}).get('melonId')) != melon['trackId']
            or str(info.get('albumIdMap', {}).get('melonId')) != melon['albumId']):
        raise ValueError('Secondary song/album ID mismatch')
    if norm(info.get('name')) != norm(melon['title']): raise ValueError('Secondary title mismatch')
    artist, expected = norm(info.get('artistName')), norm(melon['artist'])
    group = {'이세계아이돌', '이세계아이돌isegyeidol', 'isegyeidol'}
    if artist != expected and not {artist, expected}.issubset(group):
        raise ValueError('Secondary artist mismatch')
    if '멜론 최고 성적' not in soup.get_text(' ', strip=True):
        raise ValueError('Missing historical peak section')
    records = {key: {'rank': None, 'date': None} for key in LIMITS}
    seen = set()
    for heading in soup.select('h3'):
        label = text(heading)
        if label not in LABELS: continue
        key, limit = LABELS[label]
        if key in seen: raise ValueError('Duplicate chart heading')
        seen.add(key)
        content = text(heading.parent)
        ranks = re.findall(r'(?<!\d)(\d+)\s*위', content)
        if len(ranks) > 1: raise ValueError('Ambiguous historical rank')
        if not ranks: continue
        rank = int(ranks[0])
        if not 1 <= rank <= limit: raise ValueError('Invalid historical rank')
        dates = re.findall(r'(?<!\d)(\d{4}|\d{2})\.(\d{1,2})\.(\d{1,2})(?!\d)', content)
        if len(dates) > 1: raise ValueError('Ambiguous historical date')
        date = None
        if dates:
            y, m, d = map(int, dates[0]); y = y + 2000 if y < 100 else y
            date = datetime(y, m, d).date().isoformat()
        records[key] = {'rank': rank, 'date': date}
    if not seen: raise ValueError('No historical peak entries')
    result = {'schemaVersion': 1, 'state': 'verified', 'sourceType': TYPE,
              'trackId': melon['trackId'], 'albumId': melon['albumId'],
              'source': source_url(record_id), 'checkedAt': checked_at,
              'fetchState': 'ok', 'records': records}
    if not reusable(result, melon, record_id): raise ValueError('Invalid secondary record')
    return result

def reusable(record, melon, record_id=None):
    if not isinstance(record, dict) or record.get('schemaVersion') != 1: return False
    if record.get('state') != 'verified' or record.get('sourceType') != TYPE: return False
    if (record.get('trackId') != melon.get('trackId') or record.get('albumId') != melon.get('albumId')
            or not allowed_source(record.get('source'))): return False
    if record_id is not None and record['source'] != source_url(record_id): return False
    try:
        when = datetime.fromisoformat(record['checkedAt'].replace('Z', '+00:00'))
        if when.tzinfo is None or when > datetime.now(timezone.utc) + timedelta(minutes=10): return False
        day = when.astimezone(timezone(timedelta(hours=9))).date().isoformat()
        rows = record['records']
        if not isinstance(rows, dict) or set(rows) != set(LIMITS): return False
        for key, limit in LIMITS.items():
            row = rows[key]; rank, date = row['rank'], row['date']
            if rank is None:
                if date is not None: return False
            elif type(rank) is not int or not 1 <= rank <= limit: return False
            if date is not None:
                parsed = datetime.strptime(date, '%Y-%m-%d').date().isoformat()
                if parsed != date or not '2000-01-01' <= parsed <= day: return False
    except (KeyError, TypeError, ValueError, AttributeError): return False
    return True

def collect_reference_peaks(result, previous, fetch):
    stamp = datetime.now(timezone.utc).isoformat()
    mappings = json.loads((ROOT/'albums/record-sources.json').read_text())['tracks']
    report = {}
    # Discover every newly registered album track, not just the legacy allowlisted songs.
    # Selector names only shortlist candidates: each page must match the actual Melon
    # song ID, album ID, title and artist before any rank can be accepted.
    missing = {sid: item for sid, item in result['tracks'].items()
               if sid not in mappings and item.get('melon', {}).get('state') == 'ok'}
    discovered = {}
    discovery_error = None
    if missing:
        try:
            discovered = discover_ids(fetch(SELECTOR), missing)
        except Exception as exc:
            discovery_error = type(exc).__name__
    for sid, item in result['tracks'].items():
        item.pop('melonPeakFallback', None)
        melon = item.get('melon', {})
        entry = mappings.get(sid)
        if melon.get('state') != 'ok':
            continue
        record_id = (entry['recordId'] if entry and melon.get('trackId') == entry['melonId']
                     else discovered.get(sid) if not entry else None)
        old = previous.get('tracks', {}).get(sid, {}).get('melonPeakFallback')
        if record_id is None:
            retained = reusable(old, melon)
            if retained:
                item['melonPeakFallback'] = {**old, 'fetchState': 'error', 'lastAttemptAt': stamp}
            report[sid] = {'state': 'unverified', 'reason': discovery_error or 'no_unique_selector_match',
                           'retainedVerified': retained}
            continue
        url = source_url(record_id)
        try:
            raw = fetch(url)
            value = parse_reference(raw.decode('utf-8'), melon, record_id, stamp)
            value['responseSha256'] = hashlib.sha256(raw).hexdigest()
            item['melonPeakFallback'] = value
            report[sid] = value
        except Exception as exc:
            retained = reusable(old, melon, record_id)
            if retained:
                item['melonPeakFallback'] = {**old, 'fetchState': 'error', 'lastAttemptAt': stamp}
            report[sid] = {'state': 'error', 'source': url, 'error': type(exc).__name__,
                           'retainedVerified': retained}
    return report
