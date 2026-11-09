"""Short-video duration metadata is conservative and never guesses aspect ratio."""
import json,sys,unittest
from pathlib import Path
from urllib.parse import urlsplit,parse_qs
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import enrich_video_durations as shorts
from backfill_channel_videos import APIError
VID1='a1234567890';VID2='b1234567890'
class ShortsDurationTests(unittest.TestCase):
 def test_iso_duration_and_invalid(self):
  self.assertEqual(shorts.parse_duration('PT59S'),59)
  self.assertEqual(shorts.parse_duration('PT3M'),180)
  self.assertEqual(shorts.parse_duration('PT1H2M5S'),3725)
  self.assertIsNone(shorts.parse_duration('not-iso'))
  self.assertIsNone(shorts.parse_duration('PT'))
 def test_public_api_and_preservation(self):
  seen=[]
  data={'channels':[{'videos':[{'id':VID1},{'id':VID2}]}]}
  def fetch(url):
   seen.append(parse_qs(urlsplit(url).query))
   return json.dumps({'items':[{'id':VID2,'status':{'privacyStatus':'public'},'contentDetails':{'duration':'PT1M20S'}}]}).encode()
  result,attempted=shorts.collect(data,{'seconds':{VID1:210}},'A'*20,fetch)
  self.assertEqual(attempted,1)
  self.assertEqual(result['seconds'],{VID1:210,VID2:80})
  self.assertEqual(seen[0]['part'],['contentDetails,status'])
 def test_private_video_never_enriched(self):
  data={'channels':[{'videos':[{'id':VID1}]}]}
  def fetch(url):
   return json.dumps({'items':[{'id':VID1,'status':{'privacyStatus':'private'},'contentDetails':{'duration':'PT30S'}}]}).encode()
  result,_=shorts.collect(data,{},'A'*20,fetch)
  self.assertEqual(result['seconds'],{})
 def test_bad_video_id_is_rejected(self):
  with self.assertRaises(APIError):shorts.collect({'channels':[{'videos':[{'id':'bad'}]}]}, {}, 'A'*20)
if __name__=='__main__':unittest.main()
