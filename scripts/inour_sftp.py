#!/usr/bin/env python3
"""Fixed-root SFTP deployment. Never changes /web or MIR routing/files."""
from __future__ import annotations
import base64
import hashlib
import json
import os
import posixpath
import re
import socket
import stat
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = '/web/_isegye_idol'
MIR = '/web/_mir_site'
HOST, PORT, USER, UID = 'seirian.inour.net', 1922, 'seirian', 5048
FINGERPRINT = 'SHA256:aAMSU6UVE9lIpzE/XifPGYrEGcHO7HQDTMURgfrinRc'
ORIGIN = 'https://isegye-idol.kr'
OWNER = b'isegye-idol-fansite:isolated-root:v1\n'
PROTECTED = ('/web/.htaccess', '/web/index.html', '/web/index.php', '/web/robots.txt',
             MIR + '/.htaccess', '/web/mir/.htaccess')
RID = re.compile(r'r[0-9a-f]{12}')

class Stop(RuntimeError):
    pass

def require(ok, message):
    if not ok:
        raise Stop(message)

def digest(data):
    return hashlib.sha256(data).hexdigest()

def write_path(path):
    require(isinstance(path, str) and path.startswith(ROOT + '/'), 'Write outside isolated site root')
    require(posixpath.normpath(path) == path and '\\' not in path, 'Non-canonical path')
    require(all(re.fullmatch(r'[A-Za-z0-9_.-]+', p) and p not in ('.', '..') for p in path.split('/')[1:]), 'Unsafe path')
    return path

def router(release=None):
    require(release is None or RID.fullmatch(release), 'Invalid release identifier')
    rules = ('# ISEGYE-ISOLATED-ROOT-V1 ' + (release or 'unpublished') + '\n'
             'Options -Indexes\nDirectoryIndex index.html\nRewriteEngine On\n'
             'RewriteCond %{HTTP_HOST} !^isegye-idol\\.kr(?::443)?$ [NC]\n'
             'RewriteRule ^ - [F,L]\nRewriteRule (^|/)\\. - [F,L]\n'
             'RewriteRule ^isegye-probe-[0-9a-f]+\\.txt$ - [L]\n')
    if release:
        rules += ('RewriteRule ^_isegye_releases/r[0-9a-f]{12}/ - [L]\n'
                  f'RewriteRule ^$ _isegye_releases/{release}/index.html [L]\n'
                  f'RewriteRule ^((?:src|assets)/.+|index\\.html|robots\\.txt|build-info\\.json)$ _isegye_releases/{release}/$1 [L]\n'
                  'RewriteRule ^ - [R=404,L]\n')
    else:
        rules += 'RewriteRule ^ - [R=503,L]\n'
    return rules.encode()

def managed_router(data):
    if data == router():
        return True
    if not data:
        return False
    first = data.splitlines()[0].decode('ascii', errors='replace')
    release = first.removeprefix('# ISEGYE-ISOLATED-ROOT-V1 ')
    return bool(RID.fullmatch(release)) and data == router(release)

def load_payload(directory, commit):
    require(re.fullmatch(r'[0-9a-f]{40}', commit), 'Missing full commit SHA')
    root = Path(directory)
    require(root.is_dir() and not root.is_symlink(), 'Invalid build directory')
    result = {}
    for path in sorted(root.rglob('*')):
        require(not path.is_symlink(), 'Build symlinks are forbidden')
        if path.is_dir():
            continue
        rel = path.relative_to(root).as_posix()
        require(rel in ('index.html', 'robots.txt', 'build-info.json', '.nojekyll') or
                re.fullmatch(r'(src|assets)/[A-Za-z0-9_./-]+\.(js|css|svg|png|webp|jpg|json)', rel), 'Unexpected build file')
        write_path(ROOT + '/_isegye_releases/r' + commit[:12] + '/' + rel)
        data = path.read_bytes()
        require(len(data) <= 8 * 1024 * 1024, 'Build file too large')
        result[rel] = data
    require({'index.html', 'src/app.js', 'src/styles.css', 'build-info.json'} <= result.keys(), 'Build incomplete')
    meta = json.loads(result['build-info.json'])
    require(meta.get('mode') == 'production' and meta.get('commit') == commit, 'Production build/commit mismatch')
    return result

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args):
        return None

def http(url):
    request = urllib.request.Request(url, headers={'User-Agent': 'IsegyeIsolatedDeploy/1.0', 'Cache-Control': 'no-cache'})
    try:
        response = urllib.request.build_opener(NoRedirect).open(request, timeout=20)
    except urllib.error.HTTPError as exc:
        response = exc
    with response:
        data = response.read(9 * 1024 * 1024)
        return response.status, data

class Remote:
    def __init__(self, client):
        self.s = client

    def info(self, path):
        try:
            return self.s.lstat(path)
        except FileNotFoundError:
            return None

    def directory(self, path):
        info = self.info(path)
        require(info is not None and stat.S_ISDIR(info.st_mode) and info.st_uid == UID, 'Unexpected directory type/owner')
        require(self.s.normalize(path) == path, 'Symlink/alias directory rejected')

    def parents(self, path):
        write_path(path)
        self.directory('/web')
        self.directory(ROOT)
        current = ROOT
        for part in path[len(ROOT) + 1:].split('/')[:-1]:
            current += '/' + part
            self.directory(current)

    def read(self, path):
        info = self.info(path)
        if info is None:
            return None
        require(stat.S_ISREG(info.st_mode) and info.st_uid == UID and info.st_size <= 9 * 1024 * 1024, 'Unsafe file type/owner/size')
        with self.s.open(path, 'rb') as handle:
            return handle.read(9 * 1024 * 1024)

    def new(self, path, data):
        self.parents(path)
        require(self.info(path) is None, 'Refusing existing file')
        with self.s.open(path, 'wx') as handle:
            handle.write(data)
            handle.flush()
        self.s.chmod(path, 0o644)
        require(self.read(path) == data, 'Upload verification failed')

    def mkdir(self, path):
        self.parents(path)
        require(self.info(path) is None, 'Refusing existing directory')
        self.s.mkdir(path, 0o755)
        self.s.chmod(path, 0o755)
        self.directory(path)

    def replace(self, path, data, expected):
        self.parents(path)
        require(self.read(path) == expected, 'Concurrent router change; stopped')
        temporary = path + '.tmp-' + os.urandom(8).hex()
        self.new(temporary, data)
        # No remove-then-rename fallback: the server must support atomic rename.
        require(self.read(path) == expected, 'Concurrent router change; stopped')
        self.s.posix_rename(temporary, path)
        require(self.read(path) == data, 'Atomic router verification failed')

    def remove_own(self, path, expected):
        self.parents(path)
        require(self.read(path) == expected, 'Changed probe; refusing deletion')
        self.s.remove(path)

    def snapshot(self):
        self.directory('/web')
        self.directory(MIR)
        result = {}
        for path in PROTECTED:
            parent = posixpath.dirname(path)
            if self.info(parent) is None:
                result[path] = None
                continue
            self.directory(parent)
            data = self.read(path)
            result[path] = digest(data) if data is not None else None
        return result

    def initialize(self):
        self.directory('/web')
        marker = ROOT + '/.isegye-owner'
        if self.info(ROOT) is not None:
            self.directory(ROOT)
            if self.read(marker) == OWNER:
                require(managed_router(self.read(ROOT + '/.htaccess')), 'Unrecognized site router')
                return
            require(not self.s.listdir(ROOT), 'Nonempty unmanaged site root; stopped')
        require(os.environ.get('ISEGYE_INITIALIZE_EMPTY_ROOT') == 'true', 'First setup requires ISEGYE_INITIALIZE_EMPTY_ROOT=true')
        if self.info(ROOT) is None:
            # This is the only mkdir outside parents(): exact fixed root, checked /web.
            self.s.mkdir(ROOT, 0o755)
            self.s.chmod(ROOT, 0o755)
            self.directory(ROOT)
        self.new(ROOT + '/.htaccess', router())
        self.new(marker, OWNER)

    def prove_mapping(self):
        name = 'isegye-probe-' + os.urandom(16).hex() + '.txt'
        data = ('isegye-root-proof:' + os.urandom(32).hex()).encode()
        path = ROOT + '/' + name
        self.new(path, data)
        try:
            require(http(ORIGIN + '/' + name) == (200, data), 'Domain document root not mapped to isolated directory')
            for origin in ('https://mir.yeop.net', 'https://yeop.net'):
                for suffix in ('/' + name, '/_isegye_idol/' + name):
                    _, body = http(origin + suffix)
                    require(data not in body, 'Cross-host exposure detected')
        finally:
            self.remove_own(path, data)

    def deploy(self, payload, commit):
        before = self.snapshot()
        self.initialize()
        lock = ROOT + '/.deploy-lock'
        self.mkdir(lock)
        try:
            self.prove_mapping()
            parent = ROOT + '/_isegye_releases'
            if self.info(parent) is None:
                self.mkdir(parent)
            self.directory(parent)
            release = 'r' + commit[:12]
            target = parent + '/' + release
            self.mkdir(target)
            for rel, data in payload.items():
                current = target
                for part in rel.split('/')[:-1]:
                    current += '/' + part
                    if self.info(current) is None:
                        self.mkdir(current)
                self.new(target + '/' + rel, data)
            # Initial router intentionally denies release URLs until activation.
            # Validate staged bytes with SFTP; all live files are verified after the swap.
            require(self.snapshot() == before, 'Protected routes changed; activation blocked')
            path = ROOT + '/.htaccess'
            old = self.read(path)
            require(managed_router(old), 'Unmanaged router')
            new = router(release)
            try:
                self.replace(path, new, old)
                for rel, data in payload.items():
                    if rel == '.nojekyll':
                        continue
                    require(http(ORIGIN + '/' + rel) == (200, data), 'Public release verification failed')
                require(http(ORIGIN + '/') == (200, payload['index.html']), 'Homepage verification failed')
                require(self.snapshot() == before, 'Protected routes changed during activation')
            except Exception:
                if self.read(path) == new:
                    self.replace(path, old, new)
                raise
            return {'status': 'deployed', 'release': release, 'root': ROOT, 'protected_files_unchanged': True,
                    'file_count': len(payload), 'mapping_proved': True}
        finally:
            self.parents(lock)
            self.s.rmdir(lock)

def main():
    require(os.environ.get('GITHUB_REF') == 'refs/heads/main', 'Deployment is main-only')
    require(os.environ.get('PRODUCTION_ENABLED') == 'true', 'Production not enabled')
    commit = os.environ.get('GITHUB_SHA', '')
    payload = load_payload('dist', commit)
    password = os.environ.get('ISEGYE_SFTP_PASSWORD', '')
    require(password, 'ISEGYE_SFTP_PASSWORD is unavailable in this repository/environment')
    import paramiko
    transport = paramiko.Transport(socket.create_connection((HOST, PORT), timeout=15))
    client = None
    try:
        transport.get_security_options().key_types = ('ssh-ed25519',)
        transport.start_client(timeout=15)
        key = transport.get_remote_server_key()
        fingerprint = 'SHA256:' + base64.b64encode(hashlib.sha256(key.asbytes()).digest()).decode().rstrip('=')
        require(key.get_name() == 'ssh-ed25519' and fingerprint == FINGERPRINT, 'Host key mismatch; credentials not sent')
        transport.auth_password(USER, password)
        password = None
        require(transport.is_authenticated(), 'SFTP authentication failed')
        client = paramiko.SFTPClient.from_transport(transport)
        client.get_channel().settimeout(30)
        return Remote(client).deploy(payload, commit)
    finally:
        password = None
        if client:
            client.close()
        transport.close()

if __name__ == '__main__':
    try:
        report = main()
    except Exception as exc:
        # Do not emit server/library exception messages, which may contain credentials.
        report = {'status': 'blocked_or_failed', 'error_type': type(exc).__name__,
                  'reason': str(exc) if isinstance(exc, Stop) else 'See safe preflight checks; no credentials logged'}
    Path('inour-report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
    sys.exit(0 if report['status'] == 'deployed' else 1)
