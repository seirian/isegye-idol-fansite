"""Validated public-window metadata carried with the private schedule snapshot.

Never fetch URLs or trust Search snippets here. The isolated public-browser review
produces the same author/board/role checks as the operator-reviewed packets. Only
that bounded packet can extend the server and client allowlists. Successful older
observations survive a failed run without being stamped as newly checked.
"""
from __future__ import annotations
import copy
import re
from datetime import date, timedelta
import cafe_batch as cb
import notice_policy as policy

EVIDENCE_FIELDS = {'schemaVersion', 'notices', 'fanSeries'}
FAN_FIELDS = {'articleId', 'title', 'date', 'publishedAt', 'sameBoard', 'sameAuthor', 'public'}
MAX_NOTICES = 600
MAX_FANS = 100
CARD_STATUS = {'rest': '휴방 예상', 'expected': '방송 예정 · 팬 정리', 'unknown': '방송 여부 미확인'}


def safe_text(value):
    return isinstance(value, str) and 0 < len(value) <= 220 and not re.search(r'[<>\x00-\x1f]', value)


def validate_evidence(value, now):
    if value is None:
        return {'schemaVersion': 1, 'notices': [], 'fanSeries': []}
    if not isinstance(value, dict) or set(value) != EVIDENCE_FIELDS or value['schemaVersion'] != 1:
        raise ValueError('invalid cafe evidence schema')
    until = cb.timestamp(now)
    used = set()
    for key, limit in (('notices', MAX_NOTICES), ('fanSeries', MAX_FANS)):
        rows = value[key]
        if not isinstance(rows, list) or len(rows) > limit:
            raise ValueError('cafe evidence limit')
        for item in rows:
            fields = policy.FIELDS if key == 'notices' else FAN_FIELDS
            if not isinstance(item, dict) or set(item) != fields | {'checkedAt'}:
                raise ValueError('unexpected cafe evidence fields')
            row = {k: v for k, v in item.items() if k != 'checkedAt'}
            checked, published = cb.timestamp(item['checkedAt']), cb.timestamp(item['publishedAt'])
            if not published <= checked <= until or not safe_text(row['title']):
                raise ValueError('invalid cafe evidence observation')
            aid = row['articleId']
            if type(aid) is not int or aid <= 0 or aid in used or cb.PREFIX + str(aid) in policy.EXCLUDED_URLS:
                raise ValueError('invalid cafe evidence article')
            used.add(aid)
            if key == 'notices':
                policy.validate_archive({'schemaVersion': 1, 'rangeStart': '2021-08-26',
                    'rangeEnd': checked.astimezone(cb.KST).date().isoformat(),
                    'checkedAt': item['checkedAt'], 'notices': [row]})
            else:
                day = date.fromisoformat(row['date'])
                match = re.fullmatch(r'\[\s*(\d{1,2})/(\d{1,2})\([^)]{1,4}\)\s*\]\s*이세돌\s*뱅온정보', row['title'])
                if not all(row[k] is True for k in ('sameBoard', 'sameAuthor', 'public')) or not match:
                    raise ValueError('unverified fan series')
                if (int(match[1]), int(match[2])) != (day.month, day.day) or published.astimezone(cb.KST).date() != day:
                    raise ValueError('fan date mismatch')
    return value


def source_map(value, now):
    evidence = validate_evidence(value, now)
    result = {}
    for key in ('notices', 'fanSeries'):
        for row in evidence[key]:
            sid = cb.IDS[row['menuId']] if key == 'notices' else 'fan-roundup'
            result[cb.PREFIX + str(row['articleId'])] = (sid, row)
    return result


def matches(row, approved):
    entry = approved.get(row.get('sourceUrl'))
    if not entry or row.get('sourceId') != entry[0]:
        return False
    sid, proof = entry
    if row.get('publishedAt') != proof['publishedAt']:
        return False
    if sid == 'fan-roundup':
        return row.get('date') == proof['date'] and row.get('certainty') in ('unknown', 'tentative')
    return (row.get('title') == proof['title'] and row.get('members') == proof['members']
            and row.get('checkedAt') == proof['checkedAt'])


def validate_packet(packet, now):
    cb.validate(packet)
    allowed = {'schemaVersion', 'from', 'checkedAt', 'boards', 'notices', 'fan', 'fanSeries',
               'fanCheckedAt', 'fanCards', 'cardCheckedAt', 'fanWindowComplete'}
    if not set(packet) <= allowed:
        raise ValueError('unexpected public review fields')
    until = cb.timestamp(now)
    for k in ('checkedAt', 'fanCheckedAt', 'cardCheckedAt'):
        if k in packet and cb.timestamp(packet[k]) > until:
            raise ValueError('future review packet')
    listed = {str(r['articleId']) for r in packet.get('fanSeries', [])}
    cards = packet.get('fanCards', {})
    if not isinstance(cards, dict) or not set(cards) <= listed:
        raise ValueError('unapproved fan cards')
    for sections in cards.values():
        if not isinstance(sections, dict) or not set(sections) <= policy.MEMBERS:
            raise ValueError('unknown fan card member')
        for row in sections.values():
            if not isinstance(row, dict) or set(row) != {'status', 'time'} or row['status'] not in CARD_STATUS:
                raise ValueError('invalid fan card')
            if row['time'] is not None and (row['status'] != 'expected' or not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d', row['time'])):
                raise ValueError('invalid fan time')
    return packet


def populate(data, previous, packet, now, static_states):
    """Extend only reviewed sources; preserve last success on partial collection."""
    if packet is None and not (previous or {}).get('cafeEvidence'):
        return {}
    import schedule_feed as feed
    prior = validate_evidence((previous or {}).get('cafeEvidence'), now)
    if packet is not None:
        validate_packet(packet, now)
    evidence = {'schemaVersion': 1}
    for key, limit in (('notices', MAX_NOTICES), ('fanSeries', MAX_FANS)):
        byid = {r['articleId']: copy.deepcopy(r) for r in prior[key]}
        at = (packet or {}).get('checkedAt') if key == 'notices' else (packet or {}).get('fanCheckedAt')
        for row in (packet or {}).get(key, []):
            observed = at or packet['checkedAt']
            old = byid.get(row['articleId'])
            if old is None or cb.timestamp(observed) >= cb.timestamp(old['checkedAt']):
                byid[row['articleId']] = {**row, 'checkedAt': observed}
        evidence[key] = sorted(byid.values(), key=lambda r: (cb.timestamp(r['publishedAt']), r['articleId']), reverse=True)[:limit]
    data['cafeEvidence'] = validate_evidence(evidence, now)
    for row in evidence['notices']:
        post = feed.public_item(cb.IDS[row['menuId']], cb.PREFIX + str(row['articleId']), row['title'],
            row['publishedAt'], row['checkedAt'], members=row['members'],
            detail='공개 게시판의 작성자·권한·게시일 확인 · 공지 게시일 기준')
        data['news'].append(post)
        event = feed.event_from_title(row['title'], row['publishedAt'], True) if not row['titleGeneralized'] else None
        if event:
            data['events'].append({**post, **event, 'id': post['id'] + '-' + event['date']})
    # Preserve member-level reference cards when a later attempt cannot read them.
    for row in evidence['fanSeries']:
        aid = str(row['articleId']); url = cb.PREFIX + aid
        old_cards = [r for r in (previous or {}).get('forecasts', []) if r['sourceUrl'] == url]
        supplied = (packet or {}).get('fanCards', {}).get(aid)
        ref = feed.public_item('fan-roundup', url, row['title'], row['publishedAt'], row['checkedAt'],
            members=list(feed.MEMBERS), detail='동일 작성자·게시판의 팬 정리 원문 · 실제 방송 여부 미확인')
        ref.update(date=row['date'], time=None, type='broadcast', status='reference', certainty='unknown', dateBasis='roundup_title')
        data['forecasts'] = [r for r in data['forecasts'] if r['sourceUrl'] != url]
        if supplied:
            for member, card in supplied.items():
                st, tm = card['status'], card['time']
                data['forecasts'].append({**ref, 'id': ref['id'] + '-' + member,
                    'title': feed.MEMBERS[member] + ' · ' + CARD_STATUS[st] + (' · ' + tm if tm else ''),
                    'members': [member], 'time': tm, 'certainty': 'unknown' if st == 'unknown' else 'tentative',
                    'checkedAt': packet['cardCheckedAt']})
        else:
            data['forecasts'].extend(old_cards or [ref])
    for key in ('news', 'events', 'forecasts'):
        rows = {}
        for row in data[key]:
            old = rows.get(row['id'])
            if old is None or cb.timestamp(row['checkedAt']) >= cb.timestamp(old['checkedAt']):
                rows[row['id']] = row
        data[key] = list(rows.values())
    old_sources = {s['id']: s for s in (previous or {}).get('sources', [])}
    states = {}
    for menu, sid in cb.IDS.items():
        prior_state = old_sources.get(sid, static_states[sid])
        board = (packet or {}).get('boards', {}).get(str(menu), {})
        checked = (packet or {}).get('checkedAt')
        ok = board.get('state') == 'reviewed'
        states[sid] = {'mode': 'verified_public_window', 'state': 'ok' if ok else 'error',
            'lastAttemptAt': checked or now,
            'lastSuccessAt': checked if ok else prior_state.get('lastSuccessAt'),
            'coverage': {'fromKst': (packet or {}).get('from'), 'asOf': checked if ok else prior_state.get('lastSuccessAt'),
                         'inputType': 'verified_public_metadata', 'complete': ok, 'count': board.get('count') if ok else None},
            'detail': '공개 목록의 작성자·권한·게시일 검증 완료 · ' + checked if ok else '카페 원본 확인 실패 · 이전 확인 자료 유지'}
        # A fresh short window must not conceal an older outage gap.
        old_coverage = prior_state.get('coverage', {})
        gap = old_coverage.get('gapFromKst')
        through = old_coverage.get('gapThroughKst')
        if ok and prior_state.get('lastSuccessAt'):
            last_day = cb.timestamp(prior_state['lastSuccessAt']).astimezone(cb.KST).date().isoformat()
            if last_day < packet['from'] and (not gap or last_day < gap):
                gap = last_day
                through = (date.fromisoformat(packet['from']) - timedelta(days=1)).isoformat()
        if ok and gap and packet['from'] <= gap:
            gap = through = None
        if gap:
            states[sid]['coverage'].update(gapFromKst=gap, gapThroughKst=through)
    fans = (packet or {}).get('fanSeries', [])
    at = (packet or {}).get('fanCheckedAt')
    old = old_sources.get('fan-roundup', static_states['fan-roundup'])
    states['fan-roundup'] = {'mode': 'verified_public_window', 'state': 'ok' if fans else 'needs_review',
        'lastAttemptAt': at or now, 'lastSuccessAt': at if fans else old.get('lastSuccessAt'),
        'coverage': {'fromKst': (packet or {}).get('from'), 'asOf': at if fans else old.get('lastSuccessAt'),
                     'inputType': 'verified_public_metadata', 'verifiedArticles': len(fans), 'complete': False,
                     'scope': 'same-author-series-references-only'},
        'detail': '동일 작성자·게시판의 팬 정리 확인 · 방송 확정 아님' if fans else '팬 정리 원문 확인 미완료 · 이전 자료 유지'}
    return states
