#!/usr/bin/env python3
"""Publish only the protected monitor and a narrowly extended auth runtime.

No site UI/feed/schedule writes; no account/config/session reads. Shared lock,
fixed owner/path/SSH fingerprint, byte readback and compare-before-rollback stay.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse, base64, hashlib, json, os, re, socket, stat, sys
import inour_sftp as d
import auth_routing as a
from albums_composer import preserved_root_metadata, runtime_id
from deploy_google_access import upload_tree
from deploy_verified_albums import VerifiedTransferRemote
from build_batch_monitor_host import patched, readonly_patched, previous_patched, baseline
from batch_monitor_snapshot import merge_observations

ROOT = Path(__file__).resolve().parents[1]
FOLDER = d.ROOT+'/.batch-monitoring'
MARKER = b'isegye-batch-monitoring:v1\n'
NAMES = ('index.html','monitor.css','monitor.js','data.json')


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, separators=(',',':'), sort_keys=True)+'\n').encode()


def release_payload(doc):
    if doc.get('schemaVersion') != 1 or doc.get('readOnly') is not True or len(doc.get('batches', [])) != 8:
        raise ValueError('Invalid monitoring snapshot')
    files = {name:(ROOT/'monitoring'/name).read_bytes() for name in NAMES if name != 'data.json'}
    files['data.json'] = encoded(doc)
    if any(len(value) > 4_000_000 for value in files.values()):
        raise ValueError('Monitoring payload oversized')
    manifest = encoded({'schemaVersion':1,'files':{k:d.digest(v) for k,v in files.items()}})
    release = 'm'+d.digest(manifest)[:12]
    pointer = encoded({'release':release,'manifestSha256':d.digest(manifest)})
    files['manifest.json'] = manifest
    return release, files, pointer


def old_snapshot(remote, pointer):
    if pointer is None:
        return {}
    value = json.loads(pointer)
    d.require(re.fullmatch('m[0-9a-f]{12}', value.get('release','')) is not None, 'Invalid monitor release')
    folder = FOLDER+'/releases/'+value['release']
    remote.directory(folder)
    raw = remote.read(folder+'/manifest.json')
    d.require(raw is not None and d.digest(raw) == value.get('manifestSha256'), 'Existing monitor manifest mismatch')
    manifest = json.loads(raw)
    raw = remote.read(folder+'/data.json')
    d.require(raw is not None and d.digest(raw) == manifest.get('files',{}).get('data.json'), 'Existing monitor data mismatch')
    return json.loads(raw)


def private_replace(remote, path, raw, expected):
    remote.replace(path, raw, expected)
    remote.s.chmod(path, 0o600)
    d.require(stat.S_IMODE(remote.info(path).st_mode) == 0o600, 'Private permissions mismatch')


def publish(remote, doc, commit, report):
    _, files = a.bundle(ROOT/'auth-bundle')
    source = (ROOT/'auth/Gateway.php').read_text()
    d.require(files['Gateway.php'] == patched(source).encode(), 'Unexpected monitor gateway')
    d.require(files['BatchMonitor.php'] == (ROOT/'monitoring/BatchMonitor.php').read_bytes(), 'Unexpected monitor handler')
    remote.directory('/web'); remote.directory(d.ROOT)
    d.require(remote.read(d.ROOT+'/.isegye-owner') == d.OWNER, 'Wrong isolated owner')
    for lock in ('/web/.yeop-migration-lock', d.ROOT+'/.auth-stage-lock'):
        d.require(remote.info(lock) is None, 'Other maintenance in progress')
    lock = d.ROOT+'/.deploy-lock'; remote.mkdir(lock)
    entry_path = d.ROOT+'/access.php'
    old_entry = new_entry = old_pointer = pointer = None
    entry_changed = pointer_changed = False
    try:
        router = remote.read(d.ROOT+'/.htaccess')
        production, gated = a.release_of(router)
        d.require(gated, 'Existing access gate required')
        protected = remote.snapshot()
        production_files = {n:d.digest(remote.read(d.ROOT+'/_isegye_releases/'+production+'/'+n)) for n in ('index.html','build-info.json','src/app.js')}
        http_before = {p:d.http(d.ORIGIN+p) for p in ('/','/auth/status','/auth/terms','/auth/privacy','/src/app.js','/build-info.json')}
        d.require(http_before['/auth/status'][0] == 200, 'Access status unavailable')
        status = json.loads(http_before['/auth/status'][1])
        d.require(status.get('authenticated') is False and status.get('administrator') is False, 'Unexpected anonymous privilege')
        old_entry = remote.read(entry_path)
        match = re.search(rb"/\.auth-runtime/(g[0-9a-f]{12})'", old_entry or b'')
        d.require(match is not None, 'Unrecognized managed entry')
        old_runtime = match[1].decode()
        parent = d.ROOT+'/.auth-runtime'
        old_folder = parent+'/'+old_runtime
        remote.directory(parent); remote.directory(old_folder)
        d.require(old_entry == a.entry(remote.read(old_folder+'/access.php.template'), old_runtime), 'Entry differs from managed template')
        # Reuse byte-identical current code and preserve composer root metadata.
        for name, value in list(files.items()):
            if name in ('Gateway.php','BatchMonitor.php','BatchManual.php','manual.js','manual.css'):
                continue
            if name == 'google-client.js':
                old_value = remote.read(old_folder+'/'+name)
                d.require(old_value == value or (old_value is not None and d.digest(old_value) ==
                    'a496b5ab557505075e3db9c25f21f6c1460f6e2fb098b4e4a48baaedf5cd4600'),
                    'Unknown active Google client')
                continue
            old_value = remote.read(old_folder+'/'+name)
            if name == 'vendor/composer/installed.php':
                files[name] = preserved_root_metadata(old_value, value)
            else:
                d.require(old_value == value, 'Current authentication source differs: '+name)
        old_gateway = remote.read(old_folder+'/Gateway.php')
        d.require(old_gateway in (baseline.patched(source).encode(), previous_patched(source).encode(), readonly_patched(source).encode(), files['Gateway.php']), 'Unknown active gateway extension')
        if old_gateway == previous_patched(source).encode():
            old_handler = remote.read(old_folder+'/BatchMonitor.php')
            d.require(old_handler is not None and d.digest(old_handler) ==
                'd396e71764d6bd8fef52811f5980cf74e309b5f879f3eda0e119566af67c0cac',
                'Unknown legacy monitor handler')
        runtime = runtime_id(files)
        # Existing feeds and previews remain untouched and are checked under the lock.
        unchanged = {}
        for name in ('.schedule-feed/current.json','.music-feed/current.json','.history-feed/current.json',
                     '.playground-bank/current.json','.review-1st/active.json','.review-2nd/active.json',
                     '.review-albums/active.json','.review-fanmade/active.json','.review-playground/active.json'):
            value = remote.read(d.ROOT+'/'+name)
            unchanged[name] = d.digest(value) if value is not None else None
        if remote.info(FOLDER) is None:
            remote.mkdir(FOLDER); remote.s.chmod(FOLDER,0o700)
            remote.new(FOLDER+'/.owner',MARKER); remote.s.chmod(FOLDER+'/.owner',0o600)
            remote.new(FOLDER+'/.htaccess',b'Require all denied\n'); remote.s.chmod(FOLDER+'/.htaccess',0o600)
        remote.directory(FOLDER)
        d.require(remote.read(FOLDER+'/.owner') == MARKER and remote.read(FOLDER+'/.htaccess') == b'Require all denied\n', 'Unowned monitor folder')
        for name in ('releases','backups'):
            folder = FOLDER+'/'+name
            if remote.info(folder) is None:
                remote.mkdir(folder); remote.s.chmod(folder,0o700)
            remote.directory(folder)
        old_pointer = remote.read(FOLDER+'/active.json')
        doc = merge_observations(old_snapshot(remote,old_pointer),doc)
        release, payload, pointer = release_payload(doc)
        upload_tree(remote, FOLDER+'/releases/'+release, payload, private=True)
        upload_tree(remote, parent+'/'+runtime, files, private=True)
        backup = FOLDER+'/backups/'+os.urandom(12).hex()
        upload_tree(remote,backup,{'entry.before':old_entry,**({'pointer.before':old_pointer} if old_pointer else {})},private=True)
        d.require(remote.read(d.ROOT+'/.htaccess') == router and remote.read(entry_path) == old_entry, 'Concurrent routing change')
        pointer_changed = True
        private_replace(remote,FOLDER+'/active.json',pointer,old_pointer)
        new_entry = a.entry(files['access.php.template'],runtime)
        entry_changed = True
        remote.replace(entry_path,new_entry,old_entry)
        d.require(remote.read(entry_path) == new_entry and remote.read(FOLDER+'/active.json') == pointer, 'Activation readback failed')
        for name, value in payload.items():
            d.require(remote.read(FOLDER+'/releases/'+release+'/'+name) == value, 'Monitor file readback failed')
        from batch_monitor_storage import verify_anonymous
        from batch_manual_worker import initialize, verify_boundary
        initialize(remote)
        verify_anonymous()
        verify_boundary()
        for path in ('/.batch-monitoring/active.json','/.batch-monitoring/releases/'+release+'/data.json','/.auth-runtime/'+runtime+'/BatchMonitor.php'):
            code, body = d.http(d.ORIGIN+path)
            d.require(code in (403,404,503) and body != payload['data.json'], 'Private monitor path exposed')
        for path, before in http_before.items():
            d.require(d.http(d.ORIGIN+path) == before, 'Existing route changed: '+path)
        d.require(remote.snapshot() == protected and remote.read(d.ROOT+'/.htaccess') == router, 'Shared or site router changed')
        for name, digest in production_files.items():
            d.require(d.digest(remote.read(d.ROOT+'/_isegye_releases/'+production+'/'+name)) == digest, 'Operating UI changed')
        for name, digest in unchanged.items():
            raw = remote.read(d.ROOT+'/'+name)
            d.require((d.digest(raw) if raw is not None else None) == digest, 'Existing feed or preview changed')
        report.update(status='gated_monitor_production_verified',url=d.ORIGIN+'/ops/batches/',commit=commit,
            release=release,runtime=runtime,sourceCheckedAt=doc['checkedAt'],productionUIUnchanged=True,manualControlsInstalled=True,manualControlAnonymousDenied=True,
            existingRoutesUnchanged=True,sharedRouterUnchanged=True,feedsUnchanged=True,
            anonymousUIAndAPIDenied=True,anonymousDocumentRedirectVerified=True,loginNoticeVerified=True,privatePathsBlocked=True,requiresExistingAdministrator=True,
            accountConfigOrSessionAccessed=False,realGoogleLoginPerformed=False,
            authorizedRenderingVerification='local TLS synthetic accounts; deployed bytes verified by SFTP',
            scheduledRefreshEnabled=True,refreshEverySeconds=600,readOnly=True,
            verifiedAt=datetime.now(timezone.utc).isoformat(),snapshotSha256=d.digest(payload['data.json']))
    except Exception:
        try:
            if entry_changed:
                current = remote.read(entry_path)
                d.require(current in (old_entry,new_entry), 'Concurrent entry change; rollback stopped')
                if current == new_entry:
                    remote.replace(entry_path,old_entry,new_entry)
            if pointer_changed:
                current = remote.read(FOLDER+'/active.json')
                d.require(current in (old_pointer,pointer), 'Concurrent snapshot change; rollback stopped')
                if current == pointer:
                    if old_pointer is None:
                        remote.remove_own(FOLDER+'/active.json',pointer)
                    else:
                        private_replace(remote,FOLDER+'/active.json',old_pointer,pointer)
            report['previousEntryAndPointerRestored'] = True
        except Exception:
            report['manualRecoveryRequired'] = True
        raise
    finally:
        remote.parents(lock); remote.s.rmdir(lock)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--refresh-only',action='store_true')
    args=parser.parse_args()
    report = {'status':'failed','checkedAt':datetime.now(timezone.utc).isoformat()}
    resources = []
    password = os.environ.pop('ISEGYE_SFTP_PASSWORD','')
    try:
        d.require(os.getenv('GITHUB_REPOSITORY') == 'seirian/isegye-idol-fansite' and os.getenv('GITHUB_REF') == 'refs/heads/main', 'Monitor production main only')
        d.require(os.getenv('MONITOR_PRODUCTION_ENABLED') == 'true' and os.getenv('PRODUCTION_PAUSED') != 'true' and os.getenv('ISEGYE_MONITOR_PAUSED') != 'true', 'Monitor disabled or paused')
        d.require(bool(password), 'Existing SFTP credential missing')
        commit = os.getenv('MONITOR_COMMIT') or os.getenv('GITHUB_SHA','')
        d.require(re.fullmatch('[0-9a-f]{40}',commit) is not None, 'Commit required')
        doc = json.loads((ROOT/'monitoring-dist/data.json').read_text())
        from batch_monitor_storage import validate_snapshot, refresh
        validate_snapshot(doc,commit)
        import paramiko
        sock = socket.create_connection((d.HOST,d.PORT),timeout=15);resources.append(sock)
        transport = paramiko.Transport(sock);resources.append(transport)
        transport.banner_timeout=15;transport.auth_timeout=20
        transport.get_security_options().key_types=('ssh-ed25519',);transport.start_client(timeout=15)
        key=transport.get_remote_server_key()
        fingerprint='SHA256:'+base64.b64encode(hashlib.sha256(key.asbytes()).digest()).decode().rstrip('=')
        d.require(key.get_name() == 'ssh-ed25519' and fingerprint == d.FINGERPRINT, 'Host key mismatch; credential not sent')
        transport.auth_password(d.USER,password);password=None
        d.require(transport.is_authenticated(), 'SFTP authentication incomplete')
        client=paramiko.SFTPClient.from_transport(transport);resources.append(client);client.get_channel().settimeout(30)
        if args.refresh_only:
            refresh(VerifiedTransferRemote(client),doc,commit,report,ROOT)
        else:
            publish(VerifiedTransferRemote(client),doc,commit,report)
    except Exception as exc:
        report['errorType']=type(exc).__name__
        if isinstance(exc,d.Stop):report['reason']=str(exc)
    finally:
        password=None
        for resource in reversed(resources):
            try:resource.close()
            except Exception:pass
        (ROOT/'batch-monitor-deployment.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps(report,ensure_ascii=False))
    return 0 if report['status'] in ('gated_monitor_production_verified','monitor_snapshot_verified') else 1

if __name__ == '__main__':
    sys.exit(main())
