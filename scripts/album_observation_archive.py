"""Recover real chart observations from this repository's trusted Actions artifacts.

Reads snapshots only, never extracts/executes files or imports archived code. Metadata,
images and current source clocks are not replaced. Credentials are only sent to the
fixed GitHub API; the signed artifact download is fetched without authorization.
"""
from copy import deepcopy
from datetime import timedelta
from io import BytesIO
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request, build_opener, HTTPRedirectHandler
import hashlib
import json
import os
import re
import time
import zipfile

from album_hourly import ROOT, KINDS, now, clock, allowed
from daily_albums import validate, MAX_BYTES

REPOSITORY = 'seirian/isegye-idol-fansite'
API = 'https://api.github.com/repos/'+REPOSITORY
SOURCES = {'melon_top100': 'https://www.melon.com/chart/index.htm',
           'melon_hot100': 'https://www.melon.com/chart/hot100/index.htm?chartType=D100'}

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args):
        return None

def request(url, token='', binary=False):
    headers = {'User-Agent': 'IsegyeAlbumRecovery/1.0', 'Accept': 'application/vnd.github+json'}
    if token:
        if not url.startswith(API+'/'):
            raise ValueError('Unapproved authenticated URL')
        headers['Authorization'] = 'Bearer '+token
    response = None
    try:
        response = build_opener(NoRedirect).open(Request(url, headers=headers), timeout=30)
    except HTTPError as exc:
        if binary and exc.code == 302:
            location = exc.headers.get('Location', '')
            host = urlparse(location)
            exc.close()
            if (host.scheme != 'https' or host.username or host.password
                    or not (host.hostname or '').endswith(('.blob.core.windows.net', '.actions.githubusercontent.com'))):
                raise ValueError('Unapproved artifact redirect') from None
            return request(location, binary=True)
        raise RuntimeError('GitHub artifact HTTP '+str(exc.code)) from None
    with response:
        raw = response.read(8_000_001 if binary else 2_000_001)
    if len(raw) > (8_000_000 if binary else 2_000_000):
        raise ValueError('Oversized archive response')
    return raw if binary else json.loads(raw)

def read_snapshot(raw, digest):
    if digest != 'sha256:'+hashlib.sha256(raw).hexdigest():
        raise ValueError('Artifact digest mismatch')
    with zipfile.ZipFile(BytesIO(raw)) as archive:
        rows = [i for i in archive.infolist() if i.filename == 'albums/snapshot.json']
        if not rows:
            gates = [i for i in archive.infolist() if i.filename == 'albums-gate.json']
            if len(gates) == 1 and gates[0].file_size <= 4096:
                gate = json.loads(archive.read(gates[0]))
                if gate.get('status') == 'paused' and gate.get('allowed') is False:
                    return None
        if len(rows) != 1 or rows[0].file_size > MAX_BYTES:
            raise ValueError('Missing, duplicate or oversized snapshot')
        data = validate(json.loads(archive.read(rows[0])))
        if data.get('feed') != 'daily-albums':
            raise ValueError('Unapproved feed')
        return data

def recover_points(current, archived, at=None):
    """Merge only identity-matching, ranked/out points; existing evidence wins conflicts."""
    at = at or now()
    generated = clock(archived['generatedAt'])
    if not timedelta(0) <= at-generated <= timedelta(days=2):
        raise ValueError('Archive outside recovery window')
    added = conflicts = 0
    for sid, item in current['tracks'].items():
        old = archived['tracks'].get(sid, {})
        identity = item.get('melon', {})
        reference = old.get('melon', {})
        if (not identity.get('trackId') or identity.get('trackId') != reference.get('trackId')
                or identity.get('albumId') != reference.get('albumId')):
            continue
        for kind in KINDS:
            source = archived.get('domesticCharts', {}).get(kind, {})
            if source.get('source') != SOURCES[kind]:
                continue
            target = {clock(p['at']).isoformat(): deepcopy(p) for p in item.get('charts', {}).get(kind, [])}
            for point in old.get('charts', {}).get(kind, []):
                try:
                    stamp = clock(point['at'])
                    rank = point.get('rank')
                    valid = ((point.get('status') == 'ranked' and type(rank) is int and 1 <= rank <= 100)
                             or (point.get('status') == 'out' and rank is None))
                    if (not valid or point.get('trackId') != identity['trackId'] or stamp > generated+timedelta(minutes=10)
                            or stamp.minute or stamp.second or not timedelta(0) <= at-stamp <= timedelta(days=30)):
                        continue
                    key = stamp.isoformat()
                    normalized = {k: point.get(k) for k in ('at','trackId','rank','status')}
                    normalized['at'] = key
                    if key in target and target[key].get('status') in ('ranked','out'):
                        if any(target[key].get(k) != normalized[k] for k in ('rank','status','trackId')):
                            conflicts += 1
                        continue
                    target[key] = normalized
                    added += 1
                except (TypeError, ValueError, KeyError, AttributeError):
                    continue
            if target:
                rows = sorted(target.values(), key=lambda p: clock(p['at']))[-1440:]
                item.setdefault('charts', {})[kind] = rows
                item['melon'][kind.replace('melon_', '')+'History'] = deepcopy(rows)
    return added, conflicts

def main():
    report = {'status':'no_archives', 'addedPoints':0, 'conflicts':0, 'artifacts':[], 'skippedArtifacts':[], 'errors':[]}
    token = os.environ.pop('GH_TOKEN', '')
    if not allowed():
        report['status'] = 'paused'
    else:
        try:
            if not token or os.getenv('GITHUB_REPOSITORY') != REPOSITORY or os.getenv('GITHUB_REF') != 'refs/heads/main':
                raise ValueError('Main-only artifact recovery')
            current = validate(json.loads((ROOT/'albums/snapshot.json').read_text()))
            listing = request(API+'/actions/artifacts?per_page=100', token)
            selected = []
            for item in listing.get('artifacts', []):
                match = re.fullmatch(r'(?:album-observation|daily-albums)-(\d+)-(\d+)', item.get('name',''))
                if (not match or item.get('expired') or not 0 < item.get('size_in_bytes', 0) <= 8_000_000
                        or not timedelta(0) <= now()-clock(item['created_at']) <= timedelta(days=2)):
                    continue
                selected.append((item, int(match[1])))
            # Newest evidence is preferred; current published evidence always wins.
            deadline = time.monotonic()+120
            for item, run_id in selected[:40]:
                if not allowed() or time.monotonic() > deadline:
                    break
                try:
                    run = request(API+'/actions/runs/'+str(run_id), token)
                    provenance = item.get('workflow_run', {})
                    if (run.get('head_branch') != 'main' or run.get('path') != '.github/workflows/albums-daily.yml'
                            or run.get('event') not in ('schedule','workflow_dispatch','workflow_run','push')
                            or run.get('repository', {}).get('full_name') != REPOSITORY
                            or provenance.get('head_sha') != run.get('head_sha') or provenance.get('id') != run_id
                            or not re.fullmatch(r'sha256:[0-9a-f]{64}', item.get('digest',''))):
                        raise ValueError('Untrusted artifact provenance')
                    raw = request(API+'/actions/artifacts/'+str(int(item['id']))+'/zip', token, binary=True)
                    candidate = read_snapshot(raw, item['digest'])
                    if candidate is None:
                        report['skippedArtifacts'].append({'id': item['id'], 'reason': 'scheduled_night_pause'})
                        continue
                    count, conflicts = recover_points(current, candidate)
                    report['artifacts'].append({'id': item['id'], 'runId': run_id, 'digest': item['digest'], 'addedPoints': count})
                    report['addedPoints'] += count
                    report['conflicts'] += conflicts
                except Exception as exc:
                    report['errors'].append({'artifactId': item['id'], 'error': type(exc).__name__})
            if report['addedPoints']:
                validate(current)
                (ROOT/'albums/snapshot.json').write_text(json.dumps(current, ensure_ascii=False, separators=(',', ':'))+'\n')
            report['status'] = 'recovered' if report['addedPoints'] else 'no_new_observations'
        except Exception as exc:
            report['status'] = 'unavailable'
            report['errors'].append({'error': type(exc).__name__})
    token = None
    (ROOT/'albums-recovery.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(report, ensure_ascii=False))
    if report['errors']:
        print('::warning::Some archived chart observations could not be recovered; current collection is still required.')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
