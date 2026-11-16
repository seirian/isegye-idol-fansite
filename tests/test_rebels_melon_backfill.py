from copy import deepcopy
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch
import json,sys,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import rebels_melon_backfill as b
AT=b.END+timedelta(minutes=1)

def sample():
    return {'generatedAt':'2026-11-16T00:00:00+00:00','providers':{'untouched':True},
            'tracks':{'other':{'sentinel':[1,2,3]},'rebels':{'melon':{'trackId':b.TRACK,'albumId':b.ALBUM},
                       'charts':{k:[] for k in b.KINDS},'youtube':{'sentinel':True}}}}

class BackfillTests(unittest.TestCase):
    def test_scoped_idempotent_no_clock_changes(self):
        data=sample();old=deepcopy(data);r=b.apply(data,at=AT)
        self.assertGreater(r['addedPoints'],100)
        self.assertEqual(data['tracks']['other'],old['tracks']['other'])
        self.assertEqual(data['providers'],old['providers'])
        self.assertEqual(data['generatedAt'],old['generatedAt'])
        once=deepcopy(data);r=b.apply(data,at=AT);self.assertEqual(data,once);self.assertEqual(r['addedPoints'],0)
    def test_release_first_rank_and_utc_conversion(self):
        data=sample();b.apply(data,at=AT)
        for k,rank in [('melon_top100',97),('melon_hot100',11)]:
            p=next(p for p in data['tracks']['rebels']['charts'][k] if p['at']=='2026-11-09T10:00:00+00:00')
            self.assertEqual(p['rank'],rank)
    def test_existing_valid_conflict_never_overwritten(self):
        data=sample();p={'at':'2026-11-09T19:00:00+09:00','trackId':b.TRACK,'rank':99,'status':'ranked'}
        data['tracks']['rebels']['charts']['melon_top100']=[p]
        r=b.apply(data,at=AT);self.assertEqual(len(r['conflicts']),1)
        self.assertIn(p,data['tracks']['rebels']['charts']['melon_top100'])
    def test_errors_can_be_replaced_by_actual_evidence(self):
        data=sample();data['tracks']['rebels']['charts']['melon_top100']=[{'at':'2026-11-09T10:00:00+00:00','trackId':b.TRACK,'rank':None,'status':'error'}]
        b.apply(data,at=AT);self.assertEqual(next(p for p in data['tracks']['rebels']['charts']['melon_top100'] if p['at']=='2026-11-09T10:00:00+00:00')['rank'],97)
    def test_wrong_identity_refused(self):
        data=sample();data['tracks']['rebels']['melon']['trackId']='1'
        with self.assertRaises(ValueError):b.apply(data,at=AT)
    def test_no_hot100_rank_in_unpublished_hours(self):
        data=sample();b.apply(data,at=AT)
        self.assertFalse(any(2<=b.clock(p['at']).astimezone(b.KST).hour<=6 for p in data['tracks']['rebels']['charts']['melon_hot100']))
    def test_future_and_expired_backfill(self):
        with self.assertRaises(ValueError):b.apply(sample(),at=b.END-timedelta(seconds=1))
        data=sample();r=b.apply(data,at=b.END+timedelta(days=31));self.assertEqual(r['addedPoints'],0)
    def test_duplicate_existing_timestamps_refused(self):
        data=sample();p={'at':'2026-11-09T10:00:00+00:00','trackId':b.TRACK,'rank':97,'status':'ranked'}
        data['tracks']['rebels']['charts']['melon_top100']=[p,dict(p,at='2026-11-09T19:00:00+09:00')]
        with self.assertRaises(ValueError):b.apply(data,at=AT)
    def test_dataset_bad_rank_and_unsupported_source_refused(self):
        data,_=b.load_dataset()
        for mutate in [lambda d:d['charts']['melon_top100']['ranked'].append([1,0]),lambda d:d['charts']['melon_top100'].update(source='https://invalid.example/')]:
            bad=deepcopy(data);mutate(bad)
            with tempfile.TemporaryDirectory() as tmp:
                p=Path(tmp)/'bad.json';p.write_text(json.dumps(bad))
                with self.assertRaises(ValueError):b.load_dataset(p)
    def test_history_mirrors_match(self):
        data=sample();b.apply(data,at=AT)
        item=data['tracks']['rebels']
        for k in b.KINDS:self.assertEqual(item['charts'][k],item['melon'][k.replace('melon_','')+'History'])
    def test_remote_patch_and_second_run_noop(self):
        import album_runtime as runtime
        from test_albums_daily import remote,complete_data
        r=remote();
        from test_schedule_feed import OLD
        r.files[runtime.d.ROOT+'/_isegye_releases/'+OLD+'/src/app.js']='albumHistoricalReference 과거 기록 출처: 가이섬'.encode()
        data=complete_data();data['tracks']['rebels']['melon'].update(trackId=b.TRACK,albumId=b.ALBUM)
        data['tracks']['rebels']['charts']={k:[] for k in b.KINDS}
        raw=json.dumps(data).encode();r.mkdir(runtime.DIR);r.new(runtime.path('.owner'),runtime.OWNER);r.new(runtime.path('current.json'),raw)
        real=b.apply
        with patch.object(b,'apply',side_effect=lambda d:real(d,at=AT)):
            report=b.patch_remote(r);self.assertTrue(report['verifiedReadback']);self.assertEqual(r.read(runtime.path('previous.json')),raw)
            after=r.read(runtime.path('current.json'));report2=b.patch_remote(r)
        self.assertEqual(report2['status'],'already_applied');self.assertEqual(r.read(runtime.path('current.json')),after)
        self.assertNotIn(runtime.path('.lock'),r.files)
        for path in r.writes:self.assertTrue(path.startswith(runtime.DIR+'/'))
    def test_remote_foreign_lock_preserved(self):
        import album_runtime as runtime
        from test_albums_daily import remote
        r=remote();
        from test_schedule_feed import OLD
        r.files[runtime.d.ROOT+'/_isegye_releases/'+OLD+'/src/app.js']='albumHistoricalReference 과거 기록 출처: 가이섬'.encode()
        r.mkdir(runtime.DIR);r.new(runtime.path('.owner'),runtime.OWNER);r.new(runtime.path('.lock'),b'foreign')
        with self.assertRaises(runtime.d.Stop):b.patch_remote(r)
        self.assertEqual(r.read(runtime.path('.lock')),b'foreign')

if __name__=='__main__':unittest.main()
