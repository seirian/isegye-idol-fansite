#!/usr/bin/env python3
"""Package the owner-approved readable group-hero design without remote writes.

The preview compilers remain noindex-only. This explicit release entry point
validates the approved result and applies production metadata on main only.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'dist'
ORIGIN = 'https://isegye-idol.kr/'


def production_app(text: str) -> str:
    required = ('디자인 개선 검토', '읽기 편하게, 더 가까이', 'hero-group', 'profile-attribution')
    for anchor in required:
        if anchor not in text:
            raise RuntimeError('Reviewed production wording anchor missing: ' + anchor)
    text = text.replace('디자인 개선 검토', '공개 베타')
    text = text.replace('읽기 편하게, 더 가까이', '좋아하는 마음을, 오래도록')
    for before, after in (
        ('검토판에 등록된 음반 6건입니다.', '현재 등록된 음반 6건입니다.'),
        ('첫 검토판에는', '공개 베타에는'),
        ('검토판에는 비공개 접수 서버가 없습니다.', '현재 비공개 접수 서버는 없습니다.'),
        ('현재 검토판의 구현 범위', '현재 공개 베타의 구현 범위'),
    ):
        text = text.replace(before, after)
    if any(t in text for t in ('YOU ARE INVITED TO', 'OUR<br>UNIVERSE', 'portrait-credit')):
        raise RuntimeError('Unapproved legacy UI remains')
    return text


def package(source: Path, mode: str, approval: dict) -> dict:
    """Promote only the generated current build; never copy sources or credentials."""
    if mode not in ('preview', 'production'):
        raise RuntimeError('Unknown package mode')
    if source.is_symlink() or OUT.is_symlink():
        raise RuntimeError('Symlink build directory refused')
    meta = json.loads((source / 'build-info.json').read_text(encoding='utf-8'))
    if (meta.get('verifiedPortraitCount') != 6 or meta.get('pendingPortraitCount') != 0
            or meta.get('profileSource') != 'Genie Music'
            or meta.get('groupHero', {}).get('sha256') != approval['groupImageSha256']):
        raise RuntimeError('Approved profiles and group hero are required')
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(source, OUT, ignore=shutil.ignore_patterns('review.html'))
    html = (OUT / 'index.html').read_text(encoding='utf-8')
    if 'content="noindex,nofollow"' not in html or 'rel="canonical"' in html:
        raise RuntimeError('Expected unpromoted preview metadata')
    meta.update(mode=mode, branch=os.environ.get('GITHUB_REF_NAME') or
                ('main' if mode == 'production' else 'develop'),
                commit=os.environ.get('GITHUB_SHA', meta['commit']), version='0.3.0',
                operatorApprovedDeployment=True, rightsPermissionVerified=False,
                sourceBackup=approval['sourceBackup'], approvedReview=approval['reviewedCommit'])
    if mode == 'production':
        if not re.fullmatch(r'[0-9a-f]{40}', meta['commit']):
            raise RuntimeError('Production build requires full GITHUB_SHA')
        html = html.replace('content="noindex,nofollow"', 'content="index,follow"')
        html = html.replace('</head>', '  <link rel="canonical" href="' + ORIGIN + '">\n</head>')
        html = re.sub(r'<title>.*?</title>', '<title>ISEGYE! · 이세계아이돌 비공식 팬 아카이브</title>', html)
        app = production_app((OUT / 'src/app.js').read_text(encoding='utf-8'))
        (OUT / 'src/app.js').write_text(app, encoding='utf-8')
        (OUT / 'robots.txt').write_text('User-agent: *\nAllow: /\n', encoding='utf-8')
    else:
        shutil.copy2(source / 'review.html', OUT / 'review.html')
    (OUT / 'index.html').write_text(html, encoding='utf-8')
    (OUT / 'build-info.json').write_text(json.dumps(meta, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    subprocess.run(['node', '--check', str(OUT / 'src/app.js')], check=True)
    if mode == 'production':
        import inour_sftp
        inour_sftp.load_payload(OUT, meta['commit'])
    return meta


def main() -> None:
    mode = 'production' if os.environ.get('DEPLOY_ENV') == 'production' else 'preview'
    if mode == 'production' and os.environ.get('GITHUB_REF') not in (None, '', 'refs/heads/main'):
        raise RuntimeError('Production builds are main-only in Actions')
    approval = json.loads((ROOT / 'review/release.json').read_text(encoding='utf-8'))
    if approval.get('approvedDesign') != 'readability-group-hero' or approval.get('operatorApprovedDeployment') is not True:
        raise RuntimeError('Current design has not been selected for release')
    # These child compilers only create local noindex artifacts. Deployment is
    # performed separately by the existing production environment workflow.
    env = dict(os.environ, DEPLOY_ENV='preview')
    for script in ('prepare_genie_portraits.py', 'build_group_hero.py'):
        subprocess.run([sys.executable, str(ROOT / 'scripts' / script)], cwd=ROOT, env=env, check=True)
    meta = package(ROOT / 'readability-dist', mode, approval)
    print(json.dumps({'status': 'built', 'mode': mode, 'output': 'dist',
                      'commit': meta['commit'], 'portraits': 6, 'groupHero': True}, ensure_ascii=False))


if __name__ == '__main__':
    main()
