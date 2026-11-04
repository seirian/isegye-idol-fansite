#!/usr/bin/env python3
"""Add one admin-only preview handler to a GENERATED auth bundle; sources untouched."""
from pathlib import Path
import hashlib, json
import build_auth_bundle as base

ROOT=Path(__file__).resolve().parents[1]
ANCHOR="        if ($path === '/api/history') {"
HOOK="""        // ISEGYE-REVIEW-1ST: after the unchanged account/maintenance gate.
        if ($path === '/review-1st' || str_starts_with($path, '/review-1st/')) {
            require_once $this->runtime.'/ReviewPreview.php';
            ReviewPreview::serve($this->root, $path, $access['role']); return;
        }
"""

def patched(source):
    if source.count(ANCHOR)!=1 or HOOK in source:raise ValueError('Gateway anchor changed')
    if source.index("if (!$access['allowed'])")>=source.index(ANCHOR):raise ValueError('Authorization must precede preview')
    return source.replace(ANCHOR,HOOK+ANCHOR,1)

def main():
    base.main()
    out=ROOT/'auth-bundle';original=(ROOT/'auth/Gateway.php').read_bytes()
    (out/'Gateway.php').write_text(patched(original.decode()))
    (out/'ReviewPreview.php').write_bytes((ROOT/'review-1st/hosting/ReviewPreview.php').read_bytes())
    files={p.relative_to(out).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.rglob('*')) if p.is_file() and p.name!='manifest.json'}
    runtime='g'+hashlib.sha256(json.dumps(files,sort_keys=True).encode()).hexdigest()[:12]
    (out/'manifest.json').write_text(json.dumps({'runtime':runtime,'files':files,'active':False,'personalDataIncluded':False},indent=2)+'\n')
    assert (ROOT/'auth/Gateway.php').read_bytes()==original
    print(json.dumps({'runtime':runtime,'previewRoute':'/review-1st/','requiresExistingAdministrator':True,'authSourcesChanged':False}))

if __name__=='__main__':main()
