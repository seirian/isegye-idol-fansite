import copy
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import playground_bank as bank
import playground_pipeline as pipeline
import playground_growth_alert as alert
import collect_playground as collector
import publish_playground_bank as publisher
from test_playground_bank import Remote, proposal
from batch_monitor_snapshot import row_state


class Pipeline(unittest.TestCase):
    def setUp(self):
        self.now = datetime.now(timezone.utc)

    def assemble(self, old=None, now=None):
        now = now or self.now
        catalog = old['catalog'] if old else bank.seed()
        used = old.get('addedToday', 0) if old and old['batchDate'] == now.astimezone(bank.KST).date().isoformat() else 0
        proposals, stats = pipeline.reserve_proposals(catalog, now, max(0, pipeline.DAILY_TARGET-used))
        feed, ids = bank.assemble(old, proposals, now)
        _, remaining = pipeline.reserve_proposals(feed['catalog'], now, 0)
        feed['growth'] = pipeline.growth_report(old, feed, ids, remaining['readyBefore'], now, {})
        return feed, ids

    def test_reserve_is_reviewed_and_unique_with_four_topics(self):
        index = pipeline.reserve_index()
        self.assertEqual(len(index), 68)
        self.assertEqual({x['question']['category'] for x in index.values()}, set(bank.seed()['categories']))
        self.assertEqual(len({x['question']['provenance']['factKey'] for x in index.values()}), len(index))
        for entry in index.values():
            self.assertLessEqual(entry['source']['checkedAt'], '2026-11-24')
            self.assertNotIn('당일 다시 대조', entry['source']['note'])

    def test_first_day_balanced_next_day_eligibility_and_immutable_seed(self):
        feed, ids = self.assemble()
        self.assertEqual(len(ids), 4)
        self.assertEqual(feed['catalog']['questions'][:80], bank.seed()['questions'])
        self.assertEqual({q['category'] for q in feed['catalog']['questions'][80:]}, set(bank.seed()['categories']))
        for q in feed['catalog']['questions'][80:]:
            self.assertEqual(q['eligibleFrom'], (self.now.astimezone(bank.KST).date()+timedelta(days=1)).isoformat())
        bank.validate_feed(feed)

    def test_repeat_does_not_double_count_or_use_more_daily_budget(self):
        first, _ = self.assemble()
        repeated, ids = self.assemble(first)
        self.assertEqual(ids, [])
        self.assertEqual(repeated['sha256'], first['sha256'])
        self.assertEqual(repeated['growth']['todayAdded'], 4)
        self.assertEqual(len(repeated['growth']['history']), 1)
        self.assertEqual(repeated['growth']['lastAdditionAt'], first['growth']['lastAdditionAt'])
        self.assertEqual(repeated['growth']['consecutiveZeroDays'], 0)

    def test_next_day_adds_new_distinct_facts(self):
        first, one = self.assemble()
        second, two = self.assemble(first, self.now+timedelta(days=1))
        self.assertEqual(len(two), 4)
        self.assertFalse(set(one) & set(two))
        self.assertEqual(second['catalog']['questions'][:84], first['catalog']['questions'])

    def test_expired_supply_is_not_infinite_or_reported_as_growth(self):
        old = None; all_ids = []
        for day in range(20):
            old, ids = self.assemble(old, self.now+timedelta(days=day))
            all_ids += ids
        self.assertEqual(len(all_ids), 68)
        self.assertEqual(len(set(all_ids)), 68)
        self.assertEqual(old['growth']['readyCount'], 0)
        self.assertEqual(old['growth']['consecutiveZeroDays'], 3)
        self.assertEqual(old['growth']['state'], 'stalled')
        self.assertIn('reserve_low', old['growth']['alerts'])

    def test_no_fake_historical_streak_and_no_repeat_day_inflation(self):
        f, _ = bank.assemble(None, [], self.now)
        g = pipeline.growth_report(None, f, [], 68, self.now, {})
        self.assertEqual(g['consecutiveZeroDays'], 1)
        self.assertIsNone(g['lastAdditionAt'])
        f['growth'] = g
        again = pipeline.growth_report(f, f, [], 68, self.now, {})
        self.assertEqual(again['consecutiveZeroDays'], 1)
        self.assertEqual(len(again['history']), 1)

    def test_forged_reserve_answer_source_and_unknown_item_rejected(self):
        feed, _ = self.assemble()
        for change in ('answer', 'source', 'unknown'):
            f = copy.deepcopy(feed); q = f['catalog']['questions'][-1]
            if change == 'answer': q['answer'] = (q['answer']+1)%4
            if change == 'source': f['catalog']['sources'][q['sources'][0]]['url'] = 'https://example.org/fake'
            if change == 'unknown': q['id'] = 'reserve-not-approved'
            f['sha256'] = bank.digest(f['catalog'])
            with self.assertRaises(ValueError): bank.validate_feed(f)

    def test_existing_video_does_not_reappear_as_another_question(self):
        cat = bank.seed(); entry = next(e for e in pipeline.reserve_index().values() if e['question']['provenance'].get('videoId'))
        vid = entry['question']['provenance']['videoId']
        cat['questions'].append({'id':'existing-video','stem':'다른 질문','provenance':{'videoId':vid}})
        proposed, _ = pipeline.reserve_proposals(cat, self.now, 500)
        self.assertNotIn(entry['question']['id'], [q['id'] for q, _, _ in proposed])

    def test_collector_uses_reserve_when_every_live_source_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); work = root/'state'; work.mkdir()
            row = {'videoId':'12345678901','factKey':'f'*64}
            with patch.object(collector, 'ROOT', root), patch.object(collector, 'WORK', work), \
                 patch.object(collector, 'rows', return_value=[row]), \
                 patch.object(collector, 'verify', side_effect=ValueError('unavailable')), \
                 patch.object(collector, 'discover_references', return_value=({}, [])), \
                 patch.object(collector, 'check_reference_bodies', return_value=({}, [])):
                self.assertEqual(collector.collect(self.now), 0)
                report = json.loads((root/'playground-discovery.json').read_text())
                self.assertEqual(report['automaticAdded'], 0)
                self.assertEqual(report['reserveAdded'], 4)
                self.assertEqual(report['candidateCounts']['deferred'], 1)
                self.assertFalse(report['communityAutoPublished'])

    def test_live_and_reserve_do_not_publish_same_video_in_one_run(self):
        entry=next(e for e in pipeline.reserve_index().values() if e['question']['provenance'].get('videoId'))
        vid=entry['question']['provenance']['videoId']
        row={'videoId':vid,'title':'검증된 공식 영상','type':'cover','members':['ine'],'factKey':'f'*64}
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); work=root/'state'; work.mkdir()
            with patch.object(collector,'ROOT',root), patch.object(collector,'WORK',work), \
                 patch.object(collector,'rows',return_value=[row]), \
                 patch.object(collector,'verify',return_value={'member':'ine'}), \
                 patch.object(collector,'discover_references',return_value=({},[])), \
                 patch.object(collector,'check_reference_bodies',return_value=({},[])):
                self.assertEqual(collector.collect(self.now),0)
                value=json.loads((work/'candidate.json').read_text())
                ids=[q['id'] for q in value['catalog']['questions']]
                self.assertNotIn(entry['question']['id'],ids)
                self.assertEqual(sum(q.get('provenance',{}).get('videoId')==vid for q in value['catalog']['questions']),1)

    def test_real_collector_retries_do_not_call_public_sources_again(self):
        first, _ = self.assemble()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); work=root/'state'; work.mkdir()
            (work/'previous.json').write_bytes(bank.encoded(first))
            with patch.object(collector,'ROOT',root), patch.object(collector,'WORK',work), \
                 patch.object(collector,'rows',return_value=[]), \
                 patch.object(collector,'verify') as verify, patch.object(collector,'discover_references') as discover:
                self.assertEqual(collector.collect(self.now),0)
                verify.assert_not_called(); discover.assert_not_called()
                report=json.loads((root/'playground-discovery.json').read_text())
                self.assertEqual(report['totalAdded'],0)
                self.assertEqual(report['growth']['todayAdded'],4)

    def test_readback_and_rollback_keep_growth_with_catalog(self):
        feed, ids = self.assemble()
        report = {'status':'checked','generatedAt':feed['generatedAt'],'previousSha256':None,
                  'automaticAdded':0,'reserveAdded':4,'totalAdded':4,'referenceWarnings':[]}
        remote=Remote(); result=publisher.publish(remote,feed,report,{})
        self.assertEqual(result['added'],4); self.assertEqual(result['reserveAdded'],4)
        self.assertEqual(result['growth'],feed['growth']); self.assertTrue(result['verifiedReadback'])
        stored=json.loads(remote.read(publisher.path('current.json')))
        bank.validate_feed(stored); self.assertEqual(stored['growth'],feed['growth'])

    def test_content_alert_is_separate_from_successful_publication(self):
        row={'listingComplete':True,'dataState':'healthy','run':{'status':'completed','conclusion':'success'},'growth':{'alerts':['reserve_low']}}
        self.assertEqual(row_state(row),'attention'); self.assertEqual(row['dataState'],'healthy')

    def test_notification_is_deduplicated_and_only_verified_recovery_closes(self):
        pub={'status':'published','verifiedReadback':True,'growth':{'schemaVersion':1,'alerts':['stalled'],'todayAdded':0,'readyCount':0,'consecutiveZeroDays':3}}
        calls=[]
        def gh(*args):
            calls.append(args)
            return json.dumps([{'number':42,'title':alert.TITLE}]) if args[:2]==('issue','list') else ''
        self.assertEqual(alert.reconcile(pub,gh),'unchanged'); self.assertEqual(len(calls),1)
        pub['growth'].update(alerts=[],todayAdded=4)
        self.assertEqual(alert.reconcile(pub,gh),'resolved'); self.assertEqual(calls[-1][:2],('issue','close'))
        calls.clear(); pub['verifiedReadback']=False
        self.assertEqual(alert.reconcile(pub,gh),'unverified_no_change'); self.assertEqual(calls,[])

    def test_editorial_manifest_changes_text_only(self):
        manifest=pipeline.editorial_manifest()
        self.assertEqual(len(manifest['edits']),22)
        self.assertTrue(all(set(e['after']) <= {'stem','hint','explanation'} for e in manifest['edits']))


if __name__ == '__main__': unittest.main()
