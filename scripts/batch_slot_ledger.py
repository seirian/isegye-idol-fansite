"""Bounded expected-slot ledger, separate from workflow execution counts.

Missing evidence remains unverified. An expected slot is never filled with an
invented chart observation, and recovery cannot erase its original failure.
The trusted private snapshot is the persistence boundary; this module has no I/O.
"""
from datetime import datetime, timedelta, timezone
import base64
import gzip
import hashlib
import json
import re
import zlib

KST = timezone(timedelta(hours=9))
UTC = timezone.utc
STATES = {'unverified', 'awaiting', 'running', 'failed', 'partial', 'verified', 'paused', 'cancelled'}
KINDS = {'albums', 'capture', 'music', 'schedule', 'catalog', 'playground', 'history'}
MAX_ENTRIES = 5000
MAX_UNCOMPRESSED_BYTES = 12_000_000
MAX_ENCODED_BYTES = 3_000_000
METADATA = ('coverageStartAt', 'coverageEndAt', 'checkedAt', 'evidenceScope',
            'unobservedIsFailure', 'retentionDays')


def unpack_slot_ledger(value):
    """Read v1 or bounded v2; never truncate evidence to make it fit."""
    if value is None:
        return None
    if not isinstance(value, dict) or value.get('schemaVersion') not in (1, 2):
        raise ValueError('Invalid slot ledger format')
    if value['schemaVersion'] == 1:
        if (not isinstance(value.get('entries'), list) or len(value['entries']) > MAX_ENTRIES
                or len(json.dumps(value, separators=(',', ':')).encode()) > MAX_UNCOMPRESSED_BYTES):
            raise ValueError('Slot ledger exceeds bounds')
        return value
    size, count, data = value.get('uncompressedBytes'), value.get('entryCount'), value.get('data')
    if (value.get('encoding') != 'gzip+base64' or type(size) is not int
            or not 0 < size <= MAX_UNCOMPRESSED_BYTES or type(count) is not int
            or not 0 <= count <= MAX_ENTRIES or not isinstance(data, str)
            or len(data) > MAX_ENCODED_BYTES
            or not re.fullmatch(r'[0-9a-f]{64}', str(value.get('sha256', '')))):
        raise ValueError('Invalid compressed slot ledger bounds')
    try:
        packed = base64.b64decode(data, validate=True)
        stream = zlib.decompressobj(wbits=31)
        raw = stream.decompress(packed, size+1)
        if (len(raw) != size or not stream.eof or stream.unconsumed_tail or stream.unused_data
                or hashlib.sha256(raw).hexdigest() != value['sha256']):
            raise ValueError('Compressed slot ledger integrity mismatch')
        result = json.loads(raw)
    except (ValueError, zlib.error, UnicodeError) as exc:
        raise ValueError('Invalid compressed slot ledger') from exc
    if (not isinstance(result, dict) or result.get('schemaVersion') != 1
            or not isinstance(result.get('entries'), list) or len(result['entries']) != count
            or any(result.get(key) != value.get(key) for key in METADATA)):
        raise ValueError('Compressed slot ledger metadata mismatch')
    return result


def pack_slot_ledger(value):
    unpack_slot_ledger(value)
    if value.get('schemaVersion') != 1:
        raise ValueError('Uncompressed slot ledger required')
    raw = json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode()
    data = base64.b64encode(gzip.compress(raw, compresslevel=9, mtime=0)).decode('ascii')
    if len(data) > MAX_ENCODED_BYTES:
        raise ValueError('Slot ledger storage budget exceeded')
    return {'schemaVersion': 2, 'encoding': 'gzip+base64', 'sha256': hashlib.sha256(raw).hexdigest(),
            'uncompressedBytes': len(raw), 'entryCount': len(value['entries']),
            **{key: value.get(key) for key in METADATA}, 'data': data}


def clock(value):
    if not isinstance(value, str):
        raise ValueError('Ledger timestamp required')
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('Ledger timezone required')
    return parsed.astimezone(UTC)


def time_or_none(value, at):
    try:
        parsed = clock(value)
        return parsed.isoformat() if at-timedelta(days=90) <= parsed <= at+timedelta(minutes=2) else None
    except (ValueError, TypeError):
        return None


def clean_event(item, at):
    if not isinstance(item, dict) or item.get('outcome') not in STATES:
        return None
    observed = time_or_none(item.get('observedAt'), at)
    if observed is None:
        return None
    result = {'observedAt': observed, 'outcome': item['outcome']}
    for name in ('runId', 'attempt'):
        result[name] = item.get(name) if type(item.get(name)) is int and item[name] > 0 else None
    for name, allowed in [('executionState', {'queued','pending','in_progress','waiting','requested','completed'}),
                          ('executionConclusion', {'success','failure','timed_out','cancelled','skipped','action_required','neutral'})]:
        result[name] = item.get(name) if item.get(name) in allowed else None
    for name in ('sourceAt', 'generatedAt', 'publishedAt', 'readbackAt'):
        result[name] = time_or_none(item.get(name), at)
    return result


def expected_slots(start, at, due_slot):
    """Use the authoritative cadence; night policy hours are not fabricated work."""
    day = start.astimezone(KST).replace(hour=0, minute=0, second=0, microsecond=0)
    while day <= at.astimezone(KST):
        for kind in sorted(KINDS):
            if kind in ('albums', 'capture'):
                candidates = [day.replace(hour=hour) for hour in (0, *range(7, 24))]
            elif kind == 'schedule':
                candidates = [day.replace(hour=hour, minute=5) for hour in range(0, 24, 2)]
            elif kind == 'history':
                candidates = [day] if day.weekday() == 6 else []
            else:
                hour, minute = {'music': (6, 0), 'catalog': (7, 15), 'playground': (8, 0)}[kind]
                candidates = [day.replace(hour=hour, minute=minute)]
            for candidate in candidates:
                due = candidate.astimezone(UTC)
                if start <= due <= at and due_slot(kind, due) == due:
                    yield kind, due
        day += timedelta(days=1)


def observed_outcome(row, due, at):
    if row.get('paused'):
        return 'paused'
    if at < due+timedelta(minutes=5):
        return 'awaiting'
    if not row.get('listingComplete') or row.get('inspectionError'):
        return 'unverified'
    if row.get('dataState') == 'healthy':
        return 'verified'
    evidence = row.get('evidence') or {}
    if row['key'] == 'capture' and evidence.get('status') == 'partial':
        if any(time_or_none(value, at) == due.isoformat() for value in (evidence.get('sourceTimes') or {}).values()):
            return 'partial'
    run = row.get('run') or {}
    started = time_or_none(run.get('startedAt'), at)
    if started and clock(started) >= due:
        if run.get('status') in ('queued', 'pending', 'in_progress', 'waiting', 'requested'):
            return 'running'
        if run.get('conclusion') == 'cancelled':
            return 'cancelled'
        if run.get('conclusion') in ('failure', 'timed_out', 'action_required', 'startup_failure'):
            return 'failed'
    return 'unverified'


def merge_slot_ledger(previous, current, due_slot):
    at = clock(current['checkedAt'])
    today = at.astimezone(KST).replace(hour=0, minute=0, second=0, microsecond=0).astimezone(UTC)
    old = unpack_slot_ledger(previous.get('slotLedger')) if isinstance(previous, dict) else None
    start = today
    entries = {}
    if isinstance(old, dict) and old.get('schemaVersion') == 1:
        items = old.get('entries', [])
        if not isinstance(items, list) or len(items) > MAX_ENTRIES:
            raise ValueError('Invalid slot ledger history')
        candidate = clock(old['coverageStartAt'])
        if candidate <= today:
            start = max(candidate, (at-timedelta(days=89)).astimezone(KST).replace(
                hour=0, minute=0, second=0, microsecond=0).astimezone(UTC))
        for item in items:
            if not isinstance(item, dict) or item.get('batch') not in KINDS or item.get('state') not in STATES:
                continue
            stamp = time_or_none(item.get('dueAt'), at)
            if stamp is None or not start <= clock(stamp) <= at:
                continue
            if due_slot(item['batch'], clock(stamp)) != clock(stamp):
                continue
            events = item.get('events', [])
            events = [clean_event(event, at) for event in events[-4:]] if isinstance(events, list) else []
            clean = {'batch': item['batch'], 'dueAt': stamp, 'state': item['state'],
                     'events': [event for event in events if event],
                     'firstFailure': clean_event(item.get('firstFailure'), at),
                     'firstVerifiedAt': time_or_none(item.get('firstVerifiedAt'), at),
                     'recoveredAt': time_or_none(item.get('recoveredAt'), at),
                     'recoveredReadbackAt': time_or_none(item.get('recoveredReadbackAt'), at)}
            entries[(clean['batch'], stamp)] = clean
    for kind, due in expected_slots(start, at, due_slot):
        key = (kind, due.isoformat())
        entries.setdefault(key, {'batch': kind, 'dueAt': key[1],
            'state': 'awaiting' if at < due+timedelta(minutes=5) else 'unverified',
            'events': [], 'firstFailure': None, 'firstVerifiedAt': None,
            'recoveredAt': None, 'recoveredReadbackAt': None})
        if entries[key]['state'] == 'awaiting' and at >= due+timedelta(minutes=5):
            entries[key]['state'] = 'unverified'
    for row in current['batches']:
        if row.get('key') not in KINDS or not row.get('dueAt'):
            continue
        due = clock(row['dueAt']); key = (row['key'], due.isoformat())
        if key not in entries:
            continue
        item = entries[key]
        outcome = observed_outcome(row, due, at)
        run = (row.get('evidenceRun') if outcome == 'verified' else row.get('run')) or {}
        evidence = row.get('evidence') or {}
        source = list((row.get('sourceTimes') or {}).values())
        event = clean_event({'observedAt': current['checkedAt'], 'outcome': outcome,
            'runId': run.get('id'), 'attempt': run.get('attempt'),
            'executionState': run.get('status'), 'executionConclusion': run.get('conclusion'),
            'sourceAt': source[0] if source and len(set(source)) == 1 else evidence.get('sourceAt'),
            'generatedAt': evidence.get('generatedAt'), 'publishedAt': evidence.get('publishedAt'),
            'readbackAt': evidence.get('readbackAt') or row.get('lastVerifiedAt')}, at)
        # Repeated checks of the same outcome/attempt update evidence without
        # consuming the bounded event history or erasing the first failure.
        signature = lambda value: (value['outcome'], value.get('runId'), value.get('attempt'))
        if item['events'] and signature(item['events'][-1]) == signature(event):
            item['events'][-1] = event
        else:
            item['events'] = (item['events']+[event])[-4:]
        if outcome in ('failed', 'partial', 'cancelled') and item['firstFailure'] is None:
            item['firstFailure'] = event.copy()
        if outcome == 'verified':
            verified = event.get('readbackAt') or event['observedAt']
            item['firstVerifiedAt'] = item['firstVerifiedAt'] or verified
            if item['firstFailure']:
                # Confirmation may observe an earlier readback after a delayed
                # failed snapshot. Keep both clocks; never claim time travel.
                item['recoveredAt'] = item['recoveredAt'] or event['observedAt']
                item['recoveredReadbackAt'] = item['recoveredReadbackAt'] or event.get('readbackAt')
        # Subsequent inspector errors cannot revoke a previously verified slot.
        if item['state'] != 'verified' or outcome == 'verified':
            item['state'] = outcome
    ordered = sorted(entries.values(), key=lambda item: (item['dueAt'], item['batch']))
    current['slotLedger'] = pack_slot_ledger({'schemaVersion': 1, 'coverageStartAt': start.isoformat(),
        'coverageEndAt': at.isoformat(), 'checkedAt': at.isoformat(), 'retentionDays': 90,
        'evidenceScope': 'observed_snapshots_only', 'unobservedIsFailure': False, 'entries': ordered})
    for row in current['batches']:
        if row['key'] not in KINDS:
            continue
        items = [item for item in ordered if item['batch'] == row['key'] and clock(item['dueAt']) >= today]
        row['slotSummary'] = {'day': today.astimezone(KST).date().isoformat(), 'expected': len(items),
            **{state: sum(item['state'] == state for item in items) for state in sorted(STATES)},
            'recovered': sum(item['recoveredAt'] is not None for item in items),
            'historyScope': 'verified_observations_since_ledger_rollout'}
    return current
