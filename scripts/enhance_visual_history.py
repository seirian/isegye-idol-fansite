"""Reviewed thumbnail rendering and source-backed history; feature preview only."""
from __future__ import annotations
from datetime import date
import json
import os
from pathlib import Path
import re
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
MEMBERS = {'ine', 'jingburger', 'lilpa', 'jururu', 'gosegu', 'viichan'}
TYPES = {'audition', 'release', 'performance', 'content', 'collaboration', 'award'}


def once(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise ValueError('Template anchor changed: ' + old[:90])
    return text.replace(old, new, 1)


def validate_history(data: dict) -> None:
    checked = date.fromisoformat(data['checkedAt'])
    sources = data['sources']
    seen = set()
    for key, source in sources.items():
        url = urlsplit(source['url'])
        if url.scheme != 'https' or url.username or url.password or url.hostname not in {'namu.wiki', 'cafe.naver.com', 'news.nate.com', 'parable-asia.com'}:
            raise ValueError('Unapproved history source: ' + key)
        if source['basis'] not in {'wiki', 'linked', 'official', 'press'}:
            raise ValueError('Unknown attribution type')
    for row in data['events']:
        if row['id'] in seen or row['type'] not in TYPES:
            raise ValueError('Duplicate event or invalid type')
        seen.add(row['id'])
        start = date.fromisoformat(row['date'])
        end = date.fromisoformat(row.get('endDate', row['date']))
        if not date(2021, 1, 1) <= start <= end <= checked:
            raise ValueError('Unverified event date')
        if not set(row['members']) <= MEMBERS or len(row['members']) != len(set(row['members'])):
            raise ValueError('Invalid event participants')
        if not row['sources'] or any(key not in sources for key in row['sources']):
            raise ValueError('Missing source')
        if all(sources[key]['basis'] == 'linked' for key in row['sources']):
            raise ValueError('Unretrieved related link is not sufficient evidence')
        if not row['title'].strip():
            raise ValueError('Empty event title')


def enhance_visual_history(out: Path, app: str, css: str, html: str) -> tuple[str, str, str]:
    if os.environ.get('DEPLOY_ENV') == 'production':
        raise RuntimeError('Visual/history changes remain a feature preview.')
    history = json.loads((ROOT / 'visuals/history.json').read_text())
    validate_history(history)
    # Consulting provenance remains in source control, not in the visitor UI.
    public = {**history, 'sources': {key: {k: v for k, v in s.items() if k != 'consultedUrl'} for key, s in history['sources'].items()}}
    data_path = out / 'src/data.js'
    data = data_path.read_text()
    data = once(data, "  {id:'videos',name:'방송·영상',icon:'video',en:'ON AIR & VIDEO'},\n", '')
    data = data.replace('입문·멤버에서', '멤버 소개에서')
    # Remove the retired view, navigation and home tile. Legacy deep links resolve to LIVE.
    a, b = app.index('function videosView('), app.index('function historyView(')
    if b <= a:
        raise ValueError('Retired view order changed')
    app = app[:a] + app[b:]
    a, b = app.index('function historyView('), app.index('function scheduleView(')
    if b <= a:
        raise ValueError('History template order changed')
    app = app[:a] + 'function historyView(params){return archiveHistoryView(params);}\n' + app[b:]
    app = once(app, 'videos:videosView,', '')
    app = once(app, "const page=parts[0]==='dictionary'?'live':parts[0]||'home';", "const page=['dictionary','videos'].includes(parts[0])?'live':parts[0]||'home';")
    tile = re.compile(r'<a class="explore-card violet" href="#/videos">.*?</a>')
    if len(tile.findall(app)) != 1:
        raise ValueError('Ambiguous video navigation tile')
    app = tile.sub('', app)
    app = app.replace("video:'videos'", "video:'live'").replace('href="#/videos"', 'href="#/live"')
    for old, new in [('02 / LIVE', '01 / LIVE'), ('03 / REMEMBER', '02 / REMEMBER'), ('04 / TOGETHER', '03 / TOGETHER'), ('음악 · 행사 · 협업 타임라인', '2021년부터 함께한 발자취')]:
        app = app.replace(old, new)
    mirror = "${s.consultedUrl?`<span>·</span>${external(s.consultedUrl,'확인본(미러)')}`:''}"
    if app.count(mirror) != 2:
        raise ValueError('Attribution renderer changed')
    app = app.replace(mirror, '')
    # A broadcast ID is taken only from a current, validated channel response.
    app = once(app, "return {...result,state:'live',broadcastId:String(no),title:liveText(broad.broad_title),", "return {...result,state:'live',broadcastId:String(no),title:liveText(broad.broad_title),mediaRestricted:Number(broad.broad_grade)>=19||broad.is_password==='Y'||String(broad.subscription_only)==='1',")
    app = once(app, '${liveImage(m)}<span class="live-card-label">', '${visualLiveArt(r,m)}<span class="live-card-label">')
    app = once(app, '${liveImage(m)}<span><strong>${m.name}</strong>', '${visualMiniArt(r,m)}<span><strong>${m.name}</strong>')
    # Keep existing metadata and abstract art as fallback; only replace the image area.
    a, b = app.index('function catalogSongCard(s){'), app.index('function catalogMusicView(')
    func = app[a:b]
    start = func.index('<div class="catalog-song-art ')
    end = func.index('<div class="catalog-song-copy">', start)
    art = func[start:end]
    func = func[:start] + '${visualSongArt(s,`' + art + '`)}' + func[end:]
    app = app[:a] + func + app[b:]
    app = once(app, '<span class="catalog-muted">목록용 그래픽 · 공식 앨범 커버 아님</span>', '<span class="catalog-muted">${visualMusicThumbnail(s)?\'YouTube 영상 썸네일\':\'목록용 그래픽 · 공식 앨범 커버 아님\'}</span>')
    app = app.replace('LIVE와 홈 화면은 SOOP에 공개 방송 상태를 직접 요청합니다.', 'LIVE와 홈 화면은 SOOP에 공개 방송 상태를 직접 요청하며, 방송 미리보기는 SOOP 이미지 서버에서 불러옵니다.')
    core = re.sub(r'^export ', '', (ROOT / 'visuals/core.js').read_text(), flags=re.M)
    app = once(app, 'shell();render();', 'const HISTORY=' + json.dumps(public, ensure_ascii=False, separators=(',', ':')) + ';\n' + core + '\n' + (ROOT / 'visuals/ui.js').read_text() + '\nshell();render();')
    app = once(app, '<span class="music-video-label">YouTube</span>', '<span class="music-video-label">${e(musicVideoLabel(s))}</span>')
    css += '\n' + (ROOT / 'visuals/theme.css').read_text()
    html = once(html, "img-src 'self' data: https://i.ytimg.com", "img-src 'self' data: https://i.ytimg.com https://liveimg.sooplive.com")
    html = once(html, '<html ', '<html data-visual-history="true" ')
    if '확인본(미러)' in app or 'href="#/videos"' in app or "id:'videos'" in data:
        raise ValueError('Retired visitor UI remains')
    meta_path = out / 'build-info.json'
    meta = json.loads(meta_path.read_text())
    meta['visualHistory'] = {'version': 1, 'historyItems': len(history['events']), 'historyFrom': min(r['date'] for r in history['events']), 'checkedAt': history['checkedAt'], 'liveThumbnail': 'current-broadcast-only', 'musicThumbnails': 'YouTube-video-id', 'navigationCount': 7}
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + '\n')
    for path, text in [(data_path, data), (out / 'src/app.js', app), (out / 'src/styles.css', css), (out / 'index.html', html)]:
        path.write_text(text, encoding='utf-8')
    return app, css, html
