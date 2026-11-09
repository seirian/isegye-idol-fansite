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

def restore(remote):
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

def publish(remote, data):
    validate(data, exact=True, fresh=True)
    d.require(data.get('feed') == 'daily-albums', 'Wrong album feed type')
    report = health(data)
    d.require(report['state'] == 'complete', 'Required album sources incomplete; previous feed preserved')
    assets = {}
    for sha, entry in asset_entries(data).items():
        local = (ROOT/entry['path']).resolve()
        d.require(local.is_relative_to((ROOT/'albums/asset-cache').resolve()) and not (ROOT/entry['path']).is_symlink(), 'Unsafe local album asset')
        assets[sha] = image_bytes(local.read_bytes(), sha)
    raw = (json.dumps(data, ensure_ascii=False, separators=(',', ':'))+'\n').encode()
    d.require(len(raw) <= MAX_BYTES, 'Album feed too large')
    router, rid, _ = active(remote)
    if remote.info(DIR) is None:
        remote.mkdir(DIR); remote.s.chmod(DIR, 0o700)
        remote.new(path('.owner'), OWNER); remote.s.chmod(path('.owner'), 0o600)
    owned(remote)
    d.require(remote.info(path('.lock')) is None, 'Existing album lock; refusing overlap')
    lock = os.urandom(24); remote.new(path('.lock'), lock); remote.s.chmod(path('.lock'), 0o600)
    try:
        old = remote.read(path('current.json'))
        if old is not None: decode(old)
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
        if old is not None and old != raw:
            remote.replace(path('previous.json'), old, remote.read(path('previous.json')))
            remote.s.chmod(path('previous.json'), 0o600)
        if old != raw:
            remote.replace(path('current.json'), raw, old); remote.s.chmod(path('current.json'), 0o600)
        try:
            d.require(remote.read(path('current.json')) == raw, 'Album feed read-back failed')
            d.require(remote.read(d.ROOT+'/.htaccess') == router, 'Release changed after publication')
        except Exception:
            if old is not None and remote.read(path('current.json')) == raw:
                remote.replace(path('current.json'), old, raw)
            raise
        return {'status': 'published', 'release': rid, 'generatedAt': data['generatedAt'],
                'totalTracks': len(data['tracks']), 'assets': len(assets), 'sha256': d.digest(raw),
                'collectionHealth': report, 'verifiedReadback': True, 'routingUnchanged': True,
                'accountStoreReadOrWritten': False,
                'releaseBindings': {sid: {'melonId': data['tracks'][sid]['melon']['trackId'],
                    'albumId': data['tracks'][sid]['melon']['albumId'],
                    'artwork': bool(data['tracks'][sid].get('artwork'))}
                    for sid in report['releaseTracks']}}
    finally:
        remote.remove_own(path('.lock'), lock)

@contextmanager
def connection():
    resources = []; password = os.environ.pop('ISEGYE_SFTP_PASSWORD', '')
    try:
        d.require(os.getenv('GITHUB_REF') == 'refs/heads/main'
                  and os.getenv('GITHUB_REPOSITORY') == 'seirian/isegye-idol-fansite', 'Main repository only')
        d.require(os.getenv('PRODUCTION_PAUSED') != 'true'
                  and os.getenv('ISEGYE_ALBUMS_PAUSED') != 'true' and bool(password), 'Paused or missing credential')
        import paramiko
        from deploy_verified_albums import VerifiedTransferRemote
        sock = socket.create_connection((d.HOST, d.PORT), timeout=15); resources.append(sock)
        transport = paramiko.Transport(sock); resources.append(transport)
        transport.banner_timeout = 15; transport.auth_timeout = 20
        transport.get_security_options().key_types = ('ssh-ed25519',); transport.start_client(timeout=15)
        key = transport.get_remote_server_key()
        fingerprint = 'SHA256:'+base64.b64encode(hashlib.sha256(key.asbytes()).digest()).decode().rstrip('=')
        d.require(key.get_name() == 'ssh-ed25519' and fingerprint == d.FINGERPRINT, 'Host key mismatch')
        transport.auth_password(d.USER, password); password = None
        d.require(transport.is_authenticated(), 'SFTP authentication failed')
        client = paramiko.SFTPClient.from_transport(transport); resources.append(client)
        client.get_channel().settimeout(45)
        yield VerifiedTransferRemote(client)
    finally:
        password = None
        for resource in reversed(resources):
            try: resource.close()
            except Exception: pass

def main():
    parser = argparse.ArgumentParser(); parser.add_argument('action', choices=('restore', 'publish')); args = parser.parse_args()
    try:
        with connection() as remote:
            result = restore(remote) if args.action == 'restore' else publish(remote, json.loads((ROOT/'albums/snapshot.json').read_text()))
    except Exception as exc:
        result = {'status': 'failed', 'error': str(exc) if isinstance(exc, d.Stop) else type(exc).__name__}
    output = ROOT/('albums-restore.json' if args.action == 'restore' else 'albums-publication.json')
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(result, ensure_ascii=False))
    return int(result['status'] not in ('restored', 'published'))

if __name__ == '__main__':
    raise SystemExit(main())
