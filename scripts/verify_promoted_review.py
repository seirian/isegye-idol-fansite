#!/usr/bin/env python3
"""Validate accepted second-review rendering and the exact promoted bundle."""
from pathlib import Path
import json,os,subprocess,sys,time
from urllib.request import urlopen
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'test-results/review-promotion';OUT.mkdir(parents=True,exist_ok=True)

def server(directory,port):
 p=subprocess.Popen([sys.executable,'-m','http.server',str(port),'--bind','127.0.0.1','--directory',str(directory)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 for _ in range(60):
  try:urlopen(f'http://127.0.0.1:{port}/',timeout=1).close();return p
  except OSError:time.sleep(.1)
 p.terminate();raise RuntimeError('Local verification server unavailable')

def main():
 servers=[];summary={'status':'failed','commit':os.getenv('GITHUB_SHA'),'suites':{},'productionWrites':False}
 try:
  servers.append(server(ROOT/'review-2nd-dist',4197));servers.append(server(ROOT/'dist',4198))
  suites=[('accepted-ui','tests/review_2nd_browser.py'),('mobile','tests/review_2nd_mobile_browser.py'),('heading-footer','tests/review_2nd_polish_browser.py'),('cleanup','tests/review_2nd_cleanup_browser.py'),('production-runtime','tests/promoted_review_browser.py'),('member-legal-ui','tests/member_legal_browser.py'),('member-legal-auth','tests/auth/browser.py')]
  for name,script in suites:
   env=dict(os.environ,REVIEW_URL='http://127.0.0.1:4197/review.html',PROMOTED_URL='http://127.0.0.1:4198/')
   if name=='member-legal-auth':env['MEMBER_LEGAL_REAL']='1'
   run=subprocess.run([sys.executable,script],cwd=ROOT,env=env,capture_output=True,text=True,timeout=240)
   (OUT/(name+'.log')).write_text(run.stdout+run.stderr)
   summary['suites'][name]={'passed':run.returncode==0}
   print(name+': '+('passed' if not run.returncode else 'FAILED'),flush=True)
   if run.returncode:raise RuntimeError(name+' failed: '+run.stderr[-3000:])
  summary['status']='verified'
 finally:
  (OUT/'result.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
  for p in servers:p.terminate();p.wait(timeout=5)
if __name__=='__main__':main()
