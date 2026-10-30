"""Berriz public-source safety, KST dates and last-good retention (offline)."""
import copy,json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import berriz_feed as b
import schedule_feed as f
import notice_policy as p
NOW='2026-10-30T12:28:17Z'
def event(**extra):
    return {'id':'6acf0c8230c3dcddaf47c7f9','title':'HAPPY JINGBURGER DAY','type':'BIRTHDAY',
      'startDate':'2026-10-07T15:00:00Z','endDate':None,'isAllDay':True,
      'visibility':{'status':'PUBLISHED','publishAt':'2026-09-30T15:00:00Z'},'members':[{'name':'징버거'}],**extra}
def parsed(row=None,month='2026-10'):
    r=row or event();return b.calendar_rows([r],month,{r['title']},NOW)
def notice():
    return b.notice_row({'url':b.NOTICE+'2701/','text':'[안내] 이세계아이돌 영상통화 팬사인회 안내\n2026.10.30'},NOW)
class Berriz(unittest.TestCase):
    def test_only_owner_menus(self):
        for u in ['https://berriz.in/ko/other/notice/1/','https://berriz.in/ko/isegyeidol/board/1/','https://evil.test/ko/isegyeidol/notice/1/','https://user@berriz.in/ko/isegyeidol/notice/1/','https://berriz.in/ko/isegyeidol/notice/1/?next=evil','http://berriz.in/ko/isegyeidol/notice/1/']:
            self.assertIsNone(b.canonical(u))
    def test_list_title_and_published_day(self):
        row=notice();self.assertEqual(row['publishedAt'],'2026-10-30T00:00:00+09:00');self.assertNotIn('date',row);self.assertNotIn('body',row);self.assertTrue(p.is_publishable(row))
    def test_notices_cannot_be_disguised_fan_posts(self):
        row=notice();row['sourceUrl']='https://berriz.in/ko/isegyeidol/board/1/';self.assertFalse(p.is_publishable(row))
    def test_id_url_must_match(self):
        row=notice();row['id']='berriz-notice-999';self.assertFalse(p.is_publishable(row))
    def test_membership_title_excluded(self):
        self.assertIsNone(b.notice_row({'url':b.NOTICE+'999/','text':'팬클럽 전용 공지 2026.10.30'},NOW))
    def test_day_not_invented(self):
        with self.assertRaises(b.BerrizError):b.notice_row({'url':b.NOTICE+'999/','text':'새 공지'},NOW)
    def test_health_details_neutral(self):
        title=b.clean_title('[안내] 이세계아이돌 아이네 컨디션 및 향후 스케줄 참여 안내')
        self.assertNotIn('컨디션',title);self.assertEqual(b.members(title),['ine'])
    def test_birthday_kst_not_utc(self):
        row=parsed()[0];self.assertEqual(row['date'],'2026-10-08');self.assertIsNone(row['time']);self.assertEqual(row['type'],'anniversary');self.assertEqual(row['members'],['jingburger'])
    def test_timed_release_kst(self):
        row=parsed(event(title='이세계아이돌 ALBUM RELEASE',type='RELEASE',startDate='2026-11-09T09:00:00Z',isAllDay=False,members=[{'name':'이세계아이돌'}]),'2026-11')[0]
        self.assertEqual(row['time'],'18:00');self.assertEqual(row['date'],'2026-11-09');self.assertEqual(len(row['members']),6)
    def test_unknown_timezone_rejected(self):
        with self.assertRaises(b.BerrizError):parsed(event(startDate='2026-10-08T00:00:00'))
    def test_invisible_event_rejected(self):self.assertEqual(b.calendar_rows([event()],'2026-10',set(),NOW),[])
    def test_unpublished_rejected(self):self.assertEqual(parsed(event(visibility={'status':'DRAFT'})),[])
    def test_future_publication_rejected(self):self.assertEqual(parsed(event(visibility={'status':'PUBLISHED','publishAt':'2027-01-01T00:00:00Z'})),[])
    def test_extra_month_not_published(self):self.assertEqual(parsed(event(),'2026-11'),[])
    def test_no_fan_board_url_stored(self):
        row=parsed(event(boardId='fan-board',description='do not store this'))[0]
        self.assertEqual(row['sourceUrl'],b.CALENDAR);self.assertNotIn('boardId',row);self.assertNotIn('description',row)
    def test_calendar_source_identity(self):
        row=parsed()[0];self.assertTrue(p.is_publishable(row));row['calendarId']='other';self.assertFalse(p.is_publishable(row))
    def test_robots_disallow(self):
        with self.assertRaises(b.BerrizError):b.robots_ok(lambda _: 'User-agent: *\nDisallow: /')
    def test_robots_allow(self):b.robots_ok(lambda _:'User-agent: *\nAllow: /\nDisallow: /private/')
    def test_month_rollover(self):self.assertEqual(b.month_shift('2026-12',1),'2027-01');self.assertEqual(b.month_shift('2026-01',-1),'2025-12')
    def test_no_direct_service_api_client(self):
        src=(ROOT/'scripts/berriz_feed.py').read_text();self.assertNotIn("urlopen('https://svc-api",src);self.assertNotIn('context.request.get',src)
    def test_legacy_snapshot_accepted(self):f.validate(json.loads((ROOT/'schedule/snapshot.json').read_text()))
    def test_failure_retains_last_success(self):
        old=json.loads((ROOT/'schedule/seed.json').read_text());old['sources'] += [{**s,'state':'ok','lastSuccessAt':NOW} for s in b.SOURCES];old['news'].append(notice());old['events']+=parsed()
        result=f.collect(previous=old,now='2026-10-30T13:00:00Z',fetch=lambda u: (_ for _ in ()).throw(f.FeedError('fixture_fail')),berriz_reader=lambda n:{})
        self.assertTrue(any(r['id']==notice()['id'] for r in result['news']));state=next(s for s in result['sources'] if s['id']=='berriz-notice');self.assertEqual(state['lastSuccessAt'],NOW);self.assertEqual(state['state'],'error')
    def test_complete_month_removes_stale_event(self):
        old=json.loads((ROOT/'schedule/seed.json').read_text());old['sources'] += [{**s,'state':'ok','lastSuccessAt':NOW} for s in b.SOURCES];old['events']+=parsed()
        current=copy.deepcopy(old);current['events']=[r for r in current['events'] if r['sourceId']!='berriz-calendar'];current['sources'][-1]['coverage']={'months':['2026-10'],'complete':True}
        self.assertFalse(any(r['sourceId']=='berriz-calendar' for r in f.merge(old,current)['events']))
    def test_invalid_ranges_rejected(self):
        with self.assertRaises(b.BerrizError):parsed(event(endDate='2025-10-01T00:00:00Z'))
if __name__=='__main__':unittest.main()
