#!/usr/bin/env python3
"""Generated gateway extension after unchanged access checks; no source auth edits."""
from pathlib import Path
import hashlib,json
import build_review_2nd_host as previous
ROOT=Path(__file__).resolve().parents[1]
HOOK="""        // ISEGYE-ALBUMS-REVIEW: existing administrator gate; isolated files and API.
        if ($path === '/review-albums' || str_starts_with($path, '/review-albums/')) {
            require_once $this->runtime.'/AlbumsPreview.php';
            AlbumsPreview::serve($this->root, $path, $access['role']); return;
        }
"""
def patched(source):
    return previous.patched(source).replace(previous.ANCHOR,HOOK+previous.ANCHOR,1)
def main():
    previous.main();out=ROOT/'auth-bundle';original=(ROOT/'auth/Gateway.php').read_text()
    (out/'Gateway.php').write_text(patched(original))
    (out/'AlbumsPreview.php').write_bytes((ROOT/'albums/hosting/AlbumsPreview.php').read_bytes())
    files={p.relative_to(out).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.rglob('*')) if p.is_file() and p.name!='manifest.json'}
    runtime='g'+hashlib.sha256(json.dumps(files,sort_keys=True).encode()).hexdigest()[:12]
    (out/'manifest.json').write_text(json.dumps({'runtime':runtime,'files':files,'active':False,'personalDataIncluded':False},indent=2)+'\n')
    assert (ROOT/'auth/Gateway.php').read_text()==original
    print(json.dumps({'runtime':runtime,'route':'/review-albums/','api':'/review-albums/api/insights','existingAccessGatePreserved':True}))
if __name__=='__main__':main()
