"""Main-only album feed storage. No account, router, release or schedule writes.
Public-source collection runs separately, without the SFTP credential.
"""
from contextlib import contextmanager
from pathlib import Path
import argparse
import base64
import hashlib
import json
import os
import re
import socket
import time
from datetime import datetime, timezone
from album_hourly import allowed, remaining, night_deadline, NightPause

import auth_routing as routing
import inour_sftp as d
from daily_albums import ROOT, MAX_BYTES, asset_entries, health, validate

DIR = d.ROOT+'/.albums-feed'
OWNER = b'isegye-daily-albums:v1\n'

def path(name):
    d.require(name in ('.owner', '.lock', 'current.json', 'previous.json', 'assets')
              or re.fullmatch(r'assets/[0-9a-f]{64}\.webp', name), 'Unexpected album feed path')
    return DIR+'/'+name

def active(remote):
    remote.directory('/web'); remote.directory(d.ROOT)
    d.require(remote.read(d.ROOT+'/.isegye-owner') == d.OWNER, 'Wrong site owner')
    d.require(remote.info(d.ROOT+'/.deploy-lock') is None, 'Production deployment in progress')
    router = remote.read(d.ROOT+'/.htaccess'); rid, gated = routing.release_of(router)
    d.require(gated, 'Existing access gate required')
    release = d.ROOT+'/_isegye_releases/'+rid
    meta = json.loads(remote.read(release+'/build-info.json') or b'{}')
    d.require(meta.get('dailyAlbums', {}).get('schemaVersion') == 1, 'Album feed runtime not deployed')
    from album_releases import load_catalog
    d.require(meta['dailyAlbums'].get('catalogTrackIds') == sorted(s['id'] for s in load_catalog()['songs']), 'Active album catalog differs')
    return router, rid, release

def owned(remote):
    remote.directory(DIR)
    d.require(remote.read(path('.owner')) == OWNER, 'Unowned album feed directory')

def decode(raw):
    d.require(isinstance(raw, bytes) and len(raw) <= MAX_BYTES, 'Album snapshot missing or oversized')
    return validate(json.loads(raw))

def image_bytes(raw, sha):
    d.require(isinstance(raw, bytes) and 12 < len(raw) <= 180000
              and raw[:4] == b'RIFF' and raw[8:12] == b'WEBP'
              and d.digest(raw) == sha, 'Album image integrity mismatch')
    return raw

def restore(remote, progress=None):
    progress = progress if progress is not None else {}
    progress['stage'] = 'restore'
    router, rid, release = active(remote)
    source = 'release-seed'; raw = None
    if remote.info(DIR) is not None:
        owned(remote); raw = remote.read(path('current.json'))
        if raw is not None: source = 'cumulative-feed'
    if raw is None: raw = remote.read(release+'/src/albums-insights.json')
    data = decode(raw); assets = asset_entries(data)
    local = ROOT/'albums/asset-cache'; local.mkdir(parents=True, exist_ok=True)
    for sha in assets:
        name = sha+'.webp'
        remote_path = path('assets/'+name) if source == 'cumulative-feed' else release+'/assets/albums/'+name
        content = image_bytes(remote.read(remote_path), sha)
        dest = local/name
        d.require(not dest.is_symlink(), 'Local asset symlink refused')
        dest.write_bytes(content)
    d.require(remote.read(d.ROOT+'/.htaccess') == router, 'Release changed during restore')
    (ROOT/'albums/snapshot.json').write_bytes(raw)
    return {'status': 'restored', 'source': source, 'release': rid, 'tracks': len(data['tracks']),
            'assets': len(assets), 'snapshotAt': data['generatedAt'], 'remoteWrites': False}

def publish(remote, data, transaction=None, progress=None):
    transaction = transaction if transaction is not None else {}
    progress = progress if progress is not None else {}
    progress['stage'] = 'validate'
    validate(data, exact=True, fresh=True)
    d.require(data.get('feed') == 'daily-albums', 'Wrong album feed type')
    report = health(data)
    d.require(report['state'] == 'complete', 'Required album sources incomplete; previous feed preserved')
    assets = {}
    for sha, entry in asset_entries(data).items():
        local = (ROOT/entry['path']).resolve()
        d.require(local.is_relative_to((ROOT/'albums/asset-cache').resolve()) and not (ROOT/entry['path']).is_symlink(), 'Unsafe local album asset')
        assets[sha] = image_bytes(local.read_bytes(), sha)
    # A retry uses the exact same candidate and publication timestamp.
    if transaction.get('recordPublication'):
        data.setdefault('publication', {'publishedAt': datetime.now(timezone.utc).isoformat(),
            'runId': os.getenv('GITHUB_RUN_ID', ''), 'runAttempt': os.getenv('GITHUB_RUN_ATTEMPT', '')})
    raw = (json.dumps(data, ensure_ascii=False, separators=(',', ':'))+'\n').encode()
    d.require(len(raw) <= MAX_BYTES, 'Album feed too large')
    progress['stage'] = 'active_release'
    router, rid, _ = active(remote)
    if remote.info(DIR) is None:
        remote.mkdir(DIR); remote.s.chmod(DIR, 0o700)
        remote.new(path('.owner'), OWNER); remote.s.chmod(path('.owner'), 0o600)
    owned(remote)
    progress['stage'] = 'lock'
    lock = transaction.setdefault('lock', os.urandom(24))
    existing_lock = remote.read(path('.lock'))
    # Only this still-running process's random token may be recovered after a disconnect.
    if existing_lock == lock:
        remote.remove_own(path('.lock'), lock)
    d.require(remote.info(path('.lock')) is None, 'Existing album lock; refusing overlap')
    try:
        remote.new(path('.lock'), lock); remote.s.chmod(path('.lock'), 0o600)
        old = remote.read(path('current.json'))
        if old is not None:
            old_data = decode(old)
            from daily_albums import clock
            d.require(clock(old_data['generatedAt']) <= clock(data['generatedAt']), 'Newer published feed exists; refusing rollback')
        progress['stage'] = 'asset_transfer'
        if remote.info(path('assets')) is None:
            remote.mkdir(path('assets')); remote.s.chmod(path('assets'), 0o700)
        remote.directory(path('assets'))
        for sha, content in assets.items():
            name = path('assets/'+sha+'.webp'); existing = remote.read(name)
            if existing is None: remote.new(name, content)
            else: d.require(existing == content, 'Existing album asset changed')
            remote.s.chmod(name, 0o600)
            d.require(remote.read(name) == content, 'Album asset read-back failed')
        d.require(remote.read(d.ROOT+'/.htaccess') == router, 'Active release changed before publication')
        d.require(remote.info(d.ROOT+'/.deploy-lock') is None, 'Production deployment started')
        progress['stage'] = 'atomic_publish'
        if old is not None and old != raw:
            remote.replace(path('previous.json'), old, remote.read(path('previous.json')))
            remote.s.chmod(path('previous.json'), 0o600)
        if old != raw:
            remote.replace(path('current.json'), raw, old); remote.s.chmod(path('current.json'), 0o600)
        try:
            progress['stage'] = 'verify_readback'
            d.require(remote.read(path('current.json')) == raw, 'Album feed read-back failed')
            d.require(remote.read(d.ROOT+'/.htaccess') == router, 'Release changed after publication')
        except Exception:
            if old is not None and remote.read(path('current.json')) == raw:
                remote.replace(path('current.json'), old, raw)
            raise
        return {'status': 'published', 'release': rid, 'generatedAt': data['generatedAt'],
                'totalTracks': len(data['tracks']), 'assets': len(assets), 'sha256': d.digest(raw),
                'collectionHealth': report, 'publishedAt': data.get('publication', {}).get('publishedAt'), 'verifiedReadback': True, 'routingUnchanged': True,
                'accountStoreReadOrWritten': False,
                'releaseBindings': {sid: {'melonId': data['tracks'][sid]['melon']['trackId'],
                    'albumId': data['tracks'][sid]['melon']['albumId'],
                    'artwork': bool(data['tracks'][sid].get('artwork'))}
                    for sid in report['releaseTracks']}}
    finally:
        # Never delete a foreign lock, even while recovering a network failure.
        if remote.read(path('.lock')) == lock:
            remote.remove_own(path('.lock'), lock)

@contextmanager
def connection(password=None, progress=None):
    progress = progress if progress is not None else {}
    resources = []; password = password if password is not None else os.environ.pop('ISEGYE_SFTP_PASSWORD', '')
    try:
        d.require(os.getenv('GITHUB_REF') == 'refs/heads/main'
                  and os.getenv('GITHUB_REPOSITORY') == 'seirian/isegye-idol-fansite', 'Main repository only')
        d.require(os.getenv('PRODUCTION_PAUSED') != 'true'
                  and os.getenv('ISEGYE_ALBUMS_PAUSED') != 'true' and bool(password), 'Paused or missing credential')
        import paramiko
        from deploy_verified_albums import VerifiedTransferRemote
        progress['stage'] = 'connect'
        sock = socket.create_connection((d.HOST, d.PORT), timeout=30); resources.append(sock)
        transport = paramiko.Transport(sock); resources.append(transport)
        progress['stage'] = 'ssh_handshake'
        transport.banner_timeout = 30; transport.auth_timeout = 30
        transport.get_security_options().key_types = ('ssh-ed25519',); transport.start_client(timeout=30)
        key = transport.get_remote_server_key()
        fingerprint = 'SHA256:'+base64.b64encode(hashlib.sha256(key.asbytes()).digest()).decode().rstrip('=')
        d.require(key.get_name() == 'ssh-ed25519' and fingerprint == d.FINGERPRINT, 'Host key mismatch')
        progress['stage'] = 'authenticate'
        transport.auth_password(d.USER, password); password = None
        d.require(transport.is_authenticated(), 'SFTP authentication failed')
        progress['stage'] = 'sftp_open'
        client = paramiko.SFTPClient.from_transport(transport); resources.append(client)
        client.get_channel().settimeout(45)
        yield VerifiedTransferRemote(client)
    finally:
        password = None
        for resource in reversed(resources):
            try: resource.close()
            except Exception: pass

def transient(exc):
    # Validation, host identity, permissions, authentication and foreign locks fail closed.
    import errno
    if isinstance(exc, (TimeoutError, ConnectionError, EOFError)):
        return True
    return isinstance(exc, OSError) and exc.errno in (errno.ETIMEDOUT, errno.ECONNRESET,
        errno.ECONNREFUSED, errno.EHOSTUNREACH, errno.ENETUNREACH, errno.EPIPE)

def execute(action, password, factory=None, sleeper=time.sleep, permitted=allowed):
    factory = factory or connection
    attempts = []
    transaction = {'recordPublication': True}
    data = json.loads((ROOT/'albums/snapshot.json').read_text()) if action == 'publish' else None
    if data is not None:
        # An older publication stamp must not be copied onto a new collection.
        data.pop('publication', None)
    for attempt in range(1, 4):
        if not permitted():
            return {'status': 'paused', 'reason': 'KST 01:00-06:59', 'attempts': attempts}
        progress = {'stage': 'start'}
        try:
            with night_deadline(), factory(password, progress) as remote:
                result = restore(remote, progress) if action == 'restore' else publish(remote, data, transaction, progress)
            result['attempts'] = attempts + [{'attempt': attempt, 'state': 'success'}]
            return result
        except NightPause:
            return {'status':'paused', 'reason':'KST 01:00-06:59', 'attempts':attempts}
        except Exception as exc:
            retry = transient(exc)
            attempts.append({'attempt': attempt, 'at': datetime.now(timezone.utc).isoformat(),
                'stage': progress['stage'], 'error': type(exc).__name__, 'retryable': retry})
            print(json.dumps({'albumAttempt': attempts[-1]}), flush=True)
            if not retry or attempt == 3:
                return {'status':'failed', 'error': str(exc) if isinstance(exc, d.Stop) else type(exc).__name__,
                    'failedStage': progress['stage'], 'attempts': attempts}
            delay = (5, 15)[attempt-1]
            if remaining() <= delay:
                return {'status':'paused', 'reason':'KST 01:00-06:59', 'attempts':attempts}
            sleeper(delay)

def main():
    parser = argparse.ArgumentParser(); parser.add_argument('action', choices=('restore', 'publish')); args = parser.parse_args()
    password = os.environ.pop('ISEGYE_SFTP_PASSWORD', '')
    try:
        result = execute(args.action, password)
    except Exception as exc:
        result = {'status':'failed', 'error':type(exc).__name__, 'failedStage':'local_input'}
    finally:
        password = None
    output = ROOT/('albums-restore.json' if args.action == 'restore' else 'albums-publication.json')
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(result, ensure_ascii=False))
    return int(result['status'] not in ('restored', 'published', 'paused'))

if __name__ == '__main__':
    raise SystemExit(main())
