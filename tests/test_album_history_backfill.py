from copy import deepcopy
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch
import json,sys,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import album_history_backfill as b
from album_releases import load_catalog
AT=b.CUTOFF+timedelta(minutes=1);DIGEST='a'*64

def fixture():
    tracks={}
    for i,s in enumerate(load_catalog()['songs']):
        if s.get('dateKind')=='영상 공개일':continue
        track=str(100000+i);album=str(200000+i);release=s['date']+'T18:00:00+09:00';start=b.clock(release);h=b.hour(start);charts={}
        for kind,slug in b.KINDS.items():
            end=min(b.CUTOFF,start+timedelta(days=101)) if kind=='melon_hot100' else b.CUTOFF
            charts[kind]={'source':b.BASE+'/chart/melon/'+slug+'/trend/ranking/'+track,'scannedThrough':end.isoformat(),'points':[[h+1,75],[h+2,60]],'out':[],'pages':[]}
        tracks[s['id']]={'trackId':track,'albumId':album,'title':s['title'],'album':s['album'],'releaseAt':release,'identitySource':b.BASE+'/song/melon/'+track,'identitySha256':'b'*64,'charts':charts}
    return {'schemaVersion':1,'sourceType':'guyso_public_historical','cutoffAt':b.CUTOFF.isoformat(),'tracks':tracks,'excluded':[]}
def sample(ds):
    return {'schemaVersion':1,'generatedAt':'2026-11-16T00:00:00+00:00','providers':{'untouched':True},'tracks':{**{s:{'melon':{'trackId':r['trackId'],'albumId':r['albumId']},'charts':{k:[] for k in b.KINDS},'youtube':{'sentinel':1}} for s,r in ds['tracks'].items()},'video-only':{'sentinel':[1,2,3]}}}
def apply(d,ds,**kw):return b.apply(d,dataset=ds,digest=DIGEST,at=kw.pop('at',AT),**kw)

class CatalogHistoryTests(unittest.TestCase):
    def test_exact_catalog_and_identity(self):
        ds=fixture();self.assertEqual(len(ds['tracks']),24);b.validate_dataset(ds);ds['tracks']['rewind']['identitySource']='https://evil.example'
        with self.assertRaises(ValueError):b.validate_dataset(ds)
    def test_old_history_is_retained_without_expanding_rolling(self):
        ds=fixture();d=sample(ds);r=apply(d,ds)
        self.assertEqual(d['tracks']['rewind']['charts']['melon_top100'],[])
        self.assertEqual(len(d['tracks']['rewind'][b.ARCHIVE]['charts']['melon_top100']['points']),2);self.assertEqual(r['addedHistoricalSlots'],96)
    def test_scope_idempotence_and_original_clocks(self):
        ds=fixture();d=sample(ds);old=deepcopy(d);apply(d,ds);once=deepcopy(d);r=apply(d,ds)
        self.assertEqual(d,once);self.assertEqual(r['addedHistoricalSlots'],0);self.assertEqual(r['rollingAdded'],0)
        self.assertEqual(d['generatedAt'],old['generatedAt']);self.assertEqual(d['providers'],old['providers']);self.assertEqual(d['tracks']['video-only'],old['tracks']['video-only'])
    def test_existing_conflicts_win_and_survive_rolling_retention(self):
        ds=fixture();d=sample(ds);r=ds['tracks']['rewind'];h=r['charts']['melon_top100']['points'][0][0]
        p={'at':b.datetime.fromtimestamp(h*3600,b.UTC).isoformat(),'rank':99,'status':'ranked','trackId':r['trackId']}
        d['tracks']['rewind']['charts']['melon_top100']=[p];result=apply(d,ds);self.assertEqual(result['conflicts'][0]['existingRank'],99)
        previous=deepcopy(d);d['tracks']['rewind']['charts']['melon_top100']=[];d['tracks']['rewind'].pop(b.ARCHIVE)
        apply(d,ds,previous=previous,at=AT+timedelta(days=90));self.assertIn([h,99,1],d['tracks']['rewind'][b.ARCHIVE]['charts']['melon_top100']['points'])
    def test_current_verified_value_supersedes_retained_native_conflict(self):
        ds=fixture();d=sample(ds);r=ds['tracks']['rewind'];h=r['charts']['melon_top100']['points'][0][0]
        p={'at':b.datetime.fromtimestamp(h*3600,b.UTC).isoformat(),'rank':99,'status':'ranked','trackId':r['trackId']}
        d['tracks']['rewind']['charts']['melon_top100']=[p];apply(d,ds);previous=deepcopy(d);d['tracks']['rewind']['charts']['melon_top100'][0]['rank']=75
        apply(d,ds,previous=previous);self.assertIn([h,75,0],d['tracks']['rewind'][b.ARCHIVE]['charts']['melon_top100']['points'])
    def test_unknown_slots_are_not_invented(self):
        ds=fixture();d=sample(ds);apply(d,ds);c=d['tracks']['rewind'][b.ARCHIVE]['charts']['melon_top100']
        self.assertGreater(c['unverifiedHourlySlots'],40000);self.assertFalse(any(p[1] is None for p in c['points']))
    def test_out_requires_complete_timestamp_matched_chart(self):
        ds=fixture();r=ds['tracks']['rebels'];h=b.hour(b.clock(r['releaseAt']));c=r['charts']['melon_top100']
        c['out']=[{'hour':h,'source':b.BASE+'/chart/melon/top100/20261109/18','verifiedFullChartSize':100,'responseSha256':'b'*64}]
        b.validate_dataset(ds);d=sample(ds);apply(d,ds);self.assertIn([h,None,0],d['tracks']['rebels'][b.ARCHIVE]['charts']['melon_top100']['points'])
        c['out'][0]['verifiedFullChartSize']=99
        with self.assertRaises(ValueError):b.validate_dataset(ds)
    def test_invalid_rank_and_wrong_release_and_future_refused(self):
        for kind in ['rank','release','url']:
            ds=fixture()
            if kind=='rank':ds['tracks']['rewind']['charts']['melon_top100']['points'][0][1]=0
            elif kind=='release':ds['tracks']['rewind']['releaseAt']='2022-12-17T18:00:00+09:00'
            else:ds['tracks']['rewind']['charts']['melon_top100']['source']='https://evil.example'
            with self.assertRaises(ValueError):b.validate_dataset(ds)
        ds=fixture()
        with self.assertRaises(ValueError):apply(sample(ds),ds,at=b.CUTOFF-timedelta(seconds=1))
    def test_live_identity_mismatch_refused_or_reported(self):
        ds=fixture();d=sample(ds);d['tracks']['rewind']['melon']['trackId']='999'
        with self.assertRaises(ValueError):apply(d,ds)
        r=apply(d,ds,strict=False);self.assertIn('rewind',r['skipped']);self.assertNotIn(b.ARCHIVE,d['tracks']['rewind'])
    def test_recent_errors_repaired_and_mirrors_match(self):
        ds=fixture();d=sample(ds);r=ds['tracks']['rebels'];h=r['charts']['melon_top100']['points'][0][0]
        d['tracks']['rebels']['charts']['melon_top100']=[{'at':b.datetime.fromtimestamp(h*3600,b.UTC).isoformat(),'trackId':r['trackId'],'rank':None,'status':'error'}]
        apply(d,ds);self.assertEqual(d['tracks']['rebels']['charts']['melon_top100'][0]['rank'],75)
        self.assertEqual(d['tracks']['rebels']['charts']['melon_top100'],d['tracks']['rebels']['melon']['top100History'])
    def test_transport_bound_and_dataset_integrity(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'data.json';path.write_text(json.dumps(fixture()))
            with self.assertRaises(ValueError):b.load_dataset(path)
    def test_duplicate_existing_hours_refused(self):
        ds=fixture();d=sample(ds);r=ds['tracks']['rebels'];h=r['charts']['melon_top100']['points'][0][0]
        p={'at':b.datetime.fromtimestamp(h*3600,b.UTC).isoformat(),'trackId':r['trackId'],'rank':75,'status':'ranked'};d['tracks']['rebels']['charts']['melon_top100']=[p,p]
        with self.assertRaises(ValueError):apply(d,ds)
    def test_remote_atomic_publication_and_noop(self):
        import album_runtime as runtime
        from test_albums_daily import remote,complete_data
        from test_schedule_feed import OLD
        ds=fixture();r=remote();d=complete_data()
        for sid,row in ds['tracks'].items():d['tracks'][sid]['melon'].update(trackId=row['trackId'],albumId=row['albumId'])
        r.files[runtime.d.ROOT+'/_isegye_releases/'+OLD+'/src/app.js']='albumArchiveWindow 과거 기록 출처: 가이섬'.encode()
        r.mkdir(runtime.DIR);r.new(runtime.path('.owner'),runtime.OWNER);raw=json.dumps(d).encode();r.new(runtime.path('current.json'),raw)
        with patch.object(b,'load_dataset',return_value=(ds,DIGEST)):
            first=b.patch_remote(r);published=r.read(runtime.path('current.json'));second=b.patch_remote(r)
        self.assertTrue(first['verifiedReadback']);self.assertEqual(second['status'],'already_applied');self.assertEqual(r.read(runtime.path('current.json')),published)
        self.assertEqual(r.read(runtime.path('previous.json')),raw);self.assertNotIn(runtime.path('.lock'),r.files);self.assertTrue(all(x.startswith(runtime.DIR+'/') for x in r.writes))
    def test_remote_missing_attribution_or_foreign_lock_refused(self):
        import album_runtime as runtime
        from test_albums_daily import remote
        from test_schedule_feed import OLD
        r=remote()
        with self.assertRaises(runtime.d.Stop):b.patch_remote(r)
        r.files[runtime.d.ROOT+'/_isegye_releases/'+OLD+'/src/app.js']='albumArchiveWindow 과거 기록 출처: 가이섬'.encode()
        r.mkdir(runtime.DIR);r.new(runtime.path('.owner'),runtime.OWNER);r.new(runtime.path('.lock'),b'foreign')
        with self.assertRaises(runtime.d.Stop):b.patch_remote(r)
        self.assertEqual(r.read(runtime.path('.lock')),b'foreign')
if __name__=='__main__':unittest.main()
