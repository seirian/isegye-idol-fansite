"""Finite, user-requested REBELS history repair. No third-party network calls.
Only verified factual observations from the pinned 2026-11-16 review are merged.
Never replace existing valid observations or modify other songs/source clocks.
"""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
import argparse
import hashlib
import json
import os
import re

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'albums/backfills/rebels-20261116.json'
SID, TRACK, ALBUM = 'rebels', '603813508', '15120216'
KST = timezone(timedelta(hours=9))
START = datetime(2026, 11, 9, 18, tzinfo=KST)
END = datetime(2026, 11, 16, 9, tzinfo=KST)
KINDS = ('melon_top100', 'melon_hot100')
SLUGS = {'melon_top100': 'top100', 'melon_hot100': 'hot100-d100'}
BASE = 'https://xn--o39an51b2re.com'


def clock(value):
    stamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if stamp.tzinfo is None:
        raise ValueError('Timezone is required')
    return stamp.astimezone(timezone.utc)


def valid(point):
    try:
        stamp = clock(point['at'])
        rank = point.get('rank')
        return (point.get('trackId') == TRACK and not (stamp.minute or stamp.second or stamp.microsecond)
                and ((point.get('status') == 'ranked' and type(rank) is int and 1 <= rank <= 100)
                     or (point.get('status') == 'out' and rank is None)))
    except (KeyError, TypeError, ValueError, AttributeError):
        return False


def load_dataset(path=DATA):
    raw = path.read_bytes()
    data = json.loads(raw)
    if (data.get('schemaVersion') != 1 or data.get('trackId') != TRACK or data.get('albumId') != ALBUM
            or data.get('releaseAt') != START.isoformat() or data.get('cutoffAt') != END.isoformat()
            or set(data.get('charts', {})) != set(KINDS)):
        raise ValueError('Unapproved backfill identity/window')
    for kind, chart in data['charts'].items():
        expected = BASE + '/chart/melon/' + SLUGS[kind]
        if chart.get('source') != expected + '/trend/ranking/' + TRACK:
            raise ValueError('Unapproved chart source')
        if not re.fullmatch('[0-9a-f]{64}', str(chart.get('responseSha256', ''))):
            raise ValueError('Missing evidence digest')
        seen = set()
        for offset, rank in chart['ranked']:
            if type(offset) is not int or not 0 <= offset <= 159 or offset in seen or type(rank) is not int or not 1 <= rank <= 100:
                raise ValueError('Invalid or duplicate rank')
            seen.add(offset)
        for row in chart.get('out', []):
            offset = row['offset']
            if type(offset) is not int or not 0 <= offset <= 159 or offset in seen:
                raise ValueError('Invalid or duplicate chart-out')
            stamp = START + timedelta(hours=offset)
            url = expected + '/' + stamp.strftime('%Y%m%d') + '/' + str(stamp.hour)
            if (row.get('source') != url or row.get('verifiedFullChartSize') != 100
                    or not re.fullmatch('[0-9a-f]{64}', str(row.get('responseSha256', '')))):
                raise ValueError('Chart-out requires a complete timestamp-matching source chart')
            seen.add(offset)
    return data, hashlib.sha256(raw).hexdigest()


def observations(dataset, kind):
    rows = [(offset, rank, 'ranked') for offset, rank in dataset['charts'][kind]['ranked']]
    rows += [(row['offset'], None, 'out') for row in dataset['charts'][kind].get('out', [])]
    return [{'at': (START + timedelta(hours=offset)).astimezone(timezone.utc).isoformat(),
             'trackId': TRACK, 'rank': rank, 'status': status} for offset, rank, status in sorted(rows)]


def coverage(item, kind):
    points = {clock(p['at']): p for p in item.get('charts', {}).get(kind, []) if valid(p)}
    all_slots = [START + timedelta(hours=i) for i in range(160)]
    present = [t for t in all_slots if t in points]
    missing = [t for t in all_slots if t not in points]
    return {'totalHourlySlots': 160, 'verifiedSlots': len(present),
            'ranked': sum(points[t]['status'] == 'ranked' for t in present),
            'verifiedOut': sum(points[t]['status'] == 'out' for t in present),
            'missingSlotsKst': [t.isoformat() for t in missing],
            'collectorPausedMissing': sum(1 <= t.hour < 7 for t in missing)}


def apply(data, *, dataset=None, digest=None, at=None):
    if dataset is None:
        dataset, digest = load_dataset()
    at = at or datetime.now(timezone.utc)
    item = data.get('tracks', {}).get(SID, {})
    identity = item.get('melon', {})
    if identity.get('trackId') != TRACK or identity.get('albumId') != ALBUM:
        raise ValueError('Live REBELS identity mismatch')
    if at < END:
        raise ValueError('Backfill cutoff is in the future')
    before = deepcopy(data)
    report = {'trackId': TRACK, 'albumId': ALBUM, 'fromKst': START.isoformat(), 'toKst': END.isoformat(),
              'datasetSha256': digest, 'charts': {}, 'conflicts': []}
    sources = {}
    for kind in KINDS:
        original = item.get('charts', {}).get(kind, [])
        indexed = {}
        for p in original:
            key = clock(p['at'])
            if key in indexed:
                raise ValueError('Duplicate existing observation time')
            indexed[key] = deepcopy(p)
        added = []
        matched = []
        for p in observations(dataset, kind):
            key = clock(p['at'])
            if not at - timedelta(days=30) <= key <= at:
                continue
            old = indexed.get(key)
            if old is not None and valid(old):
                if any(old.get(k) != p[k] for k in ('rank', 'status', 'trackId')):
                    report['conflicts'].append({'chart': kind, 'at': p['at'], 'existing': old, 'reference': p})
                    continue
            else:
                indexed[key] = p
                added.append(p['at'])
            matched.append(p['at'])
        if added:
            rows = sorted(indexed.values(), key=lambda p: clock(p['at']))
            item.setdefault('charts', {})[kind] = rows
            item['melon'][kind.replace('melon_', '') + 'History'] = deepcopy(rows)
        if matched:
            sources[kind] = {'source': dataset['charts'][kind]['source'], 'at': matched}
        report['charts'][kind] = {'before': coverage(before['tracks'][SID], kind),
                                 'after': coverage(item, kind), 'added': len(added), 'addedAt': added}
    if sources:
        item['melonHistoricalBackfill'] = {'schemaVersion': 1, 'trackId': TRACK, 'albumId': ALBUM,
            'sourceType': 'guyso_public_historical', 'datasetSha256': digest,
            'from': START.isoformat(), 'through': END.isoformat(), 'charts': sources}
    # The proof of scope is computed, not inferred from which code paths ran.
    isolated = deepcopy(data)
    isolated['tracks'][SID] = deepcopy(before['tracks'][SID])
    if isolated != before:
        raise ValueError('Backfill touched another song or a global field')
    permitted = deepcopy(item)
    old = before['tracks'][SID]
    for kind in KINDS:
        if 'charts' in permitted:
            if kind in old.get('charts', {}): permitted['charts'][kind] = deepcopy(old['charts'][kind])
            else: permitted['charts'].pop(kind, None)
        key = kind.replace('melon_', '') + 'History'
        if key in old.get('melon', {}): permitted['melon'][key] = deepcopy(old['melon'][key])
        else: permitted['melon'].pop(key, None)
    if 'charts' not in old and not permitted.get('charts'):
        permitted.pop('charts', None)
    if 'melonHistoricalBackfill' in old: permitted['melonHistoricalBackfill'] = deepcopy(old['melonHistoricalBackfill'])
    else: permitted.pop('melonHistoricalBackfill', None)
    if permitted != old:
        raise ValueError('Backfill changed unrelated REBELS fields')
    report.update(otherTracksUnchanged=True, sourceClocksUnchanged=True,
                  changed=data != before, addedPoints=sum(v['added'] for v in report['charts'].values()))
    return report


def patch_remote(remote):
    """Historical-only atomic CAS, without re-stamping collection/publication clocks."""
    import album_runtime as runtime
    d = runtime.d
    router, release, active_path = runtime.active(remote)
    app = remote.read(active_path+'/src/app.js') or b''
    d.require(b'albumHistoricalReference' in app and '과거 기록 출처: 가이섬'.encode() in app,
              'Deploy historical source attribution before data publication')
    runtime.owned(remote)
    d.require(remote.info(runtime.path('.lock')) is None, 'Another album operation is active')
    lock = os.urandom(24)
    remote.new(runtime.path('.lock'), lock)
    remote.s.chmod(runtime.path('.lock'), 0o600)
    try:
        raw = remote.read(runtime.path('current.json'))
        d.require(raw is not None, 'An existing production feed is required')
        data = runtime.decode(raw)
        d.require(data.get('feed') == 'daily-albums', 'Wrong live feed')
        report = apply(data)
        d.require(not report['conflicts'], 'Conflicting source observations; no publication')
        from daily_albums import validate
        validate(data, exact=True)
        candidate = (json.dumps(data, ensure_ascii=False, separators=(',', ':')) + '\n').encode()
        (ROOT/'rebels-backfill-before.json').write_bytes(raw)
        (ROOT/'rebels-backfill-after.json').write_bytes(candidate)
        d.require(remote.read(d.ROOT+'/.htaccess') == router and remote.info(d.ROOT+'/.deploy-lock') is None,
                  'Release changed during historical repair')
        d.require(remote.read(runtime.path('current.json')) == raw, 'Feed changed; refusing stale overwrite')
        if report['changed']:
            remote.replace(runtime.path('previous.json'), raw, remote.read(runtime.path('previous.json')))
            remote.s.chmod(runtime.path('previous.json'), 0o600)
            remote.replace(runtime.path('current.json'), candidate, raw)
            remote.s.chmod(runtime.path('current.json'), 0o600)
        else:
            candidate = raw
        try:
            d.require(remote.read(runtime.path('current.json')) == candidate, 'Historical repair readback failed')
            d.require(remote.read(d.ROOT+'/.htaccess') == router, 'Router changed after repair')
        except Exception:
            if report['changed'] and remote.read(runtime.path('current.json')) == candidate:
                remote.replace(runtime.path('current.json'), raw, candidate)
            raise
        report.update(status='published' if report['changed'] else 'already_applied', verifiedReadback=True,
                      release=release, beforeSha256=d.digest(raw), afterSha256=d.digest(candidate),
                      collectionGeneratedAt=data['generatedAt'], checkedAt=datetime.now(timezone.utc).isoformat(),
                      routingUnchanged=True, accountStoreReadOrWritten=False)
        return report
    finally:
        if remote.read(runtime.path('.lock')) == lock:
            remote.remove_own(runtime.path('.lock'), lock)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['audit', 'publish'])
    parser.add_argument('--snapshot', type=Path, default=ROOT/'albums/snapshot.json')
    args = parser.parse_args()
    if args.action == 'audit':
        data = json.loads(args.snapshot.read_text())
        report = apply(data)
        (ROOT/'rebels-backfill-candidate.json').write_text(json.dumps(data, ensure_ascii=False))
    else:
        from album_runtime import connection
        from album_hourly import allowed, night_deadline
        if not allowed(): raise RuntimeError('Existing night pause policy respected')
        password = os.environ.pop('ISEGYE_SFTP_PASSWORD', '')
        with night_deadline(), connection(password) as remote:
            report = patch_remote(remote)
    (ROOT/'rebels-backfill-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(report, ensure_ascii=False))
    return int(bool(report['conflicts']))


if __name__ == '__main__':
    raise SystemExit(main())
