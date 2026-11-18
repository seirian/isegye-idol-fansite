#!/usr/bin/env python3
"""Preserve existing gates and previews; serve the quiz bank and approved game."""
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
    base=base.replace(anchor,HOOK+anchor,1)
    # This exact document uses the same allowed-reader check as every site asset.
    # No public router, iframe exception, new role or broad HTML glob is added.
    changes={
        "        $relative = ltrim($path, '/');": """        // ISEGYE-COURIER: canonical standalone game after the existing access gate.
        if ($path === '/games/starlight-courier') {
            header('Location: /games/starlight-courier/', true, 308); return;
        }
        $relative = $path === '/games/starlight-courier/'
            ? 'games/starlight-courier/index.html' : ltrim($path, '/');""",
        "['index.html','robots.txt','build-info.json']": "['index.html','robots.txt','build-info.json','games/starlight-courier/index.html']",
        "$mime = ['js'=>": "$mime = ['html'=>'text/html; charset=utf-8','js'=>",
    }
    for old,new in changes.items():
        if base.count(old)!=1:raise ValueError('Courier static serving anchor changed')
        base=base.replace(old,new,1)
    if base.index("if (!$access['allowed'])")>=base.index('// ISEGYE-COURIER:'):
        raise ValueError('Access gate must precede standalone game')
    return base
def main():
    preview.main();out=ROOT/'auth-bundle'
    (out/'Gateway.php').write_text(patched((ROOT/'auth/Gateway.php').read_text()))
    (out/'PlaygroundBank.php').write_bytes((ROOT/'playground/hosting/PlaygroundBank.php').read_bytes())
    files={p.relative_to(out).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.rglob('*')) if p.is_file() and p.name!='manifest.json'}
    runtime='g'+hashlib.sha256(json.dumps(files,sort_keys=True).encode()).hexdigest()[:12]
    (out/'manifest.json').write_text(json.dumps({'runtime':runtime,'files':files,'active':False,'personalDataIncluded':False},indent=2)+'\n')
if __name__=='__main__':main()
