#!/usr/bin/env python3
"""One-time import of public data from the exact reviewed Actions artifact."""
from pathlib import Path
import hashlib,json,shutil,sys
ROOT=Path(__file__).resolve().parents[1]
def main(source):
    meta=json.loads((source/'albums-dist/build-info.json').read_text())
    accepted='f2c00e2bb1f4a762e8ff1578f540584652d8053b'
    if meta.get('commit')!=accepted:raise ValueError('Not the owner-reviewed commit')
    raw=(source/'albums-dist/insights.json').read_bytes()
    if hashlib.sha256(raw).hexdigest()!='382f649ae240dd0d8df16121538c877ecce1dfa0505832b624853a04ce45d7a3':raise ValueError('Reviewed snapshot hash mismatch')
    data=json.loads(raw);out=ROOT/'albums/release-seed';out.mkdir(parents=True,exist_ok=True);(out/'snapshot.json').write_bytes(raw)
    (out/'asset-cache').mkdir(exist_ok=True)
    for group in data.get('assets',{}).values():
        for row in group.values():
            path=(source/row['path']).resolve()
            if not path.is_relative_to(source/'albums/asset-cache') or path.is_symlink():raise ValueError('Unsafe approved asset')
            content=path.read_bytes();sha=hashlib.sha256(content).hexdigest()
            if sha!=row['sha256'] or len(content)>180000:raise ValueError('Approved asset integrity failure')
            (out/'asset-cache'/path.name).write_bytes(content)
    files={p.relative_to(out).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.rglob('*')) if p.is_file() and p.name!='manifest.json'}
    (out/'manifest.json').write_text(json.dumps({'acceptedCommit':accepted,'artifactRun':42633213321,'files':files},indent=2)+'\n')
    print('Pinned public approved seed:',len(files),'files; no credentials')
if __name__=='__main__':main(Path(sys.argv[1]).resolve())
