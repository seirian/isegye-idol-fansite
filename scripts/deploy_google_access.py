#!/usr/bin/env python3
"""Main-only deployment of the site behind Google access control.

Only /web/_isegye_idol is writable. Never creates an account or a privileged
session. Existing membership and identity keys survive activation, deploy and
rollback. Rollback always keeps a server gate, including the first activation.
"""
from __future__ import annotations
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import stat
import subprocess
import sys
from datetime import datetime, timezone
import inour_sftp as d
import auth_routing as a
from production_release import EXISTING


def private_file(remote, path):
    info = remote.info(path)
    d.require(info is not None and stat.S_IMODE(info.st_mode) == 0o600, 'Private file permissions unsafe')
    return remote.read(path)


def replace_private(remote, path, value, previous):
    remote.replace(path, value, previous)
    remote.s.chmod(path, 0o600)
    d.require(private_file(remote, path) == value, 'Private configuration update failed')


def upload_tree(remote, target, files, private=False):
    if remote.info(target) is None:
        remote.mkdir(target)
    remote.directory(target)
    if private:
        remote.s.chmod(target, 0o700)
    for rel, value in files.items():
        current = target
        for part in rel.split('/')[:-1]:
            current += '/' + part
            if remote.info(current) is None:
                remote.mkdir(current)
            remote.directory(current)
            if private:
                remote.s.chmod(current, 0o700)
        path = target + '/' + rel
        old = remote.read(path)
        if old is None:
            remote.new(path, value)
        else:
            d.require(old == value, 'Immutable release content differs')
        if private:
            remote.s.chmod(path, 0o600)


def status():
    code, raw = d.http(d.ORIGIN + '/auth/status')
    d.require(code == 200, 'Access status unavailable')
    value = json.loads(raw)
    d.require(set(value) == {'authenticated', 'administrator', 'maintenance', 'allowed'} and all(type(x) is bool for x in value.values()), 'Invalid access status')
    d.require(not value['authenticated'] and not value['administrator'] and value['allowed'] != value['maintenance'], 'Anonymous privilege failure')
    return value


def verify_public(payload, report):
    before = status()
    if not before['maintenance']:
        for rel, data in payload.items():
            if rel == '.nojekyll':
                continue
            response = d.http(d.ORIGIN + '/' + rel)
            if response[0] == 503 and status()['maintenance']:
                break
            expected = a.public_html(data) if rel == 'index.html' else data
            d.require(response == (200, expected), 'Gated public file mismatch: ' + rel)
        report['publicBeforeAdministratorVerified'] = True
    now = status()
    if now['maintenance']:
        for path in ('/', '/index.html', '/src/app.js', '/build-info.json'):
            code, body = d.http(d.ORIGIN + path)
            d.require(code == 503 and '현재 사이트는'.encode() in body, 'Maintenance gate not enforced')
        report['anonymousMaintenanceVerified'] = True
    return now


def verify_browser(commit, client_id):
    env = dict(os.environ, GITHUB_SHA=commit, ISEGYE_GOOGLE_CLIENT_ID=client_id)
    result = subprocess.run([sys.executable, 'tests/auth/production_browser.py'], env=env,
                            capture_output=True, text=True, timeout=240)
    d.require(result.returncode == 0, 'Google access browser verification failed; see sanitized test report')
    out = Path('test-results/google-access-live/result.json')
    data = json.loads(out.read_text())
    d.require(data['status'] == 'verified' and data['commit'] == commit, 'Incomplete access verification')
    return data


def deploy(remote, payload, commit, client_id, report):
    runtime, files = a.bundle(Path('auth-bundle'))
    remote.directory('/web')
    remote.directory(d.ROOT)
    d.require(remote.read(d.ROOT + '/.isegye-owner') == d.OWNER, 'Ownership marker mismatch')
    d.require(remote.info('/web/.yeop-migration-lock') is None, 'Other project maintenance in progress')
    d.require(remote.info(d.ROOT + '/.auth-stage-lock') is None, 'Auth staging in progress')
    lock = d.ROOT + '/.deploy-lock'
    remote.mkdir(lock)
    activated = False
    previous = new = None
    entry_path = d.ROOT + '/access.php'
    old_entry = new_entry = None
    try:
        previous = remote.read(d.ROOT + '/.htaccess')
        old_release, was_gated = a.release_of(previous)
        remote.directory(a.PRIVATE)
        d.require(stat.S_IMODE(remote.info(a.PRIVATE).st_mode) == 0o700 and remote.read(a.PRIVATE+'/.owner') == a.PRIVATE_OWNER, 'Unrecognized private storage')
        remote.directory(a.PRIVATE + '/sessions')
        d.require(stat.S_IMODE(remote.info(a.PRIVATE+'/sessions').st_mode) == 0o700, 'Unsafe session directory')
        private_file(remote, a.PRIVATE + '/accounts.lock')
        report['membershipBefore'] = a.account_state(private_file(remote, a.PRIVATE + '/accounts.json'))
        old_config = private_file(remote, a.PRIVATE + '/config.json')
        new_config, config_changed = a.configured(old_config, client_id)
        if config_changed:
            d.require(not report['membershipBefore']['administratorRegistered'], 'Existing administrator without client configuration')
            replace_private(remote, a.PRIVATE + '/config.json', new_config, old_config)
        report['googleClientIdConfigured'] = True
        protected = remote.snapshot()
        baseline = {url: d.http(url) for url in EXISTING}
        d.require(all(value[0] == 200 for value in baseline.values()), 'Existing-site baseline unhealthy')
        remote.prove_mapping()
        parent = d.ROOT + '/.auth-runtime'
        if remote.info(parent) is None:
            remote.mkdir(parent)
        remote.s.chmod(parent, 0o700)
        upload_tree(remote, parent + '/' + runtime, files, private=True)
        old_entry = remote.read(entry_path)
        if old_entry is not None:
            match = re.search(rb"/\.auth-runtime/(g[0-9a-f]{12})'", old_entry)
            d.require(match is not None, 'Unrecognized existing gateway')
            old_runtime = match[1].decode()
            template = remote.read(parent + '/' + old_runtime + '/access.php.template')
            d.require(old_entry == a.entry(template, old_runtime), 'Existing gateway changed outside deployment')
        else:
            d.require(not was_gated, 'Gated site is missing its gateway')
        release_parent = d.ROOT + '/_isegye_releases'
        remote.directory(release_parent)
        suffix = hashlib.sha256((commit+':'+os.getenv('GITHUB_RUN_ID','local')+':'+os.getenv('GITHUB_RUN_ATTEMPT','1')).encode()).hexdigest()[:12]
        release = 'r' + suffix
        upload_tree(remote, release_parent + '/' + release, payload)
        backup_dir = d.ROOT + '/.release-backups'
        remote.directory(backup_dir)
        backup = backup_dir + '/' + release + '.before'
        if remote.info(backup) is None:
            remote.new(backup, previous)
            remote.s.chmod(backup, 0o600)
        else:
            d.require(remote.read(backup) == previous, 'Existing backup mismatch')
        if old_entry is not None and remote.info(backup + '-access.php') is None:
            remote.new(backup + '-access.php', old_entry)
            remote.s.chmod(backup + '-access.php', 0o600)
        report.update(commit=commit, release=release, runtime=runtime, root=d.ROOT,
                      previousRouterBackup=backup, previousGatePresent=was_gated)
        d.require(remote.snapshot() == protected, 'Protected site changed before activation')
        new_entry = a.entry(files['access.php.template'], runtime)
        if old_entry is None:
            remote.new(entry_path, new_entry)
        elif old_entry != new_entry:
            remote.replace(entry_path, new_entry, old_entry)
        new = a.router(release)
        activated = True
        remote.replace(d.ROOT + '/.htaccess', new, previous)
        report['accessRoutingEnabled'] = True
        verify_public(payload, report)
        browser = verify_browser(commit, client_id)
        report['browserVerified'] = True
        report['googleButtonRendered'] = browser['googleButtonRendered']
        report['googleAccountChooserReached'] = browser['googleAccountChooserReached']
        report['realGoogleAccountLoginPerformed'] = False
        for path in ('/.auth-private/accounts.json', '/.auth-private/config.json', '/.release-backups/'+release+'.before',
                     '/.auth-runtime/'+runtime+'/Store.php', '/_isegye_releases/'+old_release+'/index.html',
                     '/_isegye_releases/'+release+'/src/app.js', '/_mir_site/index.html', '/access.php'):
            code, body = d.http(d.ORIGIN + path)
            d.require(code in (403,404,503) and body != payload['index.html'] and body != payload['src/app.js'], 'Direct path exposure')
        report['membershipAfter'] = a.account_state(private_file(remote, a.PRIVATE + '/accounts.json'))
        report['maintenanceActive'] = status()['maintenance']
        d.require(report['maintenanceActive'] == report['membershipAfter']['administratorRegistered'], 'Maintenance condition mismatch')
        d.require(remote.snapshot() == protected, 'Protected site changed')
        unchanged = {url: d.http(url) == value for url, value in baseline.items()}
        d.require(all(unchanged.values()), 'Other site response changed')
        report.update(status='deployed_and_verified', privatePathsBlocked=True, protectedFilesUnchanged=True,
                      existingSitesUnchanged=unchanged, sharedRouterModified=False, administratorPrecreated=False,
                      accountStoreWrittenByDeployment=False)
    except Exception:
        if activated and previous is not None:
            try:
                current = remote.read(d.ROOT + '/.htaccess')
                recovery = a.recovery_router(previous)
                d.require(current in (new, recovery), 'Concurrent gateway change; recovery stopped')
                if current != recovery:
                    remote.replace(d.ROOT + '/.htaccess', recovery, current)
                if old_entry is not None and old_entry != new_entry and remote.read(entry_path) == new_entry:
                    remote.replace(entry_path, old_entry, new_entry)
                report['rollbackKeptAccessGate'] = True
                report['previousReleaseRestored'] = True
            except Exception:
                report['manualRecoveryRequired'] = True
        raise
    finally:
        remote.parents(lock)
        remote.s.rmdir(lock)
        report['lockRemoved'] = True


def main():
    report = {'status':'failed','checkedAt':datetime.now(timezone.utc).isoformat(),'sharedRouterModified':False}
    resources = []
    password = os.environ.pop('ISEGYE_SFTP_PASSWORD','')
    client_id = os.environ.pop('ISEGYE_GOOGLE_CLIENT_ID','').strip()
    try:
        d.require(os.getenv('GITHUB_REPOSITORY') == 'seirian/isegye-idol-fansite' and os.getenv('GITHUB_REF') == 'refs/heads/main', 'Production is repository/main-only')
        d.require(os.getenv('PRODUCTION_ENABLED') == 'true' and os.getenv('PRODUCTION_PAUSED') != 'true', 'Production is disabled or paused')
        d.require(bool(a.CLIENT.fullmatch(client_id)), 'Registered Google Web Client ID missing or malformed')
        d.require(bool(password), 'Existing SFTP credential missing')
        commit = os.getenv('GITHUB_SHA','')
        payload = d.load_payload('dist',commit)
        import paramiko
        sock = socket.create_connection((d.HOST,d.PORT),timeout=15); resources.append(sock)
        transport = paramiko.Transport(sock); resources.append(transport)
        transport.banner_timeout = 15; transport.auth_timeout = 20
        transport.get_security_options().key_types = ('ssh-ed25519',)
        transport.start_client(timeout=15)
        key = transport.get_remote_server_key()
        fingerprint = 'SHA256:' + base64.b64encode(hashlib.sha256(key.asbytes()).digest()).decode().rstrip('=')
        d.require(key.get_name() == 'ssh-ed25519' and fingerprint == d.FINGERPRINT, 'Host key mismatch; credential not sent')
        transport.auth_password(d.USER,password); password = None
        d.require(transport.is_authenticated(), 'SFTP authentication incomplete')
        client = paramiko.SFTPClient.from_transport(transport); resources.append(client); client.get_channel().settimeout(30)
        deploy(d.Remote(client),payload,commit,client_id,report)
    except Exception as exc:
        report['errorType'] = type(exc).__name__
        if isinstance(exc,d.Stop): report['reason'] = str(exc)
    finally:
        password = None; client_id = None
        for resource in reversed(resources):
            try: resource.close()
            except Exception: pass
        Path('auth-deployment.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps(report,ensure_ascii=False,indent=2))
    return 0 if report['status']=='deployed_and_verified' else 1

if __name__=='__main__': sys.exit(main())