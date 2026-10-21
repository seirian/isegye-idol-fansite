#!/usr/bin/env python3
"""User-authorized ISEGYE host routing only. No application deployment.

The only shared-file target is /web/.htaccess. The audited original must
match exactly and is backed up before an atomic, append-only replacement.
"""
from __future__ import annotations
import base64
import hashlib
import json
import os
from pathlib import Path
import socket
import stat
import sys
from datetime import datetime, timezone

AUDITED_SHA = '160341acd7b3f74f147b1556ed6e3c94e9cdf84fc7150c6e13064c84ffae5697'
SHARED = '/web/.htaccess'
SHARED_LOCK = '/web/.yeop-migration-lock'
ROOT = '/web/_isegye_idol'
BRIDGE = (b'\n# BEGIN ISEGYE-SUBDOMAIN-BRIDGE-V1\n'
          b'# Authorized host-only append; preserve the preceding MIR rules exactly.\n'
          b'RewriteCond %{HTTP_HOST} ^isegye-idol\\.kr(?::[0-9]+)?$ [NC]\n'
          b'RewriteCond %{REQUEST_URI} !^/_isegye_idol(?:/|$)\n'
          b'RewriteRule ^(.*)$ _isegye_idol/$1 [L]\n'
          b'# END ISEGYE-SUBDOMAIN-BRIDGE-V1\n')

class Stop(RuntimeError):
    pass

def require(ok: bool, message: str) -> None:
    if not ok:
        raise Stop(message)

def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def plan(current: bytes) -> tuple[bytes, bytes]:
    """Accept the audited original or exactly that original plus our block."""
    require(isinstance(current, bytes), 'Shared router missing')
    original = current[:-len(BRIDGE)] if current.endswith(BRIDGE) else current
    require(sha(original) == AUDITED_SHA, 'Shared router changed since audit; manual review required')
    require(original.startswith(b'# MIR-SUBDOMAIN-BRIDGE-V1\n'), 'MIR compatibility marker missing')
    return original, original + BRIDGE

def apply(report: dict) -> None:
    import paramiko
    import inour_sftp as d
    require(os.environ.get('GITHUB_REPOSITORY') == 'seirian/isegye-idol-fansite', 'Wrong repository')
    require(os.environ.get('GITHUB_REF') == 'refs/heads/develop', 'Infrastructure change restricted to develop')
    require(os.environ.get('ISEGYE_ALLOW_SHARED_ROUTER_APPEND') == 'true', 'Explicit shared-router consent required')
    password = os.environ.pop('ISEGYE_SFTP_PASSWORD', '')
    require(bool(password), 'Production environment secret missing')
    require(d.ROOT == ROOT, 'Isolated-root contract changed')
    resources, locks = [], []
    r = s = probe = proof = None
    stage = 'connection'
    before = baseline = old = candidate = None
    swap_attempted = False
    mode = shared_owner = temporary = None
    try:
        sock = socket.create_connection((d.HOST, d.PORT), timeout=15)
        resources.append(sock)
        t = paramiko.Transport(sock)
        resources.append(t)
        t.banner_timeout = 15
        t.auth_timeout = 20
        t.get_security_options().key_types = ('ssh-ed25519',)
        t.start_client(timeout=15)
        key = t.get_remote_server_key()
        fingerprint = 'SHA256:' + base64.b64encode(hashlib.sha256(key.asbytes()).digest()).decode().rstrip('=')
        require(key.get_name() == 'ssh-ed25519' and fingerprint == d.FINGERPRINT, 'Host key mismatch; password not sent')
        report['host_key_verified'] = True
        t.auth_password(d.USER, password, fallback=True)
        password = None
        require(t.is_authenticated(), 'SFTP authentication incomplete')
        report['authenticated'] = True
        s = paramiko.SFTPClient.from_transport(t)
        resources.append(s)
        s.get_channel().settimeout(30)
        r = d.Remote(s)
        stage = 'preflight'
        for path in ('/web', ROOT, d.MIR):
            r.directory(path)
        require(r.read(ROOT + '/.isegye-owner') == d.OWNER, 'ISEGYE ownership marker invalid')
        site_router = r.read(ROOT + '/.htaccess')
        require(d.managed_router(site_router), 'ISEGYE site router is unmanaged')
        require(s.normalize(ROOT) != s.normalize(d.MIR), 'Site directories alias each other')
        report['distinct_real_directories'] = True
        # Shared lock coordinates with the existing MIR deployment. Never steal a lock.
        for path in (ROOT + '/.deploy-lock', SHARED_LOCK):
            require(r.info(path) is None, 'Another deployment holds a lock; no changes made')
            s.mkdir(path, 0o700)
            locks.append(path)
            r.directory(path)
        before = r.snapshot()
        old = r.read(SHARED)
        original, candidate = plan(old)
        shared_info = r.info(SHARED)
        mode = stat.S_IMODE(shared_info.st_mode)
        shared_owner = (shared_info.st_uid, shared_info.st_gid)
        require(mode in (0o644, 0o640), 'Unexpected shared router permissions')
        report.update(original_sha256=sha(original), before_sha256=sha(old), planned_sha256=sha(candidate),
                      already_configured=(old == candidate), shared_mode=oct(mode))
        urls = ('https://mir.yeop.net/', 'https://mir.yeop.net/band',
                'https://mir.yeop.net/songbook', 'https://yeop.net/')
        baseline = {url: d.http(url) for url in urls}
        require(all(value[0] == 200 for value in baseline.values()), 'Existing site baseline unhealthy')
        stage = 'backup'
        folder = ROOT + '/.routing-backups'
        if r.info(folder) is None:
            r.mkdir(folder)
            s.chmod(folder, 0o700)
        r.directory(folder)
        require(stat.S_IMODE(r.info(folder).st_mode) == 0o700, 'Backup directory permissions unsafe')
        backup = folder + '/shared-router-' + AUDITED_SHA + '.before'
        if r.info(backup) is None:
            r.new(backup, original)
            s.chmod(backup, 0o600)
        require(r.read(backup) == original and stat.S_IMODE(r.info(backup).st_mode) == 0o600, 'Backup verification failed')
        report['backup_path'] = backup
        report['backup_verified'] = True

        def atomic_replace(expected: bytes, replacement: bytes) -> None:
            nonlocal temporary
            temporary = folder + '/shared-router-' + os.urandom(16).hex() + '.tmp'
            r.new(temporary, replacement)
            s.chmod(temporary, mode)
            temporary_info = r.info(temporary)
            require((temporary_info.st_uid, temporary_info.st_gid) == shared_owner,
                    'Temporary router owner/group differs from original; stopped')
            require(r.read(SHARED) == expected, 'Concurrent shared-router change; refused overwrite')
            s.posix_rename(temporary, SHARED)
            temporary = None
            require(r.read(SHARED) == replacement, 'Atomic replacement read-back failed')
            replaced = r.info(SHARED)
            require(stat.S_IMODE(replaced.st_mode) == mode, 'Shared router mode changed')
            require((replaced.st_uid, replaced.st_gid) == shared_owner, 'Shared router owner/group changed')

        stage = 'prepare_probe'
        name = 'isegye-probe-' + os.urandom(16).hex() + '.txt'
        proof = ('isegye-host-proof:' + os.urandom(32).hex()).encode()
        probe = ROOT + '/' + name
        r.new(probe, proof)
        require(d.http(d.ORIGIN + '/_isegye_idol/' + name) == (200, proof), 'Isolated nested probe unavailable')
        require(r.snapshot() == before, 'Protected files changed before routing update')
        stage = 'append_host_bridge'
        if old != candidate:
            swap_attempted = True
            atomic_replace(old, candidate)
            report['shared_router_modified'] = True
        require(r.read(SHARED) == original + BRIDGE, 'Append-only invariant failed')
        report['existing_rules_byte_preserved'] = True
        stage = 'live_validation'
        for scheme in ('https', 'http'):
            require(d.http(scheme + '://isegye-idol.kr/' + name) == (200, proof), 'Canonical domain probe failed')
        require(d.http(d.ORIGIN + '/' + name + '?routing-check=1') == (200, proof), 'Query-string probe failed')
        report.update(canonical_https_mapping=True, canonical_http_mapping=True, query_probe_passed=True)
        for origin in ('https://mir.yeop.net', 'https://yeop.net'):
            for suffix in ('/' + name, '/_isegye_idol/' + name):
                require(proof not in d.http(origin + suffix)[1], 'ISEGYE content leaked to another host')
        report['cross_host_exposure'] = False
        for suffix in ('/.isegye-owner', '/.routing-backups/' + backup.rsplit('/', 1)[1]):
            require(d.http(d.ORIGIN + suffix)[0] in (403, 404), 'Private metadata or backup is public')
        report['private_files_blocked'] = True
        home_status = d.http(d.ORIGIN + '/')[0]
        expected = 503 if site_router == d.router() else 200
        require(home_status == expected, 'Canonical homepage status differs from managed router state')
        report.update(home_http_status=home_status, application_deployed=False)
        now = r.snapshot()
        require({k:v for k,v in now.items() if k != SHARED} ==
                {k:v for k,v in before.items() if k != SHARED}, 'Non-target protected file changed')
        require(r.read(ROOT + '/.htaccess') == site_router, 'Isolated site router changed')
        report['other_protected_files_unchanged'] = True
        checks = {url: d.http(url) == value for url, value in baseline.items()}
        require(all(checks.values()), 'Existing site response changed')
        report['existing_sites_unchanged'] = checks
        r.remove_own(probe, proof)
        probe = None
        report['probe_removed'] = True
        require(r.read(SHARED) == candidate, 'Shared router changed at completion')
        report.update(status='configured_and_verified', after_sha256=sha(candidate))
    except Exception as exc:
        report.update(status='failed', failed_stage=stage, error_type=type(exc).__name__)
        if isinstance(exc, (Stop, d.Stop)):
            report['reason'] = str(exc)
        if swap_attempted and r and old is not None:
            try:
                current = r.read(SHARED)
                if current == candidate:
                    atomic_replace(candidate, old)
                else:
                    require(current == old, 'Router changed externally; automatic rollback refused')
                report['rollback_restored_original'] = r.read(SHARED) == old
                if baseline:
                    report['rollback_existing_sites_unchanged'] = all(d.http(url) == value for url, value in baseline.items())
            except Exception as rollback_error:
                report['rollback_error_type'] = type(rollback_error).__name__
                report['manual_recovery_required'] = True
    finally:
        password = None
        if r and probe and proof:
            try:
                r.remove_own(probe, proof)
                report['probe_removed'] = True
            except Exception:
                report['probe_cleanup_failed'] = True
                report['status'] = 'failed'
        if r and temporary:
            try:
                require(r.info(temporary) is not None, 'Temporary file disappeared')
                r.parents(temporary)
                s.remove(temporary)
            except Exception:
                report['temporary_cleanup_failed'] = True
                report['status'] = 'failed'
        for path in reversed(locks):
            try:
                r.directory(path)
                s.rmdir(path)
            except Exception:
                report['lock_cleanup_failed'] = True
                report['status'] = 'failed'
        for resource in reversed(resources):
            try:
                resource.close()
            except Exception:
                pass

def main() -> None:
    report = {'checked_at': datetime.now(timezone.utc).isoformat(),
              'commit': os.environ.get('GITHUB_SHA'), 'shared_router_modified': False,
              'application_deployed': False, 'status': 'failed'}
    try:
        apply(report)
    except Exception as exc:
        report.update(error_type=type(exc).__name__, failed_stage='initial_configuration')
        if isinstance(exc, Stop):
            report['reason'] = str(exc)
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    Path('inour-domain-bridge.json').write_text(payload + '\n', encoding='utf-8')
    print(payload)
    summary = os.environ.get('GITHUB_STEP_SUMMARY')
    if summary:
        with open(summary, 'a', encoding='utf-8') as handle:
            handle.write('## ISEGYE host-only routing\n\nNo application release or main merge.\n\n```json\n' + payload + '\n```\n')
    sys.exit(0 if report['status'] == 'configured_and_verified' else 1)

if __name__ == '__main__':
    main()
