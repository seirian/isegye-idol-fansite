from pathlib import Path
import sys,json,html,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import collect_album_records as c
class RecordsTests(unittest.TestCase):
 def hall(self,label='2M',artist='이세계아이돌'):
  return f'''<div class="mhall-album"><a onclick="goAlbumDetail('123', this)"></a><div class="ico-mhall ico-badge-1m-big"></div><strong class="txt-badge">{label}</strong><span class="txt-title"><span class="screen-out">앨범 : </span>KIDDING</span><span class="txt-description">{artist}</span></div><a onclick="goLink('album_detail_click', '123', '202308181800', this)"></a>'''
 def expected(self):return {'123':{'album':'KIDDING','artist':'이세계아이돌'}}
 def test_official_membership_exact(self):
  v=c.parse_hall(self.hall(),self.expected())['123'];self.assertEqual(v['label'],'2M');self.assertEqual(v['scope'],'album_first_24h');self.assertIn('issueDate=202308181800',v['source'])
 def test_unlisted_album_has_no_badge(self):self.assertEqual(c.parse_hall(self.hall(),{'999':{'album':'KIDDING','artist':'이세계아이돌'}}),{})
 def test_wrong_artist_rejected(self):
  with self.assertRaises(ValueError):c.parse_hall(self.hall(artist='다른가수'),self.expected())
 def test_unofficial_tier_not_inferred(self):
  with self.assertRaises(ValueError):c.parse_hall(self.hall(label='5M'),self.expected())
 def test_missing_issue_time_not_guessed(self):
  with self.assertRaises(ValueError):c.parse_hall(self.hall().replace('202308181800',''),self.expected())
 def test_untrusted_sources_blocked(self):
  for u in ['http://m2.melon.com/a','https://m2.melon.com.evil.test/a','https://u:p@m2.melon.com/a','https://isegyechart.com/song/828','https://127.0.0.1/a']:
   with self.assertRaises(ValueError):c.allowed(u)
if __name__=='__main__':unittest.main()
