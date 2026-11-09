"""Deployment preflight checks run without SFTP or external requests."""
from pathlib import Path
import base64
import hashlib
import json
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from deploy_albums_review import payload
from inour_sftp import Stop

COMMIT = 'a' * 40
STAMP = '2026-11-09T01:00:00+00:00'

class AlbumPayloadTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        script, style = 'const example = 1;', 'body { margin: 0; }'
        digest = lambda value: base64.b64encode(hashlib.sha256(value.encode()).digest()).decode()
        html = ('<!doctype html><meta name="robots" content="noindex,nofollow">'
                + '<meta http-equiv="Content-Security-Policy" content="script-src \'sha256-'
                + digest(script) + '\'; style-src \'sha256-' + digest(style) + '\'">'
                + '<h1>앨범 1차 검토</h1><style>' + style + '</style><script>'
                + script + '</script><!--' + 'x' * 11000 + '-->')
        (self.folder / 'review.html').write_text(html)
        meta = {'review': 'albums-first-review', 'branch': 'feature/albums',
                'baseCommit': 'b' * 40, 'commit': COMMIT, 'builtAt': STAMP,
                'mode': 'isolated-preview', 'snapshotAt': STAMP, 'counts': {}}
        (self.folder / 'build-info.json').write_text(json.dumps(meta))
        (self.folder / 'insights.json').write_text(json.dumps({'schemaVersion': 1, 'generatedAt': STAMP}))

    def test_current_album_banner_passes(self):
        release, html, metadata, pointer, data = payload(self.folder, COMMIT)
        self.assertRegex(release, r'^p[0-9a-f]{12}$')
        self.assertIn('앨범 1차 검토', html.decode())
        self.assertFalse(json.loads(metadata)['productionUIReplaced'])
        self.assertEqual(json.loads(pointer)['dataSha256'], hashlib.sha256(data).hexdigest())

    def test_obsolete_banner_is_rejected(self):
        p = self.folder / 'review.html'
        p.write_text(p.read_text().replace('앨범 1차 검토', '음반 1차 검토'))
        with self.assertRaises(Stop): payload(self.folder, COMMIT)

    def test_script_tampering_still_rejected(self):
        p = self.folder / 'review.html'
        p.write_text(p.read_text().replace('const example = 1;', 'const example = 2;'))
        with self.assertRaises(Stop): payload(self.folder, COMMIT)

    def test_unsafe_inline_policy_still_rejected(self):
        p = self.folder / 'review.html'
        p.write_text(p.read_text().replace('script-src ', "script-src 'unsafe-inline' "))
        with self.assertRaises(Stop): payload(self.folder, COMMIT)

    def test_wrong_branch_is_rejected(self):
        p = self.folder / 'build-info.json'
        meta = json.loads(p.read_text()); meta['branch'] = 'main'
        p.write_text(json.dumps(meta))
        with self.assertRaises(Stop): payload(self.folder, COMMIT)

    def test_wrong_snapshot_time_is_rejected(self):
        p = self.folder / 'insights.json'
        data = json.loads(p.read_text()); data['generatedAt'] = '2020-01-01T00:00:00Z'
        p.write_text(json.dumps(data))
        with self.assertRaises(Stop): payload(self.folder, COMMIT)

if __name__ == '__main__': unittest.main()
