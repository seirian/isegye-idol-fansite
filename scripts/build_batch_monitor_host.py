#!/usr/bin/env python3
"""Build an isolated read-only administrator route; never alter the main source."""
from pathlib import Path
import hashlib, json, shutil
import build_playground_production_host as baseline
ROOT = Path(__file__).resolve().parents[1]
ANCHOR = "        if ($path === '/auth/google') {"
HOOK = """        // ISEGYE-BATCH-MONITOR: every asset and JSON uses the existing admin role.
        if ($path === '/ops/batches' || str_starts_with($path, '/ops/batches/')) {
            require_once $this->runtime.'/BatchMonitor.php';
            BatchMonitor::serve($this->root, $path, $access); return;
        }
"""

def patched(source):
    original = baseline.patched(source)
    if original.count(ANCHOR) != 1 or 'ISEGYE-BATCH-MONITOR' in original:
        raise ValueError('Existing gateway anchor changed')
    if original.index('$access = $this->store->access') >= original.index(ANCHOR):
        raise ValueError('Authorization must precede monitoring')
    return original.replace(ANCHOR, HOOK+ANCHOR, 1)


def main():
    baseline.main()
    out = ROOT/'auth-bundle'
    (out/'Gateway.php').write_text(patched((ROOT/'auth/Gateway.php').read_text()))
    (out/'BatchMonitor.php').write_bytes((ROOT/'monitoring/BatchMonitor.php').read_bytes())
    files = {p.relative_to(out).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
             for p in sorted(out.rglob('*')) if p.is_file() and p.name != 'manifest.json'}
    runtime = 'g'+hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()[:12]
    (out/'manifest.json').write_text(json.dumps({'runtime':runtime,'files':files,'active':False,'personalDataIncluded':False},indent=2)+'\n')
    dist = ROOT/'monitoring-dist'
    dist.mkdir(exist_ok=True)
    for name in ('index.html','monitor.css','monitor.js'):
        shutil.copyfile(ROOT/'monitoring'/name, dist/name)

if __name__ == '__main__':
    main()
