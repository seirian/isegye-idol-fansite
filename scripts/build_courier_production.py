#!/usr/bin/env python3
"""Pack the Courier campaign for offline review or the existing playground route."""
from pathlib import Path
import argparse
import base64
import hashlib
import json
import os
import re
from build_rpg import packed_game_fonts, source_bytes

ROOT=Path(__file__).resolve().parents[1]
HTML_PATH='games/starlight-courier/index.html'
ROUTE='/games/starlight-courier/'
STORAGE_KEY='isegye:playground:courier:v2'
BASE_COMMIT='34f26ed647453050c38d6c1df004ecacb0f0dbb7'
MAX_HTML_BYTES=8*1024*1024
STAGE_ART=('plaza', *(f'stage{i:02d}' for i in range(2,11)))
ART_NAMES=('characters','standing','walk','items','bosses','gear',*STAGE_ART)
SOURCES=('fangames/index.html','fangames/styles.css','fangames/engine.js','fangames/renderer.js','fangames/app.js')
CARD_ASSETS=('characters','plaza')


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def once(source,old,new):
    if source.count(old)!=1:
        raise ValueError('Courier production anchor changed: '+old[:70])
    return source.replace(old,new,1)


def target(out,relative):
    path=out/relative
    for part in (path,*path.parents):
        if part==out.parent:break
        if part.is_symlink() or (os.name=='nt' and part.resolve()!=part.absolute()):
            raise ValueError('Courier output symlink')
    if not path.resolve().is_relative_to(out.resolve()):raise ValueError('Courier output escaped release')
    path.parent.mkdir(parents=True,exist_ok=True)
    return path


def render(*, preview=False):
    data={}
    for relative in (*SOURCES,*(f'fangames/assets/{name}.webp' for name in ART_NAMES)):
        file=ROOT/relative
        if not file.is_file() or file.is_symlink() or not file.resolve().is_relative_to(ROOT):
            raise ValueError('Invalid Courier source: '+relative)
        data[relative]=file.read_text(encoding='utf-8').encode() if relative in SOURCES else file.read_bytes()
    html=data['fangames/index.html'].decode()
    css=data['fangames/styles.css'].decode()
    app=data['fangames/app.js'].decode()
    if not preview:
        html=once(html,'이세돌 별빛 배송부 · 팬게임 검토본','이세돌 별빛 배송부 · 놀이터')
        html=once(html,'<a class="wordmark" href="https://isegye-idol.kr/#/playground">ISEGYE<span>✦</span></a>',
                  '<a class="wordmark" href="/#/playground">← 놀이터</a>')
        html=once(html,'미니게임 검토본','미니게임')
        html=once(html,'비공식 이세계아이돌 팬게임 · 검토 전용','비공식 이세계아이돌 팬게임')
        app=once(app,"const key = 'isegye:review:courier:v2';",f"const key = '{STORAGE_KEY}';")
    art={}
    for name in ART_NAMES:
        raw=data[f'fangames/assets/{name}.webp']
        if not 1000<len(raw)<4*1024*1024 or raw[:4]!=b'RIFF' or raw[8:12]!=b'WEBP':
            raise ValueError('Invalid generated WebP: '+name)
        art[name]='data:image/webp;base64,'+base64.b64encode(raw).decode()
    font_source='rpg/fonts.js'
    data[font_source]=source_bytes(ROOT,font_source).decode().replace('\r\n','\n').encode()
    # The Courier host uses a classic inline script. The RPG module exports these functions.
    font_loader=re.sub(r'^export (?=function )','',data[font_source].decode(),flags=re.MULTILINE)
    js='\n'.join(('const COURIER_ART=Object.freeze('+json.dumps(art,separators=(',',':'))+');',
                  packed_game_fonts(ROOT,data),font_loader,
                  data['fangames/engine.js'].decode(),data['fangames/renderer.js'].decode(),app,''))
    if '\x00' in css+js or re.search(r'</(?:script|style)',css+js,re.I):
        raise ValueError('Unsafe inline source')
    sha=lambda text:base64.b64encode(hashlib.sha256(text.encode()).digest()).decode()
    csp=("default-src 'none'; script-src 'sha256-"+sha(js)+"'; style-src 'sha256-"+sha(css)+
         "'; connect-src 'none'; img-src data:; media-src 'none'; font-src 'none'; base-uri 'none'; form-action 'none'; object-src 'none'")
    html=once(html,'<!--CSP-->','<meta http-equiv="Content-Security-Policy" content="'+csp+'">')
    html=once(html,'<!--STYLE-->','<style>'+css+'</style>')
    html=once(html,'<!--SCRIPT-->','<script>'+js+'</script>')
    if not preview and any(marker in html for marker in ('isegye:review:courier:','검토본','검토 전용')):
        raise ValueError('Preview identity leaked into production game')
    raw=html.encode()
    if not 30000<len(raw)<=MAX_HTML_BYTES:raise ValueError('Courier HTML size')
    return raw,data


def build(out=None):
    out=Path(out) if out is not None else ROOT/'dist'
    if not out.is_dir() or out.is_symlink():raise ValueError('Existing release directory required')
    release=json.loads((out/'build-info.json').read_text())
    if release.get('mode') not in ('preview','production'):raise ValueError('Known release mode required')
    if release['mode']=='production' and os.getenv('GITHUB_REF')!='refs/heads/main':
        raise ValueError('Main-only production')
    raw,data=render()
    target(out,HTML_PATH).write_bytes(raw)
    cards={}
    for name in CARD_ASSETS:
        relative=f'assets/courier/{name}.webp'
        target(out,relative).write_bytes(data[f'fangames/assets/{name}.webp'])
        cards[relative]=digest(data[f'fangames/assets/{name}.webp'])
    return {'game':'starlight-courier','version':3,'baseCommit':BASE_COMMIT,'route':ROUTE,'htmlPath':HTML_PATH,
            'htmlSha256':digest(raw),'htmlBytes':len(raw),'storageKey':STORAGE_KEY,
            'counts':{'games':1,'characters':6,'stages':10,'bosses':3},'generatedArtwork':True,
            'cardAssets':cards,'sourceHashes':{p:digest(b) for p,b in data.items()}}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preview',action='store_true',help='write a standalone local game in test-results/courier-preview')
    if parser.parse_args().preview:
        raw,_=render(preview=True)
        path=target(ROOT/'test-results/courier-preview','index.html')
        path.write_bytes(raw)
        print(path)
    else:
        print(json.dumps(build(),ensure_ascii=False,indent=2))
