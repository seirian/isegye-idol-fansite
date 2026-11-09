#!/usr/bin/env python3
"""Original Melon song achievements, with explicit daily (not TOP100) scope.
No credentials/client keys; no third-party values, lyrics or listener profiles.
"""
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse, parse_qs
import hashlib
import json
import re
from collect_album_domestic import norm

ORIGIN = 'https://m2.melon.com/m6/v5/song/info.json'
SOURCE_TYPE = 'melon_original_song_info'
KEYS = ('top100', 'hot100', 'realtime')

def record_url(track_id):
    if not isinstance(track_id, str) or not re.fullmatch(r'\d{1,12}', track_id):
        raise ValueError('Invalid Melon song ID')
    return ORIGIN + '?songId=' + track_id

def valid_source(url, track_id):
    try:
        u = urlparse(url)
        return (u.scheme == 'https' and u.hostname == 'm2.melon.com'
                and not u.username and not u.password and u.port in (None, 443)
                and u.path == '/m6/v5/song/info.json'
                and parse_qs(u.query, keep_blank_values=True) == {'songId': [track_id]} and not u.fragment)
    except (TypeError, ValueError):
        return False

def parse_record(payload, melon, checked_at):
    """Never turn BESTRANK (daily) or yesterday's rank into an hourly peak."""
    observed = datetime.fromisoformat(checked_at)
    if observed.tzinfo is None:
        raise ValueError('Observation timezone required')
    body = payload.get('response', {})
    if body.get('RESULTCODE') != '0' or body.get('RESPONSE') != 'songInfo':
        raise ValueError('Original song information unavailable')
    song = body.get('SONGINFO', {})
    ident = str(song.get('SONGID', ''))
    if ident != melon['trackId'] or str(song.get('ALBUMID', '')) != melon['albumId']:
        raise ValueError('Melon song/album identity mismatch')
    if norm(song.get('SONGNAME', '')) != norm(melon['title']) or norm(song.get('ALBUMNAME', '')) != norm(melon['album']):
        raise ValueError('Melon title/album mismatch')
    artists = {norm(a.get('ARTISTNAME', '')) for a in song.get('ARTISTLIST', [])}
    expected = norm(melon['artist'])
    accepted = {'이세계아이돌', '이세계아이돌isegyeidol', 'isegyeidol'} if expected in {'이세계아이돌', '이세계아이돌isegyeidol', 'isegyeidol'} else {expected}
    if not artists or not artists.issubset(accepted):
        raise ValueError('Melon artist mismatch')
    achievement = body.get('SONGACHIEVEMENTINFO')
    if not isinstance(achievement, dict) or '일간 차트' not in achievement.get('GUIDE', ''):
        raise ValueError('Missing explicit daily-chart scope')
    best = achievement.get('BESTRANK')
    if best in (None, '', '-', '0', '1001'):
        rank = None
        date = None
    else:
        if not isinstance(best, str) or not re.fullmatch(r'[1-9]\d{0,2}|1000', best):
            raise ValueError('Invalid daily best rank')
        if achievement.get('HASCHARTINHISTORY') != 'Y':
            raise ValueError('Inconsistent daily history')
        rank = int(best)
        date = datetime.strptime(achievement.get('BESTRANKDATE', ''), '%Y.%m.%d').date().isoformat()
        if date > observed.astimezone(timezone(timedelta(hours=9))).date().isoformat():
            raise ValueError('Future peak date')
    result = {
        'state': 'verified', 'trackId': ident, 'albumId': melon['albumId'],
        'source': record_url(ident), 'pageSource': 'https://www.melon.com/song/detail.htm?songId=' + ident,
        'sourceType': SOURCE_TYPE, 'checkedAt': checked_at,
        'ranks': dict.fromkeys(KEYS), 'dates': {},
        'dailyBestRank': rank, 'dailyBestDate': date, 'recordScope': 'daily',
        'scopeStart': '2014-01-01' if '14.01.01' in achievement.get('GUIDE', '') else None,
        'hourlyPeakState': 'not_provided_by_verified_source',
        'fetchState': 'ok',
    }
    return result

def reusable(record, melon):
    if not isinstance(record, dict): return False
    if record.get('sourceType') != SOURCE_TYPE or record.get('state') != 'verified' or record.get('recordScope') != 'daily': return False
    if record.get('trackId') != melon.get('trackId') or record.get('albumId') != melon.get('albumId') or not valid_source(record.get('source'), melon.get('trackId')): return False
    if record.get('ranks') != dict.fromkeys(KEYS): return False
    rank = record.get('dailyBestRank')
    if rank is not None and (type(rank) is not int or not 1 <= rank <= 1000): return False
    try:
        when = datetime.fromisoformat(record['checkedAt'])
        if when.tzinfo is None or when > datetime.now(timezone.utc): return False
        if rank is not None:
            date = datetime.strptime(record['dailyBestDate'], '%Y-%m-%d').date()
            if date > when.astimezone(timezone(timedelta(hours=9))).date(): return False
        elif record.get('dailyBestDate') is not None: return False
    except (KeyError, TypeError, ValueError): return False
    return True

def collect_original_records(result, previous, fetch):
    stamp = datetime.now(timezone.utc).isoformat()
    report = {}
    for sid, item in result['tracks'].items():
        # Old third-party caches may never masquerade as original records.
        item.pop('melonPeaks', None)
        melon = item.get('melon', {})
        if melon.get('state') != 'ok': continue
        url = record_url(melon['trackId'])
        try:
            raw = fetch(url)
            payload = json.loads(raw)
            record = parse_record(payload, melon, stamp)
            record['responseSha256'] = hashlib.sha256(raw).hexdigest()
            item['melonPeaks'] = record
            # Audio duration is now an original Melon field, not the MV duration.
            seconds = payload['response']['SONGINFO'].get('PLAYTIME')
            if isinstance(seconds, str) and seconds.isdigit() and 0 < int(seconds) < 3600:
                melon['durationMs'] = int(seconds) * 1000
                melon['durationSource'] = url
            report[sid] = {k: record[k] for k in ('state', 'trackId', 'source', 'sourceType', 'dailyBestRank', 'dailyBestDate', 'recordScope', 'checkedAt', 'responseSha256')}
        except Exception as exc:
            old = previous.get('tracks', {}).get(sid, {}).get('melonPeaks')
            if reusable(old, melon):
                item['melonPeaks'] = {**old, 'fetchState': 'error', 'lastAttemptAt': stamp}
            report[sid] = {'state': 'error', 'source': url, 'error': type(exc).__name__, 'retainedOriginal': reusable(old, melon)}
    return report
