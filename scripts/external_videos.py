"""Selected external uploads only. Never authorize channel-wide collection or replace an MV."""
from copy import deepcopy
from datetime import datetime, timezone, timedelta
from pathlib import Path
import json
from review_2nd_polish import one

ROOT = Path(__file__).resolve().parents[1]
CHANNEL_ID = 'UCEIi7zFR_wE23jFncVtd6-A'
CHANNEL_KEY = 'studio-choom-selected'
MEMBERS = ['ine', 'jingburger', 'lilpa', 'jururu', 'gosegu', 'viichan']
APPROVED = {
    '_E9ZHH9R7o4': ('external_teaser', '2026-11-10T13:00:38Z', 31),
    'z8AJgnTC52k': ('external_performance', '2026-11-11T13:00:27Z', 192),
}
TITLE = "ISEGYE IDOL(이세계아이돌) 'REBELS' (4K) | MOVE TO PERFORMANCE"


def clock(value):
    value = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if value.tzinfo is None:
        raise ValueError('Video timestamp needs timezone')
    return value


def validate(doc, now=None):
    now = now or datetime.now(timezone.utc)
    channel = doc.get('channel', {})
    if (doc.get('schemaVersion') != 1 or doc.get('selection') != 'owner_requested_video_ids'
            or doc.get('source') != 'YouTube Data API v3 videos.list'
            or channel.get('key') != CHANNEL_KEY or channel.get('channelId') != CHANNEL_ID
            or channel.get('name') != 'STUDIO CHOOM [스튜디오 춤]'
            or channel.get('url') != 'https://www.youtube.com/channel/' + CHANNEL_ID):
        raise ValueError('Unreviewed external channel or source')
    checked = clock(doc['checkedAt'])
    if checked > now:
        raise ValueError('Future verification')
    rows = doc.get('videos')
    if not isinstance(rows, list) or len(rows) != len(APPROVED):
        raise ValueError('Only the requested two videos are approved')
    seen = set()
    for row in rows:
        vid = row.get('id')
        if vid in seen or vid not in APPROVED:
            raise ValueError('Duplicate or unapproved video')
        seen.add(vid)
        kind, published, seconds = APPROVED[vid]
        title = ('(Teaser) ' if kind == 'external_teaser' else '') + TITLE
        if (row.get('type') != kind or row.get('title') != title
                or row.get('publishedAt') != published or clock(published) > checked
                or type(row.get('durationSeconds')) is not int or row['durationSeconds'] != seconds
                or row.get('relatedSong') != 'rebels' or row.get('privacyStatus') != 'public'
                or row.get('embeddable') is not True or row.get('qualityLabel') != '4K'
                or row.get('qualityBasis') != 'source_title'):
            raise ValueError('External video evidence mismatch')
    return doc


def load(root=ROOT):
    return validate(json.loads((root / 'catalog/external-videos.json').read_text()))


def compose(data, doc=None):
    doc = validate(doc) if doc is not None else load()
    result = deepcopy(data)
    if not any(s['id'] == 'rebels' and s.get('videoId') == 'y-klhPVFblg' for s in result['songs']):
        raise ValueError('Reviewed REBELS track and official MV must exist')
    channel = {**doc['channel'], 'kind': '외부 퍼포먼스', 'status': 'selected_verified',
               'checkedAt': doc['checkedAt'], 'coverageComplete': False,
               'coverageMode': 'selected_video_ids'}
    same = next((c for c in result['channels'] if c['key'] == CHANNEL_KEY), None)
    if same is None:
        result['channels'].append(channel)
    elif same != channel:
        raise ValueError('Conflicting selected channel')
    known = {v['id']: v for v in result['videos']}
    for source in doc['videos']:
        teaser = source['type'] == 'external_teaser'
        video = {**source, 'key': 'video:' + source['id'], 'kind': 'video',
                 'date': clock(source['publishedAt']).astimezone(timezone(timedelta(hours=9))).date().isoformat(),
                 'dateBasis': 'external_video_published', 'dateLabel': '영상 공개일',
                 'url': 'https://www.youtube.com/watch?v=' + source['id'],
                 'members': MEMBERS.copy(), 'memberBasis': 'explicit_group',
                 'channelName': channel['name'], 'channelKey': CHANNEL_KEY,
                 'channelUrl': channel['url'], 'category': 'external',
                 'format': '4K 퍼포먼스 티저' if teaser else '4K 퍼포먼스',
                 'checkedAt': doc['checkedAt'], 'firstSeenAt': doc['checkedAt'],
                 'summary': 'STUDIO CHOOM에서 공개한 REBELS 퍼포먼스 ' + ('티저' if teaser else '본편') +
                     '입니다. 이세계아이돌 공식 채널 업로드 및 기존 공식 MV와 구분합니다. 4K는 원본 제목의 표기 기준입니다.',
                 'tags': ['REBELS', '레블스', 'Across Dimensions', 'STUDIO CHOOM', '스튜디오 춤',
                          'MOVE TO PERFORMANCE', '외부 채널', '티저' if teaser else '퍼포먼스'],
                 'sourceLinks': [{'title': channel['name'] + ' · YouTube 원본',
                                  'url': 'https://www.youtube.com/watch?v=' + source['id']},
                                 {'title': '게시 채널 · ' + channel['name'], 'url': channel['url']}]}
        if source['id'] not in known:
            result['videos'].append(video)
        elif known[source['id']] != video:
            raise ValueError('Conflicting video identity')
    result['scope']['selectedExternalVideoCount'] = len(doc['videos'])
    # No songs, albums, statistics, scheduled collectors or reviewed sources are modified.
    assert all(result[k] == data[k] for k in data if k not in ('videos', 'channels', 'scope'))
    assert all(result[k][:len(data[k])] == data[k] for k in ('videos', 'channels'))
    assert all(result['scope'][k] == v for k, v in data['scope'].items())
    return result


def adapt_app(code):
    # Applied to the operating composition, never the hash-pinned review sources.
    a = code.index('function contentView(p)'); b = code.index('function videoView(id)', a)
    content = code[a:b]
    content = one(content, "['member','멤버 채널']", "['member','멤버 채널'],['external','외부 채널']")
    content = one(content, '${pg.html}<p class="data-note">',
                  '${pg.html}${tab===\'videos\'?\'<p class="data-note">외부 채널은 개별 확인한 영상만 수록하며, 해당 채널 전체를 수집하지 않습니다.</p>\':\'\'}<p class="data-note">')
    code = code[:a] + content + code[b:]
    code = one(code, "D.videos.filter(v=>v.category==='group')",
               "D.videos.filter(v=>v.category==='group'||v.type==='external_performance')")
    a = code.index('function mediaCard(r)'); b = code.index('function rowCard(r)', a)
    card = one(code[a:b], '${esc(memberText(r.members))}</p>',
               '${esc(memberText(r.members))}</p>${r.category===\'external\'?\'<p class="small muted">외부 채널 · \'+esc(r.channelName)+\'</p>\':\'\'}')
    code = code[:a] + card + code[b:]
    a = code.index('function videoView(id)'); b = code.index('function seriesView(id)', a)
    video = one(code[a:b], "${seq?`<section", "${externalPerformanceLinks(v.relatedSong,v.id)}${seq?`<section")
    video = one(video, '${esc(v.dateLabel||\'영상 공개일\')} ·',
                '${esc(v.dateLabel||\'영상 공개일\')}${v.category===\'external\'?\' · \'+Math.floor(v.durationSeconds/60)+\':\'+String(v.durationSeconds%60).padStart(2,\'0\'):\'\'} ·')
    code = code[:a] + video + code[b:]
    code = one(code, '${aiPeaks(s)}${aiSongFacts(s)}', '${aiPeaks(s)}${aiSongFacts(s)}${externalPerformanceLinks(s.id)}')
    helper = (ROOT / 'site/external-videos.js').read_text()
    return one(code, 'if(!location.hash)history.replaceState', helper + '\nif(!location.hash)history.replaceState')
