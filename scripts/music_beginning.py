"""Operating-only introduction: exact official video sources, no album mutations."""
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import json
import re
from review_2nd_polish import one

ROOT = Path(__file__).resolve().parents[1]
SERIES_ID = 'music-beginning'
TITLE = 'Re:Wind 부터 만나보는 이세계아이돌'
SELECTION = [
    ('rewind', 'RE:WIND', 'fgSXAKsq-Vo'),
    ('winter-spring', '겨울봄', 'JY-gJkMuJ94'),
    ('kidding', 'KIDDING', 'rDFUl2mHIW4'),
    ('be-my-light', 'Be My Light', '3cEUPoPXz7E'),
    ('smile-for-you', 'Smile For You', '8IY44RZHyw8'),
    ('rebels', 'REBELS', 'y-klhPVFblg'),
]
CHANNELS = {
    'UCzh4yY8rl38knH33XpNqXbQ': '왁타버스 WAKTAVERSE',
    'UCmblbE_WxTaFWcMEGFJ_97w': 'ISEGYE IDOL',
}


def clock(value):
    value = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if value.tzinfo is None:
        raise ValueError('Source timestamp needs timezone')
    return value


def validate(doc, now=None):
    now = now or datetime.now(timezone.utc)
    if (doc.get('schemaVersion') != 1 or doc.get('id') != SERIES_ID
            or doc.get('title') != TITLE or doc.get('source') != 'YouTube Data API v3 videos.list'
            or type(doc.get('evidenceRun')) is not int or doc['evidenceRun'] != 43775085793):
        raise ValueError('Unverified introductory video selection')
    checked = clock(doc['checkedAt'])
    if checked > now:
        raise ValueError('Future source verification')
    rows = doc.get('videos')
    if not isinstance(rows, list) or len(rows) != len(SELECTION):
        raise ValueError('Exactly six selected videos required')
    previous = None
    for index, (row, selected) in enumerate(zip(rows, SELECTION)):
        song, title, vid = selected
        channel = list(CHANNELS)[0 if index < 3 else 1]
        special = song == 'smile-for-you'
        kind = 'official_special_clip' if special else 'official_mv'
        source_title = row.get('sourceTitle', '')
        if ((row.get('songId'), row.get('title'), row.get('videoId')) != selected
                or row.get('channelId') != channel or row.get('channelName') != CHANNELS[channel]
                or row.get('url') != 'https://www.youtube.com/watch?v=' + vid
                or row.get('kind') != kind or row.get('privacyStatus') != 'public'
                or row.get('embeddable') is not True
                or type(row.get('durationSeconds')) is not int or not 120 <= row['durationSeconds'] <= 600
                or not isinstance(source_title, str) or len(source_title) > 300
                or '이세계아이돌' not in source_title or title.casefold() not in source_title.casefold()
                or (special and 'Special Clip' not in source_title)
                or (not special and not re.search(r'\bMV\b', source_title))
                or re.search(r'teaser|#shorts|official audio', source_title, re.I)):
            raise ValueError('Introductory video source mismatch')
        published = clock(row['publishedAt'])
        if published > checked or (previous is not None and published <= previous):
            raise ValueError('Video publication order or timestamp invalid')
        previous = published
    return doc


def load():
    return validate(json.loads((ROOT / 'catalog/music-beginning.json').read_text()))


def compose(data, available_videos, doc=None):
    """Change this series only. Shared songs, albums and video rows stay untouched."""
    doc = validate(doc) if doc is not None else load()
    series = [s for s in data['series'] if s['id'] == SERIES_ID]
    if len(series) != 1:
        raise ValueError('Expected one existing introductory series')
    songs = {s['id']: s for s in data['songs']}
    for row in doc['videos']:
        if songs.get(row['songId'], {}).get('videoId') != row['videoId']:
            raise ValueError('Existing official song binding mismatch')
        matches = [v for v in available_videos if v['id'] == row['videoId']]
        if (len(matches) != 1 or matches[0].get('url') != row['url']
                or matches[0].get('category') != 'group'
                or matches[0].get('channelName') != row['channelName']):
            raise ValueError('Existing official video missing or conflicting')
    result = deepcopy(data)
    selected = next(s for s in result['series'] if s['id'] == SERIES_ID)
    selected.update(title=TITLE, subtitle='공식 MV · 스페셜 클립',
        description='RE:WIND부터 REBELS까지, 이세계아이돌의 공식 MV와 스페셜 클립을 순서대로 만나보세요.',
        songIds=[], videoIds=[r['videoId'] for r in doc['videos']],
        officialVideos=deepcopy(doc['videos']), entryMode='youtube_original',
        basis='editorial', status='공식 원본 연결', checkedAt=doc['checkedAt'])
    assert all(result[k] == data[k] for k in data if k != 'series')
    assert [s for s in result['series'] if s['id'] != SERIES_ID] == [s for s in data['series'] if s['id'] != SERIES_ID]
    return result


def sharded_videos(out, data):
    rows = list(data['videos'])
    prefix = 'REVIEW_DATA.videos.push(...'
    for path in sorted((out / 'src').glob('video-part-*.js')):
        code = path.read_text()
        if not code.startswith(prefix) or not code.endswith(');\n'):
            raise ValueError('Unknown video shard format')
        rows.extend(json.loads(code[len(prefix):-3]))
    return rows


def adapt_app(code):
    code = one(code, 'function seriesView(id){',
               "function seriesView(id){if(id==='music-beginning')return musicBeginningView();")
    return one(code, 'if(!location.hash)history.replaceState',
               (ROOT / 'site/music-beginning.js').read_text() + '\nif(!location.hash)history.replaceState')
