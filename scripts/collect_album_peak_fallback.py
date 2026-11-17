#!/usr/bin/env python3
"""Verified Guyso song-page peak summaries. No legacy-source relabeling.
Only seven factual ranks, exact identities and provenance are retained. The
summary does not provide achievement dates; old dates are never carried over.
"""
from copy import deepcopy
from datetime import datetime, timezone, timedelta
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[1]
TYPE = 'guyso_observed_peaks'
BASE = 'https://xn--o39an51b2re.com'
CACHE_SECONDS = 6 * 3600
LABELS = {
    'TOP100': ('top100', 100), 'HOT100 (100일)': ('hot100', 100),
    '실시간차트': ('realtime', 100), 'HOT100 (30일)': ('hot100_30', 100),
    '일간차트': ('daily', 1000), '최신발매 (1주)': ('new_week', 100),
    '최신발매 (4주)': ('new_month', 100),
}
LIMITS = dict(LABELS.values())
CHARTS = dict(zip(('MELON_TOP100_CHART', 'MELON_HOT100_D100_CHART',
    'MELON_REALTIME_CHART', 'MELON_HOT100_D30_CHART', 'MELON_DAILY_CHART',
    'MELON_NEWEST_W1_CHART', 'MELON_NEWEST_W4_CHART'), LIMITS))
REVIEW_PATH = ROOT/'albums/peak-reference/guyso-20261118.json'
REVIEW_SHA256 = '57a8e8d48d3cfa5b7311f2483ba08dab528f34780b2816739ec490cb63a7b776'


def source_url(track_id):
    if isinstance(track_id, bool) or not re.fullmatch(r'[1-9]\d{0,11}', str(track_id)):
        raise ValueError('Invalid Melon song ID')
    return BASE+'/song/melon/'+str(track_id)


def allowed_source(url):
    try:
        u = urlparse(url)
        return (u.scheme == 'https' and u.netloc == 'xn--o39an51b2re.com'
            and re.fullmatch(r'/song/melon/[1-9]\d{0,11}', u.path) is not None
            and not u.query and not u.fragment)
    except (TypeError, ValueError, AttributeError):
        return False


def clock(value):
    value = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if value.tzinfo is None:
        raise ValueError('Missing source confirmation timezone')
    return value.astimezone(timezone.utc)


def reusable(record, melon, record_id=None):
    try:
        if (not isinstance(record, dict) or record.get('schemaVersion') != 1
                or record.get('state') != 'verified' or record.get('sourceType') != TYPE
                or record.get('trackId') != melon.get('trackId')
                or record.get('albumId') != melon.get('albumId')
                or record.get('source') != source_url(melon.get('trackId'))
                or not allowed_source(record.get('source'))
                or (record_id is not None and str(record_id) != melon['trackId'])
                or record.get('datePolicy') != 'summary_does_not_provide_dates'
                or not re.fullmatch('[0-9a-f]{64}', record.get('responseSha256', ''))):
            return False
        if clock(record['checkedAt']) > datetime.now(timezone.utc)+timedelta(minutes=10):
            return False
        rows = record['records']
        if not isinstance(rows, dict) or set(rows) != set(LIMITS):
            return False
        for key, limit in LIMITS.items():
            row = rows[key]
            if not isinstance(row, dict) or set(row) != {'rank', 'date'} or row['date'] is not None:
                return False
            rank = row['rank']
            if rank is not None and (type(rank) is not int or not 1 <= rank <= limit):
                return False
    except (KeyError, TypeError, ValueError, AttributeError):
        return False
    return True


def parse_reference(html, melon, record_id, checked_at):
    from bs4 import BeautifulSoup
    from collect_album_domestic import norm
    raw = html if isinstance(html, bytes) else html.encode('utf-8')
    if len(raw) > 4*1024*1024:
        raise ValueError('Oversize Guyso page')
    soup = BeautifulSoup(raw, 'html.parser')
    nodes = soup.select('script#__NEXT_DATA__')
    if len(nodes) != 1:
        raise ValueError('Missing or ambiguous Guyso page data')
    props = json.loads(nodes[0].string)['props']['pageProps']
    song = props['song']
    if (song.get('platform') != 'melon' or song.get('id') != melon['trackId']
            or str(record_id) != melon['trackId']
            or song.get('album', {}).get('platform') != 'melon'
            or song.get('album', {}).get('id') != melon['albumId']
            or norm(song.get('name')) != norm(melon['title'])):
        raise ValueError('Guyso song/album identity mismatch')
    artists = song.get('artists', [])
    if len(artists) != 1:
        raise ValueError('Ambiguous Guyso artist')
    artist, expected = norm(artists[0].get('name')), norm(melon['artist'])
    group = {'이세계아이돌', '이세계아이돌isegyeidol', 'isegyeidol'}
    solo = {'고세구', 'gosegu', '고세구gosegu'}
    if artist != expected and not any({artist, expected}.issubset(g) for g in (group, solo)):
        raise ValueError('Guyso artist mismatch')
    entries = props.get('records')
    if not isinstance(entries, list) or len(entries) > 100:
        raise ValueError('Missing Guyso record summary')
    rows = {key: {'rank': None, 'date': None} for key in LIMITS}
    seen = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError('Invalid Guyso record entry')
        if entry.get('type') != 'PEAK_RANKING' or entry.get('chart') not in CHARTS:
            continue
        key = CHARTS[entry['chart']]
        if key in seen:
            raise ValueError('Duplicate peak category')
        seen.add(key)
        rank = entry.get('score')
        if type(rank) is not int or not 1 <= rank <= LIMITS[key]:
            raise ValueError('Invalid Guyso peak rank')
        rows[key]['rank'] = rank
    result = {'schemaVersion': 1, 'state': 'verified', 'sourceType': TYPE,
        'trackId': melon['trackId'], 'albumId': melon['albumId'],
        'source': source_url(melon['trackId']), 'checkedAt': checked_at,
        'fetchState': 'ok', 'responseSha256': hashlib.sha256(raw).hexdigest(),
        'datePolicy': 'summary_does_not_provide_dates', 'records': rows}
    if not reusable(result, melon, record_id):
        raise ValueError('Invalid Guyso peak provenance')
    return result


@lru_cache(maxsize=1)
def reviewed_records():
    raw = REVIEW_PATH.read_bytes()
    if hashlib.sha256(raw).hexdigest() != REVIEW_SHA256:
        raise ValueError('Reviewed peak dataset changed')
    data = json.loads(raw)
    if data.get('schemaVersion') != 1 or data.get('sourceType') != TYPE:
        raise ValueError('Wrong reviewed peak dataset')
    for entry in data['tracks'].values():
        if not reusable(entry['reference'], entry['identity']):
            raise ValueError('Invalid reviewed source identity')
    return data['tracks']


def apply_reviewed(data, strict=False):
    """Offline migration: touch only peak-reference fields, never charts or clocks."""
    report = {'verifiedTracks': [], 'retainedNewer': [], 'excluded': [], 'rankChanges': []}
    reviewed = reviewed_records()
    if strict and not set(reviewed).issubset(data.get('tracks', {})):
        raise ValueError('Incomplete live registered catalog')
    for sid, item in data.get('tracks', {}).items():
        entry = reviewed.get(sid)
        melon = item.get('melon', {})
        prior = item.get('melonPeakFallback')
        if not entry or not reusable(entry['reference'], melon):
            if strict and entry:
                raise ValueError('Live peak identity mismatch: '+sid)
            if prior is not None and not reusable(prior, melon):
                item.pop('melonPeakFallback', None)
            report['excluded'].append(sid)
            continue
        value = entry['reference']
        if reusable(prior, melon) and clock(prior['checkedAt']) >= clock(value['checkedAt']):
            report['retainedNewer'].append(sid)
            report['verifiedTracks'].append(sid)
            continue
        for key in LIMITS:
            before = (prior or {}).get('records', {}).get(key, {}).get('rank')
            after = value['records'][key]['rank']
            if before != after:
                report['rankChanges'].append({'sid': sid, 'chart': key, 'before': before, 'after': after})
        item['melonPeakFallback'] = deepcopy(value)
        report['verifiedTracks'].append(sid)
    return report


def collect_reference_peaks(result, previous, fetch):
    """Existing batch uses exact song IDs and a six-hour per-song evidence cache."""
    now = datetime.now(timezone.utc)
    report = {}
    seeds = reviewed_records()
    for sid, item in result['tracks'].items():
        item.pop('melonPeakFallback', None)
        melon = item.get('melon', {})
        if melon.get('state') != 'ok':
            continue
        old = previous.get('tracks', {}).get(sid, {}).get('melonPeakFallback')
        if not reusable(old, melon):
            old = seeds.get(sid, {}).get('reference')
        if reusable(old, melon) and 0 <= (now-clock(old['checkedAt'])).total_seconds() < CACHE_SECONDS:
            item['melonPeakFallback'] = deepcopy(old)
            report[sid] = {'state': 'cached', 'source': old['source'], 'checkedAt': old['checkedAt']}
            continue
        url = source_url(melon['trackId'])
        try:
            raw = fetch(url)
            value = parse_reference(raw, melon, melon['trackId'], now.isoformat())
            item['melonPeakFallback'] = value
            report[sid] = value
        except Exception as exc:
            retained = reusable(old, melon)
            if retained:
                item['melonPeakFallback'] = {**deepcopy(old), 'fetchState': 'error', 'lastAttemptAt': now.isoformat()}
            report[sid] = {'state': 'error', 'source': url, 'error': type(exc).__name__, 'retainedVerified': retained}
    return report
