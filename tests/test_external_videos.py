"""Selected external video identities, classification and preservation; no network."""
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import sys, unittest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import external_videos as e

def baseline():
    return {'songs':[{'id':'rebels','videoId':'y-klhPVFblg','date':'2026-11-09','albumId':'original'}],
            'albums':[{'id':'original','songIds':['rebels']}], 'channels':[{'key':'c2'}],
            'videos':[{'id':'y-klhPVFblg','category':'group'}], 'scope':{'videoChannelCount':22},
            'history':[], 'notices':[]}

class ExternalVideos(unittest.TestCase):
    def test_exact_requested_public_metadata(self):
        doc=e.load();self.assertEqual(set(e.APPROVED),{r['id'] for r in doc['videos']})
        self.assertEqual([r['durationSeconds'] for r in doc['videos']],[31,192])
    def test_superseded_upload_refused(self):
        doc=e.load();doc['videos'][1]['id']='z8AJgnTC52k'
        with self.assertRaises(ValueError):e.validate(doc)
    def test_kst_publication_not_album_release(self):
        rows=e.compose(baseline())['videos'][1:]
        self.assertEqual([v['date'] for v in rows],['2026-11-10','2026-11-11'])
        self.assertTrue(all(v['dateLabel']=='영상 공개일' for v in rows))
    def test_original_mv_and_album_are_not_replaced(self):
        before=baseline();old=deepcopy(before);after=e.compose(before)
        self.assertEqual(before,old)
        for key in ('songs','albums','history','notices'):self.assertEqual(before[key],after[key])
    def test_only_two_selected_rows_no_complete_channel_claim(self):
        after=e.compose(baseline());self.assertEqual(len(after['videos']),3)
        channel=after['channels'][-1];self.assertFalse(channel['coverageComplete'])
        self.assertEqual(channel['coverageMode'],'selected_video_ids')
        self.assertEqual(after['scope']['videoChannelCount'],22)
    def test_repeated_composition_is_idempotent(self):
        once=e.compose(baseline());self.assertEqual(e.compose(once),once)
    def test_teaser_and_performance_have_distinct_types(self):
        rows=e.compose(baseline())['videos'][1:]
        self.assertEqual([v['type'] for v in rows],['external_teaser','external_performance'])
        self.assertTrue(all(v['category']=='external' and v['relatedSong']=='rebels' for v in rows))
    def test_channel_spoof_refused(self):
        doc=e.load();doc['channel']['channelId']='UCmblbE_WxTaFWcMEGFJ_97w'
        with self.assertRaises(ValueError):e.validate(doc)
    def test_channel_url_spoof_refused(self):
        doc=e.load();doc['channel']['url']='https://evil.invalid'
        with self.assertRaises(ValueError):e.validate(doc)
    def test_unrequested_video_refused(self):
        doc=e.load();doc['videos'][0]['id']='abcdefghijk'
        with self.assertRaises(ValueError):e.validate(doc)
    def test_duplicate_refused(self):
        doc=e.load();doc['videos'][1]=deepcopy(doc['videos'][0])
        with self.assertRaises(ValueError):e.validate(doc)
    def test_wrong_format_refused(self):
        doc=e.load();doc['videos'][0]['type']='external_performance'
        with self.assertRaises(ValueError):e.validate(doc)
    def test_wrong_date_duration_title_refused(self):
        for field,value in [('publishedAt','2026-11-09T13:00:38Z'),('durationSeconds',192),('title','unrelated')]:
            with self.subTest(field=field):
                doc=e.load();doc['videos'][0][field]=value
                with self.assertRaises(ValueError):e.validate(doc)
    def test_private_or_not_embeddable_refused(self):
        for field,value in [('privacyStatus','private'),('embeddable',False)]:
            doc=e.load();doc['videos'][0][field]=value
            with self.assertRaises(ValueError):e.validate(doc)
    def test_future_check_and_missing_timezone_refused(self):
        doc=e.load()
        with self.assertRaises(ValueError):e.validate(doc,datetime(2026,11,10,tzinfo=timezone.utc))
        doc['checkedAt']='2026-11-11T13:44:38'
        with self.assertRaises(ValueError):e.validate(doc)
    def test_missing_track_fails_closed(self):
        data=baseline();data['songs']=[]
        with self.assertRaises(ValueError):e.compose(data)
    def test_conflicting_id_fails_closed(self):
        data=baseline();data['videos'].append({'id':'Mj7q8HU8ZXg'})
        with self.assertRaises(ValueError):e.compose(data)
    def test_canonical_urls_no_tracking(self):
        for v in e.compose(baseline())['videos'][1:]:
            self.assertEqual(v['url'],'https://www.youtube.com/watch?v='+v['id'])
            self.assertEqual(v['channelUrl'],'https://www.youtube.com/channel/'+e.CHANNEL_ID)
    def test_missing_app_anchor_refused(self):
        with self.assertRaises(ValueError):e.adapt_app('function contentView(p){}')
    def test_regression_runs_before_upload(self):
        workflow=(ROOT/'.github/workflows/production.yml').read_text()
        self.assertLess(workflow.index('tests/external_videos_browser.py'),workflow.index('scripts/deploy_verified_albums.py'))
if __name__=='__main__':unittest.main()
