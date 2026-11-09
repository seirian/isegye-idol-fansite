from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import patch
import copy, html, json, sys, unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import collect_album_peak_fallback as c
import collect_album_records as records

class FallbackTests(unittest.TestCase):
 def setUp(self):
  self.m={'state':'ok','trackId':'36710003','albumId':'11308283','title':'KIDDING','album':'KIDDING','artist':'이세계아이돌'}
  self.info={'id':799,'idMap':{'melonId':36710003},'albumIdMap':{'melonId':11308283},'name':'KIDDING','artistName':'이세계아이돌','lyrics':'NEVER_EXPORT_LYRICS'}
  self.when=datetime.now(timezone.utc).isoformat()
 def page(self,values=(6,2,2,1,41,1,1)):
  # Synthetic markup is only a parser fixture, not a displayed or saved observation.
  props=html.escape(json.dumps({'songInfo':self.info}),quote=True)
  cells=''.join(f'<div><h3>{label}</h3><span>{rank}위</span><span>23.8.19</span></div>' for label,rank in zip(c.LABELS,values))
  return f'<astro-island component-url="/FeaturedSongSelector.js" props="{props}"></astro-island><h2>멜론 최고 성적</h2>{cells}'
 def parse(self,body=None):return c.parse_reference(body or self.page(),self.m,799,self.when)
 def test_seven_separate_charts(self):
  p=self.parse();self.assertEqual(len(p['records']),7);self.assertEqual(p['records']['top100']['rank'],6);self.assertEqual(p['records']['daily']['rank'],41);self.assertEqual(p['records']['hot100']['rank'],2);self.assertEqual(p['records']['hot100_30']['rank'],1)
 def test_facts_only(self):
  p=json.dumps(self.parse());self.assertNotIn('NEVER_EXPORT_LYRICS',p);self.assertNotIn('astro-island',p);self.assertEqual(self.parse()['sourceType'],c.TYPE)
 def test_exact_melon_id(self):
  self.info['idMap']['melonId']=1
  with self.assertRaises(ValueError):self.parse()
 def test_exact_album_id(self):
  self.info['albumIdMap']['melonId']=1
  with self.assertRaises(ValueError):self.parse()
 def test_same_title_different_artist_rejected(self):
  self.info['artistName']='다른 가수'
  with self.assertRaises(ValueError):self.parse()
 def test_record_page_id(self):
  self.info['id']=828
  with self.assertRaises(ValueError):self.parse()
 def test_daily_above_100_is_valid(self):self.assertEqual(self.parse(self.page((6,2,2,1,527,1,1)))['records']['daily']['rank'],527)
 def test_hourly_over100_rejected(self):
  with self.assertRaises(ValueError):self.parse(self.page((101,2,2,1,41,1,1)))
 def test_missing_value_not_zero(self):self.assertIsNone(self.parse(self.page().replace('6위','—'))['records']['top100']['rank'])
 def test_duplicate_headings_rejected(self):
  with self.assertRaises(ValueError):self.parse(self.page()+'<div><h3>TOP100</h3>1위</div>')
 def test_future_and_bad_dates_rejected(self):
  for date in ('99.1.1','26.2.30'):
   with self.assertRaises(ValueError):self.parse(self.page().replace('23.8.19',date))
 def test_url_allowlist_is_exact(self):
  self.assertTrue(c.allowed_source(c.source_url(799)));self.assertEqual(records.allowed(c.source_url(799)),c.source_url(799))
  for url in ('http://isegyechart.com/song/799','https://isegyechart.com/song/799?x=1','https://isegyechart.com/song/799#x','https://isegyechart.com.evil.test/song/799','https://u:p@isegyechart.com/song/799','https://isegyechart.com/api/private','https://isegyechart.com/song/799/../../admin'):
   self.assertFalse(c.allowed_source(url))
   with self.assertRaises(ValueError):records.allowed(url)
 def test_cache_wrong_identity_and_scope_rejected(self):
  for update in ({'trackId':'1'},{'sourceType':'melon_original_song_info'},{'source':'https://isegyechart.com/song/828'},{'checkedAt':'2099-01-01T00:00:00Z'}):
   self.assertFalse(c.reusable({**self.parse(),**update},self.m,799))
 def test_failure_retains_checked_time(self):
  old=self.parse();result={'tracks':{'kidding':{'melon':self.m}}}
  def failed(url):raise TimeoutError()
  report=c.collect_reference_peaks(result,{'tracks':{'kidding':{'melonPeakFallback':old}}},failed)
  now=result['tracks']['kidding']['melonPeakFallback'];self.assertEqual(now['checkedAt'],old['checkedAt']);self.assertEqual(now['fetchState'],'error');self.assertTrue(report['kidding']['retainedVerified'])
 def test_old_three_metric_cache_is_not_accepted(self):
  old=self.parse();old.pop('records');old['ranks']={'top100':6,'hot100':2,'realtime':2};self.assertFalse(c.reusable(old,self.m,799))
 def test_collection_does_not_modify_original_daily(self):
  origin={'sourceType':'melon_original_song_info','dailyBestRank':41};result={'tracks':{'kidding':{'melon':self.m,'melonPeaks':copy.deepcopy(origin)}}}
  c.collect_reference_peaks(result,{},lambda url:self.page().encode());self.assertEqual(result['tracks']['kidding']['melonPeaks'],origin);self.assertEqual(result['tracks']['kidding']['melonPeakFallback']['records']['top100']['rank'],6)
if __name__=='__main__':unittest.main()
