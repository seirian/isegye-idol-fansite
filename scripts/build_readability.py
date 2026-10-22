#!/usr/bin/env python3
"""Isolated readability review. No network, credentials or production writes.

Current portraits require local files and verified provenance in review/portraits.json.
Pending files render explicit name cards, not outdated avatar substitutes.
"""
from __future__ import annotations
import base64
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import runpy
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'readability-dist'
IDS = {'ine','jingburger','lilpa','jururu','gosegu','viichan'}

def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def main() -> None:
    if os.environ.get('DEPLOY_ENV') == 'production':
        raise RuntimeError('This review has not been approved for production.')
    manifest = json.loads((ROOT/'review/portraits.json').read_text())
    if {m['id'] for m in manifest['members']} != IDS or len(manifest['members']) != 6:
        raise RuntimeError('Exactly six member records required')
    runpy.run_path(str(ROOT/'second/compose.py'),run_name='__main__')
    source = ROOT/'second-dist'
    if OUT.is_symlink(): raise RuntimeError('Symlink output refused')
    if OUT.exists(): shutil.rmtree(OUT)
    (OUT/'src').mkdir(parents=True)
    (OUT/'assets/portraits').mkdir(parents=True)
    for name in ('data.js','lib.js'):
        shutil.copy2(ROOT/'src'/name,OUT/'src'/name)
    shutil.copy2(ROOT/'assets/favicon.svg',OUT/'assets/favicon.svg')
    (OUT/'.nojekyll').touch()
    (OUT/'robots.txt').write_text('User-agent: *\nDisallow: /\n')
    portraits = {}
    inline = {}
    for m in manifest['members']:
        item = {'id':m['id'],'status':m['status']}
        if m['status'] == 'verified':
            from PIL import Image
            rel = m['file']
            if not re.fullmatch(r'review/portraits/[a-z]+\.webp',rel):
                raise RuntimeError('Unsafe portrait path')
            path = ROOT/rel
            if path.is_symlink() or not m.get('verifiedAt') or not m.get('sourcePage'):
                raise RuntimeError('Missing source verification')
            data = path.read_bytes()
            if len(data)>2*1024*1024 or digest(data)!=m['sha256']:
                raise RuntimeError('Portrait checksum/size rejected')
            with Image.open(path) as image:
                if image.format!='WEBP' or min(image.size)<200: raise RuntimeError('Invalid portrait')
            (OUT/'assets/portraits'/f"{m['id']}.webp").write_bytes(data)
            item['sourcePage'] = m['sourcePage']
            inline[m['id']] = 'data:image/webp;base64,'+base64.b64encode(data).decode()
        elif m['status'] != 'pending':
            raise RuntimeError('Unrecognized portrait status')
        portraits[m['id']] = item
    (OUT/'src/portraits.js').write_text('export const IMAGE_SOURCE_NOTE = "";\nexport const PORTRAITS = '+json.dumps(portraits,ensure_ascii=False)+';\n')
    js = (source/'src/second-app.js').read_text()
    start = js.index("const portrait=(m,cls='')=>")
    end = js.index('const memberCard=m=>',start)
    js = js[:start]+'''const portrait=(m,cls='')=>PORTRAITS[m.id]?.status==='verified'?`<div class="portrait ${m.tone} ${cls}"><img src="./assets/portraits/${m.id}.webp" width="600" height="600" alt="${e(m.name)} 프로필 이미지" decoding="async" loading="eager"><span class="portrait-fallback" aria-hidden="true">이미지를 불러오지 못했어요</span></div>`:`<div class="portrait pending ${m.tone} ${cls}" role="img" aria-label="${e(m.name)} 최신 프로필 이미지 준비 중"><span class="pending-mark" aria-hidden="true">✦</span><strong class="pending-name">${e(m.name)}</strong><span class="pending-label">최신 프로필<br>준비 중</span></div>`;
''' + js[end:]
    start = js.index('function aboutView(){')
    end = js.index('function privacyView()',start)
    js = js[:start]+'''function aboutView(){return heading('좋아하는 마음을, 오래도록.','이세계아이돌 비공식 팬 아카이브')+`<p class="about-intro">멤버들의 음악과 방송, 함께한 순간을 한곳에서 찾아보는 공간입니다. 공개된 자료를 바탕으로, 팬들이 궁금한 이야기를 차곡차곡 모읍니다.</p><div class="about-grid"><section class="about-panel"><h2>무엇을 볼 수 있나요?</h2><p>멤버 소개부터 음악, 소식·일정과 활동 기록까지. 기록마다 원문 출처를 연결해 더 자세한 이야기도 확인할 수 있습니다.</p><a class="text-link" href="#/members">멤버 만나러 가기 ${icon('arrow')}</a></section><section class="about-panel"><h2>함께 채우는 기록</h2><p>잘못된 정보나 빠진 기록을 발견하셨나요? 공개된 근거와 함께 알려주세요. 확인한 뒤 수정하겠습니다.</p><a class="text-link" href="#/report">정보 제보 · 정정 요청 ${icon('arrow')}</a></section><section class="about-panel wide"><h2>이용 안내</h2><p>패러블 및 아티스트의 공식 사이트가 아닙니다. 이미지와 원본 콘텐츠의 권리는 각 권리자에게 있습니다. 자료 출처는 해당 기록에서 확인할 수 있습니다.</p><a class="text-link" href="#/record/fan-policy">운영 원칙 ${icon('arrow')}</a></section></div>`;}
''' + js[end:]
    start = js.index('${m?`<div class="portrait-credit">')
    end = js.index('${badge(r)}',start)
    js = js[:start]+js[end:]
    for before,after in [('공식 프로필 임시본 · 출처','사이트 소개'),('사이트 소개 · 이미지 출처','사이트 소개'),('이미지 출처·구현 범위','사이트 소개'),('DESIGN PREVIEW 02','가독성 개선 검토'),('멤버와 더 가까이, 새로운 팬사이트 시안','읽기 편하게, 더 가까이'),('SECOND CONCEPT','FAN ARCHIVE'),('FANMADE, WITH LOVE <b>✦</b> ',''),('<small>FAN ARCHIVE</small>','<small>팬 아카이브</small>'),('ISEGYE! 두 번째 시안','ISEGYE! 팬 아카이브')]:
        js=js.replace(before,after)
    (OUT/'src/app.js').write_text(js,encoding='utf-8')
    css = (ROOT/'second/theme.css').read_text()
    css = re.sub(r'font-size:([0-9.]+)px',lambda m:'font-size:'+str(max(14,float(m[1]))/16)+'rem',css)
    css += '\n'+(ROOT/'review/readability.css').read_text()
    (OUT/'src/styles.css').write_text(css,encoding='utf-8')
    html = (source/'index.html').read_text().replace('./src/second-app.js','./src/app.js').replace('./src/second.css','./src/styles.css')
    html = html.replace('<html ', '<html data-review="readability" ',1)
    html = html.replace('ISEGYE! · 두 번째 팬사이트 시안','ISEGYE! · 가독성 개선 검토')
    (OUT/'index.html').write_text(html,encoding='utf-8')
    metadata = {'concept':'second','review':'readability','mode':'preview','commit':os.environ.get('GITHUB_SHA','local'),
                'builtAt':datetime.now(timezone.utc).isoformat(),'verifiedPortraitCount':len(inline),
                'pendingPortraitCount':6-len(inline),'oldAvatarsIncluded':False}
    (OUT/'build-info.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n')
    parts=[]
    for name in ('data.js','lib.js','portraits.js','app.js'):
        part=(OUT/'src'/name).read_text()
        part=re.sub(r'^import .*;\r?\n','',part,flags=re.M)
        parts.append(re.sub(r'^export ','',part,flags=re.M))
    standalone_js='const INLINE_PORTRAITS='+json.dumps(inline)+';\nconst e=escapeHtml;\n'+'\n'.join(parts)
    standalone_js=standalone_js.replace('src="./assets/portraits/${m.id}.webp"','src="${INLINE_PORTRAITS[m.id]}"')
    offline=html.replace('<link rel="stylesheet" href="./src/styles.css">','<style>'+css+'</style>')
    offline=offline.replace('<script type="module" src="./src/app.js"></script>','<script type="module">'+standalone_js+'</script>')
    icon='data:image/svg+xml;base64,'+base64.b64encode((OUT/'assets/favicon.svg').read_bytes()).decode()
    offline=offline.replace('href="./assets/favicon.svg"','href="'+icon+'"')
    for kind,text in [('script',standalone_js),('style',css)]:
        h=base64.b64encode(hashlib.sha256(text.encode()).digest()).decode()
        offline=offline.replace(kind+"-src 'self'",kind+"-src 'self' 'sha256-"+h+"'")
    (OUT/'review.html').write_text(offline,encoding='utf-8')
    subprocess.run(['node','--check',str(OUT/'src/app.js')],check=True)
    print(json.dumps(metadata,ensure_ascii=False,indent=2))

if __name__=='__main__': main()
