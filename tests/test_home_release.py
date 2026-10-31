"""Approved home packaging and production boundaries. No network access."""
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build_release_home as release

class HomeReleaseTests(unittest.TestCase):
    def approval(self):
        return json.loads((ROOT / 'review/home-release.json').read_text())

    def test_exact_review_sources_and_live_unchanged(self):
        release.verify_sources(self.approval())

    def test_missing_approval_rejected(self):
        a = self.approval(); a['operatorApprovedDeployment'] = False
        with self.assertRaises(RuntimeError): release.verify_sources(a)

    def test_changed_source_hash_rejected(self):
        a = self.approval(); a['sourceHashes']['home-review/ui.js'] = '0' * 64
        with self.assertRaises(RuntimeError): release.verify_sources(a)

    def test_unknown_review_rejected(self):
        a = self.approval(); a['reviewedCommit'] = '0' * 40
        with self.assertRaises(RuntimeError): release.verify_sources(a)

    def test_feature_cannot_build_production(self):
        with patch.dict(os.environ, DEPLOY_ENV='production', GITHUB_REF='refs/heads/feature/home-simple'):
            with self.assertRaisesRegex(RuntimeError, 'main-only'): release.main()

    def test_backup_and_previous_production_preserved(self):
        a = self.approval()
        self.assertEqual(a['sourceBackup']['commit'], '885e818063eeccedf468d52ce148a4760819c97d')
        self.assertEqual(a['previousProductionCommit'], 'ecd43bdb0e994a2fe475324ef2f036663e706753')
        self.assertFalse(a['rightsPermissionVerified'])

    def fixture(self, folder):
        source = folder / 'source'; (source / 'src').mkdir(parents=True)
        original = json.loads((ROOT / 'review/live-release.json').read_text())
        meta = {'commit': 'a' * 40, 'mode': 'preview', 'review': 'home-simple',
                'verifiedPortraitCount': 6, 'profileSource': 'Genie Music',
                'groupHero': {'sha256': original['groupImageSha256']},
                'live': {'members': 6, 'failureMeansOffline': False},
                'catalog': {'songs': 154, 'channels': 21}, 'musicVideoAudit': {'linked': 151},
                'visualHistory': {'historyItems': 55, 'navigationCount': 7},
                'homeReview': {'livePreserved': True, 'communitySubmissionBanner': False, 'sections': release.SECTIONS}}
        (source / 'build-info.json').write_text(json.dumps(meta))
        (source / 'index.html').write_text('<head><title>Review</title><meta name="robots" content="noindex,nofollow"></head>')
        (source / 'src/app.js').write_text('// href="#/about">사이트소개</a> function homeSimpleView() function homeView(){return homeSimpleView();} function liveHomeView() const CATALOG= const HISTORY=')
        (source / 'src/data.js').write_text("const SITE={version:'0.4.0'};")
        (source / 'src/styles.css').write_text('body{}')
        (source / 'review.html').write_text('noindex offline preview')
        (source / 'robots.txt').write_text('User-agent: *\nDisallow: /\n')
        return source

    def test_production_output_and_source_preservation(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); src = self.fixture(root); out = root / 'out'
            with patch.dict(os.environ, GITHUB_REF='refs/heads/main', GITHUB_REF_NAME='main', GITHUB_SHA='a' * 40):
                meta = release.package(src, out, 'production', self.approval())
            self.assertEqual(meta['version'], '0.5.0')
            self.assertEqual(meta['approvedHomeReview'], release.REVIEW)
            self.assertNotIn('preview-strip', (out / 'src/app.js').read_text())
            self.assertIn('index,follow', (out / 'index.html').read_text())
            self.assertIn('rel="canonical"', (out / 'index.html').read_text())
            self.assertFalse((out / 'review.html').exists())
            self.assertIn('noindex,nofollow', (src / 'index.html').read_text())
            self.assertIn('사이트소개', (src / 'src/app.js').read_text())

    def test_preview_remains_noindex(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); src = self.fixture(root)
            meta = release.package(src, root / 'out', 'preview', self.approval())
            self.assertEqual(meta['mode'], 'preview')
            self.assertIn('noindex,nofollow', (root / 'out/index.html').read_text())
            self.assertTrue((root / 'out/review.html').exists())

    def test_incomplete_home_rejected_without_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); src = self.fixture(root); out = root / 'out'; out.mkdir()
            (out / 'untouched').write_text('keep')
            meta = json.loads((src / 'build-info.json').read_text())
            meta['homeReview']['livePreserved'] = False
            (src / 'build-info.json').write_text(json.dumps(meta))
            with self.assertRaises(RuntimeError): release.package(src, out, 'preview', self.approval())
            self.assertEqual((out / 'untouched').read_text(), 'keep')

    def test_production_requires_exact_ref_even_when_packaged_directly(self):
        with patch.dict(os.environ, GITHUB_REF='refs/heads/develop'):
            with self.assertRaisesRegex(RuntimeError, 'main-only'):
                release.package(Path('missing'), Path('unused'), 'production', self.approval())

    def test_missing_composition_rejected(self):
        with self.assertRaises(RuntimeError): release.production_text('old homepage')

if __name__ == '__main__': unittest.main()
