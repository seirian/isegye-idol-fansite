import copy
import hashlib
import json
from pathlib import Path
import sys
import unittest
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import compose_home_presentation as presentation

class HomePresentationTest(unittest.TestCase):
    def setUp(self):
        self.rows = json.loads((ROOT / 'home-review/gallery.json').read_text())
    def test_five_distinct_high_resolution_six_member_sources(self):
        self.assertEqual(len(presentation.validate(self.rows)), 5)
        self.assertEqual(len({r['sha256'] for r in self.rows}), 5)
    def test_reject_low_resolution_and_unreviewed_content(self):
        for key, value in [('width', 800), ('height', 450), ('sixMembersReviewed', False), ('sha256', 'bad'), ('id', '../outside'), ('url', 'https://example.com/image.jpg')]:
            rows = copy.deepcopy(self.rows);rows[0][key] = value
            with self.assertRaises(ValueError):presentation.validate(rows)
    def test_reject_duplicate_or_missing_source(self):
        with self.assertRaises(ValueError):presentation.validate(self.rows[:4])
        with self.assertRaises(ValueError):presentation.validate([self.rows[0]] * 5)
    def test_source_change_fails_closed(self):
        with self.assertRaises(ValueError):presentation.prepare(b'changed', self.rows[0])
    def test_composition_anchors_are_exact(self):
        self.assertEqual(presentation.once('abc', 'b', 'B'), 'aBc')
        for text in ('ac', 'abbc'):
            with self.assertRaises(ValueError):presentation.once(text, 'b', 'B')
    def test_presentation_sources_match_release_approval(self):
        approval = json.loads((ROOT / 'review/home-release.json').read_text())
        for name in ('scripts/compose_home_presentation.py', 'home-review/gallery.json', 'home-review/presentation.js', 'home-review/presentation.css', 'scripts/build_home_review.py'):
            self.assertEqual(approval['sourceHashes'][name], hashlib.sha256((ROOT / name).read_bytes()).hexdigest())
    def test_builder_embeds_offline_gallery(self):
        text = (ROOT / 'scripts/build_home_review.py').read_text()
        self.assertIn('compose_home_presentation.compose(app,css,out,meta)', text)
        self.assertIn('compose_home_presentation.inline_gallery(inline,out)', text)
    def test_release_runs_browser_regression(self):
        self.assertIn('tests/home_presentation_browser.py', (ROOT / 'scripts/verify_release_v04.py').read_text())

if __name__ == '__main__':unittest.main()
