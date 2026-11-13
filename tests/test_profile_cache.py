"""Regression: approved static portraits never depend on remote image hosts."""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import prepare_genie_portraits as genie
import home_soop_profiles as soop
import profile_cache as cache

class Profiles(unittest.TestCase):
    def rows(self):
        return soop.validate(json.loads((ROOT/'home-review/soop-profiles.json').read_text()))
    def test_genie_offline_matches_original_approved_hashes(self):
        with patch.object(genie, 'download', side_effect=AssertionError('No image network')):
            genie.main()
        for row in genie.validate_manifest(json.loads((ROOT/'review/portraits.json').read_text())):
            self.assertEqual(hashlib.sha256((ROOT/row['file']).read_bytes()).hexdigest(), row['sha256'])
    def test_missing_genie_cache_fails_without_network(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); (root/'review').mkdir()
            shutil.copy2(ROOT/'review/portraits.json',root/'review/portraits.json')
            with patch.object(genie,'ROOT',root), patch.object(genie,'download',side_effect=AssertionError('No network')):
                with self.assertRaisesRegex(ValueError,'cache missing'): genie.main()
    def test_corrupt_genie_cache_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'review/portraits').mkdir(parents=True)
            shutil.copy2(ROOT/'review/portraits.json',root/'review/portraits.json')
            (root/'review/portraits/ine.webp').write_bytes(b'changed')
            with patch.object(genie,'ROOT',root):
                with self.assertRaisesRegex(ValueError,'Unexpected existing'):genie.main()
    def test_soop_build_is_offline_and_exact(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(soop,'download',side_effect=AssertionError('No network')):
            result=soop.build(folder)
            self.assertEqual(set(result),set(cache.MEMBERS))
            for row in self.rows():
                self.assertEqual((Path(folder)/'assets/soop-profiles'/(row['id']+'.webp')).read_bytes(),cache.load_soop(row))
    def test_soop_changed_identity_and_timestamp_rejected(self):
        for key,value in [('id','../secret'),('channel','other'),('sourceImage','https://evil.invalid/x'),('sourceSha256','0'*64),('checkedAt','2026-11-14T00:00:00Z')]:
            row=copy.deepcopy(self.rows()[0]);row[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):cache.load_soop(row)
    def test_soop_corruption_and_symlinks_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'home-review/soop-cache').mkdir(parents=True)
            shutil.copy2(ROOT/'home-review/soop-cache.json',root/'home-review/soop-cache.json')
            p=root/'home-review/soop-cache/ine.webp';p.write_bytes(b'corrupt')
            with patch.object(cache,'ROOT',root):
                with self.assertRaisesRegex(ValueError,'digest mismatch'):cache.load_soop(self.rows()[0])
                p.unlink();p.symlink_to(ROOT/'home-review/soop-cache/ine.webp')
                with self.assertRaisesRegex(ValueError,'symlink'):cache.load_soop(self.rows()[0])
    def test_approval_pins_exact_cache_and_code(self):
        pins=json.loads((ROOT/'review/home-release.json').read_text())['sourceHashes']
        paths=['scripts/profile_cache.py','scripts/home_soop_profiles.py','scripts/prepare_genie_portraits.py','home-review/soop-cache.json']
        paths += [p+ident+'.webp' for p in ('review/portraits/','home-review/soop-cache/') for ident in sorted(cache.MEMBERS)]
        for path in paths:self.assertEqual(hashlib.sha256((ROOT/path).read_bytes()).hexdigest(),pins[path])

if __name__=='__main__':unittest.main()
