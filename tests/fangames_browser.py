#!/usr/bin/env python3
"""Real HTTP Playwright coverage for three original fan games, no external assets."""
from pathlib import Path
import json, threading, socket, http.server, socketserver
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
DIST=ROOT/"fangames-dist"
OUT=ROOT/"test-results/fangames"
OUT.mkdir(parents=True,exist_ok=True)
class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self,*a,**kw):super().__init__(*a,directory=str(DIST),**kw)
    def log_message(self,*a):pass
class Server(socketserver.ThreadingTCPServer):allow_reuse_address=True
with socket.socket() as s:s.bind(("127.0.0.1",0));PORT=s.getsockname()[1]
server=Server(("127.0.0.1",PORT),Handler)
thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
report={"checks":[],"errors":[]}
def ok(x,label):
    assert x,label;report["checks"].append(label)
def stage(page,name):
    page.screenshot(path=str(OUT/(name+".png")),full_page=True)
with sync_playwright() as p:
  browser=p.chromium.launch(headless=True,args=["--no-sandbox"])
  for width,height in ((1440,900),(390,844),(320,720)):
    context=browser.new_context(viewport={"width":width,"height":height},device_scale_factor=1,has_touch=width<500,is_mobile=width<500)
    page=context.new_page()
    page.on("pageerror",lambda e:report["errors"].append(str(e)[:400]))
    page.goto(f"http://127.0.0.1:{PORT}/review.html",wait_until="domcontentloaded")
    ok(page.locator(".game-card").count()==3,f"3 game cards at {width}")
    ok(page.locator("style").count()==1 and page.locator("script").count()==1,f"single hashes {width}")
    ok(page.locator("body").evaluate("(e)=>e.scrollWidth<=window.innerWidth+3"),f"no horizontal overflow {width}")
    stage(page,f"home-{width}")
    page.locator('a[href="#/arcade"]').first.click()
    ok(page.get_by_role("heading",name="우당탕 이세돌").count()>=1,f"arcade exists {width}")
    page.locator('[data-action="practice"]').click()
    page.wait_for_timeout(930)
    ok(page.locator("#stage-input .tile.bad").count()>=1,f"EMP challenge active {width}")
    page.locator("#stage-input .tile.bad").first.click()
    ok(page.locator("#stage-input .tile.bad").count()>=1,f"EMP acts {width}")
    stage(page,f"arcade-{width}")
    page.locator('a[href="#/quest"]').first.click()
    page.locator('[data-pick="2"]').first.click()
    page.locator('[data-ally="4"]').first.click()
    ok("릴파" in page.locator(".member-info").first.inner_text(),f"playable character selection {width}")
    page.locator('[data-action="start"]').click()
    ok(page.locator("#quest-canvas").count()==1,f"canvas game starts {width}")
    page.wait_for_timeout(700)
    ok(page.locator("#q-time").inner_text().startswith("0:"),f"survival ticker {width}")
    page.locator('[data-action="pause"]').click()
    ok(not page.locator("#q-overlay").is_hidden(),f"pause panel {width}")
    page.locator('#q-overlay [data-action="pause"]').click()
    ok(page.locator("#q-overlay").is_hidden(),f"resume {width}")
    stage(page,f"quest-{width}")
    page.locator('a[href="#/escape"]').first.click()
    page.locator(".puzzle-cell").first.wait_for(state="visible",timeout=5000)
    ok(page.locator(".puzzle-cell").count()==63,f"9x7 board {width}")
    ok(page.locator("[data-level]").count()==8,f"8 levels {width}")
    page.locator('[data-select="2"]').first.click()
    for _ in range(2):page.locator('[data-move="right"]').click()
    for _ in range(4):page.locator('[data-move="up"]').click()
    page.locator('[data-action="skill"]').click()
    ok(page.locator(".puzzle-cell.gate").count()==0,f"lilpa remotely opens door {width}")
    page.locator('[data-action="undo"]').click()
    ok(page.locator(".puzzle-cell.gate").count()==1,f"undo restores gate {width}")
    page.locator('[data-level="7"]').click()
    ok(page.locator(".puzzle-cell").count()==63,f"level 8 loads {width}")
    stage(page,f"escape-{width}")
    page.close();context.close()
  browser.close()
server.shutdown();server.server_close()
(OUT/"report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
assert not report["errors"],str(report["errors"])
print(json.dumps({"checks":len(report["checks"]),"errors":report["errors"],"screenshots":len(list(OUT.glob("*.png")))},ensure_ascii=False))
