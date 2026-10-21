import importlib.util
import json
import os
import stat
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('inour', Path(__file__).resolve().parents[1] / 'scripts/inour_sftp.py')
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)

class DeploymentSafetyTests(unittest.TestCase):
    def test_known_roots_are_disjoint(self):
        self.assertEqual(d.ROOT, '/web/_isegye_idol')
        self.assertEqual(d.MIR, '/web/_mir_site')
        self.assertNotEqual(d.ROOT, d.MIR)
        self.assertFalse(d.ROOT.startswith(d.MIR + '/'))

    def test_shared_and_mir_writes_rejected(self):
        for path in ('/web/.htaccess', '/web/index.html', '/web/_mir_site/index.html', '/web/mir/index.html', '/web/_yeop_releases/new', d.ROOT, d.ROOT + '-other/x'):
            with self.subTest(path=path), self.assertRaises(d.Stop):
                d.write_path(path)

    def test_traversal_and_noncanonical_paths_rejected(self):
        for suffix in ('/../_mir_site/index.html', '//index.html', '/src/../../index.html', '/x\\y', '/./index.html', '/%2e%2e/x', '/bad\nfile'):
            with self.subTest(suffix=suffix), self.assertRaises(d.Stop):
                d.write_path(d.ROOT + suffix)

    def test_owned_paths_accepted(self):
        for suffix in ('/.htaccess', '/.deploy-lock', '/.isegye-owner', '/_isegye_releases/r0123456789ab/src/app.js'):
            self.assertEqual(d.write_path(d.ROOT + suffix), d.ROOT + suffix)

    def test_exact_managed_router_only(self):
        self.assertTrue(d.managed_router(d.router()))
        self.assertTrue(d.managed_router(d.router('r0123456789ab')))
        self.assertFalse(d.managed_router(b'# ISEGYE-ISOLATED-ROOT-V1 spoof\n'))
        self.assertFalse(d.managed_router(d.router() + b'# manual change\n'))
        self.assertFalse(d.managed_router(None))

    def test_invalid_release_rejected(self):
        for value in ('../mir', 'r123', 'r' + 'f' * 13, 'r' + 'g' * 12, 'r0123456789ab\n'):
            with self.subTest(value=value), self.assertRaises(d.Stop):
                d.router(value)

    def test_host_guard_precedes_routes(self):
        text = d.router('r0123456789ab').decode()
        self.assertIn('!^isegye-idol\\.kr(?::443)?$', text)
        self.assertLess(text.index('[F,L]'), text.index('_isegye_releases'))
        self.assertNotIn('_mir_site', text)
        self.assertNotIn('_yeop_releases', text)
        self.assertIn('Options -Indexes', text)
        self.assertIn('RewriteRule (^|/)\\.', text)

    def test_unpublished_router_is_closed(self):
        self.assertIn(b'[R=503,L]', d.router())
        self.assertNotIn(b'_isegye_releases', d.router())

    def make_build(self, root, mode='production', commit='a' * 40):
        for name, data in {'index.html': '<html></html>', 'src/app.js': 'void 0;', 'src/styles.css': 'body{}',
                           'build-info.json': json.dumps({'mode': mode, 'commit': commit})}.items():
            path = Path(root) / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(data)

    def test_valid_build(self):
        with tempfile.TemporaryDirectory() as root:
            self.make_build(root)
            self.assertEqual(len(d.load_payload(root, 'a' * 40)), 4)

    def test_preview_build_not_deployable(self):
        with tempfile.TemporaryDirectory() as root:
            self.make_build(root, mode='preview')
            with self.assertRaises(d.Stop): d.load_payload(root, 'a' * 40)

    def test_commit_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            self.make_build(root)
            with self.assertRaises(d.Stop): d.load_payload(root, 'b' * 40)

    def test_unexpected_files_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            self.make_build(root)
            (Path(root) / '.env').write_text('secret=example')
            with self.assertRaises(d.Stop): d.load_payload(root, 'a' * 40)

    def test_local_symlinks_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            self.make_build(root)
            (Path(root) / 'assets').symlink_to(Path(root) / 'src', target_is_directory=True)
            with self.assertRaises(d.Stop): d.load_payload(root, 'a' * 40)

    def test_remote_symlink_rejected(self):
        fake = SimpleNamespace(lstat=lambda _: SimpleNamespace(st_mode=stat.S_IFLNK | 0o777, st_uid=d.UID), normalize=lambda p: p)
        with self.assertRaises(d.Stop): d.Remote(fake).directory(d.ROOT)

    def test_remote_alias_rejected(self):
        fake = SimpleNamespace(lstat=lambda _: SimpleNamespace(st_mode=stat.S_IFDIR | 0o755, st_uid=d.UID), normalize=lambda _: d.MIR)
        with self.assertRaises(d.Stop): d.Remote(fake).directory(d.ROOT)

    def test_foreign_owner_rejected(self):
        fake = SimpleNamespace(lstat=lambda _: SimpleNamespace(st_mode=stat.S_IFDIR | 0o755, st_uid=0), normalize=lambda p: p)
        with self.assertRaises(d.Stop): d.Remote(fake).directory(d.ROOT)

    def test_develop_cannot_deploy(self):
        with patch.dict(os.environ, {'GITHUB_REF': 'refs/heads/develop', 'PRODUCTION_ENABLED': 'true'}, clear=True):
            with self.assertRaisesRegex(d.Stop, 'main-only'): d.main()

    def test_disabled_production_cannot_deploy(self):
        with patch.dict(os.environ, {'GITHUB_REF': 'refs/heads/main'}, clear=True):
            with self.assertRaisesRegex(d.Stop, 'not enabled'): d.main()

    def test_wrong_mapping_removes_only_owned_probe(self):
        remote = d.Remote(None)
        writes = []
        remote.new = lambda p, b: writes.append((p, b))
        removed = []
        remote.remove_own = lambda p, b: removed.append((p, b))
        with patch.object(d, 'http', return_value=(200, b'personal site')):
            with self.assertRaisesRegex(d.Stop, 'not mapped'): remote.prove_mapping()
        self.assertEqual(writes, removed)
        self.assertTrue(writes[0][0].startswith(d.ROOT + '/isegye-probe-'))

    def test_cross_host_exposure_blocks_deploy(self):
        remote = d.Remote(None)
        memory = {}
        remote.new = lambda p, b: memory.update(path=p, data=b)
        remote.remove_own = lambda p, b: memory.update(cleaned=True)
        with patch.object(d, 'http', side_effect=lambda _: (200, memory['data'])):
            with self.assertRaisesRegex(d.Stop, 'Cross-host'): remote.prove_mapping()
        self.assertTrue(memory['cleaned'])

if __name__ == '__main__':
    unittest.main()
