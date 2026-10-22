#!/usr/bin/env python3
"""Compile the approved second design and package it for preview or production.

The reviewed preview compiler remains the single visual source of truth. This
entry point promotes its output to the fixed dist/ deployment contract; only
main can produce a production package in Actions. No remote server is touched.
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


def production_app(text: str) -> str:
    replacements = (
        ('DESIGN PREVIEW 02', '공개 베타 · 02'),
        ('SECOND CONCEPT', 'FAN ARCHIVE'),
        ('멤버와 더 가까이, 새로운 팬사이트 시안', '멤버와 더 가까이, 우리의 팬 아카이브'),
        ('두 번째 디자인 시안 · feature/second', '이세계아이돌 비공식 팬 아카이브 · 공개 베타'),
        ('이번 시안에 포함하지 않은 기능', '아직 제공하지 않는 기능'),
        ('운영 적용 전 요청한 원본 이미지와 개별 권리·사용 범위를 확인해야 합니다.',
         '현재 이미지는 공개된 공식 소개 페이지의 프로필을 임시 사용합니다. 요청한 나무위키 원본과의 일치 및 개별 이용허락 확인은 미완료이며, 출처 표시는 이용허락을 대신하지 않습니다.'),
        ('ISEGYE! 두 번째 시안', 'ISEGYE! 비공식 팬 아카이브'),
        ('검토판에 등록된 음반 6건입니다.', '현재 등록된 음반 6건입니다.'),
        ('첫 검토판에는', '공개 베타에는'),
        ('검토판에는 비공개 접수 서버가 없습니다.', '현재 비공개 접수 서버는 없습니다.'),
        ('현재 검토판의 구현 범위', '현재 공개 베타의 구현 범위'),
        ('/commits/develop/', '/commits/main/'),
        ("SITE.repo+'/tree/feature/second','feature/second 브랜치'", "SITE.repo+'/tree/main','운영 소스 · main'"),
    )
    for before, after in replacements:
        if before not in text:
            raise RuntimeError('Reviewed production wording anchor missing: ' + before)
        text = text.replace(before, after)
    return text


def main() -> None:
    mode = 'production' if os.environ.get('DEPLOY_ENV') == 'production' else 'preview'
    if mode == 'production' and os.environ.get('GITHUB_REF') not in (None, '', 'refs/heads/main'):
        raise RuntimeError('Production builds are main-only in Actions')
    approval = json.loads((ROOT / 'second/release.json').read_text(encoding='utf-8'))
    if approval.get('approvedConcept') != 'second' or approval.get('operatorApprovedDeployment') is not True:
        raise RuntimeError('Second design has not been selected for release')
    if OUT.is_symlink():
        raise RuntimeError('Refusing symlink dist directory')
    # First compile the reviewed noindex concept. Production-specific metadata,
    # wording, filenames and payload validation are applied below, not in its UI.
    args = [sys.executable, str(ROOT / 'scripts/build_second.py')]
    if os.environ.get('ISEGYE_PORTRAIT_ASSET_DIR'):
        args += ['--asset-dir', os.environ['ISEGYE_PORTRAIT_ASSET_DIR']]
    subprocess.run(args, cwd=ROOT, env=dict(os.environ, DEPLOY_ENV='preview'), check=True)
    source = ROOT / 'second-dist'
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(source, OUT, ignore=shutil.ignore_patterns('review-second.html', 'image-sources.json'))
    (OUT / 'src/second-app.js').rename(OUT / 'src/app.js')
    (OUT / 'src/second.css').rename(OUT / 'src/styles.css')
    shutil.copy2(source / 'image-sources.json', OUT / 'assets/portraits/sources.json')
    html = (OUT / 'index.html').read_text(encoding='utf-8')
    html = html.replace('./src/second-app.js', './src/app.js').replace('./src/second.css', './src/styles.css')
    meta = json.loads((OUT / 'build-info.json').read_text(encoding='utf-8'))
    meta.update(mode=mode, branch=(os.environ.get('GITHUB_REF_NAME') or
                ('main' if mode == 'production' else 'develop')),
                commit=os.environ.get('GITHUB_SHA', meta['commit']), version='0.2.0',
                operatorApprovedDeployment=True, rightsPermissionVerified=False,
                sourceBackup=approval['sourceBackup'], imageSource='PARABLE official profiles — attributed interim portraits')
    meta.pop('productionCleared', None)
    if mode == 'production':
        if not re.fullmatch(r'[0-9a-f]{40}', meta['commit']):
            raise RuntimeError('Production build requires full GITHUB_SHA')
        html = html.replace('content="noindex,nofollow"', 'content="index,follow"')
        html = html.replace('</head>', '  <link rel="canonical" href="https://isegye-idol.kr/">\n</head>')
        html = html.replace('ISEGYE! · 두 번째 팬사이트 시안', 'ISEGYE! · 이세계아이돌 비공식 팬 아카이브')
        app = production_app((OUT / 'src/app.js').read_text(encoding='utf-8'))
        (OUT / 'src/app.js').write_text(app, encoding='utf-8')
        (OUT / 'robots.txt').write_text('User-agent: *\nAllow: /\n', encoding='utf-8')
    else:
        # The offline review stays noindex and uses the same six embedded portraits.
        shutil.copy2(source / 'review-second.html', OUT / 'review.html')
    (OUT / 'index.html').write_text(html, encoding='utf-8')
    (OUT / 'build-info.json').write_text(json.dumps(meta, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    subprocess.run(['node', '--check', str(OUT / 'src/app.js')], check=True)
    if mode == 'production':
        import inour_sftp
        inour_sftp.load_payload(OUT, meta['commit'])
    print(json.dumps({'status': 'built', 'mode': mode, 'concept': 'second', 'output': 'dist',
                      'commit': meta['commit'], 'namuPortraitsVerified': False}, ensure_ascii=False))


if __name__ == '__main__':
    main()
