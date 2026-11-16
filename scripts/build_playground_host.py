#!/usr/bin/env python3
"""Append the isolated user-experience preview after the unchanged access gate."""
from pathlib import Path
import hashlib,json
import build_albums_host as previous
ROOT=Path(__file__).resolve().parents[1]
ANCHOR=previous.previous.ANCHOR
HOOK="""        // ISEGYE-PLAYGROUND: review access only; content is ordinary visitor UI.
        if ($path === '/review-playground' || str_starts_with($path, '/review-playground/')) {
            require_once $this->runtime.'/PlaygroundPreview.php';
            PlaygroundPreview::serve($this->root, $path, $access['role']); return;
        }
"""
FANMADE_HOOK = "        // ISEGYE-FANMADE: review access only; content is ordinary visitor UI.\n        if ($path === '/review-fanmade' || str_starts_with($path, '/review-fanmade/')) {\n            require_once $this->runtime.'/FanmadePreview.php';\n            FanmadePreview::serve($this->root, $path, $access['role']); return;\n        }\n"
def baseline_patched(source):
    base=previous.patched(source)
    if base.count(ANCHOR)!=1:raise ValueError('Existing gateway anchor moved')
    return base.replace(ANCHOR,FANMADE_HOOK+ANCHOR,1)
def patched(source):
    base=baseline_patched(source)
    if base.count(ANCHOR)!=1 or 'ISEGYE-PLAYGROUND' in base:raise ValueError('Unexpected gateway')
    if base.index("if (!$access['allowed'])")>=base.index(ANCHOR):raise ValueError('Gate must precede preview')
    return base.replace(ANCHOR,HOOK+ANCHOR,1)
def main():
    previous.main();out=ROOT/'auth-bundle';original=(ROOT/'auth/Gateway.php').read_bytes()
    (out/'Gateway.php').write_text(patched(original.decode()))
    retained=(ROOT/'playground/hosting/FanmadePreview.php').read_bytes()
    assert hashlib.sha256(retained).hexdigest()=='9299e11fa0624bd992cd74fc66a859c8c0a3ab558a8e67f5b170f2b22fec8be7'
    (out/'FanmadePreview.php').write_bytes(retained)
    (out/'PlaygroundPreview.php').write_bytes((ROOT/'playground/hosting/PlaygroundPreview.php').read_bytes())
    files={p.relative_to(out).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.rglob('*')) if p.is_file() and p.name!='manifest.json'}
    runtime='g'+hashlib.sha256(json.dumps(files,sort_keys=True).encode()).hexdigest()[:12]
    (out/'manifest.json').write_text(json.dumps({'runtime':runtime,'files':files,'active':False,'personalDataIncluded':False},indent=2)+'\n')
    assert (ROOT/'auth/Gateway.php').read_bytes()==original
if __name__=='__main__':main()
