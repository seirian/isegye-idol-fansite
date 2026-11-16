#!/usr/bin/env python3
"""Compose the approved Playground into the existing SPA, not a second site shell."""
from pathlib import Path
import json,re,os,hashlib,subprocess
from build_playground import validate
ROOT=Path(__file__).resolve().parents[1]
ACCEPTED='4583f8e1e460da0b1fc45967a010bd41e2f336b3'
def one(s,old,new):
    if s.count(old)!=1:raise ValueError('Playground integration anchor moved: '+old[:80])
    return s.replace(old,new,1)
def jsjson(value):return json.dumps(value,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c').replace('>','\\u003e').replace('\u2028','\\u2028').replace('\u2029','\\u2029')
def component():
    seed=validate(json.loads((ROOT/'playground/catalog.json').read_text()))
    src=(ROOT/'playground/app.js').read_text()
    src=one(src,"function path(){return (location.hash.slice(1)||'/playground').split('?')[0];}","function path(){const p=(location.hash.slice(1)||'/playground').split('?')[0];return p==='/playground'?'/playground':p.startsWith('/playground/')?p.slice('/playground'.length):'/outside';}")
    src=one(src,"function go(to){if(location.hash==='#'+to)render();else location.hash=to;}","function go(to){const route=to==='/playground'?to:'/playground'+to;if(location.hash==='#'+route)render();else location.hash=route;}")
    for route in ('play','quiz','records','sources','result/'):
        src=src.replace('href="#/'+route+'"','href="#/playground/'+route+'"') if not route.endswith('/') else src.replace('href="#/result/','href="#/playground/result/')
    src=src.replace('https://isegye-idol.kr/review-playground/\\n(검토본 · 기존 관리자 로그인 필요)','https://isegye-idol.kr/#/playground')
    src=src.replace('검토본 기록','놀이터 기록').replace('검토본 기록','놀이터 기록')
    src=one(src,'function render(focus=true){const p=path();',"function render(focus=true){if(!host.isConnected)return;state.dark=realDocument.documentElement.dataset.theme==='dark';applyTheme();const p=path();")
    src=one(src,"window.addEventListener('hashchange',()=>render());",'refresh=()=>render(false);')
    core=re.sub(r'^export ','',(ROOT/'playground/core.js').read_text(),flags=re.M).replace('isegye:playground:review:v1','isegye:playground:v1').replace('검토본 기록','놀이터 기록')
    core=one(core,"const pool=ids?data.questions.filter(q=>ids.includes(q.id)):questionPool(data,category);","const pool=(ids?data.questions.filter(q=>ids.includes(q.id)):questionPool(data,category)).filter(q=>mode!=='daily'||!q.eligibleFrom||q.eligibleFrom<=kstDate());")
    # Keep the reviewed UI intact, remove only its duplicate site header and review text.
    original=(ROOT/'playground/index.html').read_text()
    inner=original[original.index('<div id="storage-note"'):original.index('<!--SCRIPT-->')]
    inner=re.sub(r'<footer.*?</footer>','',inner,flags=re.S)
    inner=inner.replace('검토 링크','놀이터 링크')
    markup='<div class="pg-body"><div class="pg-tools"><a href="#/playground">놀이터</a><a href="#/playground/records">내 기록</a><a href="#/playground/sources">문항과 참고 자료</a><button id="theme" hidden>테마</button></div><p id="bank-note" class="storage-note" hidden></p>'+inner+'</div>'
    css=(ROOT/'playground/styles.css').read_text().replace(':root{',':host{').replace('body.dark{','.pg-body.dark{').replace('body{','.pg-body{')
    css+='\n:host{display:block;background:transparent}.pg-body{background:transparent}.wrap{width:100%;max-width:none}#main{padding-top:16px;padding-bottom:32px}.pg-tools{display:flex;flex-wrap:wrap;gap:20px;justify-content:flex-end;font-size:13px;padding-top:16px}.pg-tools a:hover{text-decoration:underline}button[hidden],[hidden]{display:none!important}\n'
    runtime=(ROOT/'site/playground-runtime.js').read_text()
    for key,value in {'__SEED__':jsjson(seed),'__CSS__':"''",'__MARKUP__':jsjson(markup),'__CORE__':core,'__APP__':src,'__BANK__':re.sub(r'^export ','',(ROOT/'site/playground-bank.js').read_text(),flags=re.M)}.items():runtime=runtime.replace(key,value)
    return runtime,css,seed

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
    (out/'src/playground-seed.json').write_text(json.dumps(seed,ensure_ascii=False,separators=(',',':'))+'\n')
    html=(out/'index.html').read_text();html=one(html,'<script src="src/app.js"></script>','<script src="src/playground.js"></script><script src="src/app.js"></script>');(out/'index.html').write_text(html)
    for name in ('production-ui.js','public-production-ui.js'):
        p=out/'src'/name;s=p.read_text();s=one(s,'<h2>검색과 개인 설정</h2>','<h2><a href="#/playground">놀이터</a></h2><p>오늘의 다섯 문제, 주제별 퀴즈와 발매 순서 게임을 즐길 수 있습니다. 플레이 기록은 이 브라우저에만 보관합니다.</p><h2>검색과 개인 설정</h2>');p.write_text(s)
    meta['playground']={'schemaVersion':1,'acceptedCommit':ACCEPTED,'operatorApprovedDeployment':True,'route':'/#/playground','readEndpoint':'/api/playground','seedVersion':seed['version'],'seedQuestions':len(seed['questions']),'storageKey':'isegye:playground:v1','dailySchedule':'매일 07:37 Asia/Seoul','seedSha256':hashlib.sha256((out/'src/playground-seed.json').read_bytes()).hexdigest()}
    (out/'build-info.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n')
    for n in ('app.js','playground.js'):subprocess.run(['node','--check',str(out/'src'/n)],check=True)
    print(json.dumps({'status':'playground_composed','route':'/#/playground','seedQuestions':len(seed['questions'])}))
    return meta
if __name__=='__main__':build()
