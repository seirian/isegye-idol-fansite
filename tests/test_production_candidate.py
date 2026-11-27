from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import production_candidate as candidate


class ProductionCandidateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.src, self.dst = self.root/'source', self.root/'destination'
        self.src.mkdir(); self.dst.mkdir()
        self.env = {'GITHUB_REPOSITORY': candidate.REPO, 'GITHUB_REF':'refs/heads/main',
                    'GITHUB_SHA':'a'*40, 'GITHUB_RUN_ID':'1234', 'GITHUB_RUN_ATTEMPT':'1'}
        self.at = datetime(2026,11,27,12,tzinfo=timezone.utc)
        files = {'dist/index.html':b'<html>verified</html>', 'dist/src/app.js':b'verified()',
                 'dist/build-info.json':json.dumps({'mode':'production','commit':'a'*40}).encode(),
                 'auth-bundle/manifest.json':b'{}', **{name:b'{}' for name in candidate.REPORTS}}
        for name, raw in files.items():
            path = self.src/name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(raw)
        self.archive = self.root/'candidate.tar.gz'
        self.packed = candidate.pack(self.src,self.archive,self.env,self.at)

    def unpack(self, **kwargs):
        return candidate.unpack(kwargs.get('root',self.dst),self.archive,
                                kwargs.get('digest',self.packed['sha256']),kwargs.get('attempt',1),
                                kwargs.get('env',self.env),kwargs.get('now',self.at))

    def rewrite(self, transform):
        with tarfile.open(self.archive,'r:gz') as archive:
            contents = [(item,archive.extractfile(item).read()) for item in archive]
        contents = transform(contents)
        with tarfile.open(self.archive,'w:gz') as archive:
            for item,raw in contents:
                item.size = len(raw)
                archive.addfile(item,io.BytesIO(raw))
        self.packed['sha256'] = candidate.digest(self.archive.read_bytes())

    def test_exact_round_trip(self):
        result = self.unpack()
        self.assertEqual(result['status'],'candidate_verified')
        self.assertEqual((self.dst/'dist/src/app.js').read_bytes(),b'verified()')

    def test_previous_prepare_attempt_only_with_explicit_binding(self):
        env = dict(self.env,GITHUB_RUN_ATTEMPT='2')
        self.assertEqual(self.unpack(env=env,attempt=1)['prepareAttempt'],1)
        with self.assertRaises(ValueError): self.unpack(env=env,attempt=2)
        with self.assertRaises(ValueError): self.unpack(attempt=2)

    def test_digest_run_ref_and_commit_are_required(self):
        for changes in ({'GITHUB_RUN_ID':'1235'},{'GITHUB_SHA':'b'*40},
                        {'GITHUB_REF':'refs/heads/develop'},{'GITHUB_REPOSITORY':'other/repository'}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.unpack(env=dict(self.env,**changes))
        with self.assertRaises(ValueError): self.unpack(digest='0'*64)
        self.assertEqual(list(self.dst.iterdir()),[])

    def test_expired_and_future_candidate_are_rejected(self):
        for at in (self.at+timedelta(hours=25),self.at-timedelta(minutes=3)):
            with self.assertRaises(ValueError): self.unpack(now=at)

    def test_no_partial_write_on_member_hash_mismatch(self):
        self.rewrite(lambda items:[(item,b'changed' if item.name=='dist/src/app.js' else raw)
                                   for item,raw in items])
        with self.assertRaises(ValueError): self.unpack()
        self.assertEqual(list(self.dst.iterdir()),[])

    def test_unsafe_tar_paths_and_link_types_cannot_escape(self):
        original = self.archive.read_bytes()
        for name, kind in (('../escaped',tarfile.REGTYPE),('scripts/production_lock.py',tarfile.REGTYPE),
                           ('/absolute',tarfile.REGTYPE),('dist/linked',tarfile.SYMTYPE),
                           ('dist/hardlinked',tarfile.LNKTYPE)):
            self.archive.write_bytes(original)
            item=tarfile.TarInfo(name); item.type=kind; item.linkname='../escape'
            self.rewrite(lambda items: items+[(item,b'')])
            with self.subTest(name=name), self.assertRaises(ValueError): self.unpack()
            self.assertEqual(list(self.dst.iterdir()),[])

    def test_duplicate_manifest_and_extra_file_are_rejected(self):
        original = self.archive.read_bytes()
        self.rewrite(lambda items:items+[items[0]])
        with self.assertRaises(ValueError): self.unpack()
        self.archive.write_bytes(original)
        item=tarfile.TarInfo('dist/unverified.js')
        self.rewrite(lambda items:items+[(item,b'extra')])
        with self.assertRaises(ValueError): self.unpack()

    def test_existing_extra_content_is_not_silently_accepted(self):
        (self.dst/'dist').mkdir()
        (self.dst/'dist/stale.js').write_text('stale')
        with self.assertRaises(ValueError): self.unpack()
        self.assertFalse((self.dst/'dist/index.html').exists())

    def test_destination_symlink_and_candidate_symlink_are_rejected(self):
        outside=self.root/'outside'; outside.mkdir()
        (self.dst/'dist').symlink_to(outside,target_is_directory=True)
        with self.assertRaises(ValueError): self.unpack()
        self.assertEqual(list(outside.iterdir()),[])
        (self.src/'auth-bundle/leak').symlink_to(self.src/'dist/index.html')
        with self.assertRaises(ValueError): candidate.pack(self.src,self.archive,self.env,self.at)


if __name__ == '__main__':
    unittest.main()
