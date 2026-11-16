"""Requested KST schedules and collision-safe production serialization."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
KST = timezone(timedelta(hours=9))
EXPECTED = {
    'music-daily.yml': ('0 21 * * *', 7, lambda d: (d.hour, d.minute) == (6, 0)),
    'albums-daily.yml': ('0 0-15,22-23 * * *', 126, lambda d: d.minute == 0 and not 1 <= d.hour < 7),
    'schedule-refresh.yml': ('5 * * * *', 168, lambda d: d.minute == 5),
    'history-monthly.yml': ('0 15 * * 6', 1, lambda d: d.weekday() == 6 and (d.hour, d.minute) == (0, 0)),
}

def matches(cron, value):
    fields = cron.split()
    values = (value.minute, value.hour, value.day, value.month, (value.weekday() + 1) % 7)
    def field_matches(field, item):
        return field == '*' or any(int(part) == item if '-' not in part else int(part.split('-')[0]) <= item <= int(part.split('-')[1]) for part in field.split(','))
    return all(field_matches(field, item) for field, item in zip(fields, values))

class BatchSchedules(unittest.TestCase):
    def test_exact_utc_crons_and_seven_days_of_kst_slots(self):
        # Includes the Saturday UTC -> Sunday KST boundary.
        start = datetime(2026, 11, 8, tzinfo=KST).astimezone(timezone.utc)
        for filename, (expected, count, predicate) in EXPECTED.items():
            with self.subTest(workflow=filename):
                text = (ROOT / '.github/workflows' / filename).read_text()
                crons = re.findall(r"^    - cron: '([^']+)'", text, re.M)
                self.assertEqual(crons, [expected, '20,40 0-15,22-23 * * *'] if filename == 'albums-daily.yml' else [expected])
                if filename == 'albums-daily.yml':
                    extra = [start+timedelta(minutes=i) for i in range(7*24*60) if matches(crons[1], start+timedelta(minutes=i))]
                    self.assertEqual(len(extra), 252)
                    self.assertTrue(all(not 1 <= t.astimezone(KST).hour < 7 for t in extra))
                slots = [start + timedelta(minutes=i) for i in range(7 * 24 * 60) if matches(crons[0], start + timedelta(minutes=i))]
                self.assertEqual(len(slots), count)
                self.assertTrue(all(predicate(t.astimezone(KST)) for t in slots))

    def test_only_requested_schedules_and_manual_runs(self):
        for filename in EXPECTED:
            with self.subTest(workflow=filename):
                text = (ROOT / '.github/workflows' / filename).read_text()
                triggers = text.split('on:\n', 1)[1].split('permissions:', 1)[0]
                self.assertEqual(re.findall(r'^  ([a-z_]+):', triggers, re.M), ['schedule', 'workflow_dispatch', 'push'] if filename == 'albums-daily.yml' else ['schedule', 'workflow_dispatch'])
                self.assertIn("github.ref == 'refs/heads/main'", text)
                self.assertIn("github.repository == 'seirian/isegye-idol-fansite'", text)
                self.assertIn('PRODUCTION_PAUSED', text)

    def test_shared_write_lock_and_multi_pending_queue(self):
        for filename in [*EXPECTED, 'production.yml']:
            text = (ROOT / '.github/workflows' / filename).read_text()
            self.assertIn('  group: isegye-inour-production\n  cancel-in-progress: false\n  queue: max', text)

    def test_weekly_mode_and_compatible_history_runner(self):
        text = (ROOT / '.github/workflows/history-monthly.yml').read_text()
        self.assertIn('ISEGYE_HISTORY_CADENCE: weekly', text)
        self.assertIn('runs-on: ubuntu-24.04', text)
        self.assertIn('ISEGYE_HISTORY_PAUSED', text)
        self.assertIn('scripts/monthly_history.py', text)
        self.assertIn('scripts/publish_monthly_history.py', text)
        self.assertIn('test_monthly_history*.py', text)

if __name__ == '__main__':
    unittest.main()
