import json,sys,unittest
from pathlib import Path
from unittest.mock import patch
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import daily_music as m,waktaverse_history as history,music_public_metadata as public
from test_daily_music import record,doc,remote
import publish_daily_music as publisher,inour_sftp as d
from test_schedule_feed import OLD
class Waktaverse(unittest.TestCase):
 def test_actual_music_and_nonmusic_titles(self):
  cases=json.loads((ROOT/'tests/fixtures/waktaverse-titles.json').read_text());e=m.baseline()[1];self.assertEqual(len(cases),44)
  for case in cases:
   with self.subTest(video=case['videoId']):self.assertEqual(bool(m.classify('c1',case['title'],e)),case['music'])
 def test_member_feature_is_not_solo_credit(self):
  r=m.classify('c1','[Original Song] 짬통스 - BAD END (ft. 릴파)');self.assertEqual(r['members'],['lilpa']);self.assertEqual(r['context'],'collab');self.assertIn('짬통스',r['credits'])
  for s in ['[Original Song] Talk To Talk - 해루석, 비밀소녀','HEADLINE (헤드라인) - [곽춘식, 해루석, 히키킹]',"이세계아이돌 '곡' Official MV REACTION",'이세계 페스티벌 - 모르는 곡']:self.assertIsNone(m.classify('c1',s,m.baseline()[1]))
 def test_history_idempotence(self):
  now=datetime.now(timezone.utc).isoformat();rows=[]
  for x in history.records():rows.append(dict(m.classify('c1',x['sourceTitle'],m.baseline()[1]),channelKey='c1',videoId=x['videoId'],publishedAt=x['publishedDate'],datePrecision='day',checkedAt=now))
  self.assertEqual(len(rows),15);m.validate(rows);self.assertEqual(len(m.merge([],rows)),15);self.assertEqual(len(m.merge(rows,rows)),15);self.assertIn('fgSXAKsq-Vo',m.baseline()[0]);self.assertFalse(any(r['videoId']=='fgSXAKsq-Vo' for r in rows))
 def test_invalid_fields(self):
  for changes in [{'publishedAt':'2023-07-19'},{'datePrecision':'day'},{'context':'collab'},{'credits':'<img>'},{'type':'performance'}]:
   with self.assertRaises(ValueError):m.validate([{**record(),**changes}])
 def fixture(self):
  p={'title':{'simpleText':'정확한 곡'},'dateText':{'simpleText':'최초 공개: 2023. 7. 19.'}};s={'owner':{'videoOwnerRenderer':{'navigationEndpoint':{'browseEndpoint':{'browseId':m.CHANNELS['c1'][0]}}}}};return {'contents':{'twoColumnWatchNextResults':{'results':{'results':{'contents':[{'videoPrimaryInfoRenderer':p},{'videoSecondaryInfoRenderer':s}]}}}}}
 def html(self,j,vid='12345678901'):return '<link rel="canonical" href="https://www.youtube.com/watch?v='+vid+'"><script>var ytInitialData = '+json.dumps(j)+';</script>'
 def test_date_identity(self):
  j=self.fixture();j['recommendations']={'dateText':{'simpleText':'2026. 11. 3.'}};self.assertEqual(public.public_watch_date(self.html(j),m.CHANNELS['c1'][0],'12345678901','정확한 곡'),'2023-07-19')
  for cid,vid,title in [('wrong','12345678901','정확한 곡'),(m.CHANNELS['c1'][0],'98765432109','정확한 곡'),(m.CHANNELS['c1'][0],'12345678901','다른 곡')]:
   with self.assertRaises(ValueError):public.public_watch_date(self.html(j),cid,vid,title)
  j['contents']['twoColumnWatchNextResults']['results']['results']['contents'][0]['videoPrimaryInfoRenderer']['dateText']={'simpleText':'3년 전'}
  with self.assertRaises(ValueError):public.public_watch_date(self.html(j),m.CHANNELS['c1'][0],'12345678901','정확한 곡')
 def test_failed_history(self):
  with patch.object(m,'verify_video',side_effect=OSError('temporary')):rows,stats=history.collect(datetime.now(timezone.utc))
  self.assertFalse(rows);self.assertEqual(stats['verified'],0);self.assertEqual(len(stats['errors']),15)
 def test_renderer_capability(self):
  r=remote();row=dict(record(),channelKey='c1',publishedAt='2023-07-19',datePrecision='day');before=dict(r.files)
  with self.assertRaises(d.Stop):publisher.publish(r,doc([row]))
  self.assertEqual(r.files,before);r.files[d.ROOT+'/_isegye_releases/'+OLD+'/build-info.json']=b'{"dailyMusic":{"schemaVersion":1,"waktaverseFormats":1}}';v=publisher.publish(r,doc([row]));self.assertEqual(v['added'],1);self.assertEqual(publisher.publish(r,doc([row]))['added'],0)
if __name__=='__main__':unittest.main()
