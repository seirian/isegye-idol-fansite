#!/usr/bin/env python3
"""Transfer an exact, credential-free candidate between jobs of one main run.

No network, credentials, repository source replacement, or remote writes. The
producer's archive digest is an explicit job output, not a value trusted from
inside the downloaded archive. Every member is checked before any extraction.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import tarfile

REPO = 'seirian/isegye-idol-fansite'
MANIFEST = 'production-candidate.json'
DIRECTORIES = ('dist', 'auth-bundle')
REPORTS = ('catalog-publication.json', 'test-results/music-sources/source-audit.json',
           'test-results/music-sources/source-availability.json')
MAX_BYTES = 320_000_000
MAX_FILE = 16_000_000
MAX_MEMBERS = 6000


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def allowed(name):
    return (isinstance(name, str) and re.fullmatch(r'[A-Za-z0-9_.@+/-]+', name) is not None
            and str(PurePosixPath(name)) == name and not name.startswith('/')
            and all(p not in ('', '.', '..') for p in name.split('/'))
            and (name in REPORTS or any(name.startswith(d+'/') for d in DIRECTORIES)))


def identity(environ=None, source_attempt=None):
    env = os.environ if environ is None else environ
    require(env.get('GITHUB_REPOSITORY') == REPO, 'Unexpected repository')
    require(env.get('GITHUB_REF') == 'refs/heads/main', 'Production main required')
    commit = env.get('GITHUB_SHA', '')
    run = env.get('GITHUB_RUN_ID', '')
    attempt = env.get('GITHUB_RUN_ATTEMPT', '')
    require(re.fullmatch('[0-9a-f]{40}', commit) is not None, 'Full source commit required')
    require(re.fullmatch('[1-9][0-9]*', run) is not None, 'Run ID required')
    require(re.fullmatch('[1-9][0-9]*', attempt) is not None, 'Run attempt required')
    selected = str(source_attempt) if source_attempt is not None else attempt
    require(re.fullmatch('[1-9][0-9]*', selected) is not None and int(selected) <= int(attempt),
            'Invalid producer attempt')
    return {'repository':REPO, 'commit':commit, 'runId':int(run), 'prepareAttempt':int(selected)}


def pack(root, archive, environ=None, now=None):
    root, archive = Path(root), Path(archive)
    ident = identity(environ)
    files = {}
    for directory in DIRECTORIES:
        folder = root/directory
        require(folder.is_dir() and not folder.is_symlink(), 'Missing candidate directory')
        for path in sorted(folder.rglob('*')):
            require(not path.is_symlink(), 'Candidate symlink rejected')
            if path.is_dir():
                continue
            name = path.relative_to(root).as_posix()
            require(allowed(name) and path.is_file(), 'Unexpected candidate path')
            files[name] = path.read_bytes()
    for name in REPORTS:
        path = root/name
        require(path.is_file() and not path.is_symlink(), 'Missing verified candidate report')
        files[name] = path.read_bytes()
    require({'dist/index.html','dist/build-info.json','dist/src/app.js',
             'auth-bundle/manifest.json'} <= files.keys(), 'Incomplete candidate')
    build = json.loads(files['dist/build-info.json'])
    require(build.get('mode') == 'production' and build.get('commit') == ident['commit'],
            'Candidate build identity mismatch')
    require(len(files) <= MAX_MEMBERS and sum(map(len, files.values())) <= MAX_BYTES
            and all(len(raw) <= MAX_FILE for raw in files.values()), 'Candidate exceeds bounds')
    manifest = {'schemaVersion':1, **ident,
                'preparedAt':(now or datetime.now(timezone.utc)).isoformat(),
                'files':{name:{'sha256':digest(raw),'bytes':len(raw)} for name,raw in files.items()}}
    raw_manifest = (json.dumps(manifest, sort_keys=True, separators=(',',':'))+'\n').encode()
    archive.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, 'w:gz', format=tarfile.PAX_FORMAT) as out:
        for name, raw in [(MANIFEST,raw_manifest), *sorted(files.items())]:
            item = tarfile.TarInfo(name)
            item.size, item.mode, item.mtime = len(raw), 0o644, 0
            out.addfile(item, io.BytesIO(raw))
    return {**ident, 'sha256':digest(archive.read_bytes()), 'files':len(files),
            'bytes':sum(map(len,files.values()))}


def unpack(root, archive, expected_digest, source_attempt, environ=None, now=None):
    root, archive = Path(root), Path(archive)
    ident = identity(environ, source_attempt)
    require(re.fullmatch('[0-9a-f]{64}', expected_digest or '') is not None, 'Trusted archive digest required')
    require(archive.is_file() and not archive.is_symlink() and archive.stat().st_size <= MAX_BYTES,
            'Invalid candidate archive')
    raw = archive.read_bytes()
    require(digest(raw) == expected_digest, 'Candidate archive digest mismatch')
    files, total = {}, 0
    with tarfile.open(fileobj=io.BytesIO(raw), mode='r:gz') as bundle:
        for member in bundle:
            require(len(files) <= MAX_MEMBERS and member.isfile() and not member.issym()
                    and not member.islnk() and member.name not in files
                    and (member.name == MANIFEST or allowed(member.name)), 'Unsafe candidate member')
            require(0 <= member.size <= MAX_FILE, 'Candidate member exceeds bounds')
            total += member.size
            require(total <= MAX_BYTES, 'Candidate expansion exceeds bounds')
            data = bundle.extractfile(member).read(member.size+1)
            require(len(data) == member.size, 'Candidate member size mismatch')
            files[member.name] = data
    require(MANIFEST in files, 'Candidate manifest missing')
    manifest = json.loads(files.pop(MANIFEST))
    require(manifest.get('schemaVersion') == 1 and all(manifest.get(k) == v for k,v in ident.items()),
            'Candidate run/attempt/source mismatch')
    prepared = datetime.fromisoformat(manifest['preparedAt'])
    at = now or datetime.now(timezone.utc)
    require(prepared.tzinfo is not None and at-timedelta(hours=24) <= prepared <= at+timedelta(minutes=2),
            'Candidate is stale or future dated')
    listed = manifest.get('files')
    require(isinstance(listed,dict) and set(listed) == set(files), 'Candidate membership mismatch')
    require(all(isinstance(listed[n],dict) and listed[n].get('sha256') == digest(b)
                and listed[n].get('bytes') == len(b) for n,b in files.items()), 'Candidate file mismatch')
    require(set(REPORTS) | {'dist/index.html','dist/build-info.json','dist/src/app.js',
                           'auth-bundle/manifest.json'} <= files.keys(), 'Candidate files missing')
    build = json.loads(files['dist/build-info.json'])
    require(build.get('mode') == 'production' and build.get('commit') == ident['commit'],
            'Candidate source identity mismatch')
    for directory in DIRECTORIES:
        folder = root/directory
        require(not folder.is_symlink(), 'Destination directory symlink rejected')
        if folder.exists():
            require(folder.is_dir(), 'Unexpected destination directory')
            for path in folder.rglob('*'):
                require(not path.is_symlink() and (path.is_dir() or
                        path.relative_to(root).as_posix() in files),
                        'Unverified destination content rejected')
    # Validate every destination before writing; never extract a tar into the repo.
    for name in files:
        path = root/name
        require(not path.is_symlink(), 'Destination symlink rejected')
        for parent in path.parents:
            if parent == root:
                break
            require(not parent.is_symlink(), 'Destination parent symlink rejected')
        require(not path.exists() or path.is_file(), 'Unexpected candidate destination')
    for name, content in files.items():
        path = root/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    return {'status':'candidate_verified', **ident, 'files':len(files), 'archiveSha256':expected_digest}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('pack','unpack'))
    parser.add_argument('--archive', default='production-candidate.tar.gz')
    parser.add_argument('--sha256')
    parser.add_argument('--source-attempt', type=int)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if args.action == 'pack':
        result = pack(root,args.archive)
        if os.getenv('GITHUB_OUTPUT'):
            with open(os.environ['GITHUB_OUTPUT'],'a') as out:
                out.write('sha256='+result['sha256']+'\nattempt='+str(result['prepareAttempt'])+'\n')
    else:
        result = unpack(root,args.archive,args.sha256,args.source_attempt)
        result['consumerAttempt'] = int(os.environ['GITHUB_RUN_ATTEMPT'])
        (root/'production-candidate-verified.json').write_text(json.dumps(result, sort_keys=True)+'\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
