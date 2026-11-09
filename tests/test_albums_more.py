from pathlib import Path
import json,sys,unittest
from datetime import datetime,timezone,timedelta
from email.utils import format_datetime
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import collect_album_insights as c
class MoreAlbumTests(unittest.TestCase):
    def feed(self):
        return {'feed':{'country':'kr','updated':format_datetime(datetime.now(timezone.utc)),'results':[{'id':str(i),'name':'Fixture','kind':'songs'} for i in range(1,101)]}}
    def test_rfc_feed_dates_supported(self):
        ranks,stamp=c.validate_chart(self.feed());self.assertEqual(ranks['1'],1);self.assertEqual(ranks['100'],100)
    def test_us_absence_does_not_mean_kr_chart_out(self):
        row={'kind':'song','trackId':6810571941,'trackName':'NO CAT, NO LIFE!','artistName':'GOSEGU','collectionName':'NO CAT, NO LIFE! - Single','trackTimeMillis':175000}
        def response(url):return self.feed() if url==c.CHART else {'results':[row]}
        with patch.object(c,'fetch_json',side_effect=response),patch.object(c.time,'sleep'),patch.dict(c.os.environ,{'ISEGYE_YOUTUBE_API_KEY':''}),patch.object(Path,'write_text'):
            data=c.collect()
        item=data['tracks']['cat-save-world']
        self.assertEqual(item['metadata']['storefront'],'US');self.assertEqual(item['match'],'matched')
        self.assertEqual(item['appleChartMatch'],'unverified_storefront');self.assertEqual(item['appleHistory'],[])
    def test_official_mapping_never_uses_fan_backup(self):
        source=json.loads((c.ROOT/'catalog/music.json').read_text())['songs'];mapping=c.official_bindings(source)
        self.assertEqual(mapping['cat-save-world'],'zGOzGcEbd-s');self.assertNotIn('but-you-want-more',mapping)
    def test_hourly_video_retention_and_identity(self):
        now=datetime.now(timezone.utc);point={'at':now.isoformat(),'videoId':'abcdefghijk','viewCount':100}
        old={**point,'at':(now-timedelta(days=31)).isoformat()};wrong={**point,'videoId':'other'}
        self.assertEqual(c.video_history([old,wrong],point,now,'abcdefghijk'),[point])
    def test_plain_http_provider_url_refused(self):
        with self.assertRaises(ValueError):c.fetch_json('http://itunes.apple.com/search')
if __name__=='__main__':unittest.main()
