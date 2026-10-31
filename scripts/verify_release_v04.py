#!/usr/bin/env python3
"""Exercise the exact dist or deployed URL. Never submits reports or deploys files."""
from __future__ import annotations
import json,os,subprocess,sys,time
from pathlib import Path
from urllib.request import urlopen
ROOT=Path(__file__).resolve().parents[1]

def main():
    out=ROOT/os.getenv('RELEASE_OUT','test-results/release-v04');out.mkdir(parents=True,exist_ok=True)
    url=os.getenv('RELEASE_URL','http://127.0.0.1:4199/').rstrip('/')+'/'
    mode=os.getenv('RELEASE_MODE','preview');server=None;summary={'url':url,'mode':mode,'commit':os.getenv('GITHUB_SHA'),'status':'failed','suites':{}}
    suites=[('core','tests/browser_smoke.py',{'BASE_URL':url,'SMOKE_OUT':str(out/'core')}),
            ('live','tests/live_browser.py',{'LIVE_URL':url,'LIVE_TEST_OUT':str(out/'live'),'LIVE_REAL_CHECK':'true'}),
            ('catalog','tests/catalog_browser.py',{'CATALOG_URL':url,'CATALOG_OUT':str(out/'catalog')}),
            ('visual','tests/visual_history_browser.py',{'VISUAL_URL':url,'VISUAL_OUT':str(out/'visual'),'VISUAL_REAL_CHECK':'true'}),
            ('official-mv','tests/official_mv_browser.py',{'MV_URL':url,'MV_OUT':str(out/'official-mv')}),
            ('music-sources','tests/music_sources_browser.py',{'MUSIC_URL':url,'MUSIC_OUT':str(out/'music-sources')}),
            ('group-hero','tests/group_hero_smoke.py',{'GROUP_HERO_URL':url,'GROUP_HERO_OUT_DIR':str(out/'group-hero'),'GROUP_HERO_EXPECT_MODE':mode}),
            ('home','tests/home_simple_browser.py',{'HOME_URL':url,'HOME_OUT':str(out/'home'),'HOME_EXPECT_MODE':mode,'HOME_EXPECT_APPROVED':'true','HOME_REAL_CHECK':'true'}),
            ('home-brief','tests/home_brief_browser.py',{'HOME_URL':url,'BRIEF_OUT':str(out/'home-brief')}),
            ('integrity','tests/release_v04_browser.py',{'RELEASE_URL':url,'RELEASE_OUT':str(out/'integrity'),'RELEASE_MODE':mode})]
    suites.append(('schedule','tests/schedule_browser.py',{'SCHEDULE_URL':url,'SCHEDULE_OUT':str(out/'schedule')}))
    suites.append(('berriz','tests/berriz_browser.py',{'BERRIZ_URL':url,'BERRIZ_OUT':str(out/'berriz')}))
    suites.append(('toolbar','tests/schedule_toolbar_browser.py',{'TOOLBAR_URL':url,'TOOLBAR_OUT':str(out/'toolbar')}))
    suites.append(('legal-shell','tests/legal_shell_browser.py',{'LEGAL_SHELL_URL':url,'LEGAL_SHELL_OUT':str(out/'legal-shell')}))
    try:
        if 'RELEASE_URL' not in os.environ:
            server=subprocess.Popen([sys.executable,'-m','http.server','4199','--bind','127.0.0.1','--directory','dist'],cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            for _ in range(50):
                try:urlopen(url,timeout=1).close();break
                except OSError:time.sleep(.1)
            else:raise RuntimeError('Local release server did not start')
        for name,script,settings in suites:
            result=subprocess.run([sys.executable,str(ROOT/script)],cwd=ROOT,env=dict(os.environ,**settings),capture_output=True,text=True,timeout=240)
            (out/(name+'.log')).write_text(result.stdout+result.stderr)
            summary['suites'][name]={'passed':result.returncode==0}
            print(name+': '+('passed' if result.returncode==0 else 'FAILED'),flush=True)
            if result.returncode:raise RuntimeError('Release suite failed: '+name+'\n'+result.stdout[-1200:]+result.stderr[-3000:])
            report=out/name/'result.json'
            if report.exists():
                data=json.loads(report.read_text());summary['suites'][name].update(checks=data.get('passed'),total=data.get('total'))
                if data.get('passed')!=data.get('total'):raise RuntimeError('Incomplete suite: '+name)
        capture=subprocess.run([sys.executable,str(ROOT/'tests/home_capture.py')],cwd=ROOT,env=dict(os.environ,HOME_URL=url,HOME_OUT=str(out/'home')),capture_output=True,text=True,timeout=120)
        (out/'home-capture.log').write_text(capture.stdout+capture.stderr)
        if capture.returncode:raise RuntimeError('Real home capture failed: '+capture.stderr[-2000:])
        summary['status']='verified'
    finally:
        (out/'result.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
        if server:server.terminate();server.wait(timeout=5)
if __name__=='__main__':main()
