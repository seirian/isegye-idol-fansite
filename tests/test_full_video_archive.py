"""Public Atom accumulation and paginated official YouTube uploads safety."""
import sys,unittest,json
from pathlib import Path
from datetime import datetime,timezone
from urllib.parse import urlsplit,parse_qs
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import refresh_catalog_videos as recent
import backfill_channel_videos as backfill
NOW=datetime(2026,11,6,5,35,tzinfo=timezone.utc);CID='UC1234567890123456789012'
def atom(n):
 def entry(i):
  return '<entry><yt:videoId>v%010d</yt:videoId><yt:channelId>%s</yt:channelId><title>Video %d</title><published>2026-10-%02dT10:00:00Z</published></entry>'%(i,CID,i,1+(i%28))
 return ('<feed xmlns="http://www.w3.org/2005/Atom" xmlns:yt="http://www.youtube.com/xml/schemas/2015"><title>channel</title><yt:channelId>'+CID+'</yt:channelId>'+''.join(entry(i) for i in range(n))+'</feed>').encode()
class VideoCollectionTests(unittest.TestCase):
 def test_atom_keeps_all_entries_not_three(self):
  _,rows=recent.parse_feed(atom(13),CID,NOW);self.assertEqual(len(rows),13)
 def test_merge_keeps_prior_record_and_first_seen(self):
  old={'id':'oldvideo123','title':'Old','publishedAt':'2020-01-01T00:00:00+00:00','firstSeenAt':'2026-10-01T00:00:00+00:00'}
  new={'id':'newvideo123','title':'New','publishedAt':'2026-11-05T00:00:00+00:00'}
  rows=recent.merge_rows([old],[new,{**old,'title':'Updated'}],NOW.isoformat())
  self.assertEqual(len(rows),2)
  self.assertEqual(next(r for r in rows if r['id']==old['id'])['firstSeenAt'],old['firstSeenAt'])
  self.assertEqual(next(r for r in rows if r['id']==new['id'])['firstSeenAt'],NOW.isoformat())
 def test_pinned_22_channels(self):
  channels=recent.channels()
  self.assertEqual(len(channels),22);self.assertEqual(len({x['channelId'] for x in channels}),22)
  self.assertEqual(len([x for x in channels if x['kind']=='다시보기']),5)
 def test_official_page_tokens_until_exhausted(self):
  pages=[]
  def fetch(url):
   params=parse_qs(urlsplit(url).query);pages.append(params);index=len(pages)
   row={'status':{'privacyStatus':'public'},'snippet':{'videoOwnerChannelId':CID,'title':'Test'},
     'contentDetails':{'videoId':'v%010d'%index,'videoPublishedAt':'2026-10-01T12:00:00Z'}}
   return json.dumps({'items':[row],**({'nextPageToken':'NEXT_PAGE'} if index==1 else {})}).encode()
  rows,count=backfill.collect_channel({'channelId':CID},'UU1234567890123456789012','A'*20,NOW,fetch)
  self.assertEqual((len(rows),count),(2,2));self.assertEqual(pages[-1]['pageToken'],['NEXT_PAGE'])
 def test_no_key_in_failures(self):
  key='SECRET_EXAMPLE_YOUTUBE_API_KEY'
  with self.assertRaises(backfill.APIError) as cm:backfill.request('playlistItems',{'playlistId':'bad'},key,lambda _:b'not-json')
  self.assertNotIn(key,str(cm.exception))
 def test_private_or_foreign_upload_is_excluded(self):
  items=[]
  for i,(status,owner) in enumerate([('private',CID),('public','UCother'),('public',CID)],1):
   items.append({'status':{'privacyStatus':status},'snippet':{'videoOwnerChannelId':owner,'title':'Video'},
     'contentDetails':{'videoId':'v%010d'%i,'videoPublishedAt':'2026-10-01T12:00:00Z'}})
  rows,pages=backfill.collect_channel({'channelId':CID},'UU1234567890123456789012','A'*20,NOW,lambda _:json.dumps({'items':items}).encode())
  self.assertEqual(len(rows),1);self.assertEqual(rows[0]['id'],'v0000000003')
if __name__=='__main__':unittest.main()
