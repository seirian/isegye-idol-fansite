"""Offline manifest and source integrity tests. No public HTTP or server writes."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('genie_profiles',ROOT/'scripts/prepare_genie_portraits.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class GenieProfileTests(unittest.TestCase):
    def setUp(self):
        self.doc=json.loads((ROOT/'review/portraits.json').read_text(encoding='utf-8'))
    def test_six_distinct_named_members(self):
        self.assertEqual(len(m.validate_manifest(self.doc)),6)
    def test_no_placeholder_or_retired_source(self):
        for r in self.doc['members']:
            self.assertEqual(r['status'],'verified')
            self.assertIn('image.genie.co.kr',r['sourceImage'])
            self.assertNotIn('parable',r['sourceImage'])
    def test_duplicate_member_rejected(self):
        self.doc['members'][1]=copy.deepcopy(self.doc['members'][0])
        with self.assertRaises(ValueError):m.validate_manifest(self.doc)
    def test_member_identity_swap_rejected(self):
        self.doc['members'][0]['artistId']=self.doc['members'][1]['artistId']
        with self.assertRaises(ValueError):m.validate_manifest(self.doc)
    def test_wrong_page_rejected(self):
        self.doc['members'][0]['sourcePage']='https://www.genie.co.kr/'
        with self.assertRaises(ValueError):m.validate_manifest(self.doc)
    def test_non_source_urls_rejected(self):
        for url in ('http://image.genie.co.kr/a','https://example.com/a','file:///etc/passwd',
                    self.doc['members'][0]['sourceImage']+'?redirect=other'):
            bad=copy.deepcopy(self.doc);bad['members'][0]['sourceImage']=url
            with self.subTest(url=url),self.assertRaises(ValueError):m.validate_manifest(bad)
    def test_thumbnail_not_original_rejected(self):
        self.doc['members'][0]['sourceImage']=self.doc['members'][0]['sourceImage'].replace('600x600','200x200')
        with self.assertRaises(ValueError):m.validate_manifest(self.doc)
    def test_path_escape_rejected(self):
        self.doc['members'][0]['file']='review/../src/app.js'
        with self.assertRaises(ValueError):m.validate_manifest(self.doc)
    def test_missing_digest_rejected(self):
        self.doc['members'][0]['sha256']=''
        with self.assertRaises(ValueError):m.validate_manifest(self.doc)
    def test_unverified_source_rejected(self):
        self.doc['members'][0]['verifiedAt']=None
        with self.assertRaises(ValueError):m.validate_manifest(self.doc)
    def test_changed_source_bytes_rejected_before_decode(self):
        with self.assertRaisesRegex(ValueError,'Original changed'):
            m.prepare(b'not the verified portrait',self.doc['members'][0])
    def test_six_different_original_hashes(self):
        self.assertEqual(len({x['sourceSha256'] for x in self.doc['members']}),6)

if __name__=='__main__':unittest.main()
