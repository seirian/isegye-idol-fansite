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
"$1" -m playwright install --with-deps chromium
