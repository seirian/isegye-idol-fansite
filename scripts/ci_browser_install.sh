#!/usr/bin/env bash
# Ephemeral Actions runner only. Preserve apt signature verification and all tests.
set -euo pipefail
if [[ "${GITHUB_ACTIONS:-}" == "true" ]]; then
  sudo python3 - <<'PY'
from pathlib import Path
import re
for name in ('/etc/apt/apt-mirrors.txt', '/etc/apt/sources.list.d/ubuntu.sources', '/etc/apt/sources.list'):
    path = Path(name)
    if not path.is_file():
        continue
    before = path.read_text()
    after = re.sub(r'https?://(?:azure|[a-z0-9-]+\.ec2)\.archive\.ubuntu\.com/ubuntu(?=[/\s]|$)',
                   'https://archive.ubuntu.com/ubuntu', before)
    if after != before:
        path.write_text(after)
print('Ubuntu archive mirror selected; package signature checks unchanged')
PY
fi
# Attempt a real Chromium launch using the pinned runner's existing libraries.
# Only fall back to signed apt dependencies when they are actually missing.
"$1" -m playwright install chromium
playwright_smoke() {
  "$1" - <<'PY'
from playwright.sync_api import sync_playwright
with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto("data:text/html,<title>isolated-browser-check</title>")
    assert page.title() == "isolated-browser-check"
    browser.close()
PY
}
if ! playwright_smoke "$1"; then
  echo "Chromium needs additional signed system dependencies" >&2
  "$1" -m playwright install-deps chromium
  playwright_smoke "$1"
fi
