"""Only the owner-selected M2 relay dance upload; preserve artist channels and official MV."""
from copy import deepcopy
from datetime import datetime, timezone, timedelta
from pathlib import Path
import json
from external_videos import MEMBERS, clock

ROOT = Path(__file__).resolve().parents[1]
VIDEO_ID = 'mkJRSPYjX8k'
CHANNEL_ID = 'UCTQVIXvcHrR9jYoJ6qaBAow'
CHANNEL_KEY = 'm2-relay-selected'
TITLE = '[릴레이댄스] 이세계아이돌(ISEGYE IDOL) - REBELS (4K)'
EXPECTED = {'id': 'mkJRSPYjX8k',
 'title': '[릴레이댄스] 이세계아이돌(ISEGYE IDOL) - REBELS (4K)',
 'publishedAt': '2026-11-16T09:00:17Z',
 'durationSeconds': 198,
 'privacyStatus': 'public',
 'embeddable': True,
 'type': 'external_performance',
 'performanceKind': 'relay_dance',
 'relatedSong': 'rebels',
 'qualityLabel': '4K',
 'qualityBasis': 'source_title'}
CHANNEL = {'key': 'm2-relay-selected',
 'name': 'M2',
 'channelId': 'UCTQVIXvcHrR9jYoJ6qaBAow',
 'url': 'https://www.youtube.com/channel/UCTQVIXvcHrR9jYoJ6qaBAow'}


def validate(doc, now=None):
    now = now or datetime.now(timezone.utc)
    if (doc.get('schemaVersion') != 1 or doc.get('selection') != 'owner_requested_video_ids'
            or doc.get('source') != 'YouTube Data API v3 videos.list'
            or doc.get('evidenceRun') != 44057788105 or doc.get('channel') != CHANNEL):
        raise ValueError('Unreviewed M2 relay channel or source')
    checked = clock(doc['checkedAt'])
    if checked > now or clock(EXPECTED['publishedAt']) > checked:
        raise ValueError('Invalid M2 relay verification time')
    rows = doc.get('videos')
    if not isinstance(rows, list) or len(rows) != 1 or rows[0] != EXPECTED:
        raise ValueError('Only the verified M2 relay upload is approved')
    if type(rows[0]['durationSeconds']) is not int or rows[0]['embeddable'] is not True:
        raise ValueError('Invalid metadata types')
    return doc


def load(root=ROOT):
    return validate(json.loads((root / 'catalog/m2-relay-videos.json').read_text()))


def compose(data, doc=None):
    doc = validate(doc) if doc is not None else load()
    result = deepcopy(data)
    if not any(s['id'] == 'rebels' and s.get('videoId') == 'y-klhPVFblg' for s in result['songs']):
        raise ValueError('Reviewed REBELS song and official MV must exist')
    channel = {**doc['channel'], 'kind': '외부 릴레이댄스', 'status': 'selected_verified',
               'checkedAt': doc['checkedAt'], 'coverageComplete': False,
               'coverageMode': 'selected_video_ids'}
    matches = [c for c in result['channels'] if c['key'] == CHANNEL_KEY]
    if len(matches) > 1:
        raise ValueError('Duplicate M2 relay channel')
    same = matches[0] if matches else None
    if same is None:
        result['channels'].append(channel)
    elif same != channel:
        raise ValueError('Conflicting M2 relay channel')
    source = doc['videos'][0]
    video = {**deepcopy(source), 'key': 'video:' + VIDEO_ID, 'kind': 'video',
             'date': clock(source['publishedAt']).astimezone(timezone(timedelta(hours=9))).date().isoformat(),
             'dateBasis': 'external_video_published', 'dateLabel': '영상 공개일',
             'url': 'https://www.youtube.com/watch?v=' + VIDEO_ID,
             'members': MEMBERS.copy(), 'memberBasis': 'explicit_group',
             'channelName': channel['name'], 'channelKey': CHANNEL_KEY,
             'channelUrl': channel['url'], 'category': 'external', 'format': '4K 릴레이댄스',
             'checkedAt': doc['checkedAt'], 'firstSeenAt': doc['checkedAt'],
             'summary': 'M2에서 공개한 이세계아이돌 REBELS 릴레이댄스 영상입니다. '
                        '이세계아이돌 공식 채널 업로드 및 기존 공식 MV와 구분합니다. '
                        '4K는 원본 제목의 표기 기준입니다.',
             'tags': ['REBELS', '레블스', 'Across Dimensions', 'M2', 'Mnet',
                      '릴레이댄스', '릴레이 댄스', 'Relay Dance', '외부 채널', '퍼포먼스'],
             'sourceLinks': [{'title': 'M2 · YouTube 원본', 'url': 'https://www.youtube.com/watch?v=' + VIDEO_ID},
                             {'title': '게시 채널 · M2', 'url': channel['url']}]}
    matches = [v for v in result['videos'] if v['id'] == VIDEO_ID]
    if len(matches) > 1:
        raise ValueError('Duplicate M2 relay video')
    known = matches[0] if matches else None
    if known is None:
        result['videos'].append(video)
    elif known != video:
        raise ValueError('Conflicting M2 relay video identity')
    result['scope']['selectedExternalVideoCount'] = sum(v.get('category') == 'external' for v in result['videos'])
    assert all(result[k] == data[k] for k in data if k not in ('videos', 'channels', 'scope'))
    assert all(result[k][:len(data[k])] == data[k] for k in ('videos', 'channels'))
    assert all(result['scope'][k] == v for k, v in data['scope'].items() if k != 'selectedExternalVideoCount')
    return result
