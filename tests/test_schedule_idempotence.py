"""All remote writes use in-memory fixtures, never production or live sources."""
import copy
from datetime import datetime, timedelta
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import publish_schedule_feed as p
import schedule_health as h
import inour_sftp as d
from test_schedule_feed import FeedRemote, seed

NOW = '2026-11-15T05:22:00+00:00'
STAMP = '2026-11-15T05:10:00+00:00'


def fresh():
    value = seed(); value['generatedAt'] = STAMP
    by_id = {s['id']:s for s in value['sources']}
    for sid in h.REQUIRED:
        s = by_id.get(sid)
        if s is None:
            # Use the collector's registered source identity, not an arbitrary URL.
            s = next(copy.deepcopy(x) for x in p.feed.SOURCES if x['id']==sid)
            value['sources'].append(s)
        s.update(state='ok', lastSuccessAt=STAMP, lastAttemptAt=STAMP, coverage={'complete':True})
    return value


class ScheduleIdempotence(unittest.TestCase):
    def test_slot_boundary_keeps_previous_hour_until_five(self):
        value = fresh()
        self.assertTrue(p.current_slot_verified(value, '2026-11-15T06:04:59Z'))
        self.assertFalse(p.current_slot_verified(value, '2026-11-15T06:05:00Z'))
        self.assertTrue(p.current_slot_verified(value, NOW))

    def test_stale_source_cannot_be_hidden_by_fresh_generated_at(self):
        value = fresh(); value['sources'][0]['lastSuccessAt']='2026-11-15T04:50:00Z'
        self.assertFalse(p.current_slot_verified(value, NOW))

    def test_invalid_future_naive_and_missing_time_are_not_current(self):
        for stamp in (None,'bad','2026-11-15T05:10:00','2026-11-15T06:10:00Z'):
            value=fresh();value['generatedAt']=stamp
            self.assertFalse(p.current_slot_verified(value,NOW))
        self.assertFalse(p.current_slot_verified(fresh(),'bad'))

    def test_partial_source_is_not_current(self):
        value=fresh();value['sources'][0]['state']='partial'
        self.assertFalse(p.current_slot_verified(value,NOW))

    def test_same_slot_skips_collection_and_feed_write_without_restamping(self):
        remote=FeedRemote()
        with patch.object(p.feed,'stamp',return_value=NOW):
            first=p.publish(remote,lambda **kw:fresh())
            self.assertTrue(first['verifiedReadback'])
            raw=remote.files[p.path('current.json')];writes=len(remote.writes)
            collector=Mock(side_effect=AssertionError('Duplicate collection'))
            second=p.publish(remote,collector)
        collector.assert_not_called()
        self.assertEqual(second['status'],'already_current')
        self.assertTrue(second['verifiedReadback']);self.assertFalse(second['feedWritten'])
        self.assertEqual(second['generatedAt'],STAMP)
        self.assertNotIn('publishedAt',second)
        self.assertEqual(raw,remote.files[p.path('current.json')])
        self.assertTrue(all(path==p.path('.lock') for path in remote.writes[writes:]))

    def test_new_slot_collects_once(self):
        remote=FeedRemote()
        with patch.object(p.feed,'stamp',return_value=NOW):p.publish(remote,lambda **kw:fresh())
        collector=Mock(return_value=fresh())
        with patch.object(p.feed,'stamp',return_value='2026-11-15T06:11:00Z'):
            report=p.publish(remote,collector)
        collector.assert_called_once();self.assertEqual(report['status'],'published')

    def test_foreign_lock_is_never_removed_even_when_current(self):
        remote=FeedRemote()
        with patch.object(p.feed,'stamp',return_value=NOW):p.publish(remote,lambda **kw:fresh())
        remote.files[p.path('.lock')]=b'foreign'
        with patch.object(p.feed,'stamp',return_value=NOW),self.assertRaises(d.Stop):
            p.publish(remote,Mock())
        self.assertEqual(remote.files[p.path('.lock')],b'foreign')

    def test_deployment_lock_refuses_writes(self):
        remote=FeedRemote();remote.files[d.ROOT+'/.deploy-lock']=b'foreign'
        with self.assertRaises(d.Stop):p.publish(remote,Mock())
        self.assertFalse(remote.writes)

    def test_noop_needs_explicit_readback_in_health(self):
        for readback,expected in ((True,True),(False,False)):
            with tempfile.TemporaryDirectory() as tmp, patch.object(h,'Path',side_effect=lambda name:Path(tmp)/name):
                report={'status':'already_current','verifiedReadback':readback,'collectionHealth':{'state':'complete'}}
                (Path(tmp)/'schedule-publication.json').write_text(json.dumps(report))
                self.assertEqual(h.main(),0 if expected else 1)
                self.assertEqual(json.loads((Path(tmp)/'schedule-health.json').read_text())['verified'],expected)

if __name__=='__main__':unittest.main()
