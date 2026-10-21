"""Release transaction unit tests; no real host connection or credentials."""
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase, main
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import production_release as release
import inour_sftp as d


class MemoryRemote:
    def __init__(self):
        self.files = {d.ROOT + '/.htaccess': d.router()}
        self.dirs = {d.ROOT}
        self.swaps = []
        self.s = SimpleNamespace(chmod=lambda *a: None, rmdir=self.dirs.remove)
    def initialize(self): pass
    def info(self, path): return True if path in self.files or path in self.dirs else None
    def mkdir(self, path):
        d.write_path(path)
        if self.info(path): raise d.Stop('Existing directory')
        self.dirs.add(path)
    def directory(self, path):
        if path not in self.dirs: raise d.Stop('Missing directory')
    def parents(self, path): d.write_path(path)
    def read(self, path): return self.files.get(path)
    def new(self, path, data):
        d.write_path(path)
        if path in self.files: raise d.Stop('Existing file')
        self.files[path] = data
    def snapshot(self): return {'shared': 'unchanged', 'mir': 'unchanged'}
    def prove_mapping(self): pass
    def replace(self, path, data, expected):
        d.write_path(path)
        if self.read(path) != expected: raise d.Stop('Concurrent change')
        self.files[path] = data
        self.swaps.append(data)


class ReleaseTransactionTests(TestCase):
    def setUp(self):
        self.remote = MemoryRemote()
        self.payload = {'index.html': b'ISEGYE', 'src/app.js': b'JS', '.nojekyll': b''}
        self.report = {}
        self.previous = self.remote.read(d.ROOT + '/.htaccess')
    def http(self, url):
        if url in release.EXISTING: return 200, b'EXISTING'
        if url == d.ORIGIN + '/': return 200, self.payload['index.html']
        if url.startswith(d.ORIGIN + '/'):
            path = url[len(d.ORIGIN) + 1:]
            if path in self.payload: return 200, self.payload[path]
        return 403, b'BLOCKED'
    def run_release(self, verify=lambda _: None, http=None):
        with patch.object(d, 'http', side_effect=http or self.http):
            release.deploy_verified(self.remote, self.payload, 'a' * 40, verify, self.report)
    def test_success_preserves_shared_and_mir(self):
        self.run_release()
        self.assertEqual(self.report['status'], 'deployed_and_verified')
        self.assertTrue(self.report['protected_files_unchanged'])
        self.assertFalse(self.report['shared_router_modified'])
        self.assertTrue(self.report['lock_removed'])
        self.assertEqual(len(self.remote.swaps), 1)
    def test_browser_failure_restores_previous(self):
        def fail(_): raise d.Stop('Live browser failed')
        with self.assertRaises(d.Stop): self.run_release(verify=fail)
        self.assertEqual(self.remote.read(d.ROOT + '/.htaccess'), self.previous)
        self.assertTrue(self.report['rollback_restored_previous'])
        self.assertNotIn(d.ROOT + '/.deploy-lock', self.remote.dirs)
    def test_http_mismatch_restores_previous(self):
        def wrong(url):
            return (200, b'WRONG') if url == d.ORIGIN + '/src/app.js' else self.http(url)
        with self.assertRaises(d.Stop): self.run_release(http=wrong)
        self.assertTrue(self.report['rollback_restored_previous'])
    def test_bad_baseline_does_not_activate(self):
        with self.assertRaises(d.Stop): self.run_release(http=lambda _: (503, b'UNHEALTHY'))
        self.assertEqual(self.remote.swaps, [])
        self.assertNotIn(d.ROOT + '/.deploy-lock', self.remote.dirs)
    def test_existing_site_changed_rolls_back(self):
        checks = {}
        def changed(url):
            checks[url] = checks.get(url, 0) + 1
            if url in release.EXISTING and checks[url] > 1: return 200, b'CHANGED'
            return self.http(url)
        with self.assertRaises(d.Stop): self.run_release(http=changed)
        self.assertTrue(self.report['rollback_restored_previous'])
    def test_external_router_change_is_not_overwritten(self):
        def interference(_):
            self.remote.files[d.ROOT + '/.htaccess'] = b'EXTERNAL'
            raise d.Stop('Failure after concurrent update')
        with self.assertRaises(d.Stop): self.run_release(verify=interference)
        self.assertEqual(self.remote.read(d.ROOT + '/.htaccess'), b'EXTERNAL')
        self.assertTrue(self.report['manual_recovery_required'])
    def test_existing_lock_is_not_removed(self):
        self.remote.dirs.add(d.ROOT + '/.deploy-lock')
        with self.assertRaises(d.Stop): self.run_release()
        self.assertIn(d.ROOT + '/.deploy-lock', self.remote.dirs)
    def test_backup_and_writes_stay_inside_isolated_root(self):
        self.run_release()
        self.assertEqual(self.remote.files[self.report['previous_router_backup']], self.previous)
        self.assertTrue(all(p.startswith(d.ROOT + '/') for p in self.remote.files))


if __name__ == '__main__': main()
