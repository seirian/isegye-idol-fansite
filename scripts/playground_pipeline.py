"""Reviewed reserve admission, wording review and calendar-based growth telemetry.

The reserve is committed review material, not untrusted remote quiz text. It is
never edited by a collector. Original evidence dates and limitations are kept.
"""
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
import copy
import hashlib
import json
import re
import unicodedata

ROOT = Path(__file__).resolve().parents[1]
DAILY_TARGET = 4
LOW_RESERVE = DAILY_TARGET * 7
NO_ADDITION_DAYS = 3
REFERENCE_SPEAK = re.compile(r'참고 문제집|행사 답안|공개 답안|RURU CLOSET 답안')


def canonical(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))+'\n').encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def norm(value):
    return ''.join(c for c in unicodedata.normalize('NFKC', value).casefold() if c.isalnum())


def reserve_index():
    from build_playground import validate
    doc = json.loads((ROOT/'playground/reserve.json').read_text())
    if doc.get('schemaVersion') != 1 or not 1 <= len(doc['entries']) <= 500:
        raise ValueError('Reserve schema')
    date.fromisoformat(doc['reviewedAt'])
    base = json.loads((ROOT/'playground/catalog.json').read_text())
    ids = {q['id'] for q in base['questions']}
    stems = {norm(q['stem']) for q in base['questions']}
    facts, index = set(), {}
    for entry in doc['entries']:
        q, sid, source = entry['question'], entry['sourceId'], entry['source']
        p = q.get('provenance', {})
        fact = digest([p.get('subject'), p.get('predicate')])
        if (q['id'] in ids or norm(q['stem']) in stems or fact in facts or
                q['id'] != 'reserve-'+fact[:24] or p.get('factKey') != fact or
                p.get('template') != 'reviewed-reserve-v1' or q['sources'] != [sid] or
                'eligibleFrom' in q or REFERENCE_SPEAK.search(q['stem'])):
            raise ValueError('Duplicate or unreviewed reserve fact')
        date.fromisoformat(p['reviewedAt'])
        if source.get('kind') not in ('primary', 'catalog', 'archive'):
            raise ValueError('Reserve needs reviewed evidence')
        if sid in base['sources'] and base['sources'][sid] != source:
            raise ValueError('Reserve evidence conflict')
        ids.add(q['id']); stems.add(norm(q['stem'])); facts.add(fact)
        base['questions'].append(q); base['sources'][sid] = source
        index[q['id']] = entry
    validate(base)
    return index


def validate_reserve_question(q, sources, index):
    expected = index.get(q['id'])
    if not expected:
        raise ValueError('Question is not in the reviewed reserve')
    candidate = copy.deepcopy(q)
    date.fromisoformat(candidate.pop('eligibleFrom'))
    if candidate != expected['question'] or sources.get(expected['sourceId']) != expected['source']:
        raise ValueError('Reviewed reserve answer or evidence changed')


def reserve_proposals(catalog, now, limit=DAILY_TARGET):
    from playground_bank import KST
    existing_ids = {q['id'] for q in catalog['questions']}
    existing_facts = {q.get('provenance', {}).get('factKey') for q in catalog['questions']}
    existing_videos = {q.get('provenance', {}).get('videoId') for q in catalog['questions']}
    existing_stems = {norm(q['stem']) for q in catalog['questions']}
    pools, excluded = defaultdict(list), 0
    for entry in reserve_index().values():
        q = entry['question']; p = q['provenance']
        if (q['id'] in existing_ids or p['factKey'] in existing_facts or
                norm(q['stem']) in existing_stems or
                (p.get('videoId') and p['videoId'] in existing_videos)):
            excluded += 1
            continue
        pools[q['category']].append(entry)
    ready = sum(map(len, pools.values()))
    by_category = {key: len(pools[key]) for key in catalog['categories']}
    proposals = []
    eligible = (now.astimezone(KST).date()+timedelta(days=1)).isoformat()
    # Round-robin topics, not 20 blocked rows at the head of the same list.
    while any(pools.values()) and len(proposals) < max(0, limit):
        for category in catalog['categories']:
            if pools[category] and len(proposals) < limit:
                entry = copy.deepcopy(pools[category].pop(0))
                q = entry['question']; q['eligibleFrom'] = eligible
                proposals.append((q, entry['sourceId'], entry['source']))
    return proposals, {'readyBefore': ready, 'duplicateOrUsed': excluded,
                       'readyByCategory': by_category, 'reviewedTotal': ready+excluded}


def growth_report(previous, feed, added_ids, remaining, now, candidate_counts):
    from playground_bank import KST
    today = now.astimezone(KST).date().isoformat()
    old = (previous or {}).get('growth', {})
    history = {item['date']: item for item in old.get('history', []) if item['date'] <= today}
    # addedToday is persisted with the bank. Re-runs replace a day's aggregate;
    # they must not count a second zero day or erase additions earlier that day.
    history[today] = {'date': today, 'added': feed['addedToday']}
    history = dict(sorted(history.items())[-90:])
    zero_days = 0; cursor = date.fromisoformat(today)
    while (item := history.get(cursor.isoformat())) is not None and item['added'] == 0:
        zero_days += 1; cursor -= timedelta(days=1)
    last = now.isoformat() if added_ids else old.get('lastAdditionAt')
    state = 'growing' if feed['addedToday'] else 'no_new_questions'
    if len(feed['catalog']['questions']) >= 1000:
        state = 'capacity_reached'
    elif zero_days >= NO_ADDITION_DAYS:
        state = 'stalled'
    elif not feed['addedToday'] and remaining == 0:
        state = 'reserve_exhausted'
    alerts = []
    if state in ('stalled', 'reserve_exhausted', 'capacity_reached'):
        alerts.append(state)
    if remaining < LOW_RESERVE:
        alerts.append('reserve_low')
    return {'schemaVersion': 1, 'state': state, 'trackingSince': old.get('trackingSince', today),
            'lastAdditionAt': last, 'todayAdded': feed['addedToday'], 'addedThisRun': len(added_ids),
            'dailyTarget': DAILY_TARGET, 'readyCount': remaining,
            'reserveDays': remaining//DAILY_TARGET, 'consecutiveZeroDays': zero_days,
            'alerts': alerts, 'candidateCounts': candidate_counts, 'history': list(history.values())}


def editorial_manifest():
    """Approve only exact before/after strings; never scoring or source fields."""
    doc = json.loads((ROOT/'playground/editorial.json').read_text())
    if doc.get('schemaVersion') != 1:
        raise ValueError('Editorial schema')
    seed = json.loads((ROOT/'playground/catalog.json').read_text())
    by_id = {q['id']: q for q in seed['questions']}
    seen = set()
    for edit in doc['edits']:
        if edit['id'] in seen or edit['id'] not in by_id:
            raise ValueError('Editorial identity')
        seen.add(edit['id'])
        before, after = edit['before'], edit['after']
        if set(before) != set(after) or not set(after) <= {'stem', 'hint', 'explanation'}:
            raise ValueError('Editorial scoring/evidence change prohibited')
        for field, text in after.items():
            if (before[field] != by_id[edit['id']][field] or not isinstance(text, str) or
                    not 1 <= len(text) <= 800 or re.search(r'[<>\x00-\x1f]', text) or
                    (field == 'stem' and REFERENCE_SPEAK.search(text))):
                raise ValueError('Editorial mismatch or unsafe text')
    return doc
