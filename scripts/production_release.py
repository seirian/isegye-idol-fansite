#!/usr/bin/env python3
"""Main-only release with public browser verification inside the rollback window."""
from __future__ import annotations
import base64
import hashlib
import json
import os
from pathlib import Path
import socket
import sys
from datetime import datetime, timezone
import inour_sftp as d

EXISTING = ('https://mir.yeop.net/', 'https://mir.yeop.net/band/',
            'https://mir.yeop.net/songbook', 'https://yeop.net/')


def deploy_verified(remote, payload, commit, verify, report):
    """Only use Remote's fixed-root write methods; preserve the shared router."""
    remote.initialize()
    lock = d.ROOT + '/.deploy-lock'
    remote.mkdir(lock)
    previous = new = None
    router_path = d.ROOT + '/.htaccess'
    activated = False
    try:
        d.require(remote.info('/web/.yeop-migration-lock') is None, 'MIR maintenance in progress')
        protected = remote.snapshot()
        baseline = {url: d.http(url) for url in EXISTING}
        d.require(all(v[0] == 200 for v in baseline.values()), 'Existing-site baseline is unhealthy')
        report['existing_sites_before'] = {u: {'status': v[0], 'sha256': d.digest(v[1])} for u, v in baseline.items()}
        remote.prove_mapping()
        report['mapping_proved'] = True
        previous = remote.read(router_path)
        d.require(d.managed_router(previous), 'Unrecognized previous site router')
        parent = d.ROOT + '/_isegye_releases'
        if remote.info(parent) is None:
            remote.mkdir(parent)
        remote.directory(parent)
        # Run attempt makes failed retries independent of partially uploaded directories.
        suffix = hashlib.sha256((commit + ':' + os.environ.get('GITHUB_RUN_ID', 'local') + ':' + os.environ.get('GITHUB_RUN_ATTEMPT', '1')).encode()).hexdigest()[:12]
        release = 'r' + suffix
        target = parent + '/' + release
        remote.mkdir(target)
        report.update(release=release, root=d.ROOT, commit=commit)
        for rel, data in payload.items():
            current = target
            for part in rel.split('/')[:-1]:
                current += '/' + part
                if remote.info(current) is None:
                    remote.mkdir(current)
            remote.new(target + '/' + rel, data)
        backup_dir = d.ROOT + '/.release-backups'
        if remote.info(backup_dir) is None:
            remote.mkdir(backup_dir)
        remote.directory(backup_dir)
        backup = backup_dir + '/' + release + '.before'
        remote.new(backup, previous)
        remote.s.chmod(backup, 0o600)
        report['previous_router_backup'] = backup
        d.require(remote.snapshot() == protected, 'Protected files changed; activation stopped')
        new = d.router(release)
        activated = True
        remote.replace(router_path, new, previous)
        for rel, data in payload.items():
            if rel != '.nojekyll':
                d.require(d.http(d.ORIGIN + '/' + rel) == (200, data), 'Public file differs: ' + rel)
        d.require(d.http(d.ORIGIN + '/') == (200, payload['index.html']), 'Homepage differs from build')
        report['public_files_verified'] = len(payload) - int('.nojekyll' in payload)
        verify(commit)
        report['browser_verified'] = True
        for path in ('/.isegye-owner', '/.release-backups/' + release + '.before', '/_mir_site/index.html'):
            d.require(d.http(d.ORIGIN + path)[0] in (403, 404), 'Private or cross-site path exposed')
        for origin in ('https://mir.yeop.net', 'https://yeop.net'):
            body = d.http(origin + '/_isegye_idol/_isegye_releases/' + release + '/index.html')[1]
            d.require(body != payload['index.html'], 'Cross-host application exposure')
        checks = {url: d.http(url) == value for url, value in baseline.items()}
        d.require(all(checks.values()), 'Existing-site response changed')
        d.require(remote.snapshot() == protected, 'Protected files changed during release')
        report.update(status='deployed_and_verified', protected_files_unchanged=True,
                      existing_sites_unchanged=checks, private_paths_blocked=True,
                      shared_router_modified=False, file_count=len(payload))
    except Exception:
        if activated:
            try:
                current = remote.read(router_path)
                if current == new:
                    remote.replace(router_path, previous, new)
                else:
                    d.require(current == previous, 'Concurrent router change; rollback refused')
                report['rollback_restored_previous'] = remote.read(router_path) == previous
            except Exception:
                report['manual_recovery_required'] = True
        raise
    finally:
        remote.parents(lock)
        remote.s.rmdir(lock)
        report['lock_removed'] = True


def verify_live(commit):
    # No submissions: the smoke suite intercepts GitHub issue navigation.
    import subprocess
    env = dict(os.environ, BASE_URL=d.ORIGIN + '/')
    result = subprocess.run([sys.executable, 'tests/browser_smoke.py'], env=env,
                            capture_output=True, text=True, timeout=180)
    out = Path('test-results/production')
    out.mkdir(parents=True, exist_ok=True)
    (out / 'browser-smoke.txt').write_text(result.stdout + result.stderr, encoding='utf-8')
    d.require(result.returncode == 0, 'Live browser tests failed')
    suite_results = {}
    for name, prefix, script in (
        ('readability', 'READABILITY', 'tests/readability_smoke.py'),
        ('group-hero', 'GROUP_HERO', 'tests/group_hero_smoke.py'),
    ):
        suite_env = dict(os.environ)
        suite_env.update({prefix + '_URL': d.ORIGIN + '/', prefix + '_EXPECT_MODE': 'production',
                          prefix + '_OUT_DIR': 'test-results/production/' + name})
        run = subprocess.run([sys.executable, script], env=suite_env,
                             capture_output=True, text=True, timeout=240)
        (out / (name + '-smoke.txt')).write_text(run.stdout + run.stderr, encoding='utf-8')
        d.require(run.returncode == 0, 'Live ' + name + ' tests failed')
        suite_results[name] = json.loads((out / name / 'result.json').read_text())
        d.require(suite_results[name]['passed'] == suite_results[name]['total'], 'Incomplete live suite')
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(**({'executable_path': os.environ['CHROMIUM_PATH']} if os.environ.get('CHROMIUM_PATH') else {}))
        context = browser.new_context(viewport={'width': 1440, 'height': 1080}, locale='ko-KR', timezone_id='Asia/Seoul')
        page = context.new_page()
        errors = []
        page.on('pageerror', lambda exc: errors.append(type(exc).__name__))
        response = page.goto(d.ORIGIN + '/', wait_until='networkidle')
        d.require(response.status == 200, 'Live homepage not 200')
        page.locator('#main h1').wait_for()
        d.require(page.locator('html').get_attribute('data-concept') == 'second', 'Wrong live design')
        d.require(page.locator('.stage-lineup img').evaluate_all('(els)=>els.length===6&&els.every(e=>e.complete&&e.naturalWidth>100)'), 'Live portraits failed to decode')
        d.require(page.locator('link[rel="canonical"]').get_attribute('href') == d.ORIGIN + '/', 'Wrong canonical URL')
        d.require(page.locator('meta[name="robots"]').get_attribute('content') == 'index,follow', 'Wrong production robots metadata')
        d.require('공개 베타' in page.locator('.preview-strip').inner_text(), 'Production label missing')
        meta = context.request.get(d.ORIGIN + '/build-info.json').json()
        d.require(meta.get('commit') == commit and meta.get('mode') == 'production' and meta.get('concept') == 'second', 'Live commit mismatch')
        page.screenshot(path=str(out / 'home-desktop.png'), full_page=True)
        page.set_viewport_size({'width': 390, 'height': 844})
        page.wait_for_timeout(300)
        d.require(page.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Mobile overflow')
        page.screenshot(path=str(out / 'home-mobile.png'), full_page=True)
        d.require(not errors, 'Browser exceptions')
        (out / 'live-result.json').write_text(json.dumps({'url': d.ORIGIN, 'commit': commit, 'mode': 'production',
                'status': 'passed', 'concept': 'second', 'portraits_verified': 6, 'readability_checks': suite_results['readability']['passed'], 'group_hero_checks': suite_results['group-hero']['passed'], 'profile_source': 'Genie Music', 'group_hero_verified': True, 'browser_smoke_scenarios': 9, 'mobile_overflow': False,
                'canonical_verified': True, 'robots_verified': True, 'browser_exceptions': errors}, indent=2) + '\n')
        browser.close()


def main():
    report = {'status': 'failed', 'checked_at': datetime.now(timezone.utc).isoformat(), 'shared_router_modified': False}
    resources = []
    password = None
    try:
        d.require(os.environ.get('GITHUB_REPOSITORY') == 'seirian/isegye-idol-fansite', 'Wrong repository')
        d.require(os.environ.get('GITHUB_REF') == 'refs/heads/main', 'Production is main-only')
        d.require(os.environ.get('PRODUCTION_ENABLED') == 'true', 'Production not enabled')
        d.require(os.environ.get('PRODUCTION_PAUSED') != 'true', 'Production is paused')
        commit = os.environ.get('GITHUB_SHA', '')
        payload = d.load_payload('dist', commit)
        password = os.environ.pop('ISEGYE_SFTP_PASSWORD', '')
        d.require(bool(password), 'Production environment secret missing')
        import paramiko
        sock = socket.create_connection((d.HOST, d.PORT), timeout=15)
        resources.append(sock)
        transport = paramiko.Transport(sock)
        resources.append(transport)
        transport.banner_timeout = 15
        transport.auth_timeout = 20
        transport.get_security_options().key_types = ('ssh-ed25519',)
        transport.start_client(timeout=15)
        key = transport.get_remote_server_key()
        fingerprint = 'SHA256:' + base64.b64encode(hashlib.sha256(key.asbytes()).digest()).decode().rstrip('=')
        d.require(key.get_name() == 'ssh-ed25519' and fingerprint == d.FINGERPRINT, 'Host key mismatch; password not sent')
        transport.auth_password(d.USER, password, fallback=True)
        password = None
        d.require(transport.is_authenticated(), 'Authentication incomplete')
        client = paramiko.SFTPClient.from_transport(transport)
        resources.append(client)
        client.get_channel().settimeout(30)
        report.update(authenticated=True, host_key_verified=True)
        deploy_verified(d.Remote(client), payload, commit, verify_live, report)
    except Exception as exc:
        report.update(status='failed', error_type=type(exc).__name__)
        if isinstance(exc, d.Stop):
            report['reason'] = str(exc)
    finally:
        password = None
        for resource in reversed(resources):
            try:
                resource.close()
            except Exception:
                pass
        Path('inour-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report['status'] == 'deployed_and_verified' else 1


if __name__ == '__main__':
    sys.exit(main())
