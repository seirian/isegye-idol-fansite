from pathlib import Path
from datetime import datetime,timezone,timedelta
import sys,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import collect_album_domestic as c
class DomesticTests(unittest.TestCase):
    def song(self):return {'id':'cat-save-world','title':'고양이가 세상을 구한다!','album':'NO CAT, NO LIFE!','members':['gosegu'],'dateKind':'발매일'}
    def row(self):return {'trackId':'123','title':'고양이가 세상을 구한다!','album':'NO CAT, NO LIFE!','artist':'고세구'}
    def test_exact_match(self):self.assertEqual(c.match(self.song(),[self.row()])['trackId'],'123')
    def test_wrong_artist(self):self.assertIsNone(c.match(self.song(),[{**self.row(),'artist':'다른 가수'}]))
    def test_ambiguous_ids(self):self.assertIsNone(c.match(self.song(),[self.row(),{**self.row(),'trackId':'124'}]))
    def test_video_not_assumed_distributed(self):self.assertIsNone(c.match({**self.song(),'dateKind':'영상 공개일'},[self.row()]))
    def test_bad_urls(self):
        for url in ['https://www.melon.com.evil.invalid/a','http://www.melon.com/a','https://user:pass@www.melon.com/a','https://127.0.0.1/x','https://www.melon.com:8080/x']:
            with self.assertRaises(ValueError):c.valid_url(url)
    def test_genie_rank_200_and_gap(self):
        now=datetime.now(timezone.utc);p={'at':now.isoformat(),'rank':200,'status':'ranked','trackId':'123'}
        self.assertEqual(c.merge([],p,now,'123',200),[p]);self.assertEqual(c.merge([],p,now,'123',100),[])
    def test_chart_requires_complete_rank_set(self):
        now=datetime.now(timezone.utc);kst=now.astimezone(c.KST)
        html='<div class="calendar_prid"><span class="year">'+kst.strftime('%Y.%m.%d')+'</span><span class="hour">'+kst.strftime('%H:00')+'</span></div>'
        html+='<table>'+''.join(f'<tr data-song-no="{i+1000}"><td><span class="rank">{i}</span></td></tr>' for i in range(1,101))+'</table>'
        ranks,_=c.chart_rows(html,'melon',now);self.assertEqual(len(ranks),100)
        with self.assertRaises(ValueError):c.chart_rows(html.replace('data-song-no="1100"','data-song-no="1099"'),'melon',now)
        with self.assertRaises(ValueError):c.chart_rows(html,'melon',now+timedelta(days=1))
    def test_only_source_timestamp_deduplicated(self):
        now=datetime.now(timezone.utc);p={'at':now.isoformat(),'rank':None,'status':'out','trackId':'123'}
        self.assertEqual(c.merge([p],p,now,'123',100),[p]);self.assertEqual(c.merge([],{**p,'rank':0},now,'123',100),[])
    def test_display_filters_removed(self):
        ui=(Path(__file__).resolve().parents[1]/'albums/ui.js').read_text()
        self.assertIn('한 곡에서 시작되는 이야기',ui);self.assertIn('<h2>음원 연결</h2>',ui)
        self.assertNotIn('정보 범위',ui);self.assertNotIn("p.get('coverage')",ui)
    def test_platform_links_have_no_arrow(self):
        ui=(Path(__file__).resolve().parents[1]/'albums/ui.js').read_text().split('function aiStreaming(')[1].split('function aiProviders(')[0]
        self.assertIn('ai-platform-logo',ui);self.assertNotIn("icon('external')",ui)
if __name__=='__main__':unittest.main()
