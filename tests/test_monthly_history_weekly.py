"""Weekly cutoff migration preserves legacy snapshots, evidence and write limits."""
import copy
from datetime import datetime, timedelta, timezone
import json
import unittest
from unittest.mock import patch
from test_monthly_history import h, p, d, inputs, music_row, remote, NOW, OLD

class WeeklyHistory(unittest.TestCase):
    def test_adapter_preserves_approved_source_and_requires_exact_anchors(self):
        import history_cadence as adapter
        from pathlib import Path
        root = Path(__file__).resolve().parents[1]
        original = (root/'visuals/monthly-history.js').read_bytes()
        compiled = adapter.validator(original.decode())
        self.assertIn('historyPeriodEnd(feed.generatedAt,feed.cadence)', compiled)
        self.assertEqual((root/'visuals/monthly-history.js').read_bytes(), original)
        for malformed in ('', original.decode() + original.decode(), compiled):
            with self.assertRaises(ValueError): adapter.validator(malformed)
        self.assertIn("?'주간':'월간'", adapter.ui((root/'visuals/ui.js').read_text()))

    def test_sunday_midnight_cutover_and_delayed_run(self):
        cases = {
            '2026-11-14T14:59:59+00:00': '2026-11-07',
            '2026-11-14T15:00:00+00:00': '2026-11-14',
            '2026-11-15T00:00:00+09:00': '2026-11-14',
            '2026-11-18T12:00:00+09:00': '2026-11-14',
            '2027-01-03T00:00:00+09:00': '2027-01-02',
            '2028-03-05T00:00:00+09:00': '2028-03-04',
        }
        for value, expected in cases.items():
            self.assertEqual(h.bounds(datetime.fromisoformat(value), 'weekly')[1].isoformat(), expected)
        with self.assertRaises(ValueError): h.bounds(datetime(2026, 11, 15), 'weekly')
        with self.assertRaises(ValueError): h.bounds(datetime.now(timezone.utc), 'daily')

    def test_weekly_includes_current_month_but_not_current_week(self):
        when = datetime.fromisoformat('2026-11-15T00:05:00+09:00')
        schedule = inputs([], [])['schedule']; schedule['generatedAt'] = when.isoformat()
        rows = [{**music_row(), 'checkedAt': when.isoformat(), 'publishedAt': '2026-11-14T23:59:59+09:00'}]
        weekly = h.compose(schedule, rows, when, cadence='weekly')
        self.assertEqual(weekly['through'], '2026-11-14')
        self.assertEqual(weekly['cadence'], 'weekly')
        self.assertEqual(len(weekly['events']), 1)
        self.assertFalse(h.compose(schedule, rows, when)['events'])
        rows[0]['publishedAt'] = '2026-11-15T00:00:00+09:00'
        self.assertFalse(h.compose(schedule, rows, when, cadence='weekly')['events'])

    def test_legacy_merge_idempotence_and_evidence_preserved(self):
        old = h.combine_inputs(inputs())
        fresh = inputs([], []); fresh['cadence'] = 'weekly'
        weekly = h.combine_inputs(fresh)
        merged = h.merge(old, weekly)
        self.assertEqual(merged['events'], old['events'])
        self.assertEqual(merged['sources'], old['sources'])
        self.assertEqual(merged['cadence'], 'weekly')
        self.assertEqual(h.merge(merged, weekly), merged)
        self.assertEqual(len(h.base()['events']), 55)
        for cadence in ('daily', None, False):
            bad = copy.deepcopy(merged); bad['cadence'] = cadence
            with self.assertRaises(ValueError): h.validate(bad)
        bad = copy.deepcopy(merged); bad['through'] = '2099-01-01'
        with self.assertRaises(ValueError): h.validate(bad)

    def test_collector_mode_reaches_publisher(self):
        fresh = inputs()
        with patch.dict(h.os.environ, {'ISEGYE_HISTORY_CADENCE': 'weekly'}), patch.object(h.schedule, 'collect', return_value=fresh['schedule']), patch.object(h.music, 'discover', return_value=fresh['music']):
            result = h.inputs(datetime.fromisoformat(NOW))
        self.assertEqual(result['cadence'], 'weekly')
        self.assertEqual(h.combine_inputs(result)['cadence'], 'weekly')
        with patch.dict(h.os.environ, {'ISEGYE_HISTORY_CADENCE': 'bad'}), patch.object(h.schedule, 'collect') as network:
            with self.assertRaises(ValueError): h.inputs()
            network.assert_not_called()

    def test_weekly_publish_requires_compatible_ui_then_preserves_backup(self):
        r = remote(); p.publish(r, inputs()); previous = r.read(p.path('current.json'))
        fresh = inputs(); fresh['cadence'] = 'weekly'
        with self.assertRaises(d.Stop): p.publish(r, fresh)
        self.assertEqual(r.read(p.path('current.json')), previous)
        r.files[d.ROOT+'/_isegye_releases/'+OLD+'/build-info.json'] = b'{"monthlyHistory":{"schemaVersion":1,"cadence":"weekly"}}'
        out = p.publish(r, fresh)
        self.assertEqual(out['cadence'], 'weekly')
        self.assertTrue(out['verifiedReadback'])
        self.assertEqual(r.read(p.path('previous.json')), previous)
        self.assertEqual(json.loads(r.read(p.path('current.json')))['cadence'], 'weekly')
        self.assertTrue(all(x.startswith(p.DIR+'/') for x in r.writes))
        self.assertEqual(p.publish(r, fresh)['added'], 0)

if __name__ == '__main__':
    unittest.main()
