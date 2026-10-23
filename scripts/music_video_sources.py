"""Apply a reviewed video selection without changing song identity or release metadata."""
from collections import Counter
from copy import deepcopy
import csv
from datetime import datetime
import json
from pathlib import Path
import re
from urllib.parse import urlsplit
ROOT = Path(__file__).resolve().parents[1]
KINDS = {'official_mv', 'official_audio', 'official_video', 'fan_backup', 'karaoke_tj', 'karaoke_ky', 'unavailable'}
VIDEO_ID = re.compile(r'[A-Za-z0-9_-]{11}')

def selections(root=ROOT):
    config = json.loads((root/'catalog/video-sources.json').read_text())
    if config.get('schemaVersion') != 1:
        raise ValueError('Unsupported music video schema')
    datetime.fromisoformat(config['checkedAt'])
    channels = config['channels']
    for channel in channels.values():
        u = urlsplit(channel['url'])
        if (u.scheme != 'https' or u.hostname != 'www.youtube.com' or u.username or u.password
                or u.query or u.fragment or not (u.path.startswith('/@') or u.path.startswith('/channel/'))
                or channel['role'] not in {'official', 'fan', 'karaoke'} or not channel['name'].strip()):
            raise ValueError('Invalid reviewed channel')
    rows = {}
    for row in csv.reader((root/'catalog/video-sources.tsv').read_text().splitlines(), delimiter='\t'):
        if not row or row[0].startswith('#'):
            continue
        if len(row) != 4:
            raise ValueError('Video selection needs four columns')
        sid, vid, kind, channel = row
        if sid in rows or kind not in KINDS:
            raise ValueError('Duplicate song or unknown video kind')
        if kind == 'unavailable':
            if (vid, channel) != ('-', '-') or not config['notes'].get(sid):
                raise ValueError('Unresolved song must have no selected video and a reason')
        else:
            if not VIDEO_ID.fullmatch(vid) or channel not in channels:
                raise ValueError('Invalid selected video')
            role = 'official' if kind.startswith('official_') else 'karaoke' if kind.startswith('karaoke_') else 'fan'
            if channels[channel]['role'] != role:
                raise ValueError('Video must not impersonate an official channel')
            # Every selected uploader is rechecked by check_music_video_sources.py.
            if kind.startswith('karaoke_') and not ('TJ' in channels[channel]['name'] or '금영' in channels[channel]['name'] or 'KY' in channels[channel]['name']):
                raise ValueError('Unverified karaoke provider')
        rows[sid] = {'videoId': None if vid == '-' else vid, 'kind': kind, 'channelKey': channel}
    return config, rows

def apply_video_sources(music, config=None, rows=None):
    if config is None or rows is None:
        config, rows = selections()
    if set(rows) != {s['id'] for s in music['songs']}:
        raise ValueError('Every catalogue song needs an explicit reviewed selection')
    result = deepcopy(music)
    for song in result['songs']:
        row = rows[song['id']]
        original = song.get('videoId')
        if original:
            song['originalVideoId'] = original
        if row['videoId']:
            song['videoId'] = row['videoId']
            song['url'] = 'https://www.youtube.com/watch?v=' + row['videoId']
        else:
            song.pop('videoId', None)
            song.pop('url', None)
        c = config['channels'].get(row['channelKey'], {})
        song['videoSource'] = {'kind': row['kind'], 'checkedAt': config['checkedAt'],
                               'channel': c.get('name'), 'channelUrl': c.get('url'),
                               'note': config['notes'].get(song['id'], '')}
    result['videoAudit'] = {'checkedAt': config['checkedAt'], 'songs': len(rows),
                            'linked': sum(bool(x['videoId']) for x in rows.values()),
                            'kinds': dict(Counter(x['kind'] for x in rows.values())),
                            'refresh': 'reviewed-snapshot', 'fullPlaybackVerified': False}
    return result
