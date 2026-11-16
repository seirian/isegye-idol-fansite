import copy
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import gallery_cache as cache
import album_observation_archive as archive

class GalleryCache(unittest.TestCase):
    def setUp(self):
        self.rows=json.loads((ROOT/'home-review/gallery.json').read_text())
    def test_all_five_cached_images_offline_and_exact(self):
        with patch('urllib.request.build_opener',side_effect=AssertionError('No network')):
            for row in self.rows:
                raw=cache.load(row)
                expected=json.loads((ROOT/'home-review/gallery-cache.json').read_text())['images'][row['id']]
                self.assertEqual(hashlib.sha256(raw).hexdigest(),expected['sha256'])
    def test_changed_original_identity_rejected(self):
        row=copy.deepcopy(self.rows[0]);row['sha256']='0'*64
        with self.assertRaises(ValueError):cache.load(row)
    def test_unsafe_identity_rejected(self):
        row=copy.deepcopy(self.rows[0]);row['id']='../../secret'
        with self.assertRaises(ValueError):cache.load(row)
    def test_changed_cache_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'home-review/gallery-cache').mkdir(parents=True)
            (root/'home-review/gallery-cache.json').write_bytes((ROOT/'home-review/gallery-cache.json').read_bytes())
            (root/'home-review/gallery-cache/mafia.webp').write_bytes(b'changed')
            with patch.object(cache,'ROOT',root):
                with self.assertRaises(ValueError):cache.load(self.rows[0])
    def test_source_approval_pins_cache_and_loader(self):
        pins=json.loads((ROOT/'review/home-release.json').read_text())['sourceHashes']
        for path in ['scripts/gallery_cache.py','home-review/gallery-cache.json']+['home-review/gallery-cache/'+r['id']+'.webp' for r in self.rows]:
            self.assertEqual(pins[path],hashlib.sha256((ROOT/path).read_bytes()).hexdigest())
    def test_night_archive_skipped_not_corruption(self):
        buf=io.BytesIO()
        with zipfile.ZipFile(buf,'w') as z:z.writestr('albums-gate.json',json.dumps({'status':'paused','allowed':False}))
        raw=buf.getvalue()
        self.assertIsNone(archive.read_snapshot(raw,'sha256:'+hashlib.sha256(raw).hexdigest()))
    def test_unknown_missing_snapshot_still_refused(self):
        buf=io.BytesIO()
        with zipfile.ZipFile(buf,'w') as z:z.writestr('albums-gate.json',json.dumps({'status':'allowed','allowed':True}))
        raw=buf.getvalue()
        with self.assertRaises(ValueError):archive.read_snapshot(raw,'sha256:'+hashlib.sha256(raw).hexdigest())

if __name__=='__main__':unittest.main()
