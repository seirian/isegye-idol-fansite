import json,sys,unittest
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import daily_music as m,publish_daily_music as p,inour_sftp as d
from test_schedule_feed import FeedRemote,OLD
NOW=datetime.now(timezone.utc).isoformat()
def record(v='12345678901',title='샘플 곡'):
    return dict(videoId=v,title=title,channelKey='c14',members=['lilpa'],type='cover',kind='official_video',publishedAt=NOW,checkedAt=NOW)
def doc(rows):return {'schemaVersion':1,'sources':{k:{'state':'ok'} for k in m.CHANNELS},'generatedAt':NOW,'rows':rows}
def remote():
    r=FeedRemote();r.files[d.ROOT+'/_isegye_releases/'+OLD+'/build-info.json']=b'{"dailyMusic":{"schemaVersion":1}}';return r
class Music(unittest.TestCase):
    def test_types_and_credit(self):
        self.assertEqual(m.classify('c2',"ISEGYE IDOL (이세계아이돌) ‘빛’ Official MV")['type'],'official_track')
        self.assertEqual(m.classify('c14','샘플 | Cover by 릴파')['members'],['lilpa'])
        self.assertEqual(m.classify('c4',"고세구 '별' [Original Song]")['type'],'original')
        self.assertIsNone(m.classify('c1',"다른 가수 '빛' Official MV"))
        for bad in ['리액션','Teaser','댄스 커버','#shorts','비하인드','dance cover','unboxing']:
            self.assertIsNone(m.classify('c2',"ISEGYE IDOL '빛' Official MV "+bad))
    def test_only_known_official_channels(self):
        cfg=m.selections()[0]['channels'];self.assertEqual(len(m.CHANNELS),9)
        self.assertTrue(all(cfg[k]['role']=='official' for k in m.CHANNELS))
        self.assertEqual(len({x[0] for x in m.CHANNELS.values()}),9)
    def test_idempotence_and_work_dedup(self):
        a=record();b={**a,'videoId':'98765432109','kind':'official_mv'};self.assertEqual(m.merge([], [a,b],(set(),set())),[b]);self.assertEqual(m.merge([a],[b],(set(),set())),[a]);self.assertEqual(m.merge([a],[a],(set(),set())),[a]);self.assertEqual(m.merge([],[a],({a['videoId']},set())),[])
        ids,titles=m.baseline();self.assertIn('zGOzGcEbd-s',ids);self.assertIn('TYB9ScXvq34',ids);self.assertIn('IajO_xnbyFE',ids)
    def test_spoof_invalid_future_and_extra_data(self):
        for change in [{'channelKey':'c3'},{'videoId':'../x'},{'members':['other']},{'publishedAt':'2099-01-01T00:00:00Z'},{'title':'<script>'},{'body':'third-party text'}]:
            with self.assertRaises(ValueError):m.validate([{**record(),**change}])
    def test_atomic_output_backup_and_preservation(self):
        r=remote();v=p.publish(r,doc([record()]));self.assertEqual((v['added'],v['totalAuto']),(1,1));raw=r.read(p.path('current.json'));v=p.publish(r,doc([]));self.assertEqual(v['totalAuto'],1);self.assertEqual(v['added'],0);v=p.publish(r,doc([record('09876543210','다른 곡')]));self.assertEqual(v['totalAuto'],2);self.assertEqual(r.read(p.path('previous.json')),raw);self.assertTrue(all(n.startswith(p.DIR+'/') for n in r.writes))
    def test_failure_never_becomes_empty(self):
        r=remote();p.publish(r,doc([record()]));raw=r.read(p.path('current.json'));failed=doc([]);failed['sources']={k:{'state':'error'} for k in m.CHANNELS}
        with self.assertRaises(d.Stop):p.publish(r,failed)
        self.assertEqual(r.read(p.path('current.json')),raw)
    def test_owned_paths_and_locked_state(self):
        r=remote();p.publish(r,doc([]));r.files[p.path('.lock')]=b'not-our-lock'
        with self.assertRaises(d.Stop):p.publish(r,doc([record()]))
        self.assertEqual(r.read(p.path('.lock')),b'not-our-lock')
        for path in ['../../.auth-private/','/web/.htaccess','other.json']:
            with self.assertRaises(d.Stop):p.path(path)
    def test_gate_precedes_data(self):
        s=(ROOT/'auth/Gateway.php').read_text();self.assertLess(s.index("if (!$access['allowed'])"),s.index("if ($path === '/api/music')"))
if __name__=='__main__':unittest.main()
