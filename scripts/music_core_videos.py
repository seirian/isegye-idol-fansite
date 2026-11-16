"""Only the owner-selected MBC upload; preserve artist channels and official MV."""
from copy import deepcopy
from datetime import datetime, timezone, timedelta
from pathlib import Path
import json
from external_videos import MEMBERS, clock

ROOT = Path(__file__).resolve().parents[1]
VIDEO_ID = 'sy40EGkSfRA'
CHANNEL_ID = 'UCe52oeb7Xv_KaJsEzcKXJJg'
CHANNEL_KEY = 'mbc-music-core-selected'
TITLE = 'ISEGYE IDOL (이세계아이돌) - REBELS | Show! MusicCore | MBC261114방송'
EXPECTED = {
    'id': VIDEO_ID, 'title': TITLE, 'publishedAt': '2026-11-14T06:37:04Z',
    'durationSeconds': 188, 'type': 'external_performance',
    'performanceKind': 'music_broadcast', 'relatedSong': 'rebels',
    'program': '쇼! 음악중심', 'broadcastDate': '2026-11-14',
    'broadcastDateBasis': 'source_title', 'privacyStatus': 'public',
    'embeddable': True, 'definition': 'hd', 'regionRestriction': {'blocked': ['JP']},
}
CHANNEL = {'key': CHANNEL_KEY, 'name': 'MBCkpop', 'channelId': CHANNEL_ID,
           'url': 'https://www.youtube.com/channel/' + CHANNEL_ID}


def validate(doc, now=None):
    now = now or datetime.now(timezone.utc)
    if (doc.get('schemaVersion') != 1 or doc.get('selection') != 'owner_requested_video_ids'
            or doc.get('source') != 'YouTube Data API v3 videos.list'
            or doc.get('evidenceRun') != 43573401740 or doc.get('channel') != CHANNEL):
        raise ValueError('Unreviewed Music Core channel or source')
    checked = clock(doc['checkedAt'])
    if checked > now or clock(EXPECTED['publishedAt']) > checked:
        raise ValueError('Invalid Music Core verification time')
    rows = doc.get('videos')
    if not isinstance(rows, list) or len(rows) != 1 or rows[0] != EXPECTED:
        raise ValueError('Only the verified Music Core upload is approved')
    if type(rows[0]['durationSeconds']) is not int or rows[0]['embeddable'] is not True:
        raise ValueError('Invalid metadata types')
    return doc


def load(root=ROOT):
    return validate(json.loads((root / 'catalog/music-core-videos.json').read_text()))


def compose(data, doc=None):
    doc = validate(doc) if doc is not None else load()
    result = deepcopy(data)
    if not any(s['id'] == 'rebels' and s.get('videoId') == 'y-klhPVFblg' for s in result['songs']):
        raise ValueError('Reviewed REBELS song and official MV must exist')
    channel = {**doc['channel'], 'kind': '외부 음악방송', 'status': 'selected_verified',
               'checkedAt': doc['checkedAt'], 'coverageComplete': False,
               'coverageMode': 'selected_video_ids'}
    same = next((c for c in result['channels'] if c['key'] == CHANNEL_KEY), None)
    if same is None:
        result['channels'].append(channel)
    elif same != channel:
        raise ValueError('Conflicting Music Core channel')
    source = doc['videos'][0]
    video = {**deepcopy(source), 'key': 'video:' + VIDEO_ID, 'kind': 'video',
             'date': clock(source['publishedAt']).astimezone(timezone(timedelta(hours=9))).date().isoformat(),
             'dateBasis': 'external_video_published', 'dateLabel': '영상 공개일',
             'url': 'https://www.youtube.com/watch?v=' + VIDEO_ID,
             'members': MEMBERS.copy(), 'memberBasis': 'explicit_group',
             'channelName': channel['name'], 'channelKey': CHANNEL_KEY,
             'channelUrl': channel['url'], 'category': 'external', 'format': '음악방송 무대',
             'checkedAt': doc['checkedAt'], 'firstSeenAt': doc['checkedAt'],
             'summary': 'MBCkpop에서 공개한 2026년 11월 14일 쇼! 음악중심 REBELS 무대입니다. '
                        '이세계아이돌 공식 채널 업로드 및 기존 공식 MV와 구분합니다. '
                        'YouTube 원본은 일본 지역에서 시청이 제한됩니다.',
             'tags': ['REBELS', '레블스', 'Across Dimensions', 'MBCkpop', 'MBC',
                      '쇼! 음악중심', '음악중심', 'Show! MusicCore', '외부 채널', '음악방송', '무대'],
             'sourceLinks': [{'title': 'MBCkpop · YouTube 원본', 'url': 'https://www.youtube.com/watch?v=' + VIDEO_ID},
                             {'title': '게시 채널 · MBCkpop', 'url': channel['url']}]}
    known = next((v for v in result['videos'] if v['id'] == VIDEO_ID), None)
    if known is None:
        result['videos'].append(video)
    elif known != video:
        raise ValueError('Conflicting Music Core video identity')
    result['scope']['selectedExternalVideoCount'] = sum(v.get('category') == 'external' for v in result['videos'])
    assert all(result[k] == data[k] for k in data if k not in ('videos', 'channels', 'scope'))
    assert all(result[k][:len(data[k])] == data[k] for k in ('videos', 'channels'))
    assert all(result['scope'][k] == v for k, v in data['scope'].items() if k != 'selectedExternalVideoCount')
    return result
