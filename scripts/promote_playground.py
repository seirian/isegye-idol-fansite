#!/usr/bin/env python3
"""Compose the approved Playground into the existing SPA, not a second site shell."""
from pathlib import Path
import json,re,os,hashlib,subprocess
from build_playground import validate
from build_courier_production import build as build_courier
from build_rpg_production import build as build_rpg
ROOT=Path(__file__).resolve().parents[1]
ACCEPTED='4583f8e1e460da0b1fc45967a010bd41e2f336b3'
def one(s,old,new):
    if s.count(old)!=1:raise ValueError('Playground integration anchor moved: '+old[:80])
    return s.replace(old,new,1)
def jsjson(value):return json.dumps(value,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c').replace('>','\\u003e').replace('\u2028','\\u2028').replace('\u2029','\\u2029')
def component():
    seed=validate(json.loads((ROOT/'playground/catalog.json').read_text()))
    src=(ROOT/'playground/app.js').read_text()
    src=one(src,'\n<!--PREVIEW-QUIZ-OPTIONS-->','')
    card=(ROOT/'site/playground-courier-card.html').read_text()+(ROOT/'site/playground-rpg-card.html').read_text()
    src=one(src,'`<section class="hero" aria-labelledby="daily-title">','`'+card+'<section class="hero" aria-labelledby="daily-title">')
    src=one(src,'<span class="badge">시간제한 없이, 가볍게</span>',"<span class=\"badge\">${title==='놀이터'?'퀴즈부터 미니게임까지':'시간제한 없이, 가볍게'}</span>")
    src=one(src,"function path(){return (location.hash.slice(1)||'/playground').split('?')[0];}","function path(){const p=(location.hash.slice(1)||'/playground').split('?')[0];return p==='/playground'?'/playground':p.startsWith('/playground/')?p.slice('/playground'.length):'/outside';}")
    src=one(src,"function go(to){if(location.hash==='#'+to)render();else location.hash=to;}","function go(to){const route=to==='/playground'?to:'/playground'+to;if(location.hash==='#'+route)render();else location.hash=route;}")
    for route in ('play','quiz','records','sources','result/'):
        src=src.replace('href="#/'+route+'"','href="#/playground/'+route+'"') if not route.endswith('/') else src.replace('href="#/result/','href="#/playground/result/')
    src=src.replace('https://isegye-idol.kr/review-playground/\\n(검토본 · 기존 관리자 로그인 필요)','https://isegye-idol.kr/#/playground')
    src=src.replace('검토본 기록','놀이터 기록').replace('검토본 기록','놀이터 기록')
    src=one(src,'function render(focus=true){const p=path();',"function render(focus=true){if(!host.isConnected)return;state.dark=realDocument.documentElement.dataset.theme==='dark';applyTheme();const p=path();")
    src=one(src,"window.addEventListener('hashchange',()=>render());",'refresh=()=>render(false);')
    core=re.sub(r'^export ','',(ROOT/'playground/core.js').read_text(),flags=re.M).replace('isegye:playground:review:v1','isegye:playground:v1').replace('검토본 기록','놀이터 기록')
    # Reference overview is a separately authorized module, not a hidden public page.
    start=src.index('  function sources(){');end=src.index('  function render(',start)
    src=src[:start]+"  function sources(){return adminAllowed()?(adminReferenceView?adminReferenceView(data,{heading,esc,kindNames,safeLink,orderPairs}):empty('참고 자료를 확인하고 있어요','관리자 권한을 확인한 후 자료를 불러옵니다.')):empty('관리자 전용 페이지입니다','놀이터에서 퀴즈를 즐겨주세요.');}\n"+src[end:]
    src=one(src,"    document.title=(main.querySelector('h1')", "    if(adminAllowed())main.insertAdjacentHTML('beforeend','<div class=\"pg-admin-footer\" data-admin-only=\"playground-sources\"><a href=\"#/playground/sources\">문항과 참고 자료 <span>· 관리자</span></a></div>');\n    syncAdminAccess();\n    document.title=(main.querySelector('h1')")
    # Preserve the main site shell. No duplicate navigation above the title.
    original=(ROOT/'playground/index.html').read_text()
    inner=original[original.index('<div id="storage-note"'):original.index('<!--SCRIPT-->')]
    inner=re.sub(r'<footer.*?</footer>','',inner,flags=re.S)
    inner=inner.replace('검토 링크','놀이터 링크')
    markup='<div class="pg-body"><button id="theme" hidden>테마</button>'+inner+'<p id="bank-note" class="storage-note" hidden></p></div>'
    css=(ROOT/'playground/styles.css').read_text().replace(':root{',':host{').replace('body.dark{','.pg-body.dark{').replace('body{','.pg-body{')
    css=re.sub(r':host\{[^}]*\}',":host{--paper:var(--panel);--soft:var(--accent-soft);--lavender:var(--panel2);--green:var(--good);--green-soft:var(--panel2);color:var(--ink);color-scheme:light}",css,count=1)
    css=re.sub(r'\.pg-body\.dark\{[^}]*\}',".pg-body.dark{color-scheme:dark}",css,count=1)
    css+='\n'+(ROOT/'site/playground-integration.css').read_text()
    # Use the exact shared page-heading rules, including the mobile token values.
    shared=(ROOT/'review-2nd/polish.css').read_text()
    headings=shared.split('/* The exact operating footer CSS')[0].replace(':root',':host')
    mobile=shared[shared.index('@media(max-width:640px)'):].replace(':root',':host')
    mobile=mobile.replace(' .production-footer{padding-bottom:82px}','')
    css+='\n'+headings+mobile
    from playground_pipeline import editorial_manifest
    runtime=(ROOT/'site/playground-runtime.js').read_text()
    runtime=runtime.replace('__EDITORIAL__',jsjson(editorial_manifest()))
    runtime=runtime.replace('__BANK__',re.sub(r'^export ','',(ROOT/'site/playground-editorial.js').read_text(),flags=re.M)+'\n__BANK__')
    for key,value in {'__SEED__':jsjson(seed),'__CSS__':"''",'__MARKUP__':jsjson(markup),'__CORE__':core,'__APP__':src,'__BANK__':re.sub(r'^export ','',(ROOT/'site/playground-bank.js').read_text(),flags=re.M)}.items():runtime=runtime.replace(key,value)
    return runtime,css,seed

def reference_module():
    app=(ROOT/'playground/app.js').read_text()
    start=app.index('  function sources(){');end=app.index('  function render(',start)
    body=app[start:end].strip().replace('function sources(){','export function renderReferenceView(data,{heading,esc,kindNames,safeLink,orderPairs}){',1)
    return '// Server-authorized administrator reference overview.\n'+body+'\n'

def build(out=None):
    out=out or ROOT/'dist';meta=json.loads((out/'build-info.json').read_text())
    if meta.get('mode')=='production' and os.getenv('GITHUB_REF')!='refs/heads/main':raise ValueError('Main-only production')
    if meta.get('playground'):raise ValueError('Playground already composed')
    if not meta.get('albumPromotion'):raise ValueError('Complete existing app required')
    js,css,seed=component();app=(out/'src/app.js').read_text()
    app=one(app,"['history','활동 기록','clock']];","['history','활동 기록','clock'],['playground','놀이터','spark']];")
    app=one(app,'<a href="#/history">활동 기록</a><a href="#/saved">','<a href="#/history">활동 기록</a><a href="#/playground">놀이터</a><a href="#/saved">')
    app=one(app,"else if(root==='guide')", "else if(root==='playground')html='<div id=\"playground-mount\"></div>';else if(root==='guide')")
    app=one(app,'LegalDocuments.mount();',"LegalDocuments.mount();if(root==='playground')PlaygroundUI.mount(document.getElementById('playground-mount'));")
    (out/'src/app.js').write_text(app);(out/'src/playground.js').write_text(js);(out/'src/playground.css').write_text(css)
    (out/'src/playground-admin.js').write_text(reference_module())
    (out/'src/playground-seed.json').write_text(json.dumps(seed,ensure_ascii=False,separators=(',',':'))+'\n')
    html=(out/'index.html').read_text();html=one(html,'<script src="src/app.js"></script>','<script src="src/playground.js"></script><script src="src/app.js"></script>');(out/'index.html').write_text(html)
    for name in ('production-ui.js','public-production-ui.js'):
        p=out/'src'/name;s=p.read_text();s=one(s,'<h2>검색과 개인 설정</h2>','<h2><a href="#/playground">놀이터</a></h2><p>오늘의 다섯 문제를 풀거나 별빛 배송부와 이파리 연대기를 플레이할 수 있습니다. 플레이 기록은 이 브라우저에만 보관합니다.</p><h2>검색과 개인 설정</h2>');p.write_text(s)
    meta['playground']={'schemaVersion':1,'acceptedCommit':ACCEPTED,'operatorApprovedDeployment':True,'route':'/#/playground','readEndpoint':'/api/playground','seedVersion':seed['version'],'seedQuestions':len(seed['questions']),'storageKey':'isegye:playground:v1','dailySchedule':'매일 08:00 Asia/Seoul','seedSha256':hashlib.sha256((out/'src/playground-seed.json').read_bytes()).hexdigest()}
    meta['courierGame']=build_courier(out)
    meta['rpgGame']=build_rpg(out)
    (out/'build-info.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n')
    for n in ('app.js','playground.js','playground-admin.js'):subprocess.run(['node','--check',str(out/'src'/n)],check=True)
    print(json.dumps({'status':'playground_composed','route':'/#/playground','seedQuestions':len(seed['questions'])}))
    return meta
if __name__=='__main__':build()
