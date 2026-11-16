#!/usr/bin/env python3
"""Preserve all current preview routes; add only the normal-reader quiz-bank API."""
from pathlib import Path
import json,hashlib
import build_playground_host as preview
ROOT=Path(__file__).resolve().parents[1]
HOOK="""        // ISEGYE-PLAYGROUND-BANK: regular reader endpoint after the existing gate.
        if ($path === '/api/playground') {
            require_once $this->runtime.'/PlaygroundBank.php';
            PlaygroundBank::serve($this->root, $this->release()); return;
        }
"""
def patched(s):
    base=preview.patched(s);anchor=preview.ANCHOR
    if base.count(anchor)!=1 or base.index("if (!$access['allowed'])")>base.index(anchor):raise ValueError('Existing gate moved')
    return base.replace(anchor,HOOK+anchor,1)
def main():
    preview.main();out=ROOT/'auth-bundle'
    (out/'Gateway.php').write_text(patched((ROOT/'auth/Gateway.php').read_text()))
    (out/'PlaygroundBank.php').write_bytes((ROOT/'playground/hosting/PlaygroundBank.php').read_bytes())
    files={p.relative_to(out).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.rglob('*')) if p.is_file() and p.name!='manifest.json'}
    runtime='g'+hashlib.sha256(json.dumps(files,sort_keys=True).encode()).hexdigest()[:12]
    (out/'manifest.json').write_text(json.dumps({'runtime':runtime,'files':files,'active':False,'personalDataIncluded':False},indent=2)+'\n')
if __name__=='__main__':main()
