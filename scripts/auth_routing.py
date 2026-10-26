"""Exact, fail-closed routing and validation helpers for the existing site only."""
from __future__ import annotations
import base64
import hashlib
import json
import re
from pathlib import Path
import inour_sftp as d

CLIENT = re.compile(r'[0-9]+-[A-Za-z0-9_-]+\.apps\.googleusercontent\.com')
RUNTIME = re.compile(r'g[0-9a-f]{12}')
PRIVATE = d.ROOT + '/.auth-private'
PRIVATE_OWNER = b'isegye-google-access:private-store:v1\n'
INJECTION = '<link rel="stylesheet" href="/auth/account.css"><script defer src="/auth/client.js"></script>'


def router(release: str) -> bytes:
    d.require(bool(d.RID.fullmatch(release)), 'Invalid gated release')
    return (f'# ISEGYE-AUTH-ROOT-V1 {release}\n'
            'Options -Indexes -MultiViews\nDirectoryIndex access.php\nRewriteEngine On\n'
            'RewriteCond %{HTTP_HOST} !^isegye-idol\\.kr(?::443)?$ [NC]\n'
            'RewriteRule ^ - [F,END]\n'
            'RewriteRule (^|/)\\. - [F,END]\n'
            'RewriteRule ^isegye-probe-[0-9a-f]+\\.txt$ - [END]\n'
            'RewriteRule ^access\\.php$ - [END]\n'
            'RewriteRule ^ access.php [END]\n').encode()


def release_of(data: bytes) -> tuple[str, bool]:
    d.require(isinstance(data, bytes), 'Missing site router')
    match = re.match(rb'# ISEGYE-AUTH-ROOT-V1 (r[0-9a-f]{12})\n', data)
    if match:
        release = match[1].decode()
        d.require(data == router(release), 'Gated router differs from managed rules')
        return release, True
    d.require(d.managed_router(data), 'Unrecognized site router')
    release = data.splitlines()[0].decode().removeprefix('# ISEGYE-ISOLATED-ROOT-V1 ')
    d.require(bool(d.RID.fullmatch(release)), 'Existing public release required')
    return release, False


def account_state(data: bytes) -> dict:
    # Never return identity values in reports. The deployer never writes this file.
    d.require(isinstance(data, bytes) and len(data) <= 2097152, 'Account store missing or oversized')
    state = json.loads(data)
    d.require(isinstance(state, dict) and list(state) == ['schema', 'administrator', 'accounts'] and state['schema'] == 1, 'Invalid account schema')
    accounts = state['accounts']
    d.require(isinstance(accounts, dict), 'Invalid account map')
    d.require(len(accounts) <= 10000, 'Account store over capacity')
    for key, role in accounts.items():
        d.require(isinstance(key, str) and bool(re.fullmatch('[0-9a-f]{64}', key)) and role in ('member', 'admin'), 'Invalid account fields')
    admins = [key for key, role in accounts.items() if role == 'admin']
    d.require((state['administrator'] is None and not admins) or admins == [state['administrator']], 'Inconsistent administrator')
    return {'accountCount': len(accounts), 'administratorRegistered': state['administrator'] is not None}


def configured(data: bytes, client: str) -> tuple[bytes, bool]:
    d.require(isinstance(client, str) and bool(CLIENT.fullmatch(client)), 'Google Web Client ID missing or malformed')
    c = json.loads(data)
    d.require(set(c) == {'origin', 'clientId', 'siteKey', 'adminEmailDigest'} and c['origin'] == d.ORIGIN, 'Unrecognized private configuration')
    key = base64.b64decode(c['siteKey'], validate=True)
    d.require(len(key) == 32 and bool(re.fullmatch('[0-9a-f]{64}', c['adminEmailDigest'])), 'Invalid private key configuration')
    d.require(c['clientId'] in ('', client), 'Client ID differs from configured identity; manual review required')
    if c['clientId'] == client:
        return data, False
    c['clientId'] = client
    return (json.dumps(c, separators=(',', ':')) + '\n').encode(), True


def bundle(directory: Path) -> tuple[str, dict[str, bytes]]:
    directory = Path(directory)
    manifest = json.loads((directory / 'manifest.json').read_text())
    runtime = manifest['runtime']
    d.require(bool(RUNTIME.fullmatch(runtime)), 'Invalid auth runtime name')
    files = {}
    for name, digest in manifest['files'].items():
        d.write_path(d.ROOT + '/.auth-runtime/' + runtime + '/' + name)
        path = directory / name
        d.require(path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(directory.resolve()), 'Invalid auth bundle file')
        data = path.read_bytes()
        d.require(len(data) < 2097152 and hashlib.sha256(data).hexdigest() == digest, 'Auth bundle hash mismatch')
        files[name] = data
    required = {'access.php.template','Gateway.php','GoogleVerifier.php','Session.php','Store.php','View.php','vendor/autoload.php','background.webp','client.js','google-client.js','style.css','account.css','.htaccess'}
    d.require(required <= files.keys(), 'Auth runtime incomplete')
    actual = {p.relative_to(directory).as_posix() for p in directory.rglob('*') if p.is_file()}
    d.require(actual == set(files) | {'manifest.json'}, 'Unlisted auth bundle files')
    expected = 'g' + hashlib.sha256(json.dumps(manifest['files'], sort_keys=True).encode()).hexdigest()[:12]
    d.require(expected == runtime, 'Auth runtime digest mismatch')
    d.require(files['.htaccess'] == b'Require all denied\n', 'Runtime must be HTTP denied')
    return runtime, files


def entry(template: bytes, runtime: str) -> bytes:
    d.require(bool(RUNTIME.fullmatch(runtime)) and template.count(b'RUNTIME_ID') == 1, 'Invalid gateway template')
    return template.replace(b'RUNTIME_ID', runtime.encode())


def public_html(data: bytes) -> bytes:
    text = data.decode()
    text = text.replace('form-action https://github.com', "form-action 'self' https://github.com")
    return text.replace('</head>', INJECTION + '</head>').encode()


def recovery_router(previous: bytes) -> bytes:
    # NEVER restore unauthenticated static routing, even during first activation.
    return router(release_of(previous)[0])
