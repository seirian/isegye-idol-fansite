from pathlib import Path
import sys,json,unittest,copy
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import schedule_feed as f,notice_policy as p,cafe_batch as cb,compose_schedule as ui
class CafeBatch(unittest.TestCase):
 def test_actual_backfill(self):
  rows=cb.official('2026-11-02T17:34:00Z');self.assertEqual(len(rows),14);self.assertIn(22157938,rows)
  old=json.loads((cb.ROOT/'schedule/approved-notices.json').read_text());self.assertEqual(len({r['articleId'] for r in old['notices']}),7249);self.assertEqual(len(p.archive()['notices']),len({r['articleId'] for r in p.archive()['notices']})); self.assertGreaterEqual(len(p.archive()['notices']),7263)
 def test_outside_window_and_false_zero(self):
  d=copy.deepcopy(cb.windows()[0]);d['boards']['345']['count']=0
  with self.assertRaises(ValueError): cb.validate(d)
  d=copy.deepcopy(cb.windows()[0]);d['notices'][0]['publishedAt']='2026-10-30T00:00:00Z'
  with self.assertRaises(ValueError):cb.validate(d)
 def test_idempotence_and_calendar(self):
  now='2026-11-04T00:00:00Z';fetch=lambda u: (_ for _ in ()).throw(f.FeedError('fixture'));a=f.collect(fetch=fetch,now=now);b=f.collect(previous=a,fetch=fetch,now=now)
  for key in ('news','events','forecasts'): self.assertEqual({r['id'] for r in a[key]},{r['id'] for r in b[key]});self.assertEqual(len(b[key]),len({r['id'] for r in b[key]}))
  self.assertTrue(any(r['sourceUrl'].endswith('/22157938') for r in b['news']));self.assertTrue(any(r[0]==22157938 for r in ui.history_bundle()['rows']));s=next(x for x in b['sources'] if x['id']=='cafe-agency');self.assertEqual(s['coverage']['count'],0);self.assertNotEqual(s['lastSuccessAt'],now)
  self.assertFalse(any(r.get('certainty')=='confirmed' for r in b['forecasts']));self.assertFalse(any(r['sourceId']=='fan-roundup' for r in b['events']));self.assertFalse(cb.official('2026-10-31T00:00:00Z'))
 def test_unrelated_fan_source_stays_blocked(self):
  self.assertFalse(p.is_publishable({'sourceId':'fan-roundup','sourceUrl':cb.PREFIX+'99999999'})); self.assertTrue(p.is_publishable({'sourceId':'fan-roundup','sourceUrl':cb.PREFIX+'22145101'}))
