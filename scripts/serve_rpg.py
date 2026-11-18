#!/usr/bin/env python3
"""Open the local RPG at its stable save origin, never an arbitrary new port."""
import argparse
import hashlib
import http.server
from pathlib import Path
import subprocess
import sys
import urllib.error
import urllib.request
import webbrowser

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / 'rpg-dist'
URL = 'http://127.0.0.1:4177/'


def main():
    parser = argparse.ArgumentParser(description='이파리 연대기 로컬 실행')
    parser.add_argument('--no-open', action='store_true', help='브라우저를 자동으로 열지 않음')
    args = parser.parse_args()
    if not (DIST / 'index.html').exists():
        subprocess.run([sys.executable, str(ROOT / 'scripts/build_rpg.py')], cwd=ROOT, check=True)
    expected = hashlib.sha256((DIST / 'index.html').read_bytes()).hexdigest()
    # Reuse only our identical game. Never kill another process or silently
    # choose a new origin, which would appear to lose the player's save.
    try:
        with urllib.request.urlopen(URL, timeout=2) as response:
            existing = response.read(8 * 1024 * 1024 + 1)
        if hashlib.sha256(existing).hexdigest() != expected:
            print('4177번 주소가 다른 파일을 제공하고 있습니다. 기존 서버를 확인한 뒤 다시 실행해 주세요.', file=sys.stderr)
            return 1
        print('실행 중인 게임을 엽니다: ' + URL, flush=True)
        if not args.no_open:
            webbrowser.open(URL)
        return 0
    except urllib.error.HTTPError:
        print('4177번 주소에서 다른 서버가 응답했습니다. 기존 서버를 확인해 주세요.', file=sys.stderr)
        return 1
    except (urllib.error.URLError, TimeoutError, OSError):
        pass

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=str(DIST), **kw)

    try:
        server = http.server.ThreadingHTTPServer(('127.0.0.1', 4177), Handler)
    except OSError as error:
        print('로컬 게임 주소를 열 수 없습니다: ' + str(error), file=sys.stderr)
        return 1
    print('이파리 연대기: ' + URL + '\n기존에 플레이한 브라우저를 사용하세요. 종료: Control+C 또는 이 창 닫기.', flush=True)
    if not args.no_open:
        webbrowser.open(URL)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
