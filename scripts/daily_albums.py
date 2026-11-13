"""Album-only collection and health checks; no deployment credentials or writes.
Keeps real observation times and failed chart gaps instead of inventing zeroes.
"""
from copy import deepcopy
from datetime import datetime, timezone, timedelta
from pathlib import Path
import argparse
import hashlib
import json
import re

from album_releases import load_catalog, releases
from collect_album_insights import collect as api_collect
from collect_album_domestic import collect as domestic_collect, merge, norm
from collect_album_records import collect as records_collect

ROOT = Path(__file__).resolve().parents[1]
KINDS = {'melon_top100', 'melon_hot100'}
MAX_BYTES = 8_000_000  # 30 days of hourly chart + video observations; transport remains bounded.
HOT100_POLICY = 'https://help.melon.com/web/faq/content.htm?faqId=2642'
HOT100_SOURCE = 'https://www.melon.com/chart/hot100/index.htm?chartType=D100'

def clock(value):
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise ValueError('Album observation timezone missing')
    return result

def asset_entries(data):
    result = {}
    assets = data.get('assets', {})
    if not isinstance(assets, dict) or set(assets)-{'covers', 'brands', 'badges'}:
        raise ValueError('Unknown album asset group')
    for group, entries in assets.items():
        if not isinstance(entries, dict) or len(entries) > 500:
            raise ValueError('Invalid album assets')
        for key, row in entries.items():
            sha = row.get('sha256', '')
            if (not re.fullmatch('[0-9a-f]{64}', sha)
                    or row.get('path') != 'albums/asset-cache/'+sha+'.webp'
                    or (group != 'brands' and key != sha)
                    or (group == 'brands' and key not in {'melon','genie','bugs','apple','youtube','youtube_music'})):
                raise ValueError('Unsafe album asset reference')
            result[sha] = row
    return result

def validate(data, exact=False, fresh=False):
    if (not isinstance(data, dict) or data.get('schemaVersion') != 1
            or not isinstance(data.get('tracks'), dict) or not isinstance(data.get('providers'), dict)
            or len(data['tracks']) > 500 or len(json.dumps(data).encode()) > MAX_BYTES):
        raise ValueError('Invalid album snapshot')
    when = clock(data['generatedAt']); age = (datetime.now(timezone.utc)-when).total_seconds()
    if age < -600 or (fresh and age > 7200):
        raise ValueError('Stale or future album collection')
    known = {s['id'] for s in load_catalog(ROOT)['songs']}
    if set(data['tracks'])-known or (exact and set(data['tracks']) != known):
        raise ValueError('Missing or unknown album catalog tracks')
    if set(data.get('domesticCharts', {}))-KINDS:
        raise ValueError('Unapproved chart provider')
    asset_entries(data)
    return data

def preserve(previous, result):
    """Retain verified evidence on transient errors, without re-stamping it."""
    now = clock(result['generatedAt'])
    for sid, item in result['tracks'].items():
        old = previous.get('tracks', {}).get(sid, {})
        if not item.get('metadata') and old.get('metadata'):
            item['metadata'] = deepcopy(old['metadata'])
            item['metadataFetchState'] = 'error'
        for provider in ('melon', 'genie', 'bugs', 'youtube'):
            current, prior = item.get(provider, {}), old.get(provider, {})
            if current.get('state') in ('error', 'unmatched', 'not_configured') and prior.get('state') == 'ok':
                item[provider] = {**deepcopy(prior), 'fetchState': 'error', 'lastAttemptAt': result['generatedAt']}
        melon = item.get('melon', {})
        for kind in KINDS:
            if kind not in item.get('charts', {}) and melon.get('trackId'):
                point = {'at': result['generatedAt'], 'trackId': melon['trackId'], 'rank': None, 'status': 'error'}
                history = merge(old.get('charts', {}).get(kind, []), point, now, melon['trackId'], 100)
                item.setdefault('charts', {})[kind] = history
                melon[kind.replace('melon_', '')+'History'] = history
        from collect_album_melon_record import reusable as original_ok
        from collect_album_peak_fallback import reusable as fallback_ok
        for key, check in (('melonPeaks', original_ok), ('melonPeakFallback', fallback_ok)):
            prior = old.get(key)
            if key not in item and check(prior, melon):
                item[key] = {**deepcopy(prior), 'fetchState': 'error', 'lastAttemptAt': result['generatedAt']}
        honor = old.get('melonHonor', {})
        if 'melonHonor' not in item and honor.get('albumId') == melon.get('albumId') and honor.get('state') == 'verified':
            item['melonHonor'] = {**deepcopy(honor), 'fetchState': 'error', 'lastAttemptAt': result['generatedAt']}
        if 'youtubeHistory' not in item and old.get('youtubeHistory'):
            item['youtubeHistory'] = [p for p in old['youtubeHistory']
                if 0 <= (now-clock(p['at'])).total_seconds() <= 30*86400]
    for group in ('covers', 'brands', 'badges'):
        result.setdefault('assets', {})[group] = {
            **deepcopy(previous.get('assets', {}).get(group, {})), **result['assets'].get(group, {})}
    for sid, item in result['tracks'].items():
        old = previous.get('tracks', {}).get(sid, {})
        if 'artwork' not in item and old.get('artwork', {}).get('asset') in result['assets']['covers']:
            item['artwork'] = deepcopy(old['artwork'])
    return result

def hot100_night_pause(chart, observed):
    """Official 01:00-07:00 KST non-publication window, not a new rank observation.
    Accept only a freshly fetched full chart retaining today's midnight/01:00
    published timestamp. Yesterday's data and arbitrary stale times stay errors.
    """
    try:
        local = observed.astimezone(timezone(timedelta(hours=9)))
        at = clock(chart['updatedAt']).astimezone(local.tzinfo)
        checked = clock(chart['checkedAt'])
        return (chart.get('state') == 'ok' and chart.get('source') == HOT100_SOURCE
                and 1 <= local.hour < 7 and at.date() == local.date()
                and at.hour in (0, 1) and at.minute == 0 and at.second == 0
                and at <= local and -600 <= (observed-checked).total_seconds() <= 7200)
    except (KeyError, ValueError, TypeError, AttributeError):
        return False

def health(data):
    missing, warnings, pauses = [], [], []
    observed=clock(data['generatedAt'])
    def current(value):
        try:return -600 <= (observed-clock(value)).total_seconds() <= 7200
        except (ValueError,TypeError,AttributeError):return False
    for song in load_catalog(ROOT)['songs']:
        if song.get('dateKind') == '영상 공개일':
            continue
        row = data['tracks'].get(song['id'], {}).get('melon', {})
        if row.get('state') != 'ok' or row.get('fetchState') == 'error' or not current(row.get('checkedAt')):
            missing.append('melon:'+song['id'])
    for release in releases(ROOT):
        for track in release['tracks']:
            item = data['tracks'].get(track['id'], {}); row = item.get('melon', {})
            if (row.get('albumId') != release['melonAlbumId']
                    or norm(row.get('album')) != norm(release['title'])
                    or norm(row.get('title')) not in {norm(track['title']), *map(norm, track.get('aliases', []))}
                    or norm(row.get('artist')) not in {'이세계아이돌isegyeidol', '이세계아이돌', 'isegyeidol'}):
                missing.append('identity:'+track['id'])
            if not item.get('artwork'):
                missing.append('cover:'+track['id'])
    for kind in sorted(KINDS):
        chart=data.get('domesticCharts', {}).get(kind, {})
        paused = kind == 'melon_hot100' and hot100_night_pause(chart, observed)
        if chart.get('state') != 'ok' or not current(chart.get('checkedAt')) or not (current(chart.get('updatedAt')) or paused):
            missing.append(kind)
        if paused:
            pauses.append({'source': kind, 'state': 'scheduled_night_pause',
                'lastPublishedAt': chart['updatedAt'], 'policySource': HOT100_POLICY})
    # Peak source coverage is optional for publication but must not disappear silently.
    # A missing historical rank is not necessarily a collection failure; an entirely
    # unverified secondary record for a registered Melon track requires investigation.
    from collect_album_peak_fallback import reusable as peak_source_ok
    for song in load_catalog(ROOT)['songs']:
        item = data['tracks'].get(song['id'], {})
        melon = item.get('melon', {})
        if melon.get('state') == 'ok' and not peak_source_ok(item.get('melonPeakFallback'), melon):
            warnings.append('peak-source:'+song['id']+':unverified')
    for name in ('itunes', 'youtube', 'genie', 'bugs'):
        state = data.get('providers', {}).get(name, {}).get('state', 'missing')
        if state != 'ok': warnings.append(name+':'+state)
    return {'state': 'complete' if not missing else 'partial', 'incompleteRequired': sorted(set(missing)),
            'optionalWarnings': warnings, 'scheduledSourcePauses': pauses, 'catalogTracks': len(data['tracks']),
            'releaseTracks': [t['id'] for r in releases(ROOT) for t in r['tracks']],
            'scope': 'registered releases; current verified Melon catalog and observed TOP100/HOT100; not exhaustive historical ranks'}

def collect(previous):
    validate(previous)
    data = api_collect(previous, include_apple_chart=False)
    data = domestic_collect(data, previous, chart_kinds=KINDS)
    data = records_collect(data, previous)
    data = preserve(previous, data)
    data['scope'] = 'production album observations; hourly refresh outside KST 01:00-06:59'
    data.pop('publication', None)
    data.pop('hourlyCoverage', None)
    data['feed'] = 'daily-albums'
    chart = data.get('domesticCharts', {}).get('melon_hot100', {})
    if hot100_night_pause(chart, clock(data['generatedAt'])):
        chart.update(availability='scheduled_night_pause', policySource=HOT100_POLICY,
            availabilityNote='HOT100은 01~07시 새 차트 미제공; 원문 마지막 발표 시각 유지')
    data['collectionHealth'] = health(data)
    validate(data, exact=True, fresh=True)
    return data

def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--check', action='store_true'); args = parser.parse_args()
    path = ROOT/'albums/snapshot.json'
    from album_hourly import allowed
    if not args.check and not allowed():
        print(json.dumps({'status':'paused', 'reason':'KST 01:00-06:59'}))
        return 0
    if args.check:
        data = validate(json.loads(path.read_text()), exact=True, fresh=True)
        report = health(data)
    else:
        data = collect(json.loads(path.read_text()))
        path.write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':'))+'\n')
        report = data['collectionHealth']
    (ROOT/'albums-health.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(report, ensure_ascii=False))
    # Publication is separately blocked unless mandatory source health is complete.
    return int(args.check and report['state'] != 'complete')

if __name__ == '__main__':
    raise SystemExit(main())