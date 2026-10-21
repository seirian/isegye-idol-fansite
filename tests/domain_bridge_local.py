#!/usr/bin/env python3
"""Local Apache fixtures only; no SFTP, credentials or live-site writes."""
from __future__ import annotations
import hashlib
import http.client
import json
import os
import pwd
import grp
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import time
import sys
from unittest.mock import MagicMock, patch
from types import SimpleNamespace
import urllib.request
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from inour_domain_bridge import BRIDGE, AUDITED_SHA, plan, Stop, band_redirect as inspect_band_redirect
from inour_sftp import router as site_router
MIR_BRIDGE = b'# MIR-SUBDOMAIN-BRIDGE-V1\nRewriteEngine On\n\n# Stable host bridge for the MIR fanpage only.\nRewriteCond %{HTTP_HOST} ^mir\\.yeop\\.net(?::[0-9]+)?$ [NC]\nRewriteCond %{REQUEST_URI} !^/_mir_site(?:/|$)\nRewriteRule ^(.*)$ _mir_site/$1 [L]\n\n# yeop.net and every other host intentionally fall through untouched.\n# Personal-site rewrite rules may be appended below this block.\n'

def main() -> None:
    apache = shutil.which('apache2')
    if not apache:
        raise SystemExit('apache2 is required')
    with tempfile.TemporaryDirectory(prefix='isegye-routing-') as tmp:
        root = Path(tmp)
        root.chmod(0o755)
        web = root / 'web'
        mir, isegye = web / '_mir_site', web / '_isegye_idol'
        mir.mkdir(parents=True)
        isegye.mkdir()
        (mir / '.htaccess').write_text('RewriteEngine On\nRewriteRule ^band$ https://mir.yeop.net/band/ [R=301,L]\n')
        (mir / 'band').mkdir()
        (mir / 'band' / 'index.html').write_bytes(b'MIR-BAND-FIXTURE')
        (web / '.htaccess').write_bytes(MIR_BRIDGE)
        (web / 'index.html').write_bytes(b'PERSONAL-SITE-FIXTURE')
        (mir / 'index.html').write_bytes(b'MIR-SITE-FIXTURE')
        (isegye / '.htaccess').write_bytes(site_router())
        (isegye / '.isegye-owner').write_bytes(b'fixture-owner-not-public')
        probe = 'isegye-probe-' + 'a' * 32 + '.txt'
        (isegye / probe).write_bytes(b'UNIQUE-ISEGYE-PROBE-FIXTURE')
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        user = 'www-data' if os.geteuid() == 0 else pwd.getpwuid(os.geteuid()).pw_name
        group = 'www-data' if os.geteuid() == 0 else grp.getgrgid(os.getegid()).gr_name
        config = root / 'httpd.conf'
        config.write_text(f'''ServerRoot "{root}"
PidFile "{root}/httpd.pid"
Listen 127.0.0.1:{port}
ServerName localhost
LoadModule mpm_event_module /usr/lib/apache2/modules/mod_mpm_event.so
LoadModule authz_core_module /usr/lib/apache2/modules/mod_authz_core.so
LoadModule rewrite_module /usr/lib/apache2/modules/mod_rewrite.so
LoadModule dir_module /usr/lib/apache2/modules/mod_dir.so
LoadModule mime_module /usr/lib/apache2/modules/mod_mime.so
TypesConfig /etc/mime.types
User {user}
Group {group}
ErrorLog "{root}/error.log"
LogLevel warn
DocumentRoot "{web}"
DirectoryIndex index.html
<Directory "{web}">
  AllowOverride All
  Options +FollowSymLinks -Indexes
  Require all granted
</Directory>
''')
        syntax = subprocess.run([apache, '-t', '-f', str(config)], capture_output=True, text=True)
        if syntax.returncode:
            raise RuntimeError(syntax.stderr)
        process = subprocess.Popen([apache, '-X', '-f', str(config)], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        results = []
        def request(host: str, path: str = '/') -> tuple[int, bytes]:
            conn = http.client.HTTPConnection('127.0.0.1', port, timeout=5)
            try:
                conn.request('GET', path, headers={'Host': host})
                response = conn.getresponse()
                return response.status, response.read()
            finally:
                conn.close()
        def band_redirect():
            conn = http.client.HTTPConnection('127.0.0.1', port, timeout=5)
            try:
                conn.request('GET', '/band', headers={'Host': 'mir.yeop.net'})
                response = conn.getresponse()
                return response.status, response.getheader('Location')
            finally:
                conn.close()
        def check(name: str, passed: bool):
            results.append({'test': name, 'passed': bool(passed)})
            if not passed:
                raise AssertionError(name)
        try:
            mock_response = MagicMock()
            mock_response.status = 301
            mock_response.headers = {'Location': 'https://mir.yeop.net/band/'}
            mock_response.__enter__.return_value = mock_response
            with patch('urllib.request.build_opener') as opener:
                opener.return_value.open.return_value = mock_response
                result = inspect_band_redirect(SimpleNamespace(NoRedirect=urllib.request.HTTPRedirectHandler))
                check('redirect inspector requests noncanonical URL', opener.return_value.open.call_args.args[0].full_url == 'https://mir.yeop.net/band')
                check('redirect inspector returns status and destination', result == (301, 'https://mir.yeop.net/band/'))
            check('fixture matches audited router', hashlib.sha256(MIR_BRIDGE).hexdigest() == AUDITED_SHA)
            check('append preserves original bytes', plan(MIR_BRIDGE) == (MIR_BRIDGE, MIR_BRIDGE + BRIDGE))
            check('repeated application is idempotent', plan(MIR_BRIDGE + BRIDGE) == (MIR_BRIDGE, MIR_BRIDGE + BRIDGE))
            for label, malformed in [('unknown router', b'unknown'), ('modified original', MIR_BRIDGE + b'changed'),
                                     ('duplicate append', MIR_BRIDGE + BRIDGE + BRIDGE),
                                     ('changed suffix', MIR_BRIDGE + BRIDGE + b'changed')]:
                rejected = False
                try:
                    plan(malformed)
                except Stop:
                    rejected = True
                check(label + ' rejected', rejected)
            for _ in range(50):
                try:
                    request('yeop.net')
                    break
                except ConnectionError:
                    time.sleep(0.1)
            else:
                raise RuntimeError('Local Apache did not start')
            baseline = {h: request(h) for h in ('mir.yeop.net', 'yeop.net')}
            check('initial MIR response', baseline['mir.yeop.net'] == (200, b'MIR-SITE-FIXTURE'))
            check('initial personal response', baseline['yeop.net'] == (200, b'PERSONAL-SITE-FIXTURE'))
            check('canonical probe absent before mapping', request('isegye-idol.kr', '/' + probe)[0] == 404)
            check('nested probe present before mapping', request('isegye-idol.kr', '/_isegye_idol/' + probe) == (200, b'UNIQUE-ISEGYE-PROBE-FIXTURE'))
            check('MIR band redirect before append', band_redirect() == (301, 'https://mir.yeop.net/band/'))
            check('MIR canonical band healthy', request('mir.yeop.net', '/band/') == (200, b'MIR-BAND-FIXTURE'))
            (web / '.htaccess').write_bytes(MIR_BRIDGE + BRIDGE)
            check('MIR band redirect after append', band_redirect() == (301, 'https://mir.yeop.net/band/'))
            check('original is exact prefix', (web / '.htaccess').read_bytes()[:len(MIR_BRIDGE)] == MIR_BRIDGE)
            check('canonical mapping', request('isegye-idol.kr', '/' + probe) == (200, b'UNIQUE-ISEGYE-PROBE-FIXTURE'))
            check('query preserved', request('isegye-idol.kr', '/' + probe + '?check=1') == (200, b'UNIQUE-ISEGYE-PROBE-FIXTURE'))
            check('www not enabled', b'UNIQUE-ISEGYE-PROBE-FIXTURE' not in request('www.isegye-idol.kr', '/' + probe)[1])
            check('unpublished guard retained', request('isegye-idol.kr')[0] == 503)
            for host in ('mir.yeop.net', 'yeop.net'):
                check(host + ' unchanged after append', request(host) == baseline[host])
                for path in ('/' + probe, '/_isegye_idol/' + probe):
                    check(host + path + ' blocked', b'UNIQUE-ISEGYE-PROBE-FIXTURE' not in request(host, path)[1])
            check('similar host excluded', b'UNIQUE-ISEGYE-PROBE-FIXTURE' not in request('isegye-idol.kr.example.invalid', '/' + probe)[1])
            check('owner marker blocked', request('isegye-idol.kr', '/.isegye-owner')[0] == 403)
            release = 'r123456abcdef'
            release_root = isegye / '_isegye_releases' / release
            (release_root / 'src').mkdir(parents=True)
            (release_root / 'index.html').write_bytes(b'ISEGYE-APPLICATION-FIXTURE')
            (release_root / 'src' / 'app.js').write_bytes(b'// ISEGYE-JS-FIXTURE')
            (isegye / '.htaccess').write_bytes(site_router(release))
            check('future active home', request('isegye-idol.kr') == (200, b'ISEGYE-APPLICATION-FIXTURE'))
            check('future active JS', request('isegye-idol.kr', '/src/app.js') == (200, b'// ISEGYE-JS-FIXTURE'))
            check('MIR files not served on ISEGYE', b'MIR-SITE-FIXTURE' not in request('isegye-idol.kr', '/_mir_site/index.html')[1])
            for host in ('mir.yeop.net', 'yeop.net'):
                check(host + ' unchanged after fixture activation', request(host) == baseline[host])
                check(host + ' cannot expose active ISEGYE', b'ISEGYE-APPLICATION-FIXTURE' not in request(host, f'/_isegye_idol/_isegye_releases/{release}/index.html')[1])
            (web / '.htaccess').write_bytes(MIR_BRIDGE)
            check('MIR band redirect after rollback', band_redirect() == (301, 'https://mir.yeop.net/band/'))
            check('rollback bytes match', (web / '.htaccess').read_bytes() == MIR_BRIDGE)
            check('rollback canonical result', request('isegye-idol.kr', '/' + probe)[0] == 404)
            for host in ('mir.yeop.net', 'yeop.net'):
                check(host + ' unchanged after rollback', request(host) == baseline[host])
        finally:
            process.terminate()
            process.wait(timeout=5)
        output = {'scope': 'local_apache_fixtures_only', 'live_server_changes': False,
                  'apache': subprocess.check_output([apache, '-v'], text=True).strip(),
                  'passed': sum(r['passed'] for r in results), 'total': len(results), 'tests': results,
                  'candidate_sha256': hashlib.sha256(BRIDGE).hexdigest()}
        out = ROOT / 'test-results'
        out.mkdir(exist_ok=True)
        (out / 'domain-bridge-local.json').write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n')
        print(json.dumps(output, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
