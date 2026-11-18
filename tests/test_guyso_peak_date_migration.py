"""Peak-date maintenance is a locked, scoped, compare-and-swap publication."""
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
import json
import sys
import unittest
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import migrate_guyso_peak_dates as migration
import collect_album_peak_dates as dates
import collect_album_peak_fallback as peaks


def data():
    from test_albums_daily import complete_data
    result = complete_data()
    for sid, entry in peaks.reviewed_records().items():
        result['tracks'][sid]['melon'].update(entry['identity'])
        result['tracks'][sid]['melonPeakFallback'] = deepcopy(entry['reference'])
    return result


class MigrationTests(unittest.TestCase):
    def test_scope_idempotence_and_catalog(self):
        result = data(); old = deepcopy(result); report = migration.apply(result)
        self.assertEqual(len(report['verifiedTracks']), 24)
        self.assertEqual(report['confirmedDateCount'], 164)
        self.assertEqual(result['generatedAt'], old['generatedAt'])
        for sid, item in result['tracks'].items():
            copy = deepcopy(item); copy.pop('melonPeakDates', None)
            self.assertEqual(copy, old['tracks'][sid])
        once = deepcopy(result); self.assertFalse(migration.apply(result)['changed']); self.assertEqual(once, result)

    def test_mismatched_live_identity_refuses(self):
        result = data(); result['tracks']['rebels']['melon']['trackId'] = '999'
        with self.assertRaises(ValueError): migration.apply(result)

    def test_newer_peak_is_not_patched_with_old_rank_date(self):
        result = data(); result['tracks']['kidding']['melonPeakFallback']['records']['top100']['rank'] = 5
        with self.assertRaisesRegex(ValueError, 'lack reviewed dates'): migration.apply(result)

    def remote(self):
        import album_runtime as runtime
        from test_albums_daily import remote
        from test_schedule_feed import OLD
        obj = remote()
        obj.files[runtime.d.ROOT+'/_isegye_releases/'+OLD+'/src/app.js'] = 'guyso_peak_date_evidence earliest_observed_matching_peak 최고 성적 출처와 확인 시각'.encode()
        obj.mkdir(runtime.DIR); obj.new(runtime.path('.owner'), runtime.OWNER)
        obj.new(runtime.path('current.json'), json.dumps(data()).encode())
        return obj

    def test_atomic_backup_readback_noop_and_no_unrelated_writes(self):
        import album_runtime as runtime
        obj = self.remote(); before = obj.read(runtime.path('current.json'))
        first = migration.patch_remote(obj); after = obj.read(runtime.path('current.json'))
        second = migration.patch_remote(obj)
        self.assertTrue(first['verifiedReadback']); self.assertEqual(second['status'], 'already_applied')
        self.assertEqual(obj.read(runtime.path('current.json')), after)
        self.assertEqual(obj.read(runtime.path('previous.json')), before)
        self.assertNotIn(runtime.path('.lock'), obj.files)
        self.assertTrue(all(path.startswith(runtime.DIR+'/') for path in obj.writes))
        self.assertFalse(first['accountStoreReadOrWritten'])

    def test_foreign_lock_not_removed(self):
        import album_runtime as runtime
        obj = self.remote(); obj.files[runtime.path('.lock')] = b'foreign'
        with self.assertRaises(runtime.d.Stop): migration.patch_remote(obj)
        self.assertEqual(obj.read(runtime.path('.lock')), b'foreign')

    def test_old_ui_refuses_publication(self):
        import album_runtime as runtime
        from test_schedule_feed import OLD
        obj = self.remote(); obj.files[runtime.d.ROOT+'/_isegye_releases/'+OLD+'/src/app.js'] = b'guyso_observed_peaks'
        before = obj.read(runtime.path('current.json'))
        with self.assertRaises(runtime.d.Stop): migration.patch_remote(obj)
        self.assertEqual(obj.read(runtime.path('current.json')), before)

    def test_changed_feed_compare_and_swap_refuses(self):
        import album_runtime as runtime
        obj = self.remote(); original_apply = migration.apply
        foreign = json.dumps({'foreign': True}).encode()
        def concurrent_write(value):
            report = original_apply(value)
            obj.files[runtime.path('current.json')] = foreign
            return report
        with patch.object(migration, 'apply', side_effect=concurrent_write):
            with self.assertRaisesRegex(runtime.d.Stop, 'Feed changed'): migration.patch_remote(obj)
        self.assertEqual(obj.read(runtime.path('current.json')), foreign)
        self.assertNotIn(runtime.path('.lock'), obj.files)

    def test_failed_readback_rolls_back_own_write_only(self):
        import album_runtime as runtime
        obj = self.remote(); path = runtime.path('current.json'); before = obj.read(path)
        original_read = obj.read
        failed = [False]
        def failed_once(name):
            raw = original_read(name)
            if name == path and raw != before and not failed[0]:
                failed[0] = True
                return b'failed readback'
            return raw
        with patch.object(obj, 'read', side_effect=failed_once):
            with self.assertRaisesRegex(runtime.d.Stop, 'readback failed'): migration.patch_remote(obj)
        self.assertEqual(obj.read(path), before)
        self.assertEqual(obj.read(runtime.path('previous.json')), before)
        self.assertNotIn(runtime.path('.lock'), obj.files)

    def test_workflow_gates_follow_successful_deployment(self):
        text = (ROOT/'.github/workflows/guyso-peak-dates-migration.yml').read_text()
        for required in ('workflow_run:', "conclusion == 'success'", "head_branch == 'main'",
                '[guyso-peak-dates-20261118]', 'group: isegye-inour-production', 'PRODUCTION_PAUSED', 'ISEGYE_ALBUMS_PAUSED'):
            self.assertIn(required, text)
        self.assertNotIn('cron:', text)


if __name__ == '__main__': unittest.main()
