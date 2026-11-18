#!/usr/bin/env python3
"""Bounded, resumable public-source audit for the registered album peak dates.

Old approved data supplies search dates only. Every emitted date is independently
matched to the freshly checked Guyso summary and exact chart/song trend response.
Raw source pages stay in the explicitly supplied scratch cache, never in the repo.
This is an offline review tool, not a periodic or production collector.
"""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import time
import unicodedata

ROOT = Path(__file__).resolve().parents[1]
BASE = 'https://xn--o39an51b2re.com'
TYPE = 'guyso_peak_date_evidence'
KST = timezone(timedelta(hours=9))
CHARTS = {
    'top100': ('top100', 'MELON_TOP100_CHART'),
    'hot100': ('hot100-d100', 'MELON_HOT100_D100_CHART'),
    'realtime': ('realtime', 'MELON_REALTIME_CHART'),
    'hot100_30': ('hot100-d30', 'MELON_HOT100_D30_CHART'),
    'daily': ('daily', 'MELON_DAILY_CHART'),
    'new_week': ('newest-w1', 'MELON_NEWEST_W1_CHART'),
    'new_month': ('newest-w4', 'MELON_NEWEST_W4_CHART'),
}


def norm(text):
    return re.sub(r'[^\w가-힣]', '', unicodedata.normalize('NFKC', text or '').casefold())


def identity(props, expected):
    song = props['song']
    if (song['platform'] != 'melon' or song['id'] != expected['trackId']
            or song['album']['platform'] != 'melon'
            or song['album']['id'] != expected['albumId']
            or norm(song['name']) != norm(expected['title'])):
        raise ValueError('Song/album identity mismatch')
    artists = song['artists']
    if len(artists) != 1:
        raise ValueError('Ambiguous artist')
    pair = {norm(artists[0]['name']), norm(expected['artist'])}
    if len(pair) != 1 and not any(pair.issubset(g) for g in (
            {'이세계아이돌', '이세계아이돌isegyeidol', 'isegyeidol'},
            {'고세구', 'gosegu', '고세구gosegu'})):
        raise ValueError('Artist mismatch')


def page(raw):
    if len(raw) > 4 * 1024 * 1024:
        raise ValueError('Oversize response')
    nodes = re.findall(rb'<script\b[^>]*\bid="__NEXT_DATA__"[^>]*>(.*?)</script>', raw, re.S)
    if len(nodes) != 1:
        raise ValueError('Missing/ambiguous page data')
    return json.loads(nodes[0])


def timestamp(value):
    result = datetime.fromisoformat(value)
    if result.tzinfo is None:
        result = result.replace(tzinfo=KST)
    return result.astimezone(KST).isoformat()


class Audit:
    def __init__(self, cache, delay):
        self.cache = cache
        cache.mkdir(parents=True, exist_ok=True)
        self.delay = delay

    def fetch(self, url):
        if not re.fullmatch(re.escape(BASE) + r'/(?:song/melon/[1-9]\d*|chart/melon/(?:top100|hot100-d100|hot100-d30|realtime|daily|newest-w1|newest-w4)/trend/ranking/[1-9]\d*(?:\?(?:end=\d{4}-\d{2}-\d{2}|page=[1-9]\d*))?)', url):
            raise ValueError('Non-allowlisted source')
        key = hashlib.sha256(url.encode()).hexdigest()
        body, metadata = self.cache / (key + '.html'), self.cache / (key + '.json')
        if body.exists() and metadata.exists():
            raw = body.read_bytes()
            meta = json.loads(metadata.read_text())
            if meta['source'] != url or hashlib.sha256(raw).hexdigest() != meta['responseSha256']:
                raise ValueError('Corrupt cache')
            return raw, meta
        time.sleep(self.delay)
        raw = subprocess.check_output(['curl', '-fsSL', '--max-time', '45', '--retry', '2', url])
        meta = {'source': url, 'checkedAt': datetime.now(timezone.utc).isoformat(),
                'responseSha256': hashlib.sha256(raw).hexdigest()}
        page(raw)
        body.write_bytes(raw)
        metadata.write_text(json.dumps(meta))
        return raw, meta

    def summary(self, expected):
        raw, meta = self.fetch(BASE + '/song/melon/' + expected['trackId'])
        props = page(raw)['props']['pageProps']
        identity(props, expected)
        ranks = {key: None for key in CHARTS}
        for key, (_, chart) in CHARTS.items():
            found = [r for r in props['records'] if r.get('type') == 'PEAK_RANKING' and r.get('chart') == chart]
            if len(found) > 1:
                raise ValueError('Duplicate summary chart')
            if found:
                rank = found[0]['score']
                if type(rank) is not int or not 1 <= rank <= (1000 if key == 'daily' else 100):
                    raise ValueError('Invalid summary rank')
                ranks[key] = rank
        return ranks, meta

    def trend(self, expected, key, rank, end=None, page_number=None):
        slug, chart = CHARTS[key]
        url = BASE + '/chart/melon/' + slug + '/trend/ranking/' + expected['trackId']
        if end:
            url += '?end=' + end
        if page_number:
            url += '?page=' + str(page_number)
        raw, meta = self.fetch(url)
        doc = page(raw)
        props = doc['props']['pageProps']
        identity(props, expected)
        data = props['data']
        unit = 'DAYS' if key == 'daily' else 'HOURS'
        if (data['platform'] != 'melon' or data['chart'] != chart
                or data['songId'] != expected['trackId'] or data['timeUnit'] != unit
                or doc['query']['songId'] != expected['trackId']
                or (end and doc['query'].get('end') != end)):
            raise ValueError('Trend chart identity mismatch')
        rows = data['data']
        times = [timestamp(r['time']) for r in rows]
        if len(times) != len(set(times)):
            raise ValueError('Duplicate trend timestamp')
        matches = [timestamp(r['time']) for r in rows if type(r.get('ranking')) is int and r['ranking'] == rank]
        evidence = None
        if matches:
            at = min(matches)
            evidence = {'rank': rank, 'date': at[:10], 'observedAt': at, **meta,
                        'rangeStart': min(times), 'rangeEnd': max(times),
                        'basis': 'earliest_observed_matching_peak', 'timeUnit': unit}
        report = {**meta, 'rangeStart': min(times) if times else None,
                  'rangeEnd': max(times) if times else None, 'matched': bool(matches),
                  'peakRank': rank, 'pointCount': len(rows)}
        return evidence, report, data.get('pagination')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--delay', type=float, default=0.75)
    parser.add_argument('--only', nargs='*')
    args = parser.parse_args()
    if args.delay < 0.5:
        parser.error('--delay must be at least 0.5 seconds')
    catalog = json.loads((ROOT / 'albums/peak-reference/guyso-20261118.json').read_text())
    history = json.loads((ROOT / 'albums/backfills/catalog-20261116.json').read_text())
    seed = json.loads((ROOT / 'albums/release-seed/snapshot.json').read_text())
    audit = Audit(args.cache, args.delay)
    output = {'schemaVersion': 1, 'sourceType': TYPE,
              'datePolicy': 'earliest_observed_matching_peak_not_guaranteed_first_achievement',
              'tracks': {}, 'excluded': catalog['excluded'], 'unresolved': [], 'searches': []}
    if args.output.exists():
        output = json.loads(args.output.read_text())
    now = datetime.now(KST)
    for sid, entry in catalog['tracks'].items():
        if args.only and sid not in args.only:
            continue
        expected = entry['identity']
        ranks, summary = audit.summary(expected)
        hints = {}
        for key, hkey in [('top100', 'melon_top100'), ('hot100', 'melon_hot100')]:
            points = history['tracks'].get(sid, {}).get('charts', {}).get(hkey, {}).get('points', [])
            matches = [p[0] for p in points if p[1] == ranks[key]]
            if matches:
                hints[key] = datetime.fromtimestamp(min(matches) * 3600, KST)
        release = datetime.fromisoformat(expected['releaseAt'])
        record = {'schemaVersion': 1, 'sourceType': TYPE, 'trackId': expected['trackId'],
                  'albumId': expected['albumId'], 'identity': expected, 'summary': {**summary, 'ranks': ranks}, 'records': {}}
        output['searches'] = [s for s in output['searches'] if s['sid'] != sid]
        output['unresolved'] = [s for s in output['unresolved'] if s['sid'] != sid]
        for key in CHARTS:
            rank = ranks[key]
            if rank is None:
                continue
            if key == 'daily':
                candidate, report, pagination = audit.trend(expected, key, rank)
                output['searches'].append({'sid': sid, 'chart': key, **report})
                if pagination and pagination['totalPages'] > 1:
                    if pagination['totalPages'] > 10:
                        raise ValueError('Daily pagination exceeds bounded audit')
                    for n in range(2, pagination['totalPages'] + 1):
                        other, report, _ = audit.trend(expected, key, rank, page_number=n)
                        output['searches'].append({'sid': sid, 'chart': key, **report})
                        if other and (not candidate or other['observedAt'] < candidate['observedAt']):
                            candidate = other
            else:
                primary = hints.get(key, release + timedelta(days=28))
                ends = [min(primary + timedelta(days=1), now).date().isoformat()]
                # The release window and existing catalog hint windows bound the
                # adaptive follow-up; no unbounded day-by-day historical crawl.
                alternatives = [release + timedelta(days=29), *[h + timedelta(days=1) for h in hints.values()]]
                # A former provider can point to a bounded lookup window only;
                # its date is never emitted without a matching fresh Guyso row.
                old = seed.get('tracks', {}).get(sid, {}).get('melonPeakFallback', {}).get('records', {}).get(key, {})
                if old.get('rank') == rank and re.fullmatch(r'\d{4}-\d{2}-\d{2}', old.get('date') or ''):
                    alternatives.append(datetime.fromisoformat(old['date']).replace(tzinfo=KST) + timedelta(days=1))
                for end in alternatives:
                    value = min(end, now).date().isoformat()
                    if value not in ends:
                        ends.append(value)
                candidate = None
                for end in ends:
                    candidate, report, _ = audit.trend(expected, key, rank, end=end)
                    output['searches'].append({'sid': sid, 'chart': key, **report})
                    if candidate:
                        break
            if candidate:
                record['records'][key] = candidate
            else:
                output['unresolved'].append({'sid': sid, 'chart': key, 'rank': rank, 'reason': 'no_matching_rank_in_bounded_source_windows'})
        output['tracks'][sid] = record
        output['reviewedAt'] = datetime.now(timezone.utc).isoformat()
        output['summaryChanges'] = [
            {'sid': song_id, 'chart': chart, 'before': catalog['tracks'][song_id]['reference']['records'][chart]['rank'], 'after': rank}
            for song_id, song in output['tracks'].items() for chart, rank in song['summary']['ranks'].items()
            if catalog['tracks'][song_id]['reference']['records'][chart]['rank'] != rank]
        output['absentSourcePeaks'] = [
            {'sid': song_id, 'chart': chart, 'reason': 'summary_has_no_numeric_peak'}
            for song_id, song in output['tracks'].items() for chart, rank in song['summary']['ranks'].items()
            if rank is None]
        output['coverage'] = {
            'registeredTracks': len(catalog['tracks']) + len(catalog['excluded']),
            'reviewedMelonTracks': len(output['tracks']),
            'sourceNumericPeaks': sum(rank is not None for song in output['tracks'].values() for rank in song['summary']['ranks'].values()),
            'verifiedDates': sum(len(song['records']) for song in output['tracks'].values()),
            'sourceAbsentPeaks': len(output['absentSourcePeaks']),
            'excludedVideoOnlyTracks': len(output['excluded']),
            'unresolvedNumericPeaks': len(output['unresolved']),
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n')
        print(sid, f"{len(record['records'])}/{sum(v is not None for v in ranks.values())}", flush=True)
    print('TOTAL', sum(len(t['records']) for t in output['tracks'].values()), 'unresolved', len(output['unresolved']))


if __name__ == '__main__':
    main()
