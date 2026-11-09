"""Reviewed release additions shared by the music, album and source-audit paths.
Base catalog bytes and already reviewed source timestamps are never rewritten.
"""
from copy import deepcopy
from datetime import datetime
from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parents[1]

def releases(root=ROOT):
    path = root/'catalog/album-releases.json'
    if not path.exists():
        return []
    doc = json.loads(path.read_text())
    if doc.get('schemaVersion') != 1 or not isinstance(doc.get('releases'), list):
        raise ValueError('Invalid reviewed release catalog')
    ids, videos = set(), set()
    for release in doc['releases']:
        if (not re.fullmatch(r'[a-z0-9-]+', release['id'])
                or not re.fullmatch(r'\d+', release['melonAlbumId'])
                or release['source'] != 'https://www.melon.com/album/detail.htm?albumId='+release['melonAlbumId']
                or datetime.fromisoformat(release['checkedAt']).tzinfo is None
                or datetime.strptime(release['date'], '%Y-%m-%d').date().isoformat() != release['date']
                or not release['tracks']):
            raise ValueError('Unverified release identity')
        for track in release['tracks']:
            if (track['id'] in ids or track['videoId'] in videos
                    or not re.fullmatch(r'[a-z0-9-]+', track['id'])
                    or not re.fullmatch(r'[A-Za-z0-9_-]{11}', track['videoId'])
                    or track['kind'] not in ('official_mv', 'official_audio')
                    or track['channelKey'] != 'c2'):
                raise ValueError('Invalid release track binding')
            ids.add(track['id']); videos.add(track['videoId'])
    return doc['releases']

def load_catalog(root=ROOT):
    music = json.loads((root/'catalog/music.json').read_text())
    known = {s['id'] for s in music['songs']}
    for release in releases(root):
        source_id = 'release-'+release['id']
        music['sources'][source_id] = {'id': source_id, 'title': '멜론 · '+release['title'],
                                     'url': release['source'], 'checkedAt': release['checkedAt']}
        titles = [t['title'] for t in release['tracks']]
        for track in release['tracks']:
            if track['id'] in known:
                raise ValueError('Release track duplicates base catalog')
            known.add(track['id'])
            row = {k: deepcopy(track[k]) for k in ('id', 'title', 'aliases', 'videoId', 'titleTrack') if k in track}
            row.update(type='original', scope='group', members=release['members'], date=release['date'],
                       dateKind='발매일', album=release['title'], format=release['format'], context='standard',
                       sources=[source_id], albumTracks=titles)
            music['songs'].append(row)
    return music

def video_bindings(root=ROOT):
    return {t['id']: {k: t[k] for k in ('videoId', 'kind', 'channelKey')} | {'checkedAt': r['checkedAt']}
            for r in releases(root) for t in r['tracks']}

def extend_music(music):
    """Add reviewed releases after the approved legacy build, preserving every old row."""
    result=deepcopy(music)
    config=json.loads((ROOT/'catalog/video-sources.json').read_text())
    channel=config['channels']['c2']
    if channel['role']!='official' or channel['url']!='https://www.youtube.com/@isegyeidol_ofcl':
        raise ValueError('Official release channel changed')
    catalog=load_catalog();bindings=video_bindings()
    known={s['id'] for s in result['songs']};videos={s.get('videoId') for s in result['songs']}
    for row in catalog['songs']:
        if row['id'] not in bindings:continue
        if row['id'] in known or row['videoId'] in videos:raise ValueError('Release already composed or duplicate video')
        source=bindings[row['id']]
        row=deepcopy(row)
        row.update(url='https://www.youtube.com/watch?v='+row['videoId'],originalVideoId=row['videoId'],
            videoSource={'kind':source['kind'],'checkedAt':source['checkedAt'],'channel':channel['name'],'channelUrl':channel['url'],'note':''})
        result['songs'].append(row)
        for key in row['sources']:result['sources'][key]=catalog['sources'][key]
    from collections import Counter
    audit=result.setdefault('videoAudit',{})
    audit.update(songs=len(result['songs']),linked=sum(bool(s.get('videoId')) for s in result['songs']),
        kinds=dict(Counter(s.get('videoSource',{}).get('kind','unavailable') for s in result['songs'])))
    return result

def compose_review(data, music):
    """Append to the operating REVIEW_DATA only; baseline and approved UI stay intact."""
    import hashlib
    result=deepcopy(data);known={s['id'] for s in result['songs']};album_ids={a['id'] for a in result['albums']}
    bindings=video_bindings()
    for release in releases():
        aid=hashlib.sha256((release['title']+'|'+','.join(sorted(release['members']))).encode()).hexdigest()[:12]
        if aid in album_ids:raise ValueError('Release album already composed')
        album_ids.add(aid);added=[]
        for row in music['songs']:
            if row['id'] not in {t['id'] for t in release['tracks']}:continue
            if row['id'] in known:raise ValueError('Review song already composed')
            known.add(row['id'])
            song={**deepcopy(row),'kind':'song','key':'song:'+row['id'],'albumId':aid,
                'summary':release['title'],'tags':row.get('aliases',[])+row['albumTracks'],
                'checkedAt':bindings[row['id']]['checkedAt'],
                'sourceLinks':[music['sources'][k] for k in row['sources']]}
            result['songs'].append(song);added.append(song['id'])
        result['albums'].append({'id':aid,'title':release['title'],'kind':'album','key':'album:'+aid,
            'date':release['date'],'members':release['members'],'songIds':added,
            'tracks':[t['title'] for t in release['tracks']],'format':release['format'],
            'sourceLinks':[music['sources']['release-'+release['id']]]})
    return result
