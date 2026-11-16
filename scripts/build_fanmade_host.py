#!/usr/bin/env python3
"""Append the isolated user-experience preview after the unchanged access gate."""
from pathlib import Path
import hashlib,json
import build_albums_host as previous
ROOT=Path(__file__).resolve().parents[1]
ANCHOR=previous.previous.ANCHOR
HOOK="""        // ISEGYE-FANMADE: review access only; content is ordinary visitor UI.
        if ($path === '/review-fanmade' || str_starts_with($path, '/review-fanmade/')) {
            require_once $this->runtime.'/FanmadePreview.php';
            FanmadePreview::serve($this->root, $path, $access['role']); return;
        }
"""
def patched(source):
    base=previous.patched(source)
    if base.count(ANCHOR)!=1 or 'ISEGYE-FANMADE' in base:raise ValueError('Unexpected gateway')
    if base.index("if (!$access['allowed'])")>=base.index(ANCHOR):raise ValueError('Gate must precede preview')
    return base.replace(ANCHOR,HOOK+ANCHOR,1)
def main():
    previous.main();out=ROOT/'auth-bundle';original=(ROOT/'auth/Gateway.php').read_bytes()
    (out/'Gateway.php').write_text(patched(original.decode()))
    (out/'FanmadePreview.php').write_bytes((ROOT/'fanmade/hosting/FanmadePreview.php').read_bytes())
    files={p.relative_to(out).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.rglob('*')) if p.is_file() and p.name!='manifest.json'}
    runtime='g'+hashlib.sha256(json.dumps(files,sort_keys=True).encode()).hexdigest()[:12]
    (out/'manifest.json').write_text(json.dumps({'runtime':runtime,'files':files,'active':False,'personalDataIncluded':False},indent=2)+'\n')
    assert (ROOT/'auth/Gateway.php').read_bytes()==original
if __name__=='__main__':main()
