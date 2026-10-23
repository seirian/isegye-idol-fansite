import importlib.util,unittest
from pathlib import Path
from datetime import datetime,timezone
spec=importlib.util.spec_from_file_location('feed',Path(__file__).resolve().parents[1]/'scripts/refresh_catalog_videos.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class FeedTests(unittest.TestCase):
 def feed(self,channel='UC1234567890123456789012',entry=''):
  return ('<feed xmlns="http://www.w3.org/2005/Atom" xmlns:yt="http://www.youtube.com/xml/schemas/2015"><title>channel</title><yt:channelId>'+channel+'</yt:channelId>'+entry+'</feed>').encode()
 def test_wrong_identity(self):
  with self.assertRaises(ValueError):m.parse_feed(self.feed(),'UCwrong',datetime.now(timezone.utc))
 def test_doctype_rejected(self):
  with self.assertRaises(ValueError):m.parse_feed(b'<!DOCTYPE feed>'+self.feed(),'UC1234567890123456789012',datetime.now(timezone.utc))
 def test_published_not_updated(self):
  e=lambda id,date:f'<entry><yt:videoId>{id}</yt:videoId><yt:channelId>UC1234567890123456789012</yt:channelId><title>safe</title><published>{date}</published><updated>2099-01-01T00:00:00Z</updated></entry>'
  _,rows=m.parse_feed(self.feed(entry=e('abcdefghijk','2020-01-01T00:00:00Z')+e('98765432101','2021-01-01T00:00:00Z')+e('01234567890','2099-01-01T00:00:00Z')),'UC1234567890123456789012',datetime.now(timezone.utc));self.assertEqual([r['id'] for r in rows],['98765432101','abcdefghijk'])
 def test_video_identity(self):
  e='<entry><yt:videoId>abcdefghijk</yt:videoId><yt:channelId>other</yt:channelId><title>safe</title><published>2020-01-01T00:00:00Z</published></entry>'
  with self.assertRaises(ValueError):m.parse_feed(self.feed(entry=e),'UC1234567890123456789012',datetime.now(timezone.utc))

 def test_real_feed_allows_unprefixed_root_but_requires_video_identity(self):
  title,rows=m.parse_feed(self.feed(channel='1234567890123456789012'),'UC1234567890123456789012',datetime.now(timezone.utc));self.assertEqual(rows,[])
