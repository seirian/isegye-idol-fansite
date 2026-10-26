"""Read the deployed Pages paths and ensure application bundles are not published."""
import json,os
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError
ROOT='https://seirian.github.io/isegye-idol-fansite/'
OUT=Path('test-results/pages-notice');OUT.mkdir(parents=True,exist_ok=True)
checks=[]
def read(path):
    try:r=urlopen(Request(ROOT+path,headers={'Cache-Control':'no-cache'}),timeout=20)
    except HTTPError as e:r=e
    with r:return r.status,r.read(3*1024*1024).decode(errors='replace')
def check(name,ok):
    checks.append({'name':name,'passed':bool(ok)})
    if not ok:raise AssertionError(name)
try:
    for path in ('','second/','previews/feature-readability/','previews/feature-live/','previews/feature-home-simple/'):
        code,text=read(path);check('origin-only notice '+path,code==200 and 'data-access-notice="true"' in text and 'https://isegye-idol.kr/' in text and '<script' not in text)
        for asset in ('src/app.js','src/data.js','review.html'):
            code,text=read(path+asset);check('old bundle unavailable '+path+asset,code==404 and 'const CATALOG=' not in text and 'function homeView' not in text)
    code,text=read('notice-info.json');check('notice commit matches',code==200 and json.loads(text)['commit']==os.environ['GITHUB_SHA'])
finally:(OUT/'result.json').write_text(json.dumps({'passed':sum(c['passed'] for c in checks),'total':len(checks),'checks':checks},ensure_ascii=False,indent=2)+'\n')
