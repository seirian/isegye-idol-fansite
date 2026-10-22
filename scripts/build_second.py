#!/usr/bin/env python3
"""Build the review-only second concept. Python 3.10+, Pillow 11.3.0.

python scripts/build_second.py
python -m http.server 4174 --directory second-dist --bind 127.0.0.1

The original app, main build, production workflows and host are not modified.
Images are downloaded at build time from six pinned public official URLs only.
They are explicit temporary replacements, not verified NamuWiki portraits.
"""
from __future__ import annotations
import argparse
import base64
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import re
import runpy
import shutil
import subprocess
import urllib.parse
import urllib.request
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'second-dist'
EXPECTED_IDS={'ine','jingburger','lilpa','jururu','gosegu','viichan'}
def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
def encoded_hash(text: str) -> str:
    return base64.b64encode(hashlib.sha256(text.encode()).digest()).decode()
def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--asset-dir',type=Path,help='Optional previously verified six WebP files for an offline build')
    args=parser.parse_args()
    if os.environ.get('DEPLOY_ENV')=='production':
        raise RuntimeError('Second concept is preview-only; image source requirements and rights review remain pending.')
    manifest=json.loads((ROOT/'second/portraits.json').read_text(encoding='utf-8'))
    if {m['id'] for m in manifest['members']}!=EXPECTED_IDS or len(manifest['members'])!=6:
        raise RuntimeError('Portrait manifest must contain exactly the six members')
    # The fixed output is the only directory removed by this builder.
    if OUT.exists():
        if OUT.is_symlink(): raise RuntimeError('Refusing symlink output')
        shutil.rmtree(OUT)
    (OUT/'src').mkdir(parents=True)
    (OUT/'assets/portraits').mkdir(parents=True)
    for filename in ('data.js','lib.js'):
        shutil.copy2(ROOT/'src'/filename,OUT/'src'/filename)
    shutil.copy2(ROOT/'second/theme.css',OUT/'src/second.css')
    shutil.copy2(ROOT/'assets/favicon.svg',OUT/'assets/favicon.svg')
    shutil.copy2(ROOT/'robots.txt',OUT/'robots.txt')
    (OUT/'.nojekyll').touch()
    portraits={}
    for record in manifest['members']:
        member=dict(record)
        source='https://parable-asia.com/wp-content/uploads/2026/04/'+urllib.parse.quote(member['filename'])
        target=OUT/'assets/portraits'/(member['id']+'.webp')
        if args.asset_dir:
            body=(args.asset_dir/(member['id']+'.webp')).read_bytes()
            if sha(body)!=member['preparedSha256']: raise RuntimeError('Cached portrait checksum mismatch: '+member['id'])
            target.write_bytes(body)
        else:
            request=urllib.request.Request(source,headers={'User-Agent':'Mozilla/5.0 IsegyeSecondReview/1.0'})
            with urllib.request.urlopen(request,timeout=25) as response:
                if urllib.parse.urlparse(response.url).hostname!='parable-asia.com':
                    raise RuntimeError('Unexpected image redirect host')
                body=response.read(8*1024*1024+1)
            if len(body)>8*1024*1024 or sha(body)!=member['sourceSha256']:
                raise RuntimeError('Official image changed; review and update manifest explicitly: '+member['id'])
            with Image.open(io.BytesIO(body)) as image:
                image.thumbnail((800,800))
                image.save(target,'WEBP',quality=90)
        member.update(sourceUrl=source,sourcePage=manifest['sourcePage'],requestedPage='https://namu.wiki/w/'+urllib.parse.quote(member['member']),namuMatchVerified=False,sha256=sha(target.read_bytes()))
        portraits[member['id']]=member
    (OUT/'src/portraits.js').write_text('export const IMAGE_SOURCE_NOTE = '+json.dumps(manifest['note'],ensure_ascii=False)+';\nexport const PORTRAITS = '+json.dumps(portraits,ensure_ascii=False,indent=2)+';\n',encoding='utf-8')
    runpy.run_path(str(ROOT/'second/compose.py'),run_name='__main__')
    subprocess.run(['node','--check',str(OUT/'src/second-app.js')],check=True)
    index=(OUT/'index.html').read_text(encoding='utf-8')
    if 'noindex,nofollow' not in index: raise RuntimeError('Preview indexing guard missing')
    commit=os.environ.get('SECOND_COMMIT') or os.environ.get('GITHUB_SHA') or 'local'
    build={'concept':'second','branch':'feature/second','mode':'preview','commit':commit,'builtAt':datetime.now(timezone.utc).isoformat(),'namuPortraitsVerified':False,'imageSource':'PARABLE official profiles — temporary review fallback','productionCleared':False}
    (OUT/'build-info.json').write_text(json.dumps(build,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (OUT/'image-sources.json').write_text(json.dumps({'note':manifest['note'],'images':portraits},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    # A self-contained review file avoids runtime hotlinking, external fonts and trackers.
    parts=[]
    for filename in ('data.js','lib.js','portraits.js','second-app.js'):
        text=(OUT/'src'/filename).read_text(encoding='utf-8')
        text=re.sub(r'^import .*;\r?\n','',text,flags=re.M)
        parts.append(re.sub(r'^export ','',text,flags=re.M))
    images={mid:'data:image/webp;base64,'+base64.b64encode((OUT/'assets/portraits'/(mid+'.webp')).read_bytes()).decode() for mid in portraits}
    js='const INLINE_PORTRAITS='+json.dumps(images)+';\nconst e=escapeHtml;\n'+'\n'.join(parts)
    js=js.replace('src="./assets/portraits/${m.id}.webp"','src="${INLINE_PORTRAITS[m.id]}"')
    css=(OUT/'src/second.css').read_text(encoding='utf-8')
    icon='data:image/svg+xml;base64,'+base64.b64encode((OUT/'assets/favicon.svg').read_bytes()).decode()
    html=index.replace('<link rel="stylesheet" href="./src/second.css">','<style>'+css+'</style>')
    html=html.replace('<script type="module" src="./src/second-app.js"></script>','<script type="module">'+js+'</script>')
    html=html.replace('href="./assets/favicon.svg"','href="'+icon+'"')
    html=html.replace("script-src 'self'","script-src 'self' 'sha256-"+encoded_hash(js)+"'")
    html=html.replace("style-src 'self'","style-src 'self' 'sha256-"+encoded_hash(css)+"'")
    (OUT/'review-second.html').write_text(html,encoding='utf-8')
    print(json.dumps(build,ensure_ascii=False,indent=2))
if __name__=='__main__':
    main()
