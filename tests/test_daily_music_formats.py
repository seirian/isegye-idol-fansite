import unittest,sys
from datetime import datetime,timezone
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import daily_music as m
from official_channel_music import OBSERVED_ATOM
HEAD='ISEGYE IDOL (이세계아이돌) '
MEDLEY=HEAD+'‘Across Dimensions’ HIGHLIGHT MEDLEY'
CLIP=HEAD+'‘Smile For You’ Special Clip'
class Formats(unittest.TestCase):
    def test_real_channel_titles(self):
        known=m.baseline()[1]
        positives={MEDLEY:('Across Dimensions','album_medley'),CLIP:('Smile For You','music_clip'),HEAD+'‘Smile For You’ (Official Audio)':('Smile For You','official_track'),"이세계아이돌(ISEGYE IDOL) 'Be My Light' Official Performance MV":('Be My Light','official_track'),"이세계아이돌(ISEGYE IDOL) '화이트 (White)' Special Clip":('화이트 (White)','music_clip')}
        for t,w in positives.items():
            with self.subTest(t=t):
                r=m.classify('c2',t,known);self.assertEqual((r['title'],r['type']),w);self.assertEqual(set(r['members']),set(m.NAMES))
        for t in [CLIP+' Teaser',HEAD+'‘Across Dimensions’ HIGHLIGHT',HEAD+'‘Across Dimensions’ HIGHLIGHT MEDLEY REACTION','(SUB) 이세계아이돌 Smile For You 컴백 비하인드 | ISEGYE IDOL Highlight','(SUB) ISEGYE IDOL (이세계아이돌) 8시 15분쯤 뉴스',HEAD+'Official Logo Motion',HEAD+'‘음악 토크’ Special Clip','일반 채널 ‘Across Dimensions’ HIGHLIGHT MEDLEY','(SUB) 우리 중에 스파이가 숨어 있어! | ISEGYE IDOL Highlight',HEAD+'‘Smile For You’ Special Clip #Shorts',HEAD+'‘Smile For You’ Official MV Reaction']:
            with self.subTest(t=t):self.assertIsNone(m.classify('c2',t,known))
        for other in set(m.CHANNELS)-{'c1','c2'}:
            self.assertIsNone(m.classify(other,MEDLEY));self.assertIsNone(m.classify(other,CLIP))
        self.assertEqual(m.classify('c1',MEDLEY,known)['type'],'album_medley')
        self.assertEqual(m.classify('c1',CLIP,known)['type'],'music_clip')
    def test_new_clip_needs_song_evidence(self):
        clip=HEAD+'‘새 작업’ Special Clip';audio=HEAD+'‘새 작업’ Official Audio'; self.assertIsNone(m.classify('c2',clip,set()))
        known=m.channel_evidence('c2',[audio],set());self.assertEqual(m.classify('c2',clip,known)['type'],'music_clip')
        self.assertIsNone(m.classify('c2',clip,m.channel_evidence('c2',[clip],set())))
        self.assertIsNone(m.classify('c2',HEAD+'‘다른 곡’ Special Clip',known))
    def test_format_dedup_not_song_release(self):
        evidence=m.baseline()[1];stamp='2026-11-02T09:00:14+00:00'
        def row(t,vid):return dict(m.classify('c2',t,evidence),videoId=vid,channelKey='c2',publishedAt=stamp,checkedAt=stamp)
        a=row(CLIP,'12345678901');b=row(HEAD+'‘Smile For You’ Official MV','23456789012');c=row(HEAD+'‘Smile For You’ HIGHLIGHT MEDLEY','34567890123')
        self.assertEqual(len(m.merge([],[a,b,c],(set(),set()))),3)
        self.assertEqual(m.merge([a],[dict(a,videoId='45678901234'),a],(set(),evidence)),[a]);self.assertEqual(m.merge([],[a],({a['videoId']},set())),[])
        for delta in ({'channelKey':'c4'},{'kind':'official_audio'}):
            with self.assertRaises(ValueError):m.validate([{**a,**delta}])
    def test_observed_atom_is_exact(self):
        cid=m.CHANNELS['c2'][0];self.assertEqual(OBSERVED_ATOM.get((cid,'lFgCjRoFjyU',MEDLEY)),'2026-11-02T09:00:14+00:00');self.assertIsNone(OBSERVED_ATOM.get((cid,'lFgCjRoFjyU',CLIP)));self.assertIsNone(OBSERVED_ATOM.get((m.CHANNELS['c1'][0],'lFgCjRoFjyU',MEDLEY)))
