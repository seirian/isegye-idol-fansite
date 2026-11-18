"""Package the user-approved RPG within the existing gated release."""
from pathlib import Path
import json, os
from build_rpg import assemble, digest, source_bytes, ROOT, STORAGE_KEY
from build_courier_production import target
HTML_PATH='games/ipari-chronicle/index.html'
ROUTE='/games/ipari-chronicle/'
APPROVAL='ipari-rpg-production-20261118'
CARD_ASSETS=('worlds','cast')

def render():
    raw, meta=assemble(ROOT)
    old='<footer class="site-note">'
    text=raw.decode()
    if text.count(old)!=1:raise ValueError('RPG return link anchor moved')
    text=text.replace(old,old+'<a data-rpg-return href="/#/playground">← 놀이터로 돌아가기</a>',1)
    return text.encode(),meta

def build(out=None):
    out=Path(out) if out is not None else ROOT/'dist'
    if not out.is_dir() or out.is_symlink():raise ValueError('Existing release directory required')
    release=json.loads((out/'build-info.json').read_text())
    if release.get('mode') not in ('preview','production'):raise ValueError('Known release mode required')
    if release['mode']=='production' and os.getenv('GITHUB_REF')!='refs/heads/main':raise ValueError('Main-only production')
    raw,source=render()
    target(out,HTML_PATH).write_bytes(raw)
    cards={}
    for name in CARD_ASSETS:
        data=source_bytes(ROOT,f'rpg/assets/{name}.webp')
        relative=f'assets/rpg/{name}.webp'
        target(out,relative).write_bytes(data);cards[relative]=digest(data)
    return {'game':'ipari-chronicle','version':1,'approval':APPROVAL,'route':ROUTE,'htmlPath':HTML_PATH,
            'htmlSha256':digest(raw),'htmlBytes':len(raw),'storageKey':STORAGE_KEY,'generatedArtwork':True,
            'counts':{'chapters':6,'rooms':19,'members':6},'playtime':source['playtime'],
            'cardAssets':cards,'sourceHashes':source['sourceHashes']}

if __name__=='__main__':print(json.dumps(build(),ensure_ascii=False,indent=2))
