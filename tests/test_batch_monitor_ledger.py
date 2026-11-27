"""Expected obligations include absent evidence and retain failure/recovery."""
from datetime import timedelta
from pathlib import Path
import copy
import base64
import gzip
import hashlib
import json
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import batch_slot_ledger as ledger
import batch_watchdog as policy

AT = policy.clock('2026-11-27T21:43:00+09:00')


def doc(at=AT, outcome=None):
    result = {'checkedAt': at.isoformat(), 'batches': []}
    if outcome:
        due = policy.due_slot('albums', at)
        candidate = {'id': 42 if outcome == 'failed' else 43, 'attempt': 1, 'status': 'completed',
                     'conclusion': 'failure' if outcome == 'failed' else 'success',
                     'startedAt': (due+timedelta(minutes=5)).isoformat()}
        row = {'key': 'albums', 'dueAt': due.isoformat(), 'listingComplete': True,
               'run': candidate, 'evidenceRun': candidate, 'dataState': 'attention' if outcome == 'failed' else 'healthy',
               'evidence': {'readbackAt': (at-timedelta(minutes=1)).isoformat(), 'verifiedReadback': outcome != 'failed'}}
        result['batches'].append(row)
    return result


class SlotLedger(unittest.TestCase):
    def merge(self, old, new):
        return ledger.merge_slot_ledger(old, new, policy.due_slot)

    def test_expected_slots_exist_without_any_workflow_or_evidence(self):
        value = ledger.unpack_slot_ledger(self.merge({}, doc())['slotLedger'])
        self.assertEqual(sum(item['batch']=='albums' for item in value['entries']), 16)
        self.assertEqual(sum(item['batch']=='capture' for item in value['entries']), 16)
        self.assertEqual(sum(item['batch']=='schedule' for item in value['entries']), 11)
        self.assertTrue(all(item['state']=='unverified' for item in value['entries']))
        self.assertFalse(value['unobservedIsFailure'])

    def test_night_policy_and_not_due_weekly_work_are_not_fabricated(self):
        value = self.merge({}, doc(policy.clock('2026-11-27T07:10:00+09:00')))
        contents = ledger.unpack_slot_ledger(value['slotLedger'])
        albums = [item for item in contents['entries'] if item['batch']=='albums']
        self.assertEqual(len(albums), 2)
        self.assertFalse(any(item['batch']=='history' for item in contents['entries']))

    def test_recovery_keeps_original_failure_and_exact_readback(self):
        old = self.merge({}, doc(AT-timedelta(minutes=15), 'failed'))
        new = self.merge(old, doc(AT, 'verified'))
        item = next(item for item in ledger.unpack_slot_ledger(new['slotLedger'])['entries'] if item['batch']=='albums' and item['dueAt']==policy.due_slot('albums', AT).isoformat())
        self.assertEqual(item['state'], 'verified')
        self.assertEqual(item['firstFailure']['runId'], 42)
        self.assertEqual(item['firstFailure']['executionConclusion'], 'failure')
        self.assertEqual(item['recoveredAt'], AT.isoformat())
        self.assertEqual(item['recoveredReadbackAt'], (AT-timedelta(minutes=1)).isoformat())
        self.assertEqual(new['batches'][0]['slotSummary']['recovered'], 1)

    def test_inspection_outage_does_not_erase_verified_slot(self):
        old = self.merge({}, doc(AT-timedelta(minutes=2), 'verified'))
        new = doc(); new['batches'] = copy.deepcopy(old['batches'])
        new['batches'][0].update(listingComplete=False, inspectionError='query_failed', dataState='unknown')
        result = self.merge(old, new)
        item = next(item for item in ledger.unpack_slot_ledger(result['slotLedger'])['entries'] if item['batch']=='albums' and item['dueAt']==policy.due_slot('albums', AT).isoformat())
        self.assertEqual(item['state'], 'verified')
        self.assertEqual(item['events'][-1]['outcome'], 'unverified')
        self.assertEqual(result['batches'][0]['dataState'], 'unknown')

    def test_history_allowlist_drops_unrecognized_fields(self):
        old = self.merge({}, doc(AT-timedelta(minutes=2), 'failed'))
        old['slotLedger'] = ledger.unpack_slot_ledger(old['slotLedger'])
        item = next(item for item in old['slotLedger']['entries'] if item['firstFailure'])
        item['token'] = 'DO-NOT-COPY'; item['firstFailure']['token'] = 'DO-NOT-COPY'
        result = self.merge(old, doc())
        self.assertNotIn('DO-NOT-COPY', json.dumps(result))
        self.assertNotIn('DO-NOT-COPY', json.dumps(ledger.unpack_slot_ledger(result['slotLedger'])))

    def test_schema_one_migrates_without_losing_failure_or_events(self):
        old = self.merge({}, doc(AT-timedelta(minutes=2), 'failed'))
        plain = ledger.unpack_slot_ledger(old['slotLedger'])
        legacy = dict(old, slotLedger=plain)
        old['slotLedger'] = ledger.pack_slot_ledger(plain)
        migrated = self.merge(legacy, doc())
        retained = self.merge(old, doc())
        self.assertEqual(migrated['slotLedger']['schemaVersion'], 2)
        self.assertEqual(ledger.unpack_slot_ledger(migrated['slotLedger']),
                         ledger.unpack_slot_ledger(retained['slotLedger']))

    def test_integrity_size_count_metadata_and_gzip_corruption_fail_closed(self):
        value = self.merge({}, doc())['slotLedger']
        variants = []
        for key, replacement in [('sha256', '0'*64), ('uncompressedBytes', value['uncompressedBytes']+1),
                                  ('entryCount', value['entryCount']+1), ('coverageStartAt', AT.isoformat()),
                                  ('data', 'not-base64'), ('encoding', 'deflate')]:
            variants.append(dict(value, **{key: replacement}))
        raw = base64.b64decode(value['data'])
        variants.append(dict(value, data=base64.b64encode(raw[:-4]).decode()))
        variants.append(dict(value, data=base64.b64encode(raw+gzip.compress(b'{}')).decode()))
        for modified in variants:
            with self.subTest(keys=modified.keys()), self.assertRaises(ValueError):
                self.merge({'slotLedger': modified}, doc())

    def test_expansion_bomb_and_declared_bounds_stop_before_json(self):
        value = self.merge({}, doc())['slotLedger']
        huge = b' '*(ledger.MAX_UNCOMPRESSED_BYTES+1)
        bomb = dict(value, data=base64.b64encode(gzip.compress(huge)).decode(),
                    sha256=hashlib.sha256(huge).hexdigest(), uncompressedBytes=ledger.MAX_UNCOMPRESSED_BYTES)
        with self.assertRaises(ValueError):
            ledger.unpack_slot_ledger(bomb)
        for change in [{'uncompressedBytes': ledger.MAX_UNCOMPRESSED_BYTES+1},
                       {'entryCount': ledger.MAX_ENTRIES+1}]:
            with self.assertRaises(ValueError):
                ledger.unpack_slot_ledger(dict(value, **change))

    def test_ninety_days_complete_ledger_and_observations_fit_whole_payload(self):
        from batch_monitor_snapshot import merge_observations
        from deploy_batch_monitor import release_payload
        from test_batch_monitor import fixture_snapshot
        # Start with rollout day, then fill all 90 days including every weekly
        # obligation (the preceding historic period predates weekly adoption).
        at = (AT+timedelta(days=89)).astimezone(ledger.KST).replace(hour=23, minute=59, second=59)
        start = (at-timedelta(days=89)).replace(hour=0, minute=0, second=0, microsecond=0)
        entries, observations = [], []
        for index, (kind, due) in enumerate(ledger.expected_slots(start, at, policy.due_slot)):
            events = []
            for number, outcome in enumerate(('failed', 'partial', 'cancelled', 'verified')):
                event = {'observedAt': (due+timedelta(minutes=number+1)).isoformat(),
                    'outcome': outcome, 'runId': 46000000000+index*10+number, 'attempt': number+1,
                    'executionState': 'completed', 'executionConclusion': 'success' if number==3 else 'failure',
                    'sourceAt': due.isoformat(), 'generatedAt': (due+timedelta(seconds=number+1)).isoformat(),
                    'publishedAt': (due+timedelta(seconds=number+2)).isoformat(),
                    'readbackAt': (due+timedelta(seconds=number+3)).isoformat()}
                events.append(event)
            entries.append({'batch': kind, 'dueAt': due.isoformat(), 'state': 'verified', 'events': events,
                'firstFailure': events[0], 'firstVerifiedAt': events[-1]['readbackAt'],
                'recoveredAt': events[-1]['observedAt'], 'recoveredReadbackAt': events[-1]['readbackAt']})
            observations.append({'batch': kind, 'dueAt': due.isoformat(), 'checkedAt': events[-1]['observedAt'],
                                 'state': 'healthy', 'runId': events[-1]['runId']})
        plain = {'schemaVersion': 1, 'coverageStartAt': start.astimezone(ledger.UTC).isoformat(),
                 'coverageEndAt': at.astimezone(ledger.UTC).isoformat(), 'checkedAt': at.astimezone(ledger.UTC).isoformat(),
                 'retentionDays': 90, 'evidenceScope': 'observed_snapshots_only',
                 'unobservedIsFailure': False, 'entries': entries}
        packed = ledger.pack_slot_ledger(plain)
        self.assertEqual(ledger.unpack_slot_ledger(packed), plain)
        self.assertGreater(packed['uncompressedBytes'], 8_000_000)
        self.assertEqual(len(entries), 4603)
        previous = dict(fixture_snapshot(at), slotLedger=packed, observations=observations)
        current = merge_observations(previous, fixture_snapshot(at))
        _, files, _ = release_payload(current)
        self.assertLess(len(files['data.json']), 4_000_000)
        self.assertEqual(current['slotLedger']['entryCount'], len(entries))
        restored = ledger.unpack_slot_ledger(current['slotLedger'])
        self.assertTrue(all(item['firstFailure'] is not None for item in restored['entries']))
        self.assertEqual(restored['coverageStartAt'], start.astimezone(ledger.UTC).isoformat())
        # On day 91 the window advances by one day; it must not reset to today.
        following = merge_observations(current, fixture_snapshot(at+timedelta(days=1)))
        self.assertEqual(following['slotLedger']['coverageStartAt'],
                         (start+timedelta(days=1)).astimezone(ledger.UTC).isoformat())
        self.assertGreater(following['slotLedger']['entryCount'], 4500)
        print(json.dumps({'ledger90DayEntries': len(entries), 'uncompressedLedgerBytes': packed['uncompressedBytes'],
                          'packedLedgerBytes': len(json.dumps(packed, separators=(',', ':')).encode()),
                          'wholeSnapshotBytes': len(files['data.json'])}))


if __name__ == '__main__':
    unittest.main()
