"""Local Apache routing test; never connects to the hosting provider."""
import importlib.util
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import time
import urllib.error
import urllib.request

spec = importlib.util.spec_from_file_location('inour', Path(__file__).resolve().parents[1] / 'scripts/inour_sftp.py')
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)
with tempfile.TemporaryDirectory(prefix='isegye-routing-') as work:
    root = Path(work)
    root.chmod(0o755)
    dirs = {name: root / name for name in ('_isegye_idol', '_mir_site', 'personal')}
    for path in dirs.values(): path.mkdir(mode=0o755)
    site = dirs['_isegye_idol']
    rid = 'r0123456789ab'
    release = site / '_isegye_releases' / rid
    (release / 'src').mkdir(parents=True)
    (release / 'index.html').write_text('ISEGYE HOME')
    (release / 'src/app.js').write_text('window.isegye=true;')
    (release / 'src/styles.css').write_text('body{}')
    (site / '.isegye-owner').write_bytes(d.OWNER)
    (site / 'isegye-probe-abcdef.txt').write_text('probe')
    (site / '.htaccess').write_bytes(d.router())
    (dirs['_mir_site'] / 'index.html').write_text('MIR UNCHANGED')
    (dirs['personal'] / 'index.html').write_text('PERSONAL UNCHANGED')
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    config = [f'ServerRoot "{root}"', f'PidFile "{root}/apache.pid"', f'Listen 127.0.0.1:{port}',
              'ServerName localhost', f'ErrorLog "{root}/error.log"', 'LogLevel warn']
    for mod in ('mpm_event', 'authz_core', 'authz_host', 'dir', 'mime', 'rewrite'):
        config.append(f'LoadModule {mod}_module /usr/lib/apache2/modules/mod_{mod}.so')
    if os.geteuid() == 0: config += ['User www-data', 'Group www-data']
    config += ['TypesConfig /etc/mime.types', 'DirectoryIndex index.html',
               f'<Directory "{root}">', 'Require all granted', 'AllowOverride All', 'Options FollowSymLinks', '</Directory>']
    for host, folder in [('yeop.net', 'personal'), ('mir.yeop.net', '_mir_site'), ('isegye-idol.kr', '_isegye_idol')]:
        config += [f'<VirtualHost 127.0.0.1:{port}>', f'ServerName {host}', f'DocumentRoot "{dirs[folder]}"', '</VirtualHost>']
    conf = root / 'httpd.conf'
    conf.write_text('\n'.join(config) + '\n')
    def get(host, path='/'):
        request = urllib.request.Request(f'http://127.0.0.1:{port}' + path, headers={'Host': host})
        try: response = urllib.request.urlopen(request, timeout=3)
        except urllib.error.HTTPError as exc: response = exc
        with response: return response.status, response.read(), response.headers.get('Content-Type', '')
    process = subprocess.Popen(['apache2', '-f', str(conf), '-X'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        for attempt in range(30):
            try:
                get('yeop.net')
                break
            except (ConnectionError, urllib.error.URLError): time.sleep(0.1)
        assert get('isegye-idol.kr')[0] == 503
        assert get('isegye-idol.kr', '/isegye-probe-abcdef.txt')[:2] == (200, b'probe')
        (site / '.htaccess').write_bytes(d.router(rid))
        assert get('isegye-idol.kr')[:2] == (200, b'ISEGYE HOME')
        assert get('isegye-idol.kr', '/src/app.js')[:2] == (200, b'window.isegye=true;')
        assert get('isegye-idol.kr', '/src/styles.css')[2].startswith('text/css')
        assert get('isegye-idol.kr', '/.isegye-owner')[0] == 403
        assert get('isegye-idol.kr', '/_isegye_releases/' + rid + '/index.html')[:2] == (200, b'ISEGYE HOME')
        assert get('mir.yeop.net')[:2] == (200, b'MIR UNCHANGED')
        assert get('yeop.net')[:2] == (200, b'PERSONAL UNCHANGED')
        assert get('mir.yeop.net', '/_isegye_idol/isegye-probe-abcdef.txt')[0] == 404
        assert get('yeop.net', '/_isegye_idol/isegye-probe-abcdef.txt')[0] == 404
        assert get('isegye-idol.kr', '/not-a-real-route')[0] == 404
        print('PASS: 12 local Apache routing assertions; independent roots, host routing, hidden files and assets.')
    except Exception:
        print((root / 'error.log').read_text() if (root / 'error.log').exists() else process.stderr.read().decode())
        raise
    finally:
        process.terminate()
        process.wait(timeout=10)
