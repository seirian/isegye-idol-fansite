#!/usr/bin/env python3
"""Add review-2nd after the unchanged gate; keep the first-review handler intact."""
from pathlib import Path
import hashlib,json
import build_review_host as first
ROOT=Path(__file__).resolve().parents[1]
ANCHOR=first.ANCHOR
HOOK="""        // ISEGYE-REVIEW-2ND: same existing administrator gate, independent preview.
        if ($path === '/review-2nd' || str_starts_with($path, '/review-2nd/')) {
            require_once $this->runtime.'/Review2Preview.php';
            Review2Preview::serve($this->root, $path, $access['role']); return;
        }
"""
def patched(source):
    return first.patched(source).replace(ANCHOR,HOOK+ANCHOR,1)
def main():
    first.main();out=ROOT/'auth-bundle'
    original=(ROOT/'auth/Gateway.php').read_text()
    (out/'Gateway.php').write_text(patched(original))
    (out/'Review2Preview.php').write_bytes((ROOT/'review-2nd/hosting/Review2Preview.php').read_bytes())
    files={p.relative_to(out).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.rglob('*')) if p.is_file() and p.name!='manifest.json'}
    runtime='g'+hashlib.sha256(json.dumps(files,sort_keys=True).encode()).hexdigest()[:12]
    (out/'manifest.json').write_text(json.dumps({'runtime':runtime,'files':files,'active':False,'personalDataIncluded':False},indent=2)+'\n')
    assert (ROOT/'auth/Gateway.php').read_text()==original
    assert (out/'ReviewPreview.php').read_bytes()==(ROOT/'review-1st/hosting/ReviewPreview.php').read_bytes()
    print(json.dumps({'runtime':runtime,'previewRoute':'/review-2nd/','firstReviewPreserved':True,'requiresExistingAdministrator':True}))
if __name__=='__main__':main()
