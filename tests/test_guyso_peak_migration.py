from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
import json, sys, unittest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import migrate_guyso_peaks as m
import collect_album_peak_fallback as c

def data():
 from test_albums_daily import complete_data
 d=complete_data()
 for sid,e in c.reviewed_records().items():
  d['tracks'][sid]['melon'].update(e['identity'])
  d['tracks'][sid]['melonPeakFallback']={'sourceType':'isegyechart_observed_peaks','records':{k:{'rank':99,'date':'2026-01-01'} for k in c.LIMITS}}
 return d

class MigrationTests(unittest.TestCase):
 def test_scope_idempotence_and_actual_full_catalog(self):
  d=data();old=deepcopy(d);r=m.apply(d)
  self.assertEqual(len(r['verifiedTracks']),24);self.assertEqual(r['checkedRankCount'],164);self.assertEqual(r['unknownRankCount'],4)
  self.assertEqual(d['generatedAt'],old['generatedAt'])
  for sid,item in d['tracks'].items():
   cur=deepcopy(item);prev=deepcopy(old['tracks'][sid]);cur.pop('melonPeakFallback',None);prev.pop('melonPeakFallback',None);self.assertEqual(cur,prev)
  once=deepcopy(d);self.assertFalse(m.apply(d)['changed']);self.assertEqual(d,once)
 def test_mismatched_live_identity_refuses(self):
  d=data();d['tracks']['rebels']['melon']['trackId']='999'
  with self.assertRaises(ValueError):m.apply(d)
 def remote(self):
  import album_runtime as r
  from test_albums_daily import remote
  from test_schedule_feed import OLD
  obj=remote();obj.files[r.d.ROOT+'/_isegye_releases/'+OLD+'/src/app.js']='guyso_observed_peaks 최고 성적 출처와 확인 시각 최고 성적은 가이섬'.encode()
  obj.mkdir(r.DIR);obj.new(r.path('.owner'),r.OWNER);obj.new(r.path('current.json'),json.dumps(data()).encode());return obj
 def test_atomic_backup_readback_and_noop(self):
  import album_runtime as r
  obj=self.remote();before=obj.read(r.path('current.json'));first=m.patch_remote(obj);after=obj.read(r.path('current.json'));second=m.patch_remote(obj)
  self.assertTrue(first['verifiedReadback']);self.assertEqual(second['status'],'already_applied');self.assertEqual(obj.read(r.path('current.json')),after);self.assertEqual(obj.read(r.path('previous.json')),before);self.assertNotIn(r.path('.lock'),obj.files)
  self.assertTrue(all(p.startswith(r.DIR+'/') for p in obj.writes))
 def test_foreign_lock_not_removed(self):
  import album_runtime as r
  obj=self.remote();obj.files[r.path('.lock')]=b'foreign'
  with self.assertRaises(r.d.Stop):m.patch_remote(obj)
  self.assertEqual(obj.read(r.path('.lock')),b'foreign')
 def test_legacy_ui_refuses_publication(self):
  import album_runtime as r
  from test_schedule_feed import OLD
  obj=self.remote();obj.files[r.d.ROOT+'/_isegye_releases/'+OLD+'/src/app.js']=b'legacy UI'
  before=obj.read(r.path('current.json'))
  with self.assertRaises(r.d.Stop):m.patch_remote(obj)
  self.assertEqual(obj.read(r.path('current.json')),before)
if __name__=='__main__':unittest.main()
