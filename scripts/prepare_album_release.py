#!/usr/bin/env python3
"""Restore a checksum-pinned public approved seed; optional bounded refresh.
Never touches credentials, operating stores or collection schedules.
"""
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess,sys
ROOT=Path(__file__).resolve().parents[1]
def prepare(refresh=False):
    seed=ROOT/'albums/release-seed';manifest=json.loads((seed/'manifest.json').read_text())
    if manifest.get('acceptedCommit')!='f2c00e2bb1f4a762e8ff1578f540584652d8053b':raise ValueError('Unapproved album seed')
    for name,digest in manifest['files'].items():
        path=(seed/name).resolve()
        if not path.is_relative_to(seed) or path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest()!=digest:raise ValueError('Seed integrity failed')
    path=ROOT/'albums/snapshot.json';cache=ROOT/'albums/asset-cache';cache.mkdir(parents=True,exist_ok=True)
    if not path.exists():shutil.copyfile(seed/'snapshot.json',path)
    for file in (seed/'asset-cache').glob('*.webp'):
        dest=cache/file.name
        if not dest.exists():shutil.copyfile(file,dest)
    if refresh:
        # The existing collector preserves source identities, timestamps and last verified records.
        subprocess.run([sys.executable,str(ROOT/'scripts/refresh_album_review.py')],cwd=ROOT,check=True,timeout=480)
    return path
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--refresh',action='store_true');args=p.parse_args();prepare(args.refresh)
