"""Requested series has six direct, source-verified videos; all other data is kept."""
from copy import deepcopy
from pathlib import Path
import json
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import music_beginning as m

class MusicBeginning(unittest.TestCase):
    def setUp(self):
        self.doc=m.load()
        self.videos=[dict(id=r['videoId'],url=r['url'],category='group',channelName=r['channelName']) for r in self.doc['videos']]
        self.data={'series':[{'id':'festival-2025','title':'unchanged','videoIds':['other']},{'id':m.SERIES_ID,'title':'old','songIds':['rewind'],'members':['ine']}],
          'songs':[dict(id=r['songId'],videoId=r['videoId']) for r in self.doc['videos']],
          'albums':[{'title':'keep'}],'videos':[],'channels':[],'scope':{},'events':[]}
    def test_exact_title_order_and_original_urls(self):
        self.assertEqual(self.doc['title'],'Re:Wind 부터 만나보는 이세계아이돌')
        self.assertEqual([r['videoId'] for r in self.doc['videos']],[r[2] for r in m.SELECTION])
        self.assertEqual(self.doc['videos'][1]['url'],'https://www.youtube.com/watch?v=JY-gJkMuJ94')
        self.assertEqual(self.doc['videos'][-1]['url'],'https://www.youtube.com/watch?v=y-klhPVFblg')
    def test_smile_retains_special_clip_not_fabricated_mv(self):
        self.assertEqual(self.doc['videos'][4]['kind'],'official_special_clip')
        self.assertEqual(sum(r['kind']=='official_mv' for r in self.doc['videos']),5)
    def test_compose_changes_only_selected_series(self):
        before=deepcopy(self.data);result=m.compose(self.data,self.videos,self.doc)
        self.assertEqual(self.data,before)
        for key in before:
            if key!='series': self.assertEqual(result[key],before[key])
        self.assertEqual(result['series'][0],before['series'][0])
        self.assertEqual(result['series'][1]['songIds'],[])
        self.assertEqual(result['series'][1]['entryMode'],'youtube_original')
        self.assertEqual(result['series'][1]['members'],['ine'])
    def test_repeat_is_idempotent(self):
        result=m.compose(self.data,self.videos,self.doc)
        self.assertEqual(m.compose(result,self.videos,self.doc),result)
    def test_missing_or_duplicate_series_rejected(self):
        for series in ([],self.data['series']+[self.data['series'][1]]):
            data=deepcopy(self.data);data['series']=series
            with self.assertRaises(ValueError):m.compose(data,self.videos,self.doc)
    def test_missing_or_conflicting_videos_rejected(self):
        for rows in (self.videos[1:],self.videos+[self.videos[0]]):
            with self.assertRaises(ValueError):m.compose(self.data,rows,self.doc)
        for field,value in [('category','external'),('url','https://evil.invalid/'),('channelName','Fan')]:
            rows=deepcopy(self.videos);rows[0][field]=value
            with self.assertRaises(ValueError):m.compose(self.data,rows,self.doc)
    def test_song_mv_not_replaced(self):
        self.data['songs'][0]['videoId']='different'
        with self.assertRaises(ValueError):m.compose(self.data,self.videos,self.doc)
    def test_unrequested_reordered_duplicate_missing_rejected(self):
        for rows in (self.doc['videos'][:-1],self.doc['videos'][::-1],self.doc['videos']+[self.doc['videos'][0]]):
            doc=deepcopy(self.doc);doc['videos']=rows
            with self.assertRaises(ValueError):m.validate(doc)
    def test_wrong_identity_metadata_source_and_url_rejected(self):
        for field,value in [('videoId','z8AJgnTC52k'),('channelId','foreign'),('channelName','Fan'),('url','https://youtube.com/watch?v=fgSXAKsq-Vo&x=1'),('kind','official_audio'),('privacyStatus','private'),('embeddable',False),('durationSeconds',0),('durationSeconds',True),('sourceTitle','unverified')]:
            doc=deepcopy(self.doc);doc['videos'][0][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):m.validate(doc)
    def test_teaser_not_accepted(self):
        doc=deepcopy(self.doc);doc['videos'][4]['sourceTitle']+=' Teaser'
        with self.assertRaises(ValueError):m.validate(doc)
    def test_future_and_naive_time_rejected(self):
        for t in ['2099-01-01T00:00:00Z','2026-11-15T23:29:32']:
            doc=deepcopy(self.doc);doc['checkedAt']=t
            with self.assertRaises(ValueError):m.validate(doc)
    def test_wrong_evidence_rejected(self):
        for field,value in [('source','unverified'),('evidenceRun',0),('id','other'),('title','old')]:
            doc=deepcopy(self.doc);doc[field]=value
            with self.assertRaises(ValueError):m.validate(doc)
    def test_renderer_hook_is_scoped(self):
        source="function seriesView(id){return 'other';}\nif(!location.hash)history.replaceState();"
        app=m.adapt_app(source)
        self.assertIn("if(id==='music-beginning')return musicBeginningView();",app)
        self.assertIn("return 'other';",app)
        self.assertNotIn('#/album/',app);self.assertNotIn('#/song/',app)
        self.assertIn('rel="noopener noreferrer"',app)
        self.assertIn('entry.kind===\'official_special_clip\'',app)
    def test_renderer_missing_anchor_fails(self):
        with self.assertRaises(ValueError):m.adapt_app('function other(){}')
    def test_browser_checks_run_before_upload(self):
        for filename in ('ci.yml','production.yml'):
            text=(ROOT/'.github/workflows'/filename).read_text()
            self.assertIn('tests/music_beginning_browser.py',text)
        text=(ROOT/'.github/workflows/production.yml').read_text()
        self.assertLess(text.index('tests/music_beginning_browser.py'),text.index('scripts/deploy_verified_albums.py'))

if __name__=='__main__':unittest.main()
