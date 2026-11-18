#!/usr/bin/env python3
"""Build an isolated read-only administrator route; never alter the main source."""
from pathlib import Path
import hashlib, json, shutil
import build_playground_production_host as baseline
ROOT = Path(__file__).resolve().parents[1]
ANCHOR = "        if ($path === '/auth/google') {"
LEGACY_HOOK = """        // ISEGYE-BATCH-MONITOR: every asset and JSON uses the existing admin role.
        if ($path === '/ops/batches' || str_starts_with($path, '/ops/batches/')) {
            require_once $this->runtime.'/BatchMonitor.php';
            BatchMonitor::serve($this->root, $path, $access); return;
        }
"""
HOOK = LEGACY_HOOK + """        // Fixed login context: shared UI, existing CSRF, no arbitrary next URL.
        if (in_array($path, ['/auth/login','/auth/logout'], true) && ($_GET['notice'] ?? null) === 'batch-admin') {
            require_once $this->runtime.'/BatchMonitor.php';
            if ($path === '/auth/logout') { BatchMonitor::switchAccount($this->config['origin']); return; }
            if (!in_array($method, ['GET','HEAD'], true)) { self::respond(405, 'Method not allowed', 'text/plain'); return; }
            BatchMonitor::login($access, $this->config['clientId'], $access['role'] === null ? Session::issueNonce() : '', Session::csrf()); return;
        }
"""

def previous_patched(source):
    original = baseline.patched(source)
    if original.count(ANCHOR) != 1:
        raise ValueError('Existing gateway anchor changed')
    return original.replace(ANCHOR, LEGACY_HOOK+ANCHOR, 1)


def readonly_patched(source):
    original = baseline.patched(source)
    if original.count(ANCHOR) != 1 or 'ISEGYE-BATCH-MONITOR' in original:
        raise ValueError('Existing gateway anchor changed')
    if original.index('$access = $this->store->access') >= original.index(ANCHOR):
        raise ValueError('Authorization must precede monitoring')
    return original.replace(ANCHOR, HOOK+ANCHOR, 1)


MANUAL_HOOK = """        // Separate capability worker and live-session administrator controls.
        if ($path === '/ops/batches/_agent') {
            require_once $this->runtime.'/BatchManual.php';
            BatchManual::agent($this->root, fn($id) => $this->store->access($id)); return;
        }
        if (in_array($path, ['/ops/batches/control','/ops/batches/manual.js','/ops/batches/manual.css'], true)) {
            require_once $this->runtime.'/BatchManual.php';
            BatchManual::serve($this->root, $path, $access, $this->config['origin']); return;
        }
"""

def patched(source):
    original = readonly_patched(source)
    if original.count(LEGACY_HOOK) != 1:
        raise ValueError('Read-only monitor anchor changed')
    return original.replace(LEGACY_HOOK, MANUAL_HOOK+LEGACY_HOOK, 1)


def main():
    baseline.main()
    out = ROOT/'auth-bundle'
    (out/'Gateway.php').write_text(patched((ROOT/'auth/Gateway.php').read_text()))
    (out/'BatchMonitor.php').write_bytes((ROOT/'monitoring/BatchMonitor.php').read_bytes())
    for name in ('BatchManual.php','manual.js','manual.css'):
        (out/name).write_bytes((ROOT/'monitoring'/name).read_bytes())
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
