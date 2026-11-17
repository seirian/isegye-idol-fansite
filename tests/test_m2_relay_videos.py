"""Verified owner-selected M2 relay video; no network or channel-wide collection."""
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import json, sys, unittest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import external_videos as external
import music_core_videos as core
import m2_relay_videos as relay

def baseline():
    return {'songs':[{'id':'rebels','videoId':'y-klhPVFblg','date':'2026-11-09','albumId':'original'}],
            'albums':[{'id':'original','songIds':['rebels']}], 'channels':[{'key':'c2'}],
            'videos':[{'id':'y-klhPVFblg','category':'group'}], 'scope':{'videoChannelCount':22},
            'history':[], 'notices':[]}

def previous():
    return core.compose(external.compose(baseline()))

class M2RelayVideos(unittest.TestCase):
    def test_exact_verified_public_metadata(self):
        doc=relay.load();self.assertEqual(doc['videos'],[relay.EXPECTED])
        self.assertEqual(doc['channel']['name'],'M2')
        self.assertEqual(doc['videos'][0]['durationSeconds'],198)
        self.assertEqual(doc['evidenceRun'],44057788105)
    def test_four_selected_videos_three_external_channels(self):
        before=previous();result=relay.compose(before)
        self.assertEqual(len(result['videos'])-len(before['videos']),1)
        self.assertEqual(result['scope']['selectedExternalVideoCount'],4)
        self.assertEqual(result['scope']['videoChannelCount'],22)
        self.assertEqual([c['key'] for c in result['channels'][1:]],[external.CHANNEL_KEY,core.CHANNEL_KEY,relay.CHANNEL_KEY])
        self.assertTrue(all(c['coverageMode']=='selected_video_ids' and not c['coverageComplete'] for c in result['channels'][1:]))
    def test_previous_metadata_and_original_mv_unchanged(self):
        before=previous();old=deepcopy(before);after=relay.compose(before)
        self.assertEqual(before,old)
        for key in ('songs','albums','history','notices'):self.assertEqual(before[key],after[key])
        self.assertEqual(before['videos'],after['videos'][:-1])
        self.assertEqual(before['channels'],after['channels'][:-1])
    def test_idempotent(self):
        result=relay.compose(previous());self.assertEqual(result,relay.compose(result))
    def test_publication_is_not_album_release(self):
        result=relay.compose(previous());video=result['videos'][-1]
        self.assertEqual(video['publishedAt'],'2026-11-16T09:00:17Z')
        self.assertEqual(video['date'],'2026-11-16');self.assertEqual(video['dateLabel'],'영상 공개일')
        self.assertEqual(result['songs'][0]['date'],'2026-11-09')
    def test_relay_classification_and_quality_source(self):
        video=relay.compose(baseline())['videos'][-1]
        self.assertEqual(video['category'],'external');self.assertEqual(video['type'],'external_performance')
        self.assertEqual(video['performanceKind'],'relay_dance');self.assertEqual(video['format'],'4K 릴레이댄스')
        self.assertEqual(video['qualityBasis'],'source_title');self.assertIn('원본 제목',video['summary'])
        self.assertEqual(video['members'],external.MEMBERS)
        self.assertEqual(video['relatedSong'],'rebels')
    def test_wrong_channel_or_source_refused(self):
        for field in ('channelId','name','url','key'):
            with self.subTest(field=field):
                doc=relay.load();doc['channel'][field]='unverified'
                with self.assertRaises(ValueError):relay.validate(doc)
        for field,value in [('source','unverified'),('evidenceRun',0),('selection','whole_channel')]:
            doc=relay.load();doc[field]=value
            with self.assertRaises(ValueError):relay.validate(doc)
    def test_unrequested_video_refused(self):
        for vid in ('z8AJgnTC52k','Mj7q8HU8ZXg','sy40EGkSfRA','abcdefghijk'):
            doc=relay.load();doc['videos'][0]['id']=vid
            with self.assertRaises(ValueError):relay.validate(doc)
    def test_duplicate_and_empty_selection_refused(self):
        for rows in ([],[relay.EXPECTED,relay.EXPECTED]):
            doc=relay.load();doc['videos']=rows
            with self.assertRaises(ValueError):relay.validate(doc)
    def test_modified_evidence_refused(self):
        for field,value in [('title','unverified'),('durationSeconds',192),('durationSeconds','198'),
                ('durationSeconds',198.0),('privacyStatus','private'),('embeddable',False),('embeddable',1),
                ('relatedSong','kidding'),('type','external_teaser'),('performanceKind','music_broadcast'),
                ('publishedAt','2026-11-17T09:00:17Z'),('qualityBasis','measured_resolution')]:
            with self.subTest(field=field,value=value):
                doc=relay.load();doc['videos'][0][field]=value
                with self.assertRaises(ValueError):relay.validate(doc)
    def test_invalid_verification_time_refused(self):
        with self.assertRaises(ValueError):relay.validate(relay.load(),datetime(2026,11,15,tzinfo=timezone.utc))
        for value in ('2026-11-17T09:41:08','2026-11-15T09:00:17Z'):
            doc=relay.load();doc['checkedAt']=value
            with self.assertRaises(ValueError):relay.validate(doc)
    def test_missing_or_wrong_mv_refused(self):
        for songs in ([],[{'id':'rebels','videoId':relay.VIDEO_ID}]):
            data=baseline();data['songs']=songs
            with self.assertRaises(ValueError):relay.compose(data)
    def test_conflicting_identity_refused(self):
        data=baseline();data['videos'].append({'id':relay.VIDEO_ID})
        with self.assertRaises(ValueError):relay.compose(data)
        data=baseline();data['channels'].append({'key':relay.CHANNEL_KEY})
        with self.assertRaises(ValueError):relay.compose(data)
    def test_duplicate_existing_identity_refused(self):
        data=relay.compose(previous());data['videos'].append(deepcopy(data['videos'][-1]))
        with self.assertRaises(ValueError):relay.compose(data)
        data=relay.compose(previous());data['channels'].append(deepcopy(data['channels'][-1]))
        with self.assertRaises(ValueError):relay.compose(data)
    def test_canonical_source_links_without_tracking(self):
        video=relay.compose(baseline())['videos'][-1]
        self.assertEqual(video['url'],'https://www.youtube.com/watch?v=mkJRSPYjX8k')
        self.assertEqual(video['channelUrl'],'https://www.youtube.com/channel/'+relay.CHANNEL_ID)
        self.assertEqual(video['sourceLinks'][0]['url'],video['url']);self.assertNotIn('?si=',json.dumps(video))
    def test_operating_composition_and_preupload_regression(self):
        promotion=(ROOT/'scripts/promote_albums.py').read_text()
        self.assertIn('composed=m2_relay_videos.compose(composed)',promotion)
        self.assertIn('[m2_relay_videos.VIDEO_ID]',promotion)
        workflow=(ROOT/'.github/workflows/production.yml').read_text()
        self.assertLess(workflow.index('tests/external_videos_browser.py'),workflow.index('scripts/deploy_verified_albums.py'))
    def test_no_m2_whole_channel_ingestion(self):
        for path in ('scripts/refresh_catalog_videos.py','scripts/backfill_channel_videos.py','catalog/channels.tsv'):
            p=ROOT/path
            if p.is_file():self.assertNotIn(relay.CHANNEL_ID,p.read_text())

if __name__=='__main__':unittest.main()
