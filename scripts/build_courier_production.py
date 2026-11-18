#!/usr/bin/env python3
"""Package the approved Courier game for the normal-reader production release.

The original administrator preview sources remain byte-for-byte unchanged.
Only a fixed standalone HTML and two homepage card images are written to dist.
"""
from pathlib import Path
import base64
import hashlib
import json
import os
import re

ROOT=Path(__file__).resolve().parents[1]
HTML_PATH='games/starlight-courier/index.html'
ROUTE='/games/starlight-courier/'
STORAGE_KEY='isegye:playground:courier:v2'
ACCEPTED_COMMIT='34f26ed647453050c38d6c1df004ecacb0f0dbb7'
MAX_HTML_BYTES=8*1024*1024
ART_NAMES=('characters','plaza','items')
SOURCES=('fangames/index.html','fangames/styles.css','fangames/engine.js','fangames/app.js')
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
        if part.is_symlink():raise ValueError('Courier output symlink')
    path.parent.mkdir(parents=True,exist_ok=True)
    if not path.resolve().is_relative_to(out.resolve()):raise ValueError('Courier output escaped release')
    return path


def build(out=None):
    out=Path(out) if out is not None else ROOT/'dist'
    if not out.is_dir() or out.is_symlink():raise ValueError('Existing release directory required')
    release=json.loads((out/'build-info.json').read_text())
    if release.get('mode') not in ('preview','production'):raise ValueError('Known release mode required')
    if release['mode']=='production' and os.getenv('GITHUB_REF')!='refs/heads/main':
        raise ValueError('Main-only production')
    data={}
    for relative in (*SOURCES,*(f'fangames/assets/{name}.webp' for name in ART_NAMES)):
        file=ROOT/relative
        if not file.is_file() or file.is_symlink() or not file.resolve().is_relative_to(ROOT):
            raise ValueError('Invalid Courier source: '+relative)
        data[relative]=file.read_bytes()
    html=data['fangames/index.html'].decode()
    html=once(html,'이세돌 별빛 배송부 · 팬게임 검토본','이세돌 별빛 배송부 · 놀이터')
    html=once(html,'<a class="wordmark" href="https://isegye-idol.kr/#/playground">ISEGYE<span>✦</span></a>',
              '<a class="wordmark" href="/#/playground">← 놀이터</a>')
    html=once(html,'미니게임 검토본','미니게임')
    html=once(html,'비공식 이세계아이돌 팬게임 · 검토 전용','비공식 이세계아이돌 팬게임')
    css=data['fangames/styles.css'].decode()
    app=once(data['fangames/app.js'].decode(),"const key = 'isegye:review:courier:v2';",f"const key = '{STORAGE_KEY}';")
    art={}
    for name in ART_NAMES:
        raw=data[f'fangames/assets/{name}.webp']
        if not 1000<len(raw)<4*1024*1024 or raw[:4]!=b'RIFF' or raw[8:12]!=b'WEBP':
            raise ValueError('Invalid generated WebP: '+name)
        art[name]='data:image/webp;base64,'+base64.b64encode(raw).decode()
    js='const COURIER_ART=Object.freeze('+json.dumps(art,separators=(',',':'))+');\n'+data['fangames/engine.js'].decode()+'\n'+app+'\n'
    if '\x00' in css+js or re.search(r'</(?:script|style)',css+js,re.I):
        raise ValueError('Unsafe inline source')
    sha=lambda text:base64.b64encode(hashlib.sha256(text.encode()).digest()).decode()
    csp=("default-src 'none'; script-src 'sha256-"+sha(js)+"'; style-src 'sha256-"+sha(css)+
         "'; connect-src 'none'; img-src data:; media-src 'none'; font-src 'none'; base-uri 'none'; form-action 'none'; object-src 'none'")
    html=once(html,'<!--CSP-->','<meta http-equiv="Content-Security-Policy" content="'+csp+'">')
    html=once(html,'<!--STYLE-->','<style>'+css+'</style>')
    html=once(html,'<!--SCRIPT-->','<script>'+js+'</script>')
    if 'isegye:review:courier:' in html or '검토본' in html or '검토 전용' in html:
        raise ValueError('Preview identity leaked into production game')
    raw=html.encode()
    if not 30000<len(raw)<=MAX_HTML_BYTES:raise ValueError('Courier HTML size')
    target(out,HTML_PATH).write_bytes(raw)
    cards={}
    for name in CARD_ASSETS:
        relative=f'assets/courier/{name}.webp'
        target(out,relative).write_bytes(data[f'fangames/assets/{name}.webp'])
        cards[relative]=digest(data[f'fangames/assets/{name}.webp'])
    return {'game':'starlight-courier','version':2,'acceptedCommit':ACCEPTED_COMMIT,'route':ROUTE,'htmlPath':HTML_PATH,
            'htmlSha256':digest(raw),'htmlBytes':len(raw),'storageKey':STORAGE_KEY,
            'counts':{'games':1,'characters':6,'stages':3},'generatedArtwork':True,
            'cardAssets':cards,'sourceHashes':{p:digest(b) for p,b in data.items()}}


if __name__=='__main__':
    print(json.dumps(build(),ensure_ascii=False,indent=2))
