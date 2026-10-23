#!/usr/bin/env python3
"""Use the existing fixed-root deployment transaction with the v0.4 verifier."""
import json,os,subprocess,sys
from pathlib import Path
import production_release as release
import inour_sftp as d

def verify_live(commit):
    env=dict(os.environ,RELEASE_URL=d.ORIGIN+'/',RELEASE_MODE='production',
             RELEASE_OUT='test-results/production',GITHUB_SHA=commit)
    result=subprocess.run([sys.executable,'scripts/verify_release_v04.py'],env=env,
                          capture_output=True,text=True,timeout=900)
    out=Path('test-results/production');out.mkdir(parents=True,exist_ok=True)
    (out/'verification.log').write_text(result.stdout+result.stderr)
    d.require(result.returncode==0,'Production browser verification failed; previous release will be restored')
    summary=json.loads((out/'result.json').read_text())
    d.require(summary.get('status')=='verified' and summary.get('commit')==commit,'Incomplete production verification')

if __name__=='__main__':
    release.verify_live=verify_live
    sys.exit(release.main())
