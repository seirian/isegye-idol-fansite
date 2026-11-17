from pathlib import Path
from datetime import datetime, timezone, timedelta
from unittest.mock import patch
import copy, json, sys, unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import collect_album_peak_fallback as c
import collect_album_records as records

class FallbackTests(unittest.TestCase):
 def setUp(self):
  self.m={'state':'ok','trackId':'36710003','albumId':'11308283','title':'KIDDING','album':'KIDDING','artist':'이세계아이돌'}
  self.song={'platform':'melon','id':'36710003','name':'KIDDING','album':{'platform':'melon','id':'11308283','name':'KIDDING'},'artists':[{'name':'이세계아이돌 (ISEGYE IDOL)'}],'lyrics':'NEVER_EXPORT_LYRICS'}
  self.entries=[{'chart':chart,'type':'PEAK_RANKING','score':rank} for chart,rank in zip(c.CHARTS,[6,2,2,1,41,1,1])]
  self.when=datetime.now(timezone.utc).isoformat()
 def page(self):return '<script id="__NEXT_DATA__" type="application/json">'+json.dumps({'props':{'pageProps':{'song':self.song,'records':self.entries}}})+'</script>'
 def parse(self,body=None):return c.parse_reference(body or self.page(),self.m,self.m['trackId'],self.when)
 def test_seven_separate_charts(self):
  p=self.parse();self.assertEqual(len(p['records']),7);self.assertEqual(p['records']['top100']['rank'],6);self.assertEqual(p['records']['hot100_30']['rank'],1);self.assertEqual(p['records']['daily']['rank'],41)
 def test_facts_only_and_real_source(self):
  p=self.parse();s=json.dumps(p);self.assertNotIn('NEVER_EXPORT_LYRICS',s);self.assertNotIn('<script',s);self.assertEqual(p['source'],c.source_url(self.m['trackId']));self.assertEqual(p['sourceType'],'guyso_observed_peaks')
 def test_dates_are_not_borrowed_from_legacy_or_recent_trends(self):
  self.entries[0]['time']='2026-11-09T18:00:00';self.assertTrue(all(v['date'] is None for v in self.parse()['records'].values()))
 def test_exact_melon_id(self):
  self.song['id']='1'
  with self.assertRaises(ValueError):self.parse()
 def test_exact_album_id(self):
  self.song['album']['id']='1'
  with self.assertRaises(ValueError):self.parse()
 def test_platform_identity(self):
  self.song['platform']='genie'
  with self.assertRaises(ValueError):self.parse()
 def test_same_title_different_artist_rejected(self):
  self.song['artists'][0]['name']='다른 가수'
  with self.assertRaises(ValueError):self.parse()
 def test_different_title_rejected(self):
  self.song['name']='KIDDING (Inst.)'
  with self.assertRaises(ValueError):self.parse()
 def test_multiple_artists_rejected(self):
  self.song['artists'].append({'name':'unverified'})
  with self.assertRaises(ValueError):self.parse()
 def test_daily_above100_valid(self):
  self.entries[4]['score']=527;self.assertEqual(self.parse()['records']['daily']['rank'],527)
 def test_invalid_rank_values_refused(self):
  for value in (101,0,-1,True,'6',None,3.5):
   self.entries[0]['score']=value
   with self.assertRaises(ValueError):self.parse()
 def test_other_statistics_are_not_ranks(self):
  self.entries=[{'chart':'MELON_TOP100_CHART','type':'PEAK_COUNT1','score':90000}];p=self.parse();self.assertTrue(all(v['rank'] is None for v in p['records'].values()))
 def test_missing_record_not_zero_or_chart_out(self):
  self.entries.pop(0);self.assertIsNone(self.parse()['records']['top100']['rank'])
 def test_duplicate_peak_rejected(self):
  self.entries.append(self.entries[0])
  with self.assertRaises(ValueError):self.parse()
 def test_duplicate_script_rejected(self):
  with self.assertRaises(ValueError):self.parse(self.page()+self.page())
 def test_url_allowlist_and_legacy_blocked(self):
  self.assertEqual(records.allowed(c.source_url(self.m['trackId'])),c.source_url(self.m['trackId']))
  for url in ('http://xn--o39an51b2re.com/song/melon/36710003','https://xn--o39an51b2re.com/song/melon/36710003?x=1','https://xn--o39an51b2re.com.evil.test/song/melon/36710003','https://u:p@xn--o39an51b2re.com/song/melon/36710003','https://isegyechart.com/song/799','https://isegyechart.com/api/song-selector-list'):
   self.assertFalse(c.allowed_source(url))
   with self.assertRaises(ValueError):records.allowed(url)
 def test_future_dates_and_missing_digest_refused(self):
  p=self.parse()
  for value in ({'checkedAt':'2099-01-01T00:00:00Z'},{'responseSha256':''},{'checkedAt':'2026-11-09T00:00:00'},{'sourceType':'isegyechart_observed_peaks'},{'trackId':'1'},{'albumId':'1'}):self.assertFalse(c.reusable({**p,**value},self.m))
 def test_borrowed_achievement_date_refused(self):
  p=self.parse();p['records']['top100']['date']='2023-08-19';self.assertFalse(c.reusable(p,self.m))
 def test_cache_skips_fetch_and_keeps_checked_time(self):
  old=self.parse();d={'tracks':{'fixture':{'melon':self.m}}}
  with patch.object(c,'reviewed_records',return_value={}):
   r=c.collect_reference_peaks(d,{'tracks':{'fixture':{'melonPeakFallback':old}}},lambda _:self.fail('cache must not fetch'))
  self.assertEqual(r['fixture']['state'],'cached');self.assertEqual(d['tracks']['fixture']['melonPeakFallback']['checkedAt'],old['checkedAt'])
 def test_expired_source_failure_retains_only_guyso(self):
  old=self.parse();old['checkedAt']=(datetime.now(timezone.utc)-timedelta(hours=7)).isoformat();d={'tracks':{'fixture':{'melon':self.m}}}
  with patch.object(c,'reviewed_records',return_value={}):
   r=c.collect_reference_peaks(d,{'tracks':{'fixture':{'melonPeakFallback':old}}},lambda _:(_ for _ in ()).throw(TimeoutError()))
  self.assertTrue(r['fixture']['retainedVerified']);self.assertEqual(d['tracks']['fixture']['melonPeakFallback']['checkedAt'],old['checkedAt']);self.assertEqual(d['tracks']['fixture']['melonPeakFallback']['fetchState'],'error')
 def test_legacy_never_relabelled_on_failure(self):
  old=self.parse();old['sourceType']='isegyechart_observed_peaks';d={'tracks':{'fixture':{'melon':self.m}}}
  with patch.object(c,'reviewed_records',return_value={}):c.collect_reference_peaks(d,{'tracks':{'fixture':{'melonPeakFallback':old}}},lambda _:(_ for _ in ()).throw(TimeoutError()))
  self.assertNotIn('melonPeakFallback',d['tracks']['fixture'])
 def test_collection_preserves_original_daily_and_histories(self):
  d={'tracks':{'fixture':{'melon':self.m,'melonPeaks':{'dailyBestRank':38},'charts':{'sentinel':[1]}}}};old=copy.deepcopy(d)
  with patch.object(c,'reviewed_records',return_value={}):c.collect_reference_peaks(d,{},lambda u:self.page().encode())
  self.assertEqual(d['tracks']['fixture']['melonPeaks'],old['tracks']['fixture']['melonPeaks']);self.assertEqual(d['tracks']['fixture']['charts'],old['tracks']['fixture']['charts'])
 def test_reviewed_actual_scope_and_missing_four(self):
  ds=c.reviewed_records();self.assertEqual(len(ds),24);self.assertEqual(sum(v['rank'] is not None for e in ds.values() for v in e['reference']['records'].values()),164)
  self.assertEqual(ds['love-cells']['reference']['records']['top100']['rank'],19)
  self.assertTrue(all(c.reusable(e['reference'],e['identity']) for e in ds.values()))
if __name__=='__main__':unittest.main()
