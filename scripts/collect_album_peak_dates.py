#!/usr/bin/env python3
"""Exact-rank Guyso trend evidence, kept separately from immutable peak summaries.
Only factual dates and bounded provenance are retained. An observed match is not
claimed to be the first achievement across gaps in the source archive.
"""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from urllib.parse import parse_qs, urlparse
import hashlib
import json
import re

from collect_album_peak_fallback import BASE, LIMITS, CHARTS, clock, reusable as summary_ok

ROOT = Path(__file__).resolve().parents[1]
TYPE = 'guyso_peak_date_evidence'
BASIS = 'earliest_observed_matching_peak'
KST = timezone(timedelta(hours=9))
CHART_PATHS = dict(zip(LIMITS, ('top100', 'hot100-d100', 'realtime', 'hot100-d30', 'daily', 'newest-w1', 'newest-w4')))
CHART_ENUMS = {key: enum for enum, key in CHARTS.items()}
REVIEW_PATH = ROOT/'albums/peak-reference/guyso-dates-20261118.json'
REVIEW_SHA256 = '970fad962f244610d18efd7855b8172b414dea7e2a742ddda2a614c63dcec716'
MAX_FETCHES = 14
RETRY_SECONDS = 24*3600


def date_value(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        raise ValueError('Invalid evidence date')
    return datetime.strptime(value, '%Y-%m-%d').date()


def source_url(track_id, key):
    if key not in CHART_PATHS or not re.fullmatch(r'[1-9]\d{0,11}', str(track_id)):
        raise ValueError('Invalid trend identity')
    return BASE+'/chart/melon/'+CHART_PATHS[key]+'/trend/ranking/'+str(track_id)


def allowed_source(url, track_id=None, key=None):
    try:
        u = urlparse(url)
        if u.scheme != 'https' or u.netloc != 'xn--o39an51b2re.com' or u.fragment:
            return False
        match = re.fullmatch(r'/chart/melon/('+'|'.join(CHART_PATHS.values())+r')/trend/ranking/([1-9]\d{0,11})', u.path)
        if not match or (track_id is not None and match[2] != str(track_id)) or (key is not None and match[1] != CHART_PATHS[key]):
            return False
        if u.query:
            query = parse_qs(u.query, strict_parsing=True)
            if set(query) != {'end'} or len(query['end']) != 1 or u.query != 'end='+query['end'][0]:
                return False
            date_value(query['end'][0])
        return True
    except (TypeError, ValueError, KeyError, AttributeError):
        return False


def record_ok(row, melon, key, rank):
    try:
        if (not isinstance(row, dict) or type(rank) is not int or type(row.get('rank')) is not int
                or row['rank'] != rank or key not in LIMITS or not 1 <= rank <= LIMITS[key]
                or row.get('basis') != BASIS or row.get('timeUnit') != ('DAYS' if key == 'daily' else 'HOURS')
                or not allowed_source(row.get('source'), melon['trackId'], key)
                or not re.fullmatch(r'[0-9a-f]{64}', row.get('responseSha256', ''))):
            return False
        at, start, end, checked = (clock(row[k]) for k in ('observedAt', 'rangeStart', 'rangeEnd', 'checkedAt'))
        local = at.astimezone(KST)
        if (date_value(row['date']) != local.date() or not start <= at <= end <= checked+timedelta(minutes=10)
                or checked > datetime.now(timezone.utc)+timedelta(minutes=10)
                or (key == 'daily' and (local.hour, local.minute, local.second, local.microsecond) != (0, 0, 0, 0))):
            return False
        return True
    except (KeyError, TypeError, ValueError, AttributeError):
        return False


def envelope_ok(value, melon):
    return (isinstance(value, dict) and type(value.get('schemaVersion')) is int and value.get('schemaVersion') == 1
        and value.get('sourceType') == TYPE and value.get('trackId') == melon.get('trackId')
        and value.get('albumId') == melon.get('albumId') and isinstance(value.get('records'), dict))


def verified_records(value, melon, summary):
    if not envelope_ok(value, melon) or not summary_ok(summary, melon):
        return {}
    return {key: deepcopy(row) for key, row in value['records'].items()
        if key in LIMITS and record_ok(row, melon, key, summary['records'][key]['rank'])}


def envelope(melon, records, attempts=None):
    value = {'schemaVersion': 1, 'sourceType': TYPE, 'trackId': melon['trackId'],
        'albumId': melon['albumId'], 'records': records}
    if attempts:
        value['attempts'] = attempts
    return value


@lru_cache(maxsize=1)
def reviewed_records():
    raw = REVIEW_PATH.read_bytes()
    if hashlib.sha256(raw).hexdigest() != REVIEW_SHA256:
        raise ValueError('Reviewed peak-date dataset changed')
    data = json.loads(raw)
    if data.get('schemaVersion') != 1 or data.get('sourceType') != TYPE or not isinstance(data.get('tracks'), dict):
        raise ValueError('Wrong reviewed peak-date dataset')
    from collect_album_peak_fallback import reviewed_records as summary_records
    summaries = summary_records()
    if set(data['tracks']) != set(summaries):
        raise ValueError('Incomplete reviewed peak-date catalog')
    for sid, value in data['tracks'].items():
        known = summaries.get(sid)
        if (not known or not envelope_ok(value, known['identity'])
                or len(verified_records(value, known['identity'], known['reference'])) != len(value['records'])
                or set(value['records']) != {key for key, row in known['reference']['records'].items() if row['rank'] is not None}):
            raise ValueError('Invalid reviewed peak-date identity or rank: '+sid)
    return data['tracks']


def apply_reviewed(data, strict=False):
    """Offline application touches only melonPeakDates, never source ranks/clocks."""
    seeds = reviewed_records()
    if strict and not set(seeds).issubset(data.get('tracks', {})):
        raise ValueError('Incomplete live registered peak-date catalog')
    report = {'verifiedTracks': [], 'datedRankCount': 0, 'missing': [], 'excluded': []}
    for sid, item in data.get('tracks', {}).items():
        melon, summary = item.get('melon', {}), item.get('melonPeakFallback')
        seed, old = seeds.get(sid), item.get('melonPeakDates')
        if strict and seed and (not envelope_ok(seed, melon) or not summary_ok(summary, melon)):
            raise ValueError('Live peak-date identity/summary mismatch: '+sid)
        rows = verified_records(old, melon, summary)
        for key, value in verified_records(seed, melon, summary).items():
            if key not in rows or clock(value['observedAt']) < clock(rows[key]['observedAt']):
                rows[key] = value
        if rows:
            attempts = old.get('attempts') if envelope_ok(old, melon) else None
            item['melonPeakDates'] = envelope(melon, rows, attempts)
            report['verifiedTracks'].append(sid)
            report['datedRankCount'] += len(rows)
        elif old is not None:
            item.pop('melonPeakDates', None)
        if summary_ok(summary, melon):
            report['missing'].extend({'sid': sid, 'chart': key, 'rank': row['rank']}
                for key, row in summary['records'].items() if row['rank'] is not None and key not in rows)
        else:
            report['excluded'].append(sid)
    if strict and report['missing']:
        raise ValueError('Live peak ranks lack reviewed dates: '+json.dumps(report['missing'], ensure_ascii=False))
    return report


def parse_trend(raw, melon, key, rank, url, checked_at):
    """Parse an exact track/album/chart response, taking only matching-rank times."""
    from bs4 import BeautifulSoup
    from collect_album_domestic import norm
    if not allowed_source(url, melon['trackId'], key):
        raise ValueError('Wrong trend source')
    raw = raw if isinstance(raw, bytes) else raw.encode('utf-8')
    if len(raw) > 4*1024*1024:
        raise ValueError('Oversized trend response')
    nodes = BeautifulSoup(raw, 'html.parser').select('script#__NEXT_DATA__')
    if len(nodes) != 1:
        raise ValueError('Ambiguous trend data')
    props = json.loads(nodes[0].string)['props']['pageProps']
    song, data = props['song'], props['data']
    artists = song.get('artists', [])
    if (song.get('platform') != 'melon' or song.get('id') != melon['trackId']
            or song.get('album', {}).get('platform') != 'melon' or song.get('album', {}).get('id') != melon['albumId']
            or norm(song.get('name')) != norm(melon['title']) or len(artists) != 1):
        raise ValueError('Trend song/album identity mismatch')
    artist, expected = norm(artists[0].get('name')), norm(melon['artist'])
    groups = ({'이세계아이돌', '이세계아이돌isegyeidol', 'isegyeidol'}, {'고세구', 'gosegu', '고세구gosegu'})
    if artist != expected and not any({artist, expected}.issubset(group) for group in groups):
        raise ValueError('Trend artist mismatch')
    unit = 'DAYS' if key == 'daily' else 'HOURS'
    points = data.get('data')
    if (data.get('platform') != 'melon' or data.get('songId') != melon['trackId']
            or data.get('chart') != CHART_ENUMS[key] or data.get('timeUnit') != unit
            or not isinstance(points, list) or len(points) > 5000):
        raise ValueError('Trend chart/track identity mismatch')
    seen, matches = {}, []
    for point in points:
        if not isinstance(point, dict) or not isinstance(point.get('time'), str):
            raise ValueError('Invalid trend point')
        when = datetime.fromisoformat(point['time'])
        if when.tzinfo is None:
            when = when.replace(tzinfo=KST)  # Guyso Melon local chart time.
        when = when.astimezone(KST)
        if unit == 'DAYS' and (when.hour, when.minute, when.second, when.microsecond) != (0, 0, 0, 0):
            raise ValueError('Invalid daily trend time')
        value = point.get('ranking')
        if value is not None and (type(value) is not int or not 1 <= value <= (1000 if key in {'daily', 'realtime'} else LIMITS[key])):
            raise ValueError('Invalid trend rank')
        if when in seen and seen[when] != value:
            raise ValueError('Conflicting trend point')
        seen[when] = value
        if value == rank:
            matches.append(when)
    if not matches:
        return None
    when = min(matches)
    row = {'rank': rank, 'date': when.date().isoformat(), 'observedAt': when.isoformat(),
        'source': url, 'checkedAt': checked_at, 'responseSha256': hashlib.sha256(raw).hexdigest(),
        'rangeStart': min(seen).isoformat(), 'rangeEnd': max(seen).isoformat(), 'basis': BASIS, 'timeUnit': unit}
    if not record_ok(row, melon, key, rank):
        raise ValueError('Invalid trend evidence date')
    return row


def collect_peak_dates(result, previous, fetch):
    """Reuse proven dates forever while rank matches; bound new-peak lookups.
    One latest trend window per missing category, at most 14 requests per batch;
    unsuccessful same-rank lookups wait 24h instead of crawling history hourly.
    """
    now = datetime.now(timezone.utc)
    seeds = reviewed_records()
    report = {'requested': 0, 'datedRankCount': 0, 'missing': [], 'errors': []}
    for sid, item in result['tracks'].items():
        melon, summary = item.get('melon', {}), item.get('melonPeakFallback')
        old = previous.get('tracks', {}).get(sid, {}).get('melonPeakDates')
        item.pop('melonPeakDates', None)
        if not summary_ok(summary, melon):
            continue
        rows = verified_records(old, melon, summary)
        for key, value in verified_records(seeds.get(sid), melon, summary).items():
            if key not in rows or clock(value['observedAt']) < clock(rows[key]['observedAt']):
                rows[key] = value
        attempts = {}
        for key, record in summary['records'].items():
            rank = record['rank']
            if rank is None or key in rows:
                continue
            old_attempts = old.get('attempts', {}) if envelope_ok(old, melon) else {}
            old_attempt = old_attempts.get(key) if isinstance(old_attempts, dict) else None
            try:
                cached = (isinstance(old_attempt, dict) and type(old_attempt.get('rank')) is int
                    and old_attempt['rank'] == rank and 0 <= (now-clock(old_attempt['checkedAt'])).total_seconds() < RETRY_SECONDS)
            except (KeyError, ValueError, TypeError, AttributeError):
                cached = False
            if cached:
                attempts[key] = deepcopy(old_attempt)
            elif report['requested'] < MAX_FETCHES:
                report['requested'] += 1
                url = source_url(melon['trackId'], key)
                try:
                    raw = fetch(url)
                    checked_at = datetime.now(timezone.utc).isoformat()
                    value = parse_trend(raw, melon, key, rank, url, checked_at)
                    if value:
                        rows[key] = value
                    else:
                        attempts[key] = {'rank': rank, 'checkedAt': now.isoformat(), 'state': 'not_observed'}
                except Exception as exc:
                    attempts[key] = {'rank': rank, 'checkedAt': now.isoformat(), 'state': 'error'}
                    report['errors'].append({'sid': sid, 'chart': key, 'error': type(exc).__name__})
            if key not in rows:
                report['missing'].append({'sid': sid, 'chart': key, 'rank': rank})
        if rows or attempts:
            item['melonPeakDates'] = envelope(melon, rows, attempts)
        report['datedRankCount'] += len(rows)
    return report
