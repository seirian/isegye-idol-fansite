"""Selection identity, coverage and source-label regression tests; no network."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from music_video_sources import selections,apply_video_sources
from enhance_catalog import load_music
class MusicSourcesTests(unittest.TestCase):
 def setUp(self):self.config,self.rows=selections();self.music=load_music();self.by={s['id']:s for s in self.music['songs']}
 def test_all_154_reviewed(self):self.assertEqual(len(self.rows),154);self.assertEqual(len(self.music['songs']),154)
 def test_151_selected_and_three_unresolved(self):self.assertEqual(self.music['videoAudit']['linked'],151);self.assertEqual(self.music['videoAudit']['kinds']['unavailable'],3)
 def test_selected_links_match_ids(self):
  for s in self.music['songs']:
   if s.get('videoId'):self.assertEqual(s['url'],'https://www.youtube.com/watch?v='+s['videoId'])
 def test_official_missing_mv_fixed(self):
  for sid,v in [('rewind','fgSXAKsq-Vo'),('winter-spring','JY-gJkMuJ94'),('kidding','rDFUl2mHIW4'),('be-my-light','3cEUPoPXz7E'),('cat-save-world','zGOzGcEbd-s')]:self.assertEqual(self.by[sid]['videoId'],v);self.assertTrue(self.by[sid]['videoSource']['kind'].startswith('official'))
 def test_audio_is_not_labelled_mv(self):self.assertEqual(self.by['your-turn']['videoSource']['kind'],'official_audio');self.assertEqual(self.by['pump-jump-bump']['videoSource']['kind'],'official_audio')
 def test_cover_route_identity_retained(self):self.assertEqual(self.by['cover-TYB9ScXvq34']['originalVideoId'],'TYB9ScXvq34');self.assertEqual(self.by['cover-TYB9ScXvq34']['videoId'],'IajO_xnbyFE')
 def test_fan_backup_not_official(self):self.assertEqual(self.by['cover-TYB9ScXvq34']['videoSource']['kind'],'fan_backup')
 def test_karaoke_is_explicit(self):
  for sid in ('cover-gT3HKgVJuRQ','cover-Kc85nOaqLwo','cover-buJjUHSalVA'):self.assertEqual(self.by[sid]['videoSource']['kind'],'karaoke_tj');self.assertIn('반주',self.by[sid]['videoSource']['note'])
 def test_unmatched_items_have_no_false_link(self):
  for sid in ('cover-WItY2T5zz1A','cover-7E_cZ9eU3ZE','cover-q8iiUYJsOUM'):self.assertNotIn('videoId',self.by[sid]);self.assertEqual(self.by[sid]['videoSource']['kind'],'unavailable')
 def test_dates_are_not_backup_upload_dates(self):self.assertEqual(self.by['rewind']['date'],'2021-12-17');self.assertEqual(self.by['cat-save-world']['date'],'2026-09-28')
 def test_missing_record_fails(self):rows=copy.deepcopy(self.rows);rows.pop('rewind');self.assertRaises(ValueError,apply_video_sources,self.music,self.config,rows)
 def test_extra_record_fails(self):rows=copy.deepcopy(self.rows);rows['other']=rows['rewind'];self.assertRaises(ValueError,apply_video_sources,self.music,self.config,rows)
 def test_raw_catalog_and_stable_ids_preserved(self):self.assertEqual(len(self.by),154);self.assertEqual(sum(s['type']=='cover' for s in self.music['songs']),133)
 def test_public_metadata_does_not_claim_playback_or_permission(self):self.assertIs(self.music['videoAudit']['fullPlaybackVerified'],False)
 def test_unsafe_selection_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'catalog';p.mkdir();(p/'video-sources.json').write_text(json.dumps(self.config));(p/'video-sources.tsv').write_text('rewind\tjavascript:x\tofficial_mv\tc1\n');self.assertRaises(ValueError,selections,Path(d))
 def test_channel_role_spoof_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'catalog';p.mkdir();c=copy.deepcopy(self.config);c['channels']['c1']['role']='fan';(p/'video-sources.json').write_text(json.dumps(c));(p/'video-sources.tsv').write_text('rewind\tfgSXAKsq-Vo\tofficial_mv\tc1\n');self.assertRaises(ValueError,selections,Path(d))
if __name__=='__main__':unittest.main()
