#!/usr/bin/env python3
"""Replace public static previews with a link to the server-authenticated site."""
from pathlib import Path
import json,os,shutil
OUT=Path('/tmp/isegye-pages')
HTML='''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow"><title>ISEGYE! · 운영 사이트 안내</title><style>body{margin:0;min-height:100vh;display:grid;place-items:center;background:#fcf8fa;color:#342d38;font:18px/1.8 system-ui,sans-serif}main{max-width:36rem;padding:2rem;text-align:center}h1{font-size:1.8rem}a{display:inline-block;background:#b52d55;color:white;padding:.7rem 1.4rem;border-radius:2rem;text-decoration:none}</style></head><body><main data-access-notice="true"><h1>ISEGYE!</h1><p>사이트는 운영 주소에서 이용해 주세요.<br>로그인과 접근 권한은 운영 사이트에서 확인합니다.</p><a href="https://isegye-idol.kr/">운영 사이트로 이동</a></main></body></html>'''
if OUT.exists():shutil.rmtree(OUT)
OUT.mkdir()
for path in ('index.html','404.html','second/index.html','previews/feature-readability/index.html','previews/feature-live/index.html','previews/feature-home-simple/index.html'):
    target=OUT/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_text(HTML)
(OUT/'.nojekyll').touch()
(OUT/'notice-info.json').write_text(json.dumps({'mode':'authenticated-origin-notice','commit':os.getenv('GITHUB_SHA')}))
(OUT/'robots.txt').write_text('User-agent: *\nDisallow: /\n')
print('Built origin-only notice; no application JavaScript, catalogs, thumbnails or offline HTML included.')
