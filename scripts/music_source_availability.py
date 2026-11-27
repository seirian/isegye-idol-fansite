"""Bind optional backup unavailability to a fresh, exact, same-run source audit.

This is a narrow publication policy, not a network-error bypass. Only the
already-reviewed registry below may quarantine a fan backup whose metadata
endpoint returned 404, or whose verified uploader metadata was followed by a
thumbnail 404. Every other failed/unknown inspection remains blocking.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = 'seirian/isegye-idol-fansite'
# Exact config + song/video/kind/uploader mappings reviewed before this change.
# A new mapping requires a separate source review; 404 never approves it.
REVIEWED_SELECTION_SHA256 = '5663e8f2d1d4a4af38d3beb0cd77ec44e7a3239c630ec78da497e6ce3a53e2aa'
POLICY = 'reviewed-fan-backup-availability-404-v2'
MAX_AGE = timedelta(hours=24)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()


def digest(value):
    return hashlib.sha256(value).hexdigest()


def selection_digest(config, rows):
    return digest(canonical({'config': config, 'rows': rows}))


def context():
    return {'repository': os.getenv('GITHUB_REPOSITORY', 'local'),
            'commit': os.getenv('GITHUB_SHA', 'local'),
            'runId': os.getenv('GITHUB_RUN_ID', 'local'),
            'runAttempt': os.getenv('GITHUB_RUN_ATTEMPT', 'local')}


def publication_context():
    value = context()
    origin = os.getenv('MUSIC_SOURCE_AUDIT_ORIGIN_ATTEMPT')
    if origin is not None:
        current = value['runAttempt']
        if (not re.fullmatch(r'[1-9][0-9]*', origin)
                or not re.fullmatch(r'[1-9][0-9]*', current) or int(origin) > int(current)):
            raise ValueError('Invalid source audit origin attempt')
        # The prepare/deploy artifact manifest must bind this value. This only
        # allows a trusted same-run prepare result during a later stage retry.
        value['runAttempt'] = origin
    return value


def clock(value):
    at = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if at.tzinfo is None:
        raise ValueError('Source audit requires an explicit timezone')
    return at


def classify(result, row, config, allow_unavailable=False):
    """Recompute the decision from evidence; do not trust reported success/counts."""
    if (result.get('videoId') != row['videoId'] or result.get('kind') != row['kind']
            or result.get('channelKey') != row['channelKey']):
        raise ValueError('Source audit selection identity mismatch')
    expected = config['channels'][row['channelKey']]['url'].rstrip('/').lower()
    author_url = result.get('authorUrl')
    identity_verified = (result.get('metadataStatus') == 200
                         and isinstance(author_url, str)
                         and author_url.rstrip('/').lower() == expected)
    if (result.get('ok') is True and result.get('stage') == 'complete'
            and identity_verified and not result.get('error')
            and type(result.get('thumbnailWidth')) is int and result['thumbnailWidth'] >= 320
            and type(result.get('thumbnailHeight')) is int and result['thumbnailHeight'] >= 180):
        return 'available'
    if allow_unavailable and row['kind'] == 'fan_backup' and result.get('ok') is False:
        metadata_missing = (result.get('stage') == 'metadata' and result.get('metadataStatus') == 404
                            and result.get('reasonCode') == 'metadata_http_404')
        verified_thumbnail_missing = (identity_verified and result.get('stage') == 'thumbnail'
                                      and result.get('thumbnailStatus') == 404
                                      and result.get('reasonCode') == 'thumbnail_http_404')
        if metadata_missing or verified_thumbnail_missing:
            return 'unavailable'
    return 'blocked'


def summarize(results, config, rows, allow_unavailable=False):
    selected = {sid: row for sid, row in rows.items() if row['videoId']}
    if len(results) != len(selected) or {r.get('songId') for r in results} != set(selected):
        raise ValueError('Source audit must inspect every selected song exactly once')
    if allow_unavailable and selection_digest(config, rows) != REVIEWED_SELECTION_SHA256:
        raise ValueError('Unreviewed music selection cannot use the availability policy')
    states = {r['songId']: classify(r, selected[r['songId']], config, allow_unavailable)
              for r in results}
    counts = {state: sum(value == state for value in states.values())
              for state in ('available', 'unavailable', 'blocked')}
    return states, counts


def availability_candidate(report, report_bytes, config, rows):
    states, counts = summarize(report['results'], config, rows, True)
    results = {result['songId']: result for result in report['results']}
    return {'schemaVersion': 1, 'policy': POLICY, 'checkedAt': report['checkedAt'],
            'provenance': report['provenance'], 'selectionSha256': selection_digest(config, rows),
            'sourceAuditSha256': digest(report_bytes), 'selected': len(states),
            'available': counts['available'], 'unavailable': counts['unavailable'],
            'blocked': counts['blocked'], 'unresolved': sorted(sid for sid, r in rows.items() if not r['videoId']),
            'state': 'blocked' if counts['blocked'] else 'partial' if counts['unavailable'] else 'complete',
            'deploymentAllowed': counts['blocked'] == 0,
            'unavailableSelections': [{'songId': sid, **rows[sid],
                                       'stage': results[sid]['stage'],
                                       'reasonCode': results[sid]['reasonCode']}
                                      for sid in sorted(states) if states[sid] == 'unavailable']}


def validate_candidate(report, report_bytes, candidate, config, rows, expected_context=None, now=None):
    expected_context = context() if expected_context is None else expected_context
    now = now or datetime.now(timezone.utc)
    if json.loads(report_bytes) != report:
        raise ValueError('Source audit bytes/evidence mismatch')
    if (expected_context.get('repository') != REPOSITORY
            or not re.fullmatch(r'[0-9a-f]{40}', expected_context.get('commit', ''))
            or not re.fullmatch(r'[1-9][0-9]*', expected_context.get('runId', ''))
            or not re.fullmatch(r'[1-9][0-9]*', expected_context.get('runAttempt', ''))):
        raise ValueError('Availability publication requires exact workflow provenance')
    if report.get('provenance') != expected_context or report.get('commit') != expected_context['commit']:
        raise ValueError('Source audit run/attempt/commit mismatch')
    age = now - clock(report['checkedAt'])
    if age < -timedelta(minutes=2) or age > MAX_AGE:
        raise ValueError('Source audit is stale or from the future')
    if (report.get('schemaVersion') != 2 or report.get('policy') != POLICY
            or report.get('selectionSha256') != selection_digest(config, rows)):
        raise ValueError('Source audit policy or registry digest mismatch')
    expected = availability_candidate(report, report_bytes, config, rows)
    if candidate != expected:
        raise ValueError('Availability candidate or audit digest mismatch')
    if (candidate['deploymentAllowed'] is not True or report.get('deploymentAllowed') is not True
            or report.get('fullPlaybackVerified') is not False
            or report.get('catalogue') != len(rows)
            or report.get('passed') != candidate['available']
            or report.get('failed') != candidate['unavailable']
            or report.get('selected') != candidate['selected']
            or report.get('unavailable') != candidate['unavailable']
            or report.get('blockingFailures') != 0
            or report.get('state') != candidate['state']
            or sorted(report.get('unresolved', [])) != candidate['unresolved']):
        raise ValueError('Incomplete or inconsistent source audit cannot authorize publication')
    states, _ = summarize(report['results'], config, rows, True)
    sources = {}
    for result in report['results']:
        state = states[result['songId']]
        if result.get('availability') != state:
            raise ValueError('Source result availability mismatch')
        source = sources.setdefault(result['channelKey'], {'available': 0, 'unavailable': 0, 'blocked': 0})
        source[state] += 1
    if report.get('sourceStates') != sources:
        raise ValueError('Source failure counts mismatch')
    return candidate


def load_candidate(config, rows):
    """An explicit build gate opts in; ordinary collectors do not consume stale files."""
    if os.getenv('MUSIC_SOURCE_AUDIT_REQUIRED') != 'true':
        return None
    relative = os.getenv('MUSIC_SOURCE_AUDIT_PATH', 'test-results/music-sources/source-audit.json')
    source = ROOT / relative
    path = source.resolve()
    if source.is_symlink():
        raise ValueError('Source audit symlink refused')
    if not path.is_relative_to(ROOT) or path.name != 'source-audit.json':
        raise ValueError('Unexpected source audit path')
    availability = path.with_name('source-availability.json')
    for file in (path, availability):
        if not file.is_file() or file.is_symlink() or file.stat().st_size > 2_000_000:
            raise ValueError('Missing or unsafe source audit candidate')
    raw = path.read_bytes()
    report = json.loads(raw)
    candidate = json.loads(availability.read_bytes())
    return validate_candidate(report, raw, candidate, config, rows, publication_context())


def public_evidence(candidate):
    return {key: candidate[key] for key in (
        'schemaVersion', 'policy', 'checkedAt', 'provenance', 'selectionSha256',
        'sourceAuditSha256', 'selected', 'available', 'unavailable', 'blocked',
        'unresolved', 'state', 'deploymentAllowed')}
