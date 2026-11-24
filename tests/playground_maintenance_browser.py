"""Local HTTP check of the actual compiled component, with synthetic bank data.
No real account, session, hosting credential or external network is used.
"""
from datetime import datetime, timedelta, timezone
from functools import partial
from pathlib import Path
import http.server
import json
import os
import subprocess
import sys
import tempfile
import threading
from playwright.sync_api import sync_playwright, expect

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import playground_bank as bank
from playground_pipeline import reserve_proposals
from promote_playground import component

now=datetime.now(timezone.utc)
old=None
for day in (-2,-1):
    time=now+timedelta(days=day)
    proposals=[bank.auto_question({'videoId':str(100+i).zfill(11),'title':'합성 테스트 곡 '+str(i),
                                  'type':'cover','members':['ine']},{'member':'ine'},time)
               for i in (range(8) if day==-2 else range(8,16))]
    old,_=bank.assemble(old,proposals,time)
reserved,_=reserve_proposals(old['catalog'],now,4)
feed,_=bank.assemble(old,reserved,now)
assert len(feed['catalog']['questions'])==100
state_code="""import fs from 'node:fs';import {freshState,createSession} from './playground/core.js';
const data=JSON.parse(fs.readFileSync(0,'utf8'));const state=freshState(data.version);
state.session=createSession(data,{mode:'retry',ids:['stories-ruru-festival-solo'],count:1});
console.log(JSON.stringify(state));"""
state=json.loads(subprocess.check_output(['node','--input-type=module','-e',state_code],cwd=ROOT,
                                         input=json.dumps(feed['catalog']).encode()))
js,css,seed=component();checks=[]
with tempfile.TemporaryDirectory() as tmp:
    root=Path(tmp);(root/'src').mkdir()
    (root/'src/playground.css').write_text(css)
    (root/'src/playground.js').write_text(js)
    (root/'index.html').write_text('<!doctype html><html lang="ko"><head><meta charset="utf-8"></head><body><div id="mount"></div><script src="/src/playground.js"></script><script>const mount=()=>PlaygroundUI.mount(document.getElementById("mount"));window.addEventListener("hashchange",mount);mount()</script></body></html>')
    class Handler(http.server.SimpleHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_GET(self):
            if self.path=='/api/playground':
                raw=bank.published_bytes(feed);self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(raw);return
            return super().do_GET()
    server=http.server.ThreadingHTTPServer(('127.0.0.1',0),partial(Handler,directory=tmp))
    threading.Thread(target=server.serve_forever,daemon=True).start()
    url='http://127.0.0.1:'+str(server.server_address[1])
    try:
        with sync_playwright() as p:
            opt={'headless':True}
            if os.getenv('CHROMIUM_PATH'):opt['executable_path']=os.environ['CHROMIUM_PATH']
            browser=p.chromium.launch(**opt);ctx=browser.new_context(locale='ko-KR')
            ctx.add_init_script("if(!localStorage.getItem('isegye:playground:v1'))localStorage.setItem('isegye:playground:v1',"+json.dumps(json.dumps(state))+');')
            page=ctx.new_page();errors=[];page.on('pageerror',lambda err:errors.append(str(err)))
            page.route('https://**',lambda route:route.abort())
            page.goto(url+'/#/playground/play')
            expect(page.locator('.question-panel h1')).to_have_text('이세페2에서 주르르가 솔로 무대로 선보인 곡은 무엇일까요?')
            checks.append('실제 컴파일된 운영 컴포넌트에 승인 지문 표시')
            expect(page.locator('.question-tags')).to_contain_text('커뮤니티 답안 기준')
            checks.append('출처의 한계를 질문과 분리하여 유지')
            page.get_by_role('button',name='고민중독',exact=False).click()
            expect(page.locator('.feedback')).to_contain_text('정답이에요!')
            saved=page.evaluate("JSON.parse(localStorage.getItem('isegye:playground:v1'))")
            assert saved['session']['answers'][0]['correct'] is True
            assert saved['session']['answers'][0]['choice']==2
            checks.append('기존 정답 인덱스와 브라우저 저장 기록 보존')
            page.reload();expect(page.locator('.feedback')).to_contain_text('정답이에요!')
            checks.append('페이지 재조회 후 풀던 문제와 채점 유지')
            page.goto(url+'/#/playground');expect(page.locator('.cards')).to_contain_text('100개 문항')
            checks.append('합성 96문제에서 검수 대기 4문제 반영 후 100개 표시')
            assert not errors,errors
            checks.append('JavaScript 오류 없음')
            out=ROOT/'test-results/playground-maintenance';out.mkdir(parents=True,exist_ok=True)
            page.screenshot(path=str(out/'home.png'),full_page=True)
            (out/'report.json').write_text(json.dumps({'syntheticDataOnly':True,'checks':checks},ensure_ascii=False,indent=2)+'\n')
            browser.close()
    finally:server.shutdown();server.server_close()
print(json.dumps({'syntheticDataOnly':True,'passed':len(checks),'checks':checks},ensure_ascii=False))
