"""Pinned single-video Music Core addition, without network or whole-channel discovery."""
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import json, sys, unittest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import external_videos as external
import music_core_videos as core

def baseline():
    return {'songs':[{'id':'rebels','videoId':'y-klhPVFblg','date':'2026-11-09','albumId':'original'}],
            'albums':[{'id':'original','songIds':['rebels']}], 'channels':[{'key':'c2'}],
            'videos':[{'id':'y-klhPVFblg','category':'group'}], 'scope':{'videoChannelCount':22},
            'history':[], 'notices':[]}

class MusicCoreVideos(unittest.TestCase):
    def test_exact_public_metadata(self):
        doc=core.load();self.assertEqual(doc['videos'],[core.EXPECTED])
        self.assertEqual(doc['channel']['name'],'MBCkpop')
        self.assertEqual(doc['videos'][0]['durationSeconds'],188)
    def test_three_selected_videos_and_two_external_channels(self):
        result=core.compose(external.compose(baseline()))
        self.assertEqual([r['id'] for r in result['videos']],['y-klhPVFblg','_E9ZHH9R7o4','Mj7q8HU8ZXg','sy40EGkSfRA'])
        self.assertEqual(result['scope']['selectedExternalVideoCount'],3)
        self.assertEqual(result['scope']['videoChannelCount'],22)
        self.assertEqual([c['key'] for c in result['channels'][1:]],[external.CHANNEL_KEY,core.CHANNEL_KEY])
        self.assertTrue(all(c['coverageMode']=='selected_video_ids' and not c['coverageComplete'] for c in result['channels'][1:]))
    def test_existing_rows_and_metadata_unchanged(self):
        before=external.compose(baseline());old=deepcopy(before);after=core.compose(before)
        self.assertEqual(old,before)
        for key in ('songs','albums','history','notices'):self.assertEqual(before[key],after[key])
        self.assertEqual(before['videos'],after['videos'][:-1]);self.assertEqual(before['channels'],after['channels'][:-1])
    def test_repeated_composition_is_idempotent(self):
        result=core.compose(external.compose(baseline()));self.assertEqual(result,core.compose(result))
    def test_publication_broadcast_and_release_separate(self):
        result=core.compose(external.compose(baseline()));v=result['videos'][-1]
        self.assertEqual(v['date'],'2026-11-14');self.assertEqual(v['dateLabel'],'영상 공개일')
        self.assertEqual(v['broadcastDateBasis'],'source_title');self.assertEqual(v['publishedAt'],'2026-11-14T06:37:04Z')
        self.assertEqual(result['songs'][0]['date'],'2026-11-09')
    def test_hd_not_false_4k(self):
        video=core.compose(baseline())['videos'][-1]
        self.assertEqual(video['definition'],'hd');self.assertNotIn('4K',json.dumps(video,ensure_ascii=False))
        self.assertEqual(video['format'],'음악방송 무대')
        doc=core.load();doc['videos'][0]['qualityLabel']='4K'
        with self.assertRaises(ValueError):core.validate(doc)
    def test_region_restriction_is_explicit(self):
        video=core.compose(baseline())['videos'][-1]
        self.assertEqual(video['regionRestriction'],{'blocked':['JP']});self.assertIn('일본',video['summary'])
    def test_channel_identity_and_source_refused(self):
        for field in ('channelId','name','url','key'):
            with self.subTest(field=field):
                doc=core.load();doc['channel'][field]='unverified'
                with self.assertRaises(ValueError):core.validate(doc)
        doc=core.load();doc['source']='unverified'
        with self.assertRaises(ValueError):core.validate(doc)
    def test_unrequested_or_superseded_video_refused(self):
        for vid in ('z8AJgnTC52k','Mj7q8HU8ZXg','abcdefghijk'):
            doc=core.load();doc['videos'][0]['id']=vid
            with self.assertRaises(ValueError):core.validate(doc)
    def test_duplicate_and_empty_selection_refused(self):
        for rows in ([],[core.EXPECTED,core.EXPECTED]):
            doc=core.load();doc['videos']=rows
            with self.assertRaises(ValueError):core.validate(doc)
    def test_modified_evidence_refused(self):
        for field,value in [('title','unverified'),('durationSeconds',192),('durationSeconds','188'),
                ('privacyStatus','private'),('embeddable',False),('embeddable',1),('relatedSong','kidding'),
                ('type','external_teaser'),('regionRestriction',{}),('broadcastDate','2026-11-13'),('definition','4k')]:
            with self.subTest(field=field,value=value):
                doc=core.load();doc['videos'][0][field]=value
                with self.assertRaises(ValueError):core.validate(doc)
    def test_invalid_verification_time_refused(self):
        with self.assertRaises(ValueError):core.validate(core.load(),datetime(2026,11,13,tzinfo=timezone.utc))
        for value in ('2026-11-14T07:56:19','2026-11-13T07:56:19Z'):
            doc=core.load();doc['checkedAt']=value
            with self.assertRaises(ValueError):core.validate(doc)
    def test_missing_or_wrong_original_mv_refused(self):
        for songs in ([],[{'id':'rebels','videoId':core.VIDEO_ID}]):
            data=baseline();data['songs']=songs
            with self.assertRaises(ValueError):core.compose(data)
    def test_conflicting_video_or_channel_refused(self):
        data=baseline();data['videos'].append({'id':core.VIDEO_ID})
        with self.assertRaises(ValueError):core.compose(data)
        data=baseline();data['channels'].append({'key':core.CHANNEL_KEY})
        with self.assertRaises(ValueError):core.compose(data)
    def test_canonical_source_links(self):
        video=core.compose(baseline())['videos'][-1]
        self.assertEqual(video['url'],'https://www.youtube.com/watch?v=sy40EGkSfRA')
        self.assertEqual(video['channelUrl'],'https://www.youtube.com/channel/'+core.CHANNEL_ID)
        self.assertEqual(video['sourceLinks'][0]['url'],video['url'])
    def test_related_source_names_not_hardcoded(self):
        helper=(ROOT/'site/external-videos.js').read_text()
        self.assertIn('esc(channelNames)',helper);self.assertNotIn('STUDIO CHOOM',helper)
        self.assertIn('b.publishedAt.localeCompare(a.publishedAt)',helper)
    def test_music_list_and_preupload_regression(self):
        self.assertIn("v.type==='external_performance'",(ROOT/'scripts/external_videos.py').read_text())
        workflow=(ROOT/'.github/workflows/production.yml').read_text()
        self.assertLess(workflow.index('tests/external_videos_browser.py'),workflow.index('scripts/deploy_verified_albums.py'))
        promotion=(ROOT/'scripts/promote_albums.py').read_text()
        self.assertIn('composed=music_core_videos.compose(composed)',promotion)
        self.assertIn('[music_core_videos.VIDEO_ID]',promotion)

if __name__=='__main__':unittest.main()
