"""One verified IRISE/LILPA collaboration replay, never a group performance or channel feed."""
from copy import deepcopy
from datetime import datetime, timezone, timedelta
from pathlib import Path
import json
from external_videos import clock

ROOT = Path(__file__).resolve().parents[1]
VIDEO_ID = 'P15VglxEkss'
CHANNEL_ID = 'UCMmcz1ybSoAD-GUlDx_7H2A'
CHANNEL_KEY = 'irise-collab-selected'
EXPECTED = {'id': 'P15VglxEkss',
 'title': '[IRISÉ LIVE] 오늘은 릴파 선배님과 함께! 🩵💙',
 'publishedAt': '2026-11-16T10:45:19Z',
 'durationSeconds': 5731,
 'privacyStatus': 'public',
 'embeddable': True,
 'definition': 'hd',
 'regionRestriction': {'blocked': ['RU']},
 'liveBroadcastContent': 'none',
 'liveStreamingDetails': {'actualStartTime': '2026-11-16T09:04:24Z',
                          'actualEndTime': '2026-11-16T10:39:58Z',
                          'scheduledStartTime': '2026-11-16T09:00:00Z'},
 'type': 'external_collaboration',
 'recordingKind': 'livestream_archive'}
CHANNEL = {'key': 'irise-collab-selected',
 'name': 'IRISÉ',
 'channelId': 'UCMmcz1ybSoAD-GUlDx_7H2A',
 'url': 'https://www.youtube.com/channel/UCMmcz1ybSoAD-GUlDx_7H2A'}


def validate(doc, now=None):
    now = now or datetime.now(timezone.utc)
    if (doc.get('schemaVersion') != 1 or doc.get('selection') != 'owner_requested_video_ids'
            or doc.get('source') != 'YouTube Data API v3 videos.list'
            or doc.get('evidenceRun') != 44108855400 or doc.get('channel') != CHANNEL):
        raise ValueError('Unreviewed IRISE collaboration channel or source')
    checked = clock(doc['checkedAt'])
    if checked > now or clock(EXPECTED['publishedAt']) > checked:
        raise ValueError('Invalid collaboration verification time')
    rows = doc.get('videos')
    if not isinstance(rows, list) or len(rows) != 1 or rows[0] != EXPECTED:
        raise ValueError('Only the verified IRISE collaboration is approved')
    if type(rows[0]['durationSeconds']) is not int or rows[0]['embeddable'] is not True:
        raise ValueError('Invalid metadata types')
    return doc


def load(root=ROOT):
    return validate(json.loads((root / 'catalog/irise-lilpa-videos.json').read_text(encoding='utf-8')))


def compose(data, doc=None):
    doc = validate(doc) if doc is not None else load()
    result = deepcopy(data)
    channel = {**doc['channel'], 'kind': '외부 합방', 'status': 'selected_verified',
               'checkedAt': doc['checkedAt'], 'coverageComplete': False,
               'coverageMode': 'selected_video_ids'}
    matches = [c for c in result['channels'] if c['key'] == CHANNEL_KEY]
    if len(matches) > 1 or (matches and matches[0] != channel):
        raise ValueError('Conflicting or duplicate IRISE channel')
    if not matches:
        result['channels'].append(channel)
    source = doc['videos'][0]
    video = {**deepcopy(source), 'key': 'video:' + VIDEO_ID, 'kind': 'video',
             'date': clock(source['publishedAt']).astimezone(timezone(timedelta(hours=9))).date().isoformat(),
             'dateBasis': 'external_video_published', 'dateLabel': '영상 공개일',
             'url': 'https://www.youtube.com/watch?v=' + VIDEO_ID,
             'members': ['lilpa'], 'memberBasis': 'explicit_credit',
             'externalGuests': ['키리', '티즈'], 'guestBasis': 'source_description_hashtags',
             'channelName': channel['name'], 'channelKey': CHANNEL_KEY,
             'channelUrl': channel['url'], 'category': 'external', 'format': '합방 다시보기',
             'checkedAt': doc['checkedAt'], 'firstSeenAt': doc['checkedAt'],
             'summary': 'IRISÉ(아이리제) 채널에서 공개한 릴파와 키리·티즈의 합방 다시보기입니다. '
                        '원본 제목·설명에 안내된 신곡 챌린지와 K-POP 랜덤 플레이 댄스 합방으로 분류했습니다. '
                        '방송 시작은 2026년 11월 16일 18:04:24, 영상 공개는 같은 날 19:45:19(한국시간)입니다. '
                        '이세계아이돌 단체 무대나 공식 MV와 구분하며, 러시아 지역에서는 원본 시청이 제한됩니다.',
             'tags': ['IRISÉ', 'IRISE', '아이리제', '릴파', 'LILPA', '키리', 'KIIRI', '티즈', 'TIZ',
                      '합방', '합동 방송', '다시보기', '신곡 챌린지', 'K-POP', '랜덤 플레이 댄스', '외부 채널'],
             'sourceLinks': [{'title': 'IRISÉ · YouTube 원본', 'url': 'https://www.youtube.com/watch?v=' + VIDEO_ID},
                             {'title': '게시 채널 · IRISÉ', 'url': channel['url']},
                             {'title': 'IRISÉ 공식 위버스 · 합방 안내', 'url': 'https://weverse.io/irise/live/0-181588285?hl=ko'}]}
    matches = [v for v in result['videos'] if v['id'] == VIDEO_ID]
    if len(matches) > 1 or (matches and matches[0] != video):
        raise ValueError('Conflicting or duplicate IRISE video identity')
    if not matches:
        result['videos'].append(video)
    result['scope']['selectedExternalVideoCount'] = sum(v.get('category') == 'external' for v in result['videos'])
    assert all(result[k] == data[k] for k in data if k not in ('videos', 'channels', 'scope'))
    assert all(result[k][:len(data[k])] == data[k] for k in ('videos', 'channels'))
    assert all(result['scope'][k] == v for k, v in data['scope'].items() if k != 'selectedExternalVideoCount')
    return result
