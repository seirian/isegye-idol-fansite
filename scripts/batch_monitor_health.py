"""Separate inspection health from batch outcomes and preserve verified history.

This module never performs I/O. Retained history is a small allow-listed summary,
not a replacement for the current slot and never raw publication/account data.
"""
from datetime import datetime, timedelta, timezone
import re


def clock(value):
    if not isinstance(value, str):
        raise ValueError('Timestamp required')
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise ValueError('Timezone required')
    return result.astimezone(timezone.utc)


def inspection_health(doc):
    rows = doc['batches']
    failed = sum(bool(r.get('inspectionError')) or not r.get('listingComplete', False) for r in rows)
    missing = sum(r.get('dataState') == 'unknown' for r in rows)
    # An unknown publication outcome is not itself a failed inspection: the verified
    # read may be complete while a new release is still awaiting publication.
    # Count unknown outcomes separately; never treat them as verified successes.
    state = 'failed' if failed == len(rows) else 'degraded' if failed else 'ok'
    # A batch failure is an observed outcome, NOT an inspector failure.
    return {'state': state, 'checkedAt': doc['checkedAt'], 'total': len(rows),
            'inspected': len(rows)-failed, 'failed': failed, 'unresolved': missing,
            'code': 'all_inspections_failed' if state == 'failed' else
                    'partial_inspection' if state == 'degraded' else 'inspection_complete'}


def verified_summary(row, at):
    """Only a verified healthy outcome can establish a historical success."""
    if row.get('dataState') != 'healthy' or not row.get('listingComplete') or row.get('inspectionError'):
        return None
    evidence = row.get('evidence') or {}
    run = row.get('evidenceRun') or {}
    return clean_summary({'observedAt': row.get('checkedAt'), 'dueAt': row.get('dueAt'),
                          'readbackAt': row.get('lastVerifiedAt') or evidence.get('readbackAt'),
                          'runId': run.get('id'), 'attempt': run.get('attempt'),
                          'commit': run.get('commit'), 'kind': 'inspection' if row['key']=='watchdog' else 'observation' if row['key']=='capture' else 'publication'}, at)


def clean_summary(item, at):
    if not isinstance(item, dict):
        return None
    try:
        observed = clock(item.get('observedAt'))
        if not at-timedelta(days=90) <= observed <= at:
            return None
        result = {'observedAt': observed.isoformat(), 'kind': item.get('kind')}
        if result['kind'] not in ('publication', 'inspection', 'observation'):
            return None
        for field in ('dueAt', 'readbackAt'):
            value = item.get(field)
            result[field] = clock(value).isoformat() if value is not None else None
            if value is not None and clock(value) > observed+timedelta(minutes=2):
                return None
        for field in ('runId', 'attempt'):
            value = item.get(field)
            result[field] = value if type(value) is int and value > 0 else None
        commit = item.get('commit')
        result['commit'] = commit if isinstance(commit, str) and re.fullmatch('[0-9a-f]{40}', commit) else None
        return result
    except (ValueError, TypeError, OverflowError):
        return None


def preserve_verified(previous, current):
    """Keep historical evidence while leaving the new outcome/errors untouched."""
    at = clock(current['checkedAt'])
    old_rows = previous.get('batches', []) if isinstance(previous, dict) and previous.get('schemaVersion')==1 else []
    old = {r.get('key'): r for r in old_rows if isinstance(r, dict)} if isinstance(old_rows, list) else {}
    for row in current['batches']:
        prior = old.get(row['key'], {})
        candidates = [verified_summary(row, at), clean_summary(prior.get('lastVerifiedResult'), at),
                      verified_summary(prior, at) if prior.get('key') else None]
        candidates = [c for c in candidates if c]
        row['lastVerifiedResult'] = max(candidates, key=lambda c: clock(c['observedAt'])) if candidates else None
    health = current.get('collectorHealth') or inspection_health(current)
    current['collectorHealth'] = health
    last = current['checkedAt'] if health['state']=='ok' else None
    if last is None and isinstance(previous, dict):
        candidate = previous.get('lastCompleteInspectionAt')
        if not candidate and (previous.get('collectorHealth') or {}).get('state')=='ok':
            candidate = previous.get('checkedAt')
        try:
            if at-timedelta(days=90) <= clock(candidate) <= at:
                last = clock(candidate).isoformat()
        except (ValueError, TypeError):
            pass
    current['lastCompleteInspectionAt'] = last
    return current
