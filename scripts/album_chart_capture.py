#!/usr/bin/env python3
"""Fast, credential-free hourly Melon evidence capture; never writes production.

The complete 100-rank table is retained only in a private GitHub Actions artifact.
Its source clock and checksum allow the normal album job to recover real missing
observations later, even if the publication queue delays that job.
"""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import os
import socket
import ssl
import time
import urllib.error

from album_hourly import KINDS, ROOT, allowed, clock, slot
from collect_album_domestic import CHARTS, chart_rows, fetch

REPOSITORY = 'seirian/isegye-idol-fansite'
WORKFLOW = 'melon-chart-capture.yml'
OUTPUT = ROOT / 'melon-chart-capture.json'
SOURCE_TYPE = 'melon_public_full_chart'


def failure_class(exc):
    """Stable diagnostics without source bodies, request URLs or credentials."""
    if isinstance(exc, urllib.error.HTTPError):
        return 'http_status_' + str(exc.code)
    if isinstance(exc, urllib.error.URLError):
        reason = exc.reason
        if isinstance(reason, socket.gaierror):
            return 'dns'
        if isinstance(reason, (socket.timeout, TimeoutError)):
            return 'timeout'
        if isinstance(reason, ssl.SSLError):
            return 'tls'
        return 'network'
    if isinstance(exc, (socket.timeout, TimeoutError)):
        return 'timeout'
    if isinstance(exc, ValueError):
        return 'source_validation'
    return type(exc).__name__


def capture(at=None, reader=None, run_id=0, attempt=1):
    at = at or datetime.now(timezone.utc)
    if at.tzinfo is None:
        raise ValueError('An aware clock is required')
    at = at.astimezone(timezone.utc)
    supplied_reader = reader is not None
    reader = reader or (lambda url: fetch(url, binary=True))
    result = {'schemaVersion': 1, 'repository': REPOSITORY, 'workflow': WORKFLOW,
              'runId': run_id, 'runAttempt': attempt, 'checkedAt': at.isoformat(),
              'sourceType': SOURCE_TYPE, 'charts': {}, 'errors': {}}
    if not allowed(at):
        result['status'] = 'scheduled_night_pause'
        return result
    for kind in KINDS:
        _, url, limit = CHARTS[kind]
        try:
            try:
                raw = reader(url)
            except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
                # One bounded transport retry only; never retry HTTP rejection,
                # identity/schema failures or a caller-provided reader.
                if supplied_reader or isinstance(exc, urllib.error.HTTPError):
                    raise
                time.sleep(2)
                raw = reader(url)
            if not isinstance(raw, bytes) or not 0 < len(raw) <= 4_000_000:
                raise ValueError('Invalid chart response bytes')
            ranks, source_at = chart_rows(raw.decode('utf-8', errors='replace'), 'melon', at, limit)
            # Stale, delayed or mixed hours must not be relabeled as the current hour.
            if clock(source_at) != slot(at):
                raise ValueError('Source clock is not the due hour')
            rows = [[track, rank] for track, rank in sorted(ranks.items(), key=lambda pair: pair[1])]
            if (len(rows) != 100 or set(r for _, r in rows) != set(range(1, 101))
                    or len({song for song, _ in rows}) != 100):
                raise ValueError('Incomplete original chart')
            result['charts'][kind] = {'source': url, 'sourceAt': source_at,
                                       'responseSha256': hashlib.sha256(raw).hexdigest(), 'rows': rows}
        except Exception as exc:
            result['errors'][kind] = type(exc).__name__
            result.setdefault('errorClasses', {})[kind] = failure_class(exc)
    result['status'] = ('complete' if set(result['charts']) == set(KINDS) else
                        'partial' if result['charts'] else 'failed')
    return result


def main():
    if (os.getenv('GITHUB_REPOSITORY') != REPOSITORY or os.getenv('GITHUB_REF') != 'refs/heads/main'
            or not os.getenv('GITHUB_RUN_ID', '').isdigit()
            or not os.getenv('GITHUB_RUN_ATTEMPT', '').isdigit()):
        raise ValueError('Main-only capture')
    result = capture(run_id=int(os.environ['GITHUB_RUN_ID']),
                     attempt=int(os.environ['GITHUB_RUN_ATTEMPT']))
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, separators=(',', ':')) + '\n')
    print(json.dumps({'status': result['status'], 'checkedAt': result['checkedAt'],
                      'sourceAt': {k: v['sourceAt'] for k, v in result['charts'].items()},
                      'errors': result['errors'], 'errorClasses': result.get('errorClasses', {})}, ensure_ascii=False))
    return 0 if result['status'] in ('complete', 'scheduled_night_pause') else 1


if __name__ == '__main__':
    raise SystemExit(main())
