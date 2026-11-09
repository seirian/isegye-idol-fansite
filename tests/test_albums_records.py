from pathlib import Path
import sys,json,html,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import collect_album_records as c
class RecordsTests(unittest.TestCase):
 def hall(self,label='2M',artist='이세계아이돌'):
  return f'''<div class="mhall-album"><a onclick="goAlbumDetail('123', this)"></a><div class="ico-mhall ico-badge-1m-big"></div><strong class="txt-badge">{label}</strong><span class="txt-title"><span class="screen-out">앨범 : </span>KIDDING</span><span class="txt-description">{artist}</span></div><a onclick="goLink('album_detail_click', '123', '202308181800', this)"></a>'''
 def expected(self):return {'123':{'album':'KIDDING','artist':'이세계아이돌'}}
 def melon(self):return {'trackId':'456','albumId':'123','title':'KIDDING','artist':'이세계아이돌'}
 def record(self,ident='456',rank=6):
  info={'songInfo':[0,{'id':[0,799],'name':[0,'KIDDING'],'artistName':[0,'이세계아이돌'],'albumIdMap':[0,{'melonId':[0,123]}],'idMap':[0,{'melonId':[0,ident]}],'lyrics':[0,'DO NOT EXPORT']} ]}
  return '<astro-island component-url="/FeaturedSongSelector.js" props="'+html.escape(json.dumps(info),quote=True)+'"></astro-island><h2>멜론 최고 성적</h2>'+''.join(f'<span><h3>{n}</h3><span>{r}위</span><span>23.8.20</span></span>' for n,r in [('TOP100',rank),('실시간차트',1),('HOT100 (100일)',1)])
 def test_official_membership_exact(self):
  v=c.parse_hall(self.hall(),self.expected())['123'];self.assertEqual(v['label'],'2M');self.assertEqual(v['scope'],'album_first_24h');self.assertIn('issueDate=202308181800',v['source'])
 def test_unlisted_album_has_no_badge(self):self.assertEqual(c.parse_hall(self.hall(),{'999':{'album':'KIDDING','artist':'이세계아이돌'}}),{})
 def test_wrong_artist_rejected(self):
  with self.assertRaises(ValueError):c.parse_hall(self.hall(artist='다른가수'),self.expected())
 def test_unofficial_tier_not_inferred(self):
  with self.assertRaises(ValueError):c.parse_hall(self.hall(label='5M'),self.expected())
 def test_missing_issue_time_not_guessed(self):
  with self.assertRaises(ValueError):c.parse_hall(self.hall().replace('202308181800',''),self.expected())
 def test_historical_peaks_exact_id(self):
  p=c.parse_peaks(self.record(),self.melon(),799);self.assertEqual(p['ranks'],{'top100':6,'hot100':1,'realtime':1});self.assertNotIn('lyrics',json.dumps(p));self.assertEqual(p['dates']['top100'],'2023-08-20')
 def test_wrong_melon_id_rejected(self):
  with self.assertRaises(ValueError):c.parse_peaks(self.record(ident='999'),self.melon(),799)
 def test_invalid_rank_rejected(self):
  with self.assertRaises(ValueError):c.parse_peaks(self.record(rank=101),self.melon(),799)
 def test_missing_hot100_is_unknown(self):
  src=self.record().replace('<span><h3>HOT100 (100일)</h3><span>1위</span><span>23.8.20</span></span>','')
  self.assertIsNone(c.parse_peaks(src,self.melon(),799)['ranks']['hot100'])
 def test_no_current_rank_invented_as_peak(self):
  with self.assertRaises(ValueError):c.parse_peaks(self.record().replace('멜론 최고 성적','현재 차트'),self.melon(),799)
 def test_untrusted_sources_blocked(self):
  for u in ['http://m2.melon.com/a','https://m2.melon.com.evil.test/a','https://u:p@m2.melon.com/a','https://isegyechart.com:8080/','https://127.0.0.1/a']:
   with self.assertRaises(ValueError):c.allowed(u)
 def test_lyrics_discarded_during_deserialization(self):self.assertNotIn('lyrics',c.unastro({'lyrics':[0,'x'],'id':[0,1]}))
if __name__=='__main__':unittest.main()
