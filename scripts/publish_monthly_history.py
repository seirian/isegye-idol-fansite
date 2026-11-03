"""Owned, atomic history-only publication. Reads other feeds; never modifies them."""
from pathlib import Path
from datetime import datetime, timezone
import base64, hashlib, json, os, socket, sys
import inour_sftp as d
import auth_routing as routing
import monthly_history as history

DIR = d.ROOT + '/.history-feed'
OWNER = b'isegye-monthly-history:v1\n'
NAMES = {'.owner', '.lock', 'current.json', 'previous.json'}

def path(name):
    d.require(name in NAMES, 'Unexpected history path')
    return DIR + '/' + name

def read_snapshot(remote, folder, marker, limit):
    if remote.info(folder) is None:
        return None
    remote.directory(folder)
    d.require(remote.read(folder + '/.owner') == marker, 'Unowned upstream data folder')
    raw = remote.read(folder + '/current.json')
    if raw is None:
        return None
    d.require(len(raw) <= limit, 'Upstream snapshot too large')
    return json.loads(raw)

def publish(remote, fresh):
    when = history.stamp(fresh['generatedAt'])
    d.require(0 <= (datetime.now(timezone.utc) - when).total_seconds() <= 7200, 'Stale history collection')
    remote.directory('/web'); remote.directory(d.ROOT)
    d.require(remote.read(d.ROOT + '/.isegye-owner') == d.OWNER, 'Wrong owner')
    router = remote.read(d.ROOT + '/.htaccess')
    rid, gated = routing.release_of(router)
    d.require(gated, 'Access gate required')
    meta = json.loads(remote.read(d.ROOT + '/_isegye_releases/' + rid + '/build-info.json') or b'{}')
    d.require(meta.get('monthlyHistory', {}).get('schemaVersion') == 1, 'History-enabled release not active')
    protected = remote.snapshot()
    schedule = read_snapshot(remote, d.ROOT + '/.schedule-feed', b'isegye-schedule-feed:v1\n', 2097152)
    music = read_snapshot(remote, d.ROOT + '/.music-feed', b'isegye-daily-music:v1\n', 1500000)
    if music:
        d.require(music.get('feed') == 'daily-music' and music.get('schemaVersion') == 1, 'Invalid upstream music snapshot')
    current = history.combine_inputs(fresh, schedule, music['rows'] if music else None)
    if remote.info(DIR) is None:
        remote.mkdir(DIR); remote.s.chmod(DIR, 0o700)
        remote.new(path('.owner'), OWNER); remote.s.chmod(path('.owner'), 0o600)
    remote.directory(DIR)
    d.require(remote.read(path('.owner')) == OWNER, 'Unowned history directory')
    lock = os.urandom(24)
    d.require(remote.info(path('.lock')) is None, 'Existing history lock; no overwrite')
    remote.new(path('.lock'), lock); remote.s.chmod(path('.lock'), 0o600)
    try:
        old = remote.read(path('current.json'))
        previous = history.validate(json.loads(old)) if old else None
        value = history.merge(previous, current)
        before = {r['id']: r for r in previous['events']} if previous else {}
        added = [r for r in value['events'] if r['id'] not in before]
        updated = [r for r in value['events'] if r['id'] in before and r != before[r['id']]]
        raw = (json.dumps(value, ensure_ascii=False, separators=(',', ':')) + '\n').encode()
        d.require(len(raw) <= history.MAX_BYTES, 'History snapshot too large')
        d.require(remote.read(d.ROOT + '/.htaccess') == router, 'Active release changed')
        d.require(remote.snapshot() == protected, 'Protected site changed during history publication')
        if old and raw != old:
            remote.replace(path('previous.json'), old, remote.read(path('previous.json')))
            remote.s.chmod(path('previous.json'), 0o600)
        if raw != old:
            remote.replace(path('current.json'), raw, old); remote.s.chmod(path('current.json'), 0o600)
        d.require(remote.read(path('current.json')) == raw, 'History publication readback differs')
        return {'status': 'published', 'release': rid, 'generatedAt': value['generatedAt'], 'through': value['through'],
                'added': len(added), 'updated': len(updated), 'totalAuto': len(value['events']),
                'curatedPreserved': len(history.base()['events']), 'totalDisplayed': len(history.base()['events']) + len(value['events']),
                'newItems': added, 'coverage': value['coverage'], 'sha256': d.digest(raw),
                'verifiedReadback': True, 'protectedFilesUnchanged': True, 'upstreamFeedsReadOnly': True}
    finally:
        remote.remove_own(path('.lock'), lock)

def main():
    result = {'status': 'failed'}; resources = []; password = os.environ.pop('ISEGYE_SFTP_PASSWORD', '')
    try:
        d.require(os.getenv('GITHUB_REF') == 'refs/heads/main' and os.getenv('GITHUB_REPOSITORY') == 'seirian/isegye-idol-fansite', 'Main only')
        d.require(os.getenv('PRODUCTION_PAUSED') != 'true' and os.getenv('ISEGYE_HISTORY_PAUSED') != 'true' and bool(password), 'Paused or missing credential')
        import paramiko
        sock = socket.create_connection((d.HOST, d.PORT), timeout=15); resources.append(sock)
        transport = paramiko.Transport(sock); resources.append(transport)
        transport.banner_timeout = 15; transport.auth_timeout = 20
        transport.get_security_options().key_types = ('ssh-ed25519',); transport.start_client(timeout=15)
        key = transport.get_remote_server_key()
        fingerprint = 'SHA256:' + base64.b64encode(hashlib.sha256(key.asbytes()).digest()).decode().rstrip('=')
        d.require(key.get_name() == 'ssh-ed25519' and fingerprint == d.FINGERPRINT, 'Host key mismatch')
        transport.auth_password(d.USER, password); password = None
        d.require(transport.is_authenticated(), 'SFTP authentication failed')
        client = paramiko.SFTPClient.from_transport(transport); resources.append(client); client.get_channel().settimeout(30)
        result = publish(d.Remote(client), json.loads(Path('history-inputs.json').read_text()))
    except Exception as exc:
        result = {'status': 'failed', 'error': str(exc) if isinstance(exc, (d.Stop, ValueError)) else type(exc).__name__}
    finally:
        password = None
        for item in reversed(resources):
            try: item.close()
            except Exception: pass
        Path('history-publication.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
        print(json.dumps(result, ensure_ascii=False))
    return int(result['status'] != 'published')

if __name__ == '__main__':
    sys.exit(main())
