"""The preview collects only Melon time-series; free metadata stays available."""
from pathlib import Path
from unittest.mock import patch
import sys, unittest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import collect_album_insights as insights
class FlowScopeTests(unittest.TestCase):
    def test_apple_chart_is_not_called_in_melon_only_mode(self):
        calls=[]
        def response(url):
            calls.append(url)
            return {'results':[]}
        with patch.object(insights,'fetch_json',side_effect=response),patch.object(insights.time,'sleep'),patch.dict(insights.os.environ,{'ISEGYE_YOUTUBE_API_KEY':''}):
            data=insights.collect({},include_apple_chart=False)
        self.assertEqual(len(calls),2)
        self.assertTrue(all(u.startswith('https://itunes.apple.com/search?') for u in calls))
        self.assertEqual(data['providers']['apple_chart']['state'],'excluded')
        self.assertEqual(data['providers']['itunes']['state'],'ok')
    def test_cached_apple_chart_is_not_restored_as_new_measurement(self):
        row={'kind':'song','trackId':6810571941,'trackName':'NO CAT, NO LIFE!','artistName':'GOSEGU','collectionName':'NO CAT, NO LIFE! - Single','trackTimeMillis':175000}
        prior={'tracks':{'cat-save-world':{'metadata':{'trackId':'6810571941'},'appleChartMatch':'observed_kr_feed','appleHistory':[{'rank':12}]}}}
        with patch.object(insights,'fetch_json',return_value={'results':[row]}),patch.object(insights.time,'sleep'),patch.dict(insights.os.environ,{'ISEGYE_YOUTUBE_API_KEY':''}):
            data=insights.collect(prior,include_apple_chart=False)
        self.assertEqual(data['tracks']['cat-save-world']['appleHistory'],[])
        self.assertIn('metadata',data['tracks']['cat-save-world'])
    def test_review_entrypoint_explicitly_selects_melon(self):
        source=(ROOT/'scripts/refresh_album_review.py').read_text()
        self.assertIn('include_apple_chart=False',source)
        self.assertIn("chart_kinds={'melon_top100','melon_hot100'}",source)
    def test_curve_does_not_enable_scheduled_collection(self):
        flow=(ROOT/'.github/workflows/albums-preview.yml').read_text()
        self.assertNotIn('schedule:',flow)
        self.assertNotIn('APPLE_MUSIC_TOKEN',flow)
if __name__=='__main__':unittest.main()
