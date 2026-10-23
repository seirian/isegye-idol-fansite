#!/usr/bin/env python3
"""Build the isolated LIVE review. The approved production compiler is unchanged."""
from __future__ import annotations
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'live-dist'

def replace_once(text: str, old: str, new: str) -> str:
    if text.count(old)!=1: raise RuntimeError('Unexpected template anchor: '+old[:90])
    return text.replace(old,new,1)

def main() -> None:
    if os.environ.get('DEPLOY_ENV')=='production':
        raise RuntimeError('LIVE remains a separate review; production approval is required.')
    subprocess.run([sys.executable,str(ROOT/'scripts/build_selected.py')],cwd=ROOT,check=True)
    if OUT.is_symlink():raise RuntimeError('Symlink output refused')
    if OUT.exists():shutil.rmtree(OUT)
    shutil.copytree(ROOT/'dist',OUT)
    data=(OUT/'src/data.js').read_text()
    data=replace_once(data,"{id:'dictionary',name:'이세돌 사전',icon:'book',en:'DICTIONARY'}","{id:'live',name:'LIVE',icon:'video',en:'LIVE'}")
    data=data.replace('세 번째, 낯선 표현은 사전에서 찾아보세요.','세 번째, LIVE에서 방송 중인 멤버를 만나보세요.')
    (OUT/'src/data.js').write_text(data)
    app=(OUT/'src/app.js').read_text()
    # Remove the old menu's view rather than just relabeling it.
    a=app.index('function dictionaryView(');b=app.index('function videosView(',a)
    app=app[:a]+app[b:]
    app=replace_once(app,'dictionary:()=>dictionaryView(params),','live:liveView,')
    app=replace_once(app,"const page=parts[0]||'home';","const page=parts[0]==='dictionary'?'live':parts[0]||'home';")
    app=replace_once(app,"document.getElementById('main').innerHTML=html;","document.getElementById('main').innerHTML=html;\n liveMount(page);")
    app=replace_once(app,'return `<section class="hero">','return liveHomeView()+`<section class="hero">')
    # All old navigational entry points lead to the live monitor; existing documents remain archived.
    app=app.replace('href="#/dictionary"','href="#/live"')
    app=app.replace("entry:'dictionary'","entry:'search'")
    for old,new in [('02 / DISCOVER','02 / LIVE'),('<span>Aa</span>','<span>ON AIR</span>'),('궁금한 건 못 참지','지금, 함께하는 순간'),('용어부터 시작하는 이세돌 사전','여섯 멤버의 실시간 방송 현황'),('실시간 방송 상태는 아직 연동하지 않았어요.','지금 방송 중인 멤버는 LIVE에서 확인해요.'),('궁금한 이야기 찾아보기','방송 중인 멤버 만나기'),('용어에서 관련 콘텐츠로 연결.','LIVE에서 공식 방송으로 바로 연결.'),('디자인 개선 검토','LIVE 기능 검토')]:app=app.replace(old,new)
    app=app.replace('현재 멤버 페이지는 기본 소개와 등록된 음악 연결을 제공합니다. 공식 채널의 직접 주소, 세부 프로필·취향은 검수 후 추가하며, 확인되지 않은 링크를 공식 채널로 안내하지 않습니다.','멤버 소개와 연결된 음악을 살펴보세요. 공식 SOOP 방송 채널과 방송 상태는 LIVE에서 확인할 수 있습니다.')
    app=app.replace('공식 출처와 GitHub를 방문하면 해당 서비스의 정책이 적용됩니다.','LIVE와 홈 화면은 SOOP에 공개 방송 상태를 직접 요청합니다. SOOP는 이 요청의 IP 주소 등 접속 정보를 자체 정책에 따라 처리할 수 있습니다. 요청에 로그인 쿠키나 검색어는 보내지 않습니다. 공식 출처와 GitHub를 방문하면 해당 서비스의 정책이 적용됩니다.')
    core=re.sub(r'^export ','',(ROOT/'live/core.js').read_text(),flags=re.M)
    app=replace_once(app,'shell();render();',core+'\n'+(ROOT/'live/ui.js').read_text()+'\nshell();render();')
    if '이세돌 사전' in app or 'YOU ARE INVITED TO' in app:raise RuntimeError('Retired UI remains')
    (OUT/'src/app.js').write_text(app)
    css=(OUT/'src/styles.css').read_text()+'\n'+(ROOT/'live/theme.css').read_text()
    (OUT/'src/styles.css').write_text(css)
    html=(OUT/'index.html').read_text()
    html=html.replace('멤버, 음악, 일정, 용어를 한곳에서 찾아보세요.','멤버, 음악, 일정, LIVE를 한곳에서 찾아보세요.')
    html=replace_once(html,'<html ','<html data-live-review="true" ')
    html=replace_once(html,"connect-src 'self'","connect-src 'self' https://chapi.sooplive.co.kr")
    html=re.sub(r'<title>.*?</title>','<title>ISEGYE! · LIVE 검토</title>',html)
    (OUT/'index.html').write_text(html)
    meta=json.loads((OUT/'build-info.json').read_text())
    meta.update(review='live',branch='feature/live',live={'source':'SOOP public station','pollSeconds':30,'staleAfterSeconds':90,'members':6,'transport':'browser-cors','failureMeansOffline':False})
    (OUT/'build-info.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n')
    parts=[]
    for name in ('data.js','lib.js','portraits.js','app.js'):
        part=(OUT/'src'/name).read_text();part=re.sub(r'^import .*;\r?\n','',part,flags=re.M)
        parts.append(re.sub(r'^export ','',part,flags=re.M))
    inline='const e=escapeHtml;\n'+'\n'.join(parts)
    portraits={p.stem:'data:image/webp;base64,'+base64.b64encode(p.read_bytes()).decode() for p in (OUT/'assets/portraits').glob('*.webp')}
    inline='const INLINE_PORTRAITS='+json.dumps(portraits)+';\n'+inline
    inline=inline.replace('src="./assets/portraits/${m.id}.webp?v=${PORTRAITS[m.id].version}"','src="${INLINE_PORTRAITS[m.id]}"')
    group=OUT/'assets/isegye-group-hero.webp'
    inline=re.sub(r'\./assets/isegye-group-hero.webp\?v=[0-9a-f]+','data:image/webp;base64,'+base64.b64encode(group.read_bytes()).decode(),inline)
    offline=html.replace('<link rel="stylesheet" href="./src/styles.css">','<style>'+css+'</style>')
    offline=offline.replace('<script type="module" src="./src/app.js"></script>','<script type="module">'+inline+'</script>')
    offline=offline.replace('href="./assets/favicon.svg"','href="data:image/svg+xml;base64,'+base64.b64encode((OUT/'assets/favicon.svg').read_bytes()).decode()+'"')
    for kind,text in [('script',inline),('style',css)]:
        h=base64.b64encode(hashlib.sha256(text.encode()).digest()).decode();offline=offline.replace(kind+"-src 'self'",kind+"-src 'self' 'sha256-"+h+"'")
    (OUT/'review.html').write_text(offline)
    subprocess.run(['node','--check',str(OUT/'src/app.js')],check=True)
    print(json.dumps({'liveReviewBuilt':True,'output':'live-dist','commit':meta['commit']},ensure_ascii=False))
if __name__=='__main__':main()
