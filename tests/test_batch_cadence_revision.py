"""2026-11-17 KST cadence contract; no network or production writes."""
from datetime import datetime, timedelta
from pathlib import Path
import copy
import re
import sys
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import batch_watchdog as w
from test_batch_schedule_contract import matches


class CadenceRevision(unittest.TestCase):
    def test_every_minute_matches_last_scheduled_slot_for_a_week(self):
        start = datetime(2026, 11, 16, tzinfo=w.KST)
        for kind in ('schedule', 'playground'):
            text = (ROOT / '.github/workflows' / w.SPECS[kind][0]).read_text()
            crons = re.findall(r"^    - cron: '([^']+)'", text, re.M)
            self.assertEqual(len(crons), 1)
            previous = start - timedelta(days=1)
            slots = []
            for minute in range(8 * 24 * 60):
                at = previous + timedelta(minutes=minute)
                if matches(crons[0], at.astimezone(w.UTC)):
                    slots.append(at)
                if at >= start:
                    self.assertEqual(w.due_slot(kind, at), slots[-1], (kind, at))
            current = [at for at in slots if at >= start]
            self.assertEqual(len(current), 84 if kind == 'schedule' else 7)
            for at in current:
                self.assertEqual((at.minute, at.hour % 2), (5, 0)) if kind == 'schedule' else self.assertEqual((at.hour, at.minute), (8, 0))

    def test_schedule_midnight_and_even_hour_boundary(self):
        cases = [('2026-11-17T00:04:59+09:00', '2026-11-16T22:05:00+09:00'),
                 ('2026-11-17T00:05:00+09:00', '2026-11-17T00:05:00+09:00'),
                 ('2026-11-17T01:59:59+09:00', '2026-11-17T00:05:00+09:00'),
                 ('2026-11-17T02:04:59+09:00', '2026-11-17T00:05:00+09:00'),
                 ('2026-11-17T02:05:00+09:00', '2026-11-17T02:05:00+09:00')]
        for at, expected in cases:
            with self.subTest(at=at):
                self.assertEqual(w.due_slot('schedule', datetime.fromisoformat(at)), datetime.fromisoformat(expected))

    def test_odd_hour_does_not_recollect_healthy_schedule(self):
        published = datetime(2026, 11, 17, 14, 12, tzinfo=w.KST)
        pub = {'status': 'published', 'generatedAt': published.isoformat(),
               'publishedAt': published.isoformat(), 'readbackAt': published.isoformat(),
               'evidenceVersion': 2, 'verifiedReadback': True,
               'collectionHealth': {'state': 'complete', 'sources': {
                   key: {'state': 'complete', 'lastSuccessAt': published.isoformat()}
                   for key in w.REQUIRED_SCHEDULE}}}
        files = {'schedule-publication.json': pub, 'schedule-health.json': {'verified': True}}
        for hour, minute, expected in ((14, 32, True), (15, 52, True), (16, 4, True), (16, 5, False)):
            at = published.replace(hour=hour, minute=minute)
            due = w.due_slot('schedule', at)
            healthy = w.evidence_ok('schedule', files, due, at)
            self.assertEqual(healthy, expected)
            if healthy:
                self.assertEqual(w.recovery_action([], at, due, healthy), 'healthy')
        pub['verifiedReadback'] = False
        self.assertFalse(w.evidence_ok('schedule', files, due, at))

    def test_playground_previous_day_until_eight(self):
        for at, expected in [('2026-11-17T07:59:59+09:00', '2026-11-16T08:00:00+09:00'),
                             ('2026-11-17T08:00:00+09:00', '2026-11-17T08:00:00+09:00')]:
            self.assertEqual(w.due_slot('playground', datetime.fromisoformat(at)), datetime.fromisoformat(expected))

    def test_new_even_slot_invalidates_inflight_recovery_decision(self):
        at = datetime(2026, 11, 17, 16, 4, 59, tzinfo=w.KST)
        row = {'state': 'dispatch', 'dueAt': w.due_slot('schedule', at).isoformat()}
        getter = Mock()
        with patch.object(w, 'inspect_batch', side_effect=[copy.deepcopy(row), copy.deepcopy(row)]):
            result = w.recover_batch('schedule', True, getter,
                                     Mock(side_effect=[at, at, at + timedelta(seconds=1)]))
        self.assertEqual(result['state'], 'slot_changed')
        getter.assert_not_called()

    def test_no_extra_playground_auto_triggers_or_source_check_dispatch(self):
        workflow = (ROOT / '.github/workflows/playground-daily.yml').read_text()
        triggers = workflow.split('on:\n', 1)[1].split('permissions:', 1)[0]
        self.assertEqual(re.findall(r'^  ([a-z_]+):', triggers, re.M), ['schedule', 'workflow_dispatch'])
        source_check = (ROOT / '.github/workflows/playground-bank-checks.yml').read_text()
        self.assertNotIn('/dispatches', source_check)
        self.assertNotIn('actions: write', source_check)
        self.assertNotIn('\n  refresh:', source_check)
        self.assertIn("'dailySchedule':'매일 08:00 Asia/Seoul'", (ROOT / 'scripts/promote_playground.py').read_text())

    def test_completion_workflow_name_remains_consistent(self):
        target = (ROOT / '.github/workflows/schedule-refresh.yml').read_text().splitlines()[0].removeprefix('name: ')
        self.assertEqual(w.COMPLETION_WORKFLOWS[target], 'schedule-refresh.yml')
        self.assertIn('      - ' + target + '\n', (ROOT / '.github/workflows/batch-watchdog.yml').read_text())


if __name__ == '__main__':
    unittest.main()
