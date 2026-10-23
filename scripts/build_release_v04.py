#!/usr/bin/env python3
"""Promote the approved LIVE/catalog review; never performs network writes."""
from __future__ import annotations
import json, os, re, shutil, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
ORIGIN='https://isegye-idol.kr/'

def validate(meta, approval):
    if approval.get('operatorApprovedDeployment') is not True or approval.get('reviewedCommit')!='a2c8993a2e20b25c689f61b64dcabda0a0866d26':
        raise RuntimeError('The reviewed LIVE release must be explicitly approved')
    expected=[(meta.get('verifiedPortraitCount'),6),(meta.get('profileSource'),'Genie Music'),
              (meta.get('groupHero',{}).get('sha256'),approval['groupImageSha256']),
              (meta.get('live',{}).get('members'),6),(meta.get('catalog',{}).get('songs'),154),
              (meta.get('catalog',{}).get('channels'),21),(meta.get('musicVideoAudit',{}).get('linked'),151),
              (meta.get('visualHistory',{}).get('historyItems'),55),
              (meta.get('visualHistory',{}).get('navigationCount'),7)]
    if any(a!=b for a,b in expected):raise RuntimeError('Approved review content is incomplete')
    if meta.get('live',{}).get('failureMeansOffline') is not False:raise RuntimeError('LIVE error safety contract changed')

def production_text(text):
    for anchor in ('멤버·음악 개선 검토','hero-group','function liveView(','const CATALOG=','const HISTORY='):
        if anchor not in text:raise RuntimeError('Release composition missing: '+anchor)
    text=text.replace('멤버·음악 개선 검토','공개 베타').replace('읽기 편하게, 더 가까이','좋아하는 마음을, 오래도록')
    text=text.replace('PRIVACY IN THIS PREVIEW','PRIVACY')
    text=text.replace('검토판에는 비공개 접수 서버가 없습니다.','현재 비공개 접수 서버는 없습니다.')
    text=text.replace('현재 검토판의 구현 범위','현재 공개 베타의 구현 범위')
    return text

def package(source, output, mode, approval):
    if mode not in ('preview','production'):raise RuntimeError('Invalid release mode')
    source,output=Path(source),Path(output)
    if source.is_symlink() or output.is_symlink() or source.resolve()==output.resolve():raise RuntimeError('Unsafe build path')
    meta=json.loads((source/'build-info.json').read_text());validate(meta,approval)
    html=(source/'index.html').read_text()
    if 'content="noindex,nofollow"' not in html or 'rel="canonical"' in html:raise RuntimeError('Expected unpromoted preview')
    commit=os.getenv('GITHUB_SHA',meta['commit'])
    if mode=='production' and not re.fullmatch(r'[0-9a-f]{40}',commit):raise RuntimeError('Full production commit required')
    if output.exists():shutil.rmtree(output)
    shutil.copytree(source,output,ignore=shutil.ignore_patterns('review.html') if mode=='production' else None)
    meta.update(mode=mode,commit=commit,version='0.4.0',branch=os.getenv('GITHUB_REF_NAME') or ('main' if mode=='production' else 'develop'),
                operatorApprovedDeployment=True,approvedReview=approval['reviewedCommit'],sourceBackup=approval['sourceBackup'],
                previousProductionCommit=approval['previousProductionCommit'],rightsPermissionVerified=False)
    (output/'src/data.js').write_text(re.sub(r"version:'[^']+'","version:'0.4.0'",(output/'src/data.js').read_text(),count=1))
    if mode=='production':
        html=html.replace('content="noindex,nofollow"','content="index,follow"')
        html=re.sub(r'<title>.*?</title>','<title>ISEGYE! · 이세계아이돌 비공식 팬 아카이브</title>',html)
        html=html.replace('</head>','  <link rel="canonical" href="'+ORIGIN+'">\n</head>')
        (output/'src/app.js').write_text(production_text((output/'src/app.js').read_text()))
        (output/'robots.txt').write_text('User-agent: *\nAllow: /\n')
    (output/'index.html').write_text(html)
    (output/'build-info.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n')
    subprocess.run(['node','--check',str(output/'src/app.js')],check=True)
    if mode=='production':
        import inour_sftp
        inour_sftp.load_payload(output,commit)
    return meta

def main():
    mode='production' if os.getenv('DEPLOY_ENV')=='production' else 'preview'
    if mode=='production' and os.getenv('GITHUB_REF')!='refs/heads/main':raise RuntimeError('Production is main-only')
    approval=json.loads((ROOT/'review/live-release.json').read_text())
    subprocess.run([sys.executable,str(ROOT/'scripts/build_live.py')],cwd=ROOT,env=dict(os.environ,DEPLOY_ENV='preview'),check=True)
    meta=package(ROOT/'live-dist',ROOT/'dist',mode,approval)
    print(json.dumps({'status':'built','version':meta['version'],'mode':mode,'commit':meta['commit'],'output':'dist'}))
if __name__=='__main__':main()
