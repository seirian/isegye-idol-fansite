"""Selected collaboration evidence, member attribution and preservation; no network."""
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import json, sys, unittest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import irise_lilpa_videos as collab
import external_videos, music_core_videos, m2_relay_videos

def baseline():
    return {'songs':[{'id':'rebels','videoId':'y-klhPVFblg','date':'2026-11-09'}],
            'albums':[{'id':'original','songIds':['rebels']}], 'channels':[{'key':'c2'}],
            'videos':[{'id':'y-klhPVFblg','category':'group'}], 'scope':{'videoChannelCount':22},
            'history':[], 'notices':[], 'events':[], 'members':[{'id':'lilpa'}]}

def previous():
    return m2_relay_videos.compose(music_core_videos.compose(external_videos.compose(baseline())))

class IriseLilpaVideos(unittest.TestCase):
    def test_exact_public_source(self):
        doc=collab.load();self.assertEqual(doc['videos'],[collab.EXPECTED])
        self.assertEqual(doc['evidenceRun'],44108855400)
        self.assertEqual(doc['channel']['name'],'IRISÉ')
        self.assertEqual(doc['videos'][0]['durationSeconds'],5731)
    def test_only_one_selected_video(self):
        before=previous();after=collab.compose(before)
        self.assertEqual(len(after['videos']),len(before['videos'])+1)
        self.assertEqual(after['scope']['selectedExternalVideoCount'],5)
        self.assertEqual(after['scope']['videoChannelCount'],22)
        self.assertFalse(after['channels'][-1]['coverageComplete'])
        self.assertEqual(after['channels'][-1]['coverageMode'],'selected_video_ids')
    def test_lilpa_only_not_all_group_members(self):
        video=collab.compose(baseline())['videos'][-1]
        self.assertEqual(video['members'],['lilpa'])
        self.assertEqual(video['externalGuests'],['키리','티즈'])
        self.assertEqual(video['memberBasis'],'explicit_credit')
    def test_collaboration_not_music_performance(self):
        video=collab.compose(baseline())['videos'][-1]
        self.assertEqual(video['category'],'external')
        self.assertEqual(video['type'],'external_collaboration')
        self.assertEqual(video['format'],'합방 다시보기')
        self.assertEqual(video['recordingKind'],'livestream_archive')
        self.assertNotIn('relatedSong',video)
        self.assertNotIn('qualityLabel',video)
        self.assertNotIn('4K',video['summary'])
    def test_broadcast_start_and_video_publication_are_distinct(self):
        video=collab.compose(baseline())['videos'][-1]
        self.assertEqual(video['date'],'2026-11-16')
        self.assertEqual(video['dateLabel'],'영상 공개일')
        self.assertEqual(video['publishedAt'],'2026-11-16T10:45:19Z')
        self.assertEqual(video['liveStreamingDetails']['actualStartTime'],'2026-11-16T09:04:24Z')
        self.assertEqual(video['liveStreamingDetails']['actualEndTime'],'2026-11-16T10:39:58Z')
        self.assertEqual(video['liveBroadcastContent'],'none')
        self.assertIn('18:04:24',video['summary']);self.assertIn('19:45:19',video['summary'])
    def test_region_restriction_preserved(self):
        video=collab.compose(baseline())['videos'][-1]
        self.assertEqual(video['regionRestriction'],{'blocked':['RU']})
        self.assertIn('러시아',video['summary'])
    def test_original_content_and_input_unchanged(self):
        before=previous();saved=deepcopy(before);after=collab.compose(before)
        self.assertEqual(before,saved)
        for key in before:
            if key not in ('videos','channels','scope'):self.assertEqual(before[key],after[key])
        self.assertEqual(before['videos'],after['videos'][:-1])
        self.assertEqual(before['channels'],after['channels'][:-1])
    def test_idempotent_and_deeply_copied(self):
        once=collab.compose(previous());self.assertEqual(once,collab.compose(once))
        once['videos'][-1]['liveStreamingDetails']['actualStartTime']='changed'
        self.assertEqual(collab.load()['videos'][0],collab.EXPECTED)
    def test_unrequested_or_duplicate_ids_refused(self):
        for rows in ([],[collab.EXPECTED,collab.EXPECTED]):
            doc=collab.load();doc['videos']=rows
            with self.assertRaises(ValueError):collab.validate(doc)
        doc=collab.load();doc['videos'][0]['id']='abcdefghijk'
        with self.assertRaises(ValueError):collab.validate(doc)
    def test_channel_and_evidence_spoof_refused(self):
        for field in collab.CHANNEL:
            doc=collab.load();doc['channel'][field]='unverified'
            with self.assertRaises(ValueError):collab.validate(doc)
        for field,value in [('source','unverified'),('evidenceRun',0),('selection','whole_channel')]:
            doc=collab.load();doc[field]=value
            with self.assertRaises(ValueError):collab.validate(doc)
    def test_metadata_changes_refused(self):
        for field,value in [('title','unverified'),('durationSeconds',5731.0),('durationSeconds','5731'),
                ('privacyStatus','private'),('embeddable',False),('embeddable',1),
                ('type','external_performance'),('liveBroadcastContent','live'),
                ('recordingKind','music_video'),('regionRestriction',{}),('liveStreamingDetails',{}),
                ('publishedAt','2026-11-16T09:04:24Z')]:
            with self.subTest(field=field):
                doc=collab.load();doc['videos'][0][field]=value
                with self.assertRaises(ValueError):collab.validate(doc)
    def test_no_inferred_related_song_or_quality(self):
        for field,value in [('relatedSong','rebels'),('qualityLabel','4K'),('members',external_videos.MEMBERS)]:
            doc=collab.load();doc['videos'][0][field]=value
            with self.assertRaises(ValueError):collab.validate(doc)
    def test_verification_time_refused(self):
        with self.assertRaises(ValueError):collab.validate(collab.load(),datetime(2026,11,15,tzinfo=timezone.utc))
        for value in ('2026-11-17T14:57:59','2026-11-15T00:00:00Z'):
            doc=collab.load();doc['checkedAt']=value
            with self.assertRaises(ValueError):collab.validate(doc)
    def test_existing_identity_conflicts_refused(self):
        for key,identity in [('videos',{'id':collab.VIDEO_ID}),('channels',{'key':collab.CHANNEL_KEY})]:
            data=previous();data[key].append(identity)
            with self.assertRaises(ValueError):collab.compose(data)
            data=collab.compose(previous());data[key].append(deepcopy(data[key][-1]))
            with self.assertRaises(ValueError):collab.compose(data)
    def test_canonical_link_retains_video_id(self):
        video=collab.compose(baseline())['videos'][-1]
        self.assertEqual(video['url'],'https://www.youtube.com/watch?v=P15VglxEkss')
        self.assertEqual(video['sourceLinks'][0]['url'],video['url'])
        self.assertNotIn('si=',json.dumps(video))
    def test_integrated_before_upload_and_in_manifest(self):
        code=(ROOT/'scripts/promote_albums.py').read_text()
        self.assertIn('composed=irise_lilpa_videos.compose(composed)',code)
        self.assertIn('[irise_lilpa_videos.VIDEO_ID]',code)
        workflow=(ROOT/'.github/workflows/production.yml').read_text()
        self.assertLess(workflow.index('tests/external_videos_browser.py'),workflow.index('scripts/deploy_verified_albums.py'))
        browser=(ROOT/'tests/external_videos_browser.py').read_text()
        self.assertIn('video/P15VglxEkss',browser)
        self.assertIn('members=lilpa',browser)
    def test_no_channel_wide_collection(self):
        for name in ('catalog/video-sources.json','catalog/video-sources.tsv','catalog/members.json',
                'scripts/refresh_catalog_videos.py','scripts/backfill_channel_videos.py'):
            self.assertNotIn(collab.CHANNEL_ID,(ROOT/name).read_text())

if __name__=='__main__':unittest.main()
