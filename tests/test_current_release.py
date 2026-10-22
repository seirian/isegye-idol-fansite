"""Approved release packaging tests; no network, credentials or remote writes."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from build_selected import package, production_app
import build_selected as selected
from prepare_genie_portraits import validate_manifest

class CurrentReleaseTests(unittest.TestCase):
    def test_approved_review_is_exact(self):
        approval = json.loads((ROOT/'review/release.json').read_text())
        self.assertTrue(approval['operatorApprovedDeployment'])
        self.assertEqual(approval['reviewedCommit'], 'ff93882c6509acb1a8d7664ae7455e11fea95040')
        self.assertFalse(approval['rightsPermissionVerified'])
        self.assertEqual(hashlib.sha256((ROOT/'review/isegye-group-hero.webp').read_bytes()).hexdigest(), approval['groupImageSha256'])
        self.assertEqual(len(validate_manifest(json.loads((ROOT/'review/portraits.json').read_text()))), 6)

    def test_production_copy_has_no_preview_label(self):
        text = production_app('디자인 개선 검토 읽기 편하게, 더 가까이 hero-group profile-attribution')
        self.assertIn('공개 베타', text)
        self.assertNotIn('검토', text)
        self.assertIn('profile-attribution', text)

    def test_legacy_invitation_is_rejected(self):
        with self.assertRaises(RuntimeError):
            production_app('디자인 개선 검토 읽기 편하게, 더 가까이 hero-group profile-attribution YOU ARE INVITED TO')

    def fixture(self, folder):
        source = folder/'generated'
        (source/'src').mkdir(parents=True)
        (source/'index.html').write_text('<html data-hero="group-photo"><head><title>preview</title><meta name="robots" content="noindex,nofollow"></head></html>')
        (source/'src/app.js').write_text('// 디자인 개선 검토 읽기 편하게, 더 가까이 hero-group profile-attribution')
        (source/'src/styles.css').write_text('body{font-size:1rem}')
        (source/'robots.txt').write_text('User-agent: *\nDisallow: /\n')
        (source/'review.html').write_text('standalone-review')
        approval = json.loads((ROOT/'review/release.json').read_text())
        meta = {'commit':'a'*40,'mode':'preview','verifiedPortraitCount':6,'pendingPortraitCount':0,
                'profileSource':'Genie Music','groupHero':{'sha256':approval['groupImageSha256']}}
        (source/'build-info.json').write_text(json.dumps(meta))
        return source, approval

    def test_production_contract_and_preview_preservation(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);source,approval=self.fixture(folder);output=folder/'dist'
            with patch.object(selected,'OUT',output), patch.dict(os.environ,{'GITHUB_SHA':'b'*40}):
                result=package(source,'production',approval)
                self.assertEqual(result['commit'],'b'*40)
                self.assertFalse((output/'review.html').exists())
                html=(output/'index.html').read_text()
                self.assertIn('index,follow',html)
                self.assertIn('rel="canonical" href="https://isegye-idol.kr/"',html)
                self.assertIn('noindex,nofollow',(source/'index.html').read_text())
                result=package(source,'preview',approval)
                self.assertEqual(result['mode'],'preview')
                self.assertTrue((output/'review.html').exists())
                self.assertNotIn('rel="canonical"',(output/'index.html').read_text())

    def test_missing_portraits_fails_before_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);source,approval=self.fixture(folder);output=folder/'dist'
            meta=json.loads((source/'build-info.json').read_text());meta['verifiedPortraitCount']=5
            (source/'build-info.json').write_text(json.dumps(meta))
            with patch.object(selected,'OUT',output), self.assertRaises(RuntimeError):
                package(source,'production',approval)
            self.assertFalse(output.exists())

    def test_production_cannot_use_feature_ref(self):
        with patch.dict(os.environ, {'DEPLOY_ENV':'production','GITHUB_REF':'refs/heads/feature/readability'}):
            with self.assertRaisesRegex(RuntimeError,'main-only'):
                selected.main()

if __name__=='__main__': unittest.main()
