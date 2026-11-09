from pathlib import Path
import sys, unittest
from datetime import datetime,timezone,timedelta
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import collect_album_insights as c

class AlbumInsightTests(unittest.TestCase):
    def song(self): return {'title':'KIDDING','album':'KIDDING','members':['ine','jingburger','lilpa','jururu','gosegu','viichan'],'dateKind':'발매일'}
    def row(self,ident=1): return {'trackId':ident,'trackName':'KIDDING','artistName':'ISEGYE IDOL','collectionName':'KIDDING - Single','kind':'song'}
    def test_exact_identity(self):
        row,state=c.match_track(self.song(),[self.row()]);self.assertEqual(state,'matched');self.assertEqual(row['trackId'],1)
    def test_wrong_artist_is_not_same_song(self):
        row=self.row();row['artistName']='Different Artist';self.assertEqual(c.match_track(self.song(),[row])[1],'unmatched')
    def test_ambiguous_ids_not_guessed(self):self.assertEqual(c.match_track(self.song(),[self.row(1),self.row(2)])[1],'ambiguous')
    def test_video_not_assumed_distributed(self):
        s=self.song();s['dateKind']='영상 공개일';self.assertEqual(c.match_track(s,[self.row()])[1],'not_applicable')
    def test_incomplete_chart_cannot_mean_out(self):
        with self.assertRaises(ValueError):c.validate_chart({'feed':{'country':'kr','updated':datetime.now(timezone.utc).isoformat(),'results':[]}})
    def test_stale_chart_rejected(self):
        with self.assertRaises(ValueError):c.validate_chart({'feed':{'country':'kr','updated':'2020-01-01T00:00:00Z','results':[]}})
    def test_history_identity_retention_and_deduplication(self):
        now=datetime.now(timezone.utc);point={'at':now.isoformat(),'rank':5,'status':'ranked','trackId':'1'}
        other={**point,'trackId':'2'};old={**point,'at':(now-timedelta(days=31)).isoformat()}
        self.assertEqual(c.merge_history([point,other,old],point,now,'1'),[point])
    def test_invalid_out_rank_rejected(self):
        now=datetime.now(timezone.utc);point={'at':now.isoformat(),'rank':0,'status':'out','trackId':'1'}
        self.assertEqual(c.merge_history([],point,now,'1'),[])
    def test_unapproved_host_rejected(self):
        with self.assertRaises(ValueError):c.fetch_json('http://localhost/private')
if __name__=='__main__':unittest.main()
