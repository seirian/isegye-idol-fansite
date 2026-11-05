"""Build-only community links; archived reviews and public documents stay intact."""
import base64
import hashlib
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import compose_community_shortcuts as community


class CommunityShortcutsTest(unittest.TestCase):
    def test_exact_destinations(self):
        html = community.markup()
        for _, _, href in community.DESTINATIONS:
            self.assertEqual(html.count('href="'+href+'"'), 1)
        self.assertEqual(html.count('target="_blank"'), 2)
        self.assertEqual(html.count('rel="noopener noreferrer"'), 2)
        self.assertEqual(html.count('alt=""'), 2)
        self.assertIn('aria-label="커뮤니티 바로가기"', html)

    def test_source_assets_are_original_png(self):
        data = json.loads((ROOT/'site/community-logos.json').read_text())
        for asset in data['logos'].values():
            raw = base64.b64decode(''.join(asset['base64Parts']), validate=True)
            self.assertEqual(hashlib.sha256(raw).hexdigest(), asset['sha256'])
            self.assertTrue(raw.startswith(b'\x89PNG\r\n\x1a\n'))
            self.assertTrue(asset['sourceUrl'].startswith('https://'))

    def test_assets_do_not_use_external_image_requests(self):
        html = community.markup()
        self.assertEqual(html.count('src="data:image/png;base64,'), 2)
        self.assertNotIn('<script', html)
        self.assertNotIn('onclick', html)

    def test_placement_after_primary_menu(self):
        before = 'prefix<div class="wrap"><nav class="desktop-nav">SEVEN</nav></div></header>suffix'
        after = community.adapt_app(before)
        self.assertIn('SEVEN</nav><div class="community-shortcuts"', after)
        self.assertTrue(after.endswith('</div></header>suffix'))
        self.assertIn('class="wrap community-menu-row"', after)

    def test_missing_anchor_fails_closed(self):
        with self.assertRaises(ValueError):
            community.adapt_app('<header></header>')

    def test_corrupt_logo_fails_closed(self):
        assets = json.loads((ROOT/'site/community-logos.json').read_text())
        assets['logos']['berriz']['sha256'] = '0'*64
        with patch.object(Path, 'read_text', return_value=json.dumps(assets)):
            with self.assertRaises(ValueError):
                community.markup()

    def test_mobile_and_keyboard_styles(self):
        css = community.css()
        for expected in ('max-width:640px', ':focus-visible', 'min-height:44px', 'prefers-reduced-motion', 'overflow-x:auto'):
            self.assertIn(expected, css)

    def test_public_and_archived_sources_not_modified(self):
        for file in ('auth/View.php', 'auth/Gateway.php', 'review-1st/app.js', 'scripts/review_2nd_cleanup.py'):
            self.assertNotIn('community-shortcuts', (ROOT/file).read_text())
