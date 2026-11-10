"""Periodic history from verified public music and official-announcement metadata.

Never infer a concert date or an album release from an upload/announcement date.
The curated timeline is immutable. Existing successful upstream snapshots bridge
short public listing windows; failures never advance an observation timestamp.
"""
from __future__ import annotations
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit, parse_qs
import copy
import hashlib
import json
import os
import re
import unicodedata
import daily_music as music
import schedule_feed as schedule
import notice_policy

ROOT = Path(__file__).resolve().parents[1]
KST = timezone(timedelta(hours=9))
TYPES = {'audition', 'release', 'performance', 'content', 'collaboration', 'award'}
NOTICE_SOURCES = {'parable-web', 'berriz-notice', 'cafe-agency', 'cafe-members'}
FIELDS = {'id', 'date', 'title', 'type', 'members', 'sources', 'summary', 'note', 'dateBasis'}
OPTIONAL = {'relatedSong', 'announced'}
SOURCE_FIELDS = {'title', 'url', 'basis', 'checkedAt'}
MAX_BYTES = 1500000
START = date(2026, 10, 1) # Initial reviewed month; does not move when the curated catalog changes.

def base():
    return json.loads((ROOT / 'visuals/history.json').read_text())

def stamp(value):
    dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if dt.tzinfo is None:
        raise ValueError('history timestamp requires timezone')
    return dt

def bounds(now, cadence='monthly'):
    if now.tzinfo is None:
        raise ValueError('history timestamp requires timezone')
    local = now.astimezone(KST).date()
    if cadence == 'weekly':
        # Last completed Sunday-Saturday week; stable even if a Sunday run is delayed.
        return START, local - timedelta(days=(local.weekday() + 1) % 7 + 1)
    if cadence == 'monthly':
        return START, local.replace(day=1) - timedelta(days=1)
    raise ValueError('unsupported history cadence')

def day(value):
    if re.fullmatch(r'20\d{2}-\d{2}-\d{2}', value or ''):
        return date.fromisoformat(value).isoformat()
    return stamp(value).astimezone(KST).date().isoformat()

def safe_text(value, limit=400):
    return isinstance(value, str) and 0 < len(value) <= limit and not re.search(r'[<>\x00-\x1f]', value)

def source_url(url):
    try:
        u = urlsplit(url)
        if u.scheme != 'https' or u.username or u.password or u.port not in (None, 443) or u.fragment:
            return False
        if u.hostname == 'www.youtube.com':
            return u.path == '/watch' and bool(re.fullmatch(r'[\w-]{11}', parse_qs(u.query).get('v', [''])[0])) and set(parse_qs(u.query)) == {'v'}
        return schedule.source_url(url) == url and u.hostname in {'parable-asia.com', 'berriz.in', 'cafe.naver.com'} and (u.hostname != 'berriz.in' or '/notice/' in u.path)
    except (ValueError, TypeError):
        return False

def signature(row):
    title = ''.join(c for c in unicodedata.normalize('NFKC', row['title']).casefold() if c.isalnum())
    return row['date'], title, tuple(sorted(row['members']))

def validate(doc):
    if not isinstance(doc, dict) or doc.get('schemaVersion') != 1 or doc.get('feed') != 'monthly-history':
        raise ValueError('invalid history snapshot')
    when = stamp(doc['generatedAt'])
    start, through = bounds(when, doc.get('cadence', 'monthly'))
    if doc.get('through') != through.isoformat() or doc.get('windowStart') != start.isoformat():
        raise ValueError('history period boundary mismatch')
    if len(json.dumps(doc).encode()) > MAX_BYTES:
        raise ValueError('history snapshot too large')
    sources, rows = doc['sources'], doc['events']
    if not isinstance(sources, dict) or not isinstance(rows, list) or len(rows) > 3000 or len(sources) > 3000:
        raise ValueError('invalid history collection')
    for key, s in sources.items():
        if not re.fullmatch(r'mh-[a-f0-9]{24}', key) or set(s) != SOURCE_FIELDS or s['basis'] != 'official' or not source_url(s['url']) or not safe_text(s['title'], 240):
            raise ValueError('invalid history source')
        if stamp(s['checkedAt']) > when:
            raise ValueError('future source observation')
    ids, signatures = set(), set()
    for r in rows:
        if not isinstance(r, dict) or not FIELDS <= set(r) or not set(r) <= FIELDS | OPTIONAL:
            raise ValueError('invalid history fields')
        if not re.fullmatch(r'monthly-[a-f0-9]{24}', r['id']) or r['id'] in ids or r['type'] not in TYPES:
            raise ValueError('invalid history ID or type')
        if not start <= date.fromisoformat(r['date']) <= through:
            raise ValueError('history date outside completed period')
        if not all(safe_text(r[k], 240 if k == 'title' else 400) for k in ('title', 'summary', 'note')):
            raise ValueError('invalid history text')
        if not isinstance(r['members'], list) or not r['members'] or not set(r['members']) <= music.NAMES.keys() or len(set(r['members'])) != len(r['members']):
            raise ValueError('invalid history participants')
        if not isinstance(r['sources'], list) or len(r['sources']) != 1 or any(k not in sources for k in r['sources']):
            raise ValueError('history source missing')
        if r['dateBasis'] not in ('video_published', 'notice_published'):
            raise ValueError('unknown history date basis')
        url = sources[r['sources'][0]]['url']
        if (r['dateBasis'] == 'video_published') != (urlsplit(url).hostname == 'www.youtube.com'):
            raise ValueError('history source/date mismatch')
        if date.fromisoformat(r['date']) > stamp(sources[r['sources'][0]]['checkedAt']).astimezone(KST).date():
            raise ValueError('publication later than evidence')
        if 'announced' in r and r['announced'] is not True:
            raise ValueError('invalid announcement flag')
        if 'relatedSong' in r and not re.fullmatch(r'daily-[\w-]{11}', r['relatedSong']):
            raise ValueError('invalid related song')
        sig = signature(r)
        if sig in signatures:
            raise ValueError('duplicate history activity')
        signatures.add(sig); ids.add(r['id'])
    return doc

def notice_type(title):
    if re.search(r'팬클럽\s*전용|회원\s*전용|MEMBERS\s*ONLY|배송|당첨자|입금|환불|휴뱅|휴방|뱅온|컨디션|건강|병원', title, re.I):
        return None
    for typ, pattern in (
        ('award', r'수상|어워즈|awards?'),
        ('collaboration', r'콜라보|협업|팝업|POP[ -]?UP|전시|CM송|펀딩'),
        ('performance', r'콘서트|공연|페스티벌|팬미팅|팬사인회|CONCERT|FESTIVAL|FAN ?MEETING'),
        ('release', r'앨범|발매|싱글|ALBUM|RELEASE|디지털\s*음원'),
        ('content', r'웹툰|연재|뮤직비디오|공식\s*MV|다큐멘터리'),
        ('audition', r'오디션|최종\s*선발|그룹\s*결성'),
    ):
        if re.search(pattern, title, re.I):
            return typ
    return None

def compose(schedule_doc, music_rows, now=None, coverage=None, cadence='monthly'):
    now = now or datetime.now(timezone.utc)
    start, through = bounds(now, cadence)
    doc = {'schemaVersion': 1, 'feed': 'monthly-history', 'generatedAt': now.isoformat(), 'windowStart': start.isoformat(), 'through': through.isoformat(), 'sources': {}, 'events': [], 'coverage': coverage or {}}
    if cadence == 'weekly':
        doc['cadence'] = 'weekly'
    def add(url, source_title, checked, event):
        if not start.isoformat() <= event['date'] <= through.isoformat():
            return
        digest = hashlib.sha256(url.encode()).hexdigest()[:24]
        key = 'mh-' + digest
        doc['sources'][key] = dict(title=source_title, url=url, basis='official', checkedAt=checked)
        doc['events'].append(dict(event, id='monthly-' + digest, sources=[key]))
    for row in music.validate(music_rows):
        # The historical page is a milestone archive, not a copy of every cover.
        if row['type'] == 'cover':
            continue
        label = {'album_medley': '앨범 메들리', 'music_clip': '음악 스페셜클립', 'performance': '공연·편곡 영상'}.get(row['type'], '공식 음악 영상')
        add('https://www.youtube.com/watch?v=' + row['videoId'], 'YouTube · ' + music.selections()[0]['channels'][row['channelKey']]['name'], row['checkedAt'],
            dict(date=day(row['publishedAt']), title=row['title'] + ' · ' + label + ' 공개', type='content', members=row['members'][:], dateBasis='video_published', relatedSong='daily-' + row['videoId'], summary='공식 채널에서 음악 영상이 공개된 기록입니다.', note='영상 공개일 기준입니다. 음반 발매일이나 영상에 담긴 공연의 개최일을 뜻하지 않습니다.'))
    for row in schedule.validate(notice_policy.clean_snapshot(schedule_doc))['news']:
        if row['sourceId'] not in NOTICE_SOURCES or not notice_policy.is_publishable(row) or not row.get('publishedAt') or not row.get('members'):
            continue
        typ = notice_type(row['title'])
        if not typ:
            continue
        try:
            published = day(row['publishedAt'])
        except (ValueError, TypeError):
            continue
        add(row['sourceUrl'], {'parable-web': '패러블 공식 뉴스룸', 'berriz-notice': '베리즈 공식 공지', 'cafe-agency': '패러블 카페 공식 공지', 'cafe-members': '왁물원 멤버 공지'}[row['sourceId']], row['checkedAt'],
            dict(date=published, title=row['title'], type=typ, members=row['members'][:], dateBasis='notice_published', announced=True, summary='공식 소식이 게시된 날짜의 기록입니다.', note='공지 게시일 기준입니다. 공지에 포함된 예정 행사나 발매가 실제로 진행·완료됐다는 의미는 아닙니다.'))
    # An upstream source may occur more than once. Select its newest observation.
    unique = {}
    for row in doc['events']:
        unique[row['id']] = row
    seen = set(); doc['events'] = []
    for row in unique.values():
        sig = signature(row)
        if sig not in seen:
            doc['events'].append(row); seen.add(sig)
    return merge(None, doc)

def merge(previous, current):
    # Validate first, including data that a duplicate filter would otherwise hide.
    validate(current)
    if previous:
        validate(previous)
        if current['through'] < previous['through'] or stamp(current['generatedAt']) < stamp(previous['generatedAt']):
            raise ValueError('history snapshot regression')
    out = copy.deepcopy(current)
    sources = {**(previous['sources'] if previous else {}), **current['sources']}
    records = {r['id']: r for r in (previous['events'] if previous else [])}
    for row in current['events']:
        old = records.get(row['id'])
        if old:
            key = old['sources'][0]
            if stamp(previous['sources'][key]['checkedAt']) > stamp(current['sources'][row['sources'][0]]['checkedAt']):
                sources[key] = previous['sources'][key]
                continue
        records[row['id']] = row
    signatures = {signature(r) for r in base()['events']}
    out['events'] = []
    for row in sorted(records.values(), key=lambda r: (r['date'], r['id'])):
        sig = signature(row)
        if sig not in signatures:
            out['events'].append(row); signatures.add(sig)
    needed = {k for r in out['events'] for k in r['sources']}
    out['sources'] = {k: v for k, v in sources.items() if k in needed}
    return validate(out)

def inputs(now=None):
    now = now or datetime.now(timezone.utc)
    cadence = os.getenv('ISEGYE_HISTORY_CADENCE', 'monthly')
    bounds(now, cadence) # Reject bad mode before any source requests.
    return {'generatedAt': now.isoformat(), 'cadence': cadence, 'schedule': schedule.collect(now=now.isoformat()), 'music': music.discover(now=now)}

def combine_inputs(fresh, stored_schedule=None, stored_music=None):
    when = stamp(fresh['generatedAt'])
    if fresh['schedule']['generatedAt'] != fresh['generatedAt'] or fresh['music']['generatedAt'] != fresh['generatedAt']:
        raise ValueError('collection timestamps differ')
    states_in = fresh['music']['sources']
    if set(states_in) != set(music.CHANNELS) or any(v.get('state') not in ('ok', 'partial', 'error') for v in states_in.values()):
        raise ValueError('invalid music collection coverage')
    sched = schedule.merge(stored_schedule, copy.deepcopy(fresh['schedule']))
    rows = music.merge(stored_music or [], fresh['music']['rows'])
    states = {s['id']: s['state'] for s in fresh['schedule']['sources'] if s['id'] in NOTICE_SOURCES}
    states.update({'music-' + k: v['state'] for k, v in fresh['music']['sources'].items()})
    # Curated source snapshots alone do not count as successful fresh collection.
    if not any(v in ('ok', 'partial') for v in states.values()):
        raise ValueError('all live sources unavailable; previous history retained')
    return compose(sched, rows, when, {'sourceStates': states, 'partial': any(v not in ('ok', 'snapshot') for v in states.values()), 'scope': 'official announcements and non-cover official music; bounded public lists plus successful stored snapshots; no assumed completed events'}, cadence=fresh.get('cadence', 'monthly'))

if __name__ == '__main__':
    collected = inputs()
    Path('history-inputs.json').write_text(json.dumps(collected, ensure_ascii=False, indent=2) + '\n')
    preview = combine_inputs(collected)
    Path('history-discovery.json').write_text(json.dumps(preview, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'through': preview['through'], 'freshCandidates': len(preview['events']), 'coverage': preview['coverage']}, ensure_ascii=False))
