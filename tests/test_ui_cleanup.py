"""Presentation-only removal; polling and the LIVE page remain unchanged."""
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import compose_ui_cleanup as cleanup


class UICleanupTests(unittest.TestCase):
    def fixture(self):
        return '\n'.join(cleanup.REMOVALS.values()) + '\n' + (
            '<span>이세계아이돌 비공식 팬 아카이브</span>'
            '<button data-action="search">멤버·음악 검색</button>'
            '<a data-nav="members" href="#/members">멤버 소개</a>'
            '<a href="#/live">LIVE 전체 보기</a>'
            '<button data-live-key="page-refresh">새로고침</button>'
            'function liveMount(){keepPolling();}'
        )

    def test_four_nodes_are_removed_not_hidden(self):
        app, css, meta = self.fixture(), 'unchanged css', {}
        result, result_css = cleanup.compose(app, css, meta)
        for markup in cleanup.REMOVALS.values():
            self.assertNotIn(markup, result)
        self.assertEqual(result_css, css)
        self.assertEqual(meta['uiCleanup']['removed'], list(cleanup.REMOVALS))
        self.assertTrue(meta['uiCleanup']['liveAutomaticRefreshPreserved'])
        for kept in ['비공식 팬 아카이브', 'data-action="search"', 'data-nav="members"',
                     'LIVE 전체 보기', 'data-live-key="page-refresh"',
                     'function liveMount(){keepPolling();}']:
            self.assertIn(kept, result)

    def test_missing_or_duplicate_anchor_fails_without_metadata_change(self):
        for name, markup in cleanup.REMOVALS.items():
            for value in [self.fixture().replace(markup, ''), self.fixture() + markup]:
                with self.subTest(name=name), self.assertRaises(ValueError):
                    meta = {}
                    cleanup.compose(value, '', meta)
                self.assertEqual(meta, {})

    def test_build_and_release_checks_include_cleanup(self):
        build = (ROOT / 'scripts/build_home_review.py').read_text()
        self.assertIn('app,css=compose_ui_cleanup.compose(app,css,meta)', build)
        self.assertIn('tests/ui_cleanup_browser.py', (ROOT / 'scripts/verify_release_v04.py').read_text())
        approval = json.loads((ROOT / 'review/home-release.json').read_text())
        for path in ('scripts/build_home_review.py', 'scripts/compose_ui_cleanup.py'):
            self.assertEqual(approval['sourceHashes'][path], hashlib.sha256((ROOT / path).read_bytes()).hexdigest())


if __name__ == '__main__':
    unittest.main()
