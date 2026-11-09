from pathlib import Path
import sys, copy, json, unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import collect_album_melon_record as c
class OriginalMelonTests(unittest.TestCase):
 def setUp(self):
  self.m={'state':'ok','trackId':'603093102','albumId':'14547786','title':'고양이가 세상을 구한다!','album':'NO CAT, NO LIFE!','artist':'고세구'}
  self.when='2026-11-09T11:56:00+00:00'
  self.raw={'response':{'RESULTCODE':'0','RESPONSE':'songInfo','SONGINFO':{'SONGID':self.m['trackId'],'ALBUMID':self.m['albumId'],'SONGNAME':self.m['title'],'ALBUMNAME':self.m['album'],'ARTISTLIST':[{'ARTISTNAME':'고세구'}],'PLAYTIME':'175'},'SONGACHIEVEMENTINFO':{'BESTRANK':'527','BESTRANKDATE':'2026.09.28','YESTERDAYCHARTRANK':'1001','HASCHARTINHISTORY':'Y','GUIDE':'차트 기록 기준일 - 일간 차트: 14.01.01 이후 기록'},'LYRIC':'MUST NOT COPY','STREAMREPORTINFO':{'TOTALLISTENCNT':'12345'}}}
 def parse(self):return c.parse_record(self.raw,self.m,self.when)
 def test_daily_527_not_top100(self):
  p=self.parse();self.assertEqual(p['dailyBestRank'],527);self.assertEqual(p['dailyBestDate'],'2026-09-28');self.assertEqual(p['ranks'],dict.fromkeys(c.KEYS));self.assertEqual(p['recordScope'],'daily')
 def test_no_lyrics_profiles_or_stream_counts_exported(self):
  text=json.dumps(self.parse());self.assertNotIn('MUST NOT COPY',text);self.assertNotIn('12345',text)
 def test_song_identity(self):
  self.raw['response']['SONGINFO']['SONGID']='999'
  with self.assertRaises(ValueError):self.parse()
 def test_album_identity(self):
  self.raw['response']['SONGINFO']['ALBUMID']='999'
  with self.assertRaises(ValueError):self.parse()
 def test_artist_identity(self):
  self.raw['response']['SONGINFO']['ARTISTLIST']=[{'ARTISTNAME':'다른 가수'}]
  with self.assertRaises(ValueError):self.parse()
 def test_title_identity(self):
  self.raw['response']['SONGINFO']['SONGNAME']='다른 곡'
  with self.assertRaises(ValueError):self.parse()
 def test_scope_required(self):
  self.raw['response']['SONGACHIEVEMENTINFO']['GUIDE']='최고 기록'
  with self.assertRaises(ValueError):self.parse()
 def test_current_rank_not_used(self):
  self.raw['response']['SONGACHIEVEMENTINFO']['BESTRANK']='-';self.assertIsNone(self.parse()['dailyBestRank'])
 def test_sentinels_unknown(self):
  for value in ('1001','0','-',None,''):
   self.raw['response']['SONGACHIEVEMENTINFO']['BESTRANK']=value;self.assertIsNone(self.parse()['dailyBestRank'])
 def test_invalid_rank(self):
  for value in ('1002','-1','1.5',True,527):
   self.raw['response']['SONGACHIEVEMENTINFO']['BESTRANK']=value
   with self.assertRaises(ValueError):self.parse()
 def test_future_peak_rejected(self):
  self.raw['response']['SONGACHIEVEMENTINFO']['BESTRANKDATE']='2099.01.01'
  with self.assertRaises(ValueError):self.parse()
 def test_invalid_date_rejected(self):
  self.raw['response']['SONGACHIEVEMENTINFO']['BESTRANKDATE']='2026.02.30'
  with self.assertRaises(ValueError):self.parse()
 def test_notification_not_a_record(self):
  with self.assertRaises(ValueError):c.parse_record({'notification':{'message':'차트가 업데이트 되었습니다.'}},self.m,self.when)
 def test_source_url_identity(self):
  self.assertTrue(c.valid_source(c.record_url('123'),'123'))
  for url in ('https://isegyechart.com/song/828','https://m2.melon.com/m6/v5/song/info.json?songId=124','https://u:p@m2.melon.com/m6/v5/song/info.json?songId=123'):
   self.assertFalse(c.valid_source(url,'123'))
 def test_collection_calls_only_original_and_discards_external(self):
  result={'tracks':{'cat':{'melon':self.m,'melonPeaks':{'source':'https://isegyechart.com/song/828'}}}};urls=[]
  def fetch(url):urls.append(url);return json.dumps(self.raw).encode()
  report=c.collect_original_records(result,{},fetch)
  self.assertEqual(urls,[c.record_url(self.m['trackId'])]);self.assertEqual(result['tracks']['cat']['melon']['durationMs'],175000);self.assertEqual(report['cat']['recordScope'],'daily')
 def test_failure_never_falls_back_to_third_party(self):
  result={'tracks':{'cat':{'melon':self.m}}};previous={'tracks':{'cat':{'melonPeaks':{'state':'verified','sourceType':'third_party_observed_records'}}}}
  def fail(url):raise TimeoutError()
  c.collect_original_records(result,previous,fail);self.assertNotIn('melonPeaks',result['tracks']['cat'])
 def test_failure_preserves_original_without_new_checked_time(self):
  record=self.parse();result={'tracks':{'cat':{'melon':self.m}}};previous={'tracks':{'cat':{'melonPeaks':record}}}
  def fail(url):raise TimeoutError()
  c.collect_original_records(result,previous,fail)
  self.assertEqual(result['tracks']['cat']['melonPeaks']['checkedAt'],self.when);self.assertEqual(result['tracks']['cat']['melonPeaks']['fetchState'],'error')
if __name__=='__main__':unittest.main()
