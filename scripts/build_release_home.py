#!/usr/bin/env python3
"""Package only the owner-approved simple home. No remote writes or credentials.

Historical compilers still create noindex previews. This main-only entry point
promotes their reviewed output without changing LIVE or the catalog sources.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import build_release_v04

ROOT = Path(__file__).resolve().parents[1]
ORIGIN = 'https://isegye-idol.kr/'
VERSION = '0.5.0'
REVIEW = 'c770c9d590c9e46a86c55d91d02d28d27da6ac05'
SECTIONS = ['live', 'members', 'recent-videos', 'music', 'schedule-history']


def verify_sources(approval: dict) -> None:
    if (approval.get('operatorApprovedDeployment') is not True or
            approval.get('reviewedCommit') != REVIEW):
        raise RuntimeError('Exact home review approval required')
    for name, digest in approval['sourceHashes'].items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest:
            raise RuntimeError('Reviewed home source changed: ' + name)


def production_text(text: str) -> str:
    for anchor in ('href="#/about">사이트소개</a>', 'function homeSimpleView()',
                   'function homeView(){return homeSimpleView();}',
                   'function liveHomeView()', 'const CATALOG=', 'const HISTORY='):
        if anchor not in text:
            raise RuntimeError('Approved home composition missing: ' + anchor)
    if '<div class="preview-strip">' in text:
        raise RuntimeError('Retired site-wide banner is present')
    text = text.replace('PRIVACY IN THIS PREVIEW', 'PRIVACY')
    text = text.replace('검토판에는 비공개 접수 서버가 없습니다.', '현재 비공개 접수 서버는 없습니다.')
    return text.replace('현재 검토판의 구현 범위', '현재 공개 베타의 구현 범위')


def package(source: Path, output: Path, mode: str, approval: dict) -> dict:
    if mode not in ('preview', 'production'):
        raise RuntimeError('Unknown release mode')
    if (mode == 'production' and os.getenv('GITHUB_REF') != 'refs/heads/main'):
        raise RuntimeError('Production is main-only')
    verify_sources(approval)
    source, output = Path(source), Path(output)
    if source.is_symlink() or output.is_symlink() or source.resolve() == output.resolve():
        raise RuntimeError('Unsafe release path')
    meta = json.loads((source / 'build-info.json').read_text())
    build_release_v04.validate(meta, json.loads((ROOT / 'review/live-release.json').read_text()))
    home = meta.get('homeReview', {})
    if (meta.get('mode') != 'preview' or meta.get('review') != 'home-simple' or
            home.get('livePreserved') is not True or home.get('communitySubmissionBanner') is not False or
            home.get('sections') != SECTIONS):
        raise RuntimeError('Approved simple home is incomplete')
    html = (source / 'index.html').read_text()
    if 'content="noindex,nofollow"' not in html or 'rel="canonical"' in html:
        raise RuntimeError('Expected unpublished preview metadata')
    app = (source / 'src/app.js').read_text()
    public_app = production_text(app)  # Validate composition in both modes.
    commit = os.getenv('GITHUB_SHA', meta['commit'])
    if mode == 'production' and not re.fullmatch(r'[0-9a-f]{40}', commit):
        raise RuntimeError('Full production commit required')
    if output.exists():
        shutil.rmtree(output)
    shutil.copytree(source, output, ignore=shutil.ignore_patterns('review.html') if mode == 'production' else None)
    meta.update(version=VERSION, mode=mode, commit=commit,
                branch=os.getenv('GITHUB_REF_NAME', 'main' if mode == 'production' else 'develop'),
                operatorApprovedDeployment=True, approvedHomeReview=REVIEW,
                previousProductionCommit=approval['previousProductionCommit'],
                sourceBackup=approval['sourceBackup'], rightsPermissionVerified=False)
    data = (output / 'src/data.js').read_text()
    data = re.sub(r"version:'[^']+'", "version:'" + VERSION + "'", data, count=1)
    (output / 'src/data.js').write_text(data)
    if mode == 'production':
        html = html.replace('content="noindex,nofollow"', 'content="index,follow"')
        html = re.sub(r'<title>.*?</title>', '<title>ISEGYE! · 이세계아이돌 비공식 팬 아카이브</title>', html)
        html = html.replace('</head>', '  <link rel="canonical" href="' + ORIGIN + '">\n</head>')
        (output / 'src/app.js').write_text(public_app)
        (output / 'robots.txt').write_text('User-agent: *\nAllow: /\n')
    (output / 'index.html').write_text(html)
    (output / 'build-info.json').write_text(json.dumps(meta, ensure_ascii=False, indent=2) + '\n')
    subprocess.run(['node', '--check', str(output / 'src/app.js')], check=True)
    if mode == 'production':
        import inour_sftp
        inour_sftp.load_payload(output, commit)
    return meta


def main() -> None:
    mode = 'production' if os.getenv('DEPLOY_ENV') == 'production' else 'preview'
    if mode == 'production' and os.getenv('GITHUB_REF') != 'refs/heads/main':
        raise RuntimeError('Production is main-only')
    approval = json.loads((ROOT / 'review/home-release.json').read_text())
    verify_sources(approval)
    # These child processes only generate local noindex files. The actual ref is
    # validated above; upload is exclusively the existing production workflow.
    env = dict(os.environ, DEPLOY_ENV='preview', GITHUB_REF='refs/heads/feature/home-simple')
    for script in ('build_release_v04.py', 'build_home_review.py'):
        subprocess.run([sys.executable, str(ROOT / 'scripts' / script)], cwd=ROOT, env=env, check=True)
    meta = package(ROOT / 'home-dist', ROOT / 'dist', mode, approval)
    print(json.dumps({'status': 'built', 'version': VERSION, 'mode': mode,
                      'commit': meta['commit'], 'home': 'simple', 'livePreserved': True}))


if __name__ == '__main__':
    main()
