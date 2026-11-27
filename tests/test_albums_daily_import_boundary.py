"""The isolated album runtime does not load CSS presentation dependencies."""
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]


class AlbumImportBoundary(unittest.TestCase):
    def test_availability_and_album_adapter_import_without_site_packages(self):
        code = """
import sys
sys.path.insert(0, sys.argv[1])
import compose_music_source_availability
import promote_albums
assert 'review_2nd_polish' not in sys.modules
assert 'tinycss2' not in sys.modules
"""
        result = subprocess.run([sys.executable, '-I', '-S', '-c', code, str(ROOT/'scripts')],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_album_anchor_still_requires_exactly_one_match(self):
        sys.path.insert(0, str(ROOT/'scripts'))
        from compose_music_source_availability import adapt_albums
        anchor = 'return `<section class="ai-panel ai-streaming">'
        self.assertEqual(adapt_albums(anchor),
                         'return sourceAvailabilityNotice(s)+`<section class="ai-panel ai-streaming">')
        for source in ('return ``;', anchor + anchor):
            with self.subTest(source=source), self.assertRaisesRegex(ValueError, 'Polish anchor changed'):
                adapt_albums(source)


if __name__ == '__main__':
    unittest.main()
