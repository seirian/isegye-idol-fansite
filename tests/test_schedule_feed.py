"""No real network, identities or production writes in these regression tests."""
from pathlib import Path
import copy,json,os,sys,unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import schedule_feed as f
import publish_schedule_feed as pub
import inour_sftp as d
import auth_routing as a
NOW='2026-10-30T01:00:00+00:00'
def seed():return json.loads((ROOT/'schedule/seed.json').read_text())
class Dates(unittest.TestCase):
 def test_no_date_from_publication(self):self.assertIsNone(f.event_from_title('고세구 새 소식',NOW,True))
 def test_explicit_year(self):self.assertEqual(f.explicit_date('2026년 11월 2일 공연'), '2026-11-02')
 def test_kst_today(self):self.assertEqual(f.explicit_date('오늘 방송','2026-10-29T23:30:00Z',True),'2026-10-30')
 def test_unverified_today(self):self.assertIsNone(f.explicit_date('오늘 방송',NOW,False))
 def test_invalid_date(self):self.assertIsNone(f.explicit_date('2026년 2월 30일 공연'))
 def test_two_dates(self):self.assertIsNone(f.explicit_date('2026년 11월 2일, 2026년 11월 3일 공연'))
 def test_ranges_not_single_day(self):self.assertIsNone(f.explicit_date('2026년 11월 2일~3일 공연'))
 def test_no_am_pm_guess(self):self.assertIsNone(f.explicit_time('오늘 7시 방송'))
 def test_explicit_pm(self):self.assertEqual(f.explicit_time('오후 7시 30분'),'19:30')
 def test_tentative(self):self.assertEqual(f.event_from_title('오늘 방송 예상?',NOW,True)['certainty'],'tentative')
 def test_cancel(self):self.assertEqual(f.event_from_title('2026년 11월 2일 공연 취소',NOW,True)['status'],'cancelled')
 def test_past_not_event(self):self.assertIsNone(f.event_from_title('2026년 11월 2일 공연 후기',NOW,True))
class Rules(unittest.TestCase):
 def test_seed_valid(self):f.validate(seed())
 def test_no_fan_confirmed(self):
  s=seed();s['forecasts'][0]['certainty']='confirmed'
  with self.assertRaises(f.FeedError):f.validate(s)
 def test_no_private_fields(self):
  for field in ('memberKey','email','body','comments','token'):
   s=seed();s['news'][0][field]='forbidden'
   with self.assertRaises(f.FeedError):f.validate(s)
 def test_foreign_source(self):
  s=seed();s['news'][0]['sourceUrl']='https://example.com/1'
  with self.assertRaises(f.FeedError):f.validate(s)
 def test_robots_denied_stops(self):
  calls=[]
  def fetch(url):calls.append(url);return b'User-agent: *\nDisallow: /'
  with self.assertRaises(f.FeedError):f.parable(fetch,NOW)
  self.assertEqual(calls,['https://parable-asia.com/robots.txt'])
 def test_cafe_not_crawled(self):
  calls=[]
  def fetch(url,**kwargs):calls.append(url);raise f.FeedError('blocked')
  with patch.dict(os.environ,{'ISEGYE_NAVER_CLIENT_ID':'','ISEGYE_NAVER_CLIENT_SECRET':''}):v=f.collect(fetch=fetch,now=NOW)
  self.assertTrue(all('cafe.naver.com' not in x and 'apis.naver.com' not in x for x in calls))
  self.assertEqual(next(x for x in v['sources'] if x['id']=='naver-search')['state'],'needs_setup')
 def test_network_policy_rejects_cafe_internal(self):
  for url in ('https://cafe.naver.com/steamindiegame/1','https://apis.naver.com/cafe-web/x','http://parable-asia.com/'):
   with self.assertRaises(f.FeedError):f.request(url)
 def test_search_not_official_or_dated(self):
  def fetch(url,**kw):return json.dumps({'items':[{'title':'아이네 오늘 방송','link':'https://cafe.naver.com/steamindiegame/999','description':'비공개 필드는 보관하지 않음'}]}).encode()
  with patch.dict(os.environ,{'ISEGYE_NAVER_CLIENT_ID':'fixture','ISEGYE_NAVER_CLIENT_SECRET':'fixture'}),patch('schedule_feed.time.sleep'):
   n=f.naver_search(fetch,NOW)
  self.assertEqual(len(n),1);self.assertIsNone(n[0]['publishedAt']);self.assertEqual(n[0]['sourceId'],'naver-search');self.assertNotIn('description',n[0])
 def test_rss_and_explicit_event(self):
  fixtures={'https://parable-asia.com/robots.txt':b'User-agent: *\nAllow: /', 'https://parable-asia.com/newsroom/':b'<link type="application/rss+xml" href="/feed/">','https://parable-asia.com/feed/':('<rss><channel><item><title>고세구 2026년 11월 2일 공연</title><link>https://parable-asia.com/test/</link><pubDate>Fri, 30 Oct 2026 00:00:00 +0000</pubDate></item></channel></rss>').encode()}
  n,e=f.parable(lambda u:fixtures[u],NOW);self.assertEqual(len(n),1);self.assertEqual(e[0]['date'],'2026-11-02')
 def test_rss_unknown_date_stays_news(self):
  fixtures={'https://parable-asia.com/robots.txt':b'User-agent: *\nAllow: /','https://parable-asia.com/newsroom/':b'<link type="application/rss+xml" href="/feed/">','https://parable-asia.com/feed/':('<rss><channel><item><title>이세계아이돌 새 소식</title><link>https://parable-asia.com/test/</link><pubDate>Fri, 30 Oct 2026 00:00:00 +0000</pubDate></item></channel></rss>').encode()}
  n,e=f.parable(lambda u:fixtures[u],NOW);self.assertEqual(len(n),1);self.assertFalse(e)
 def test_failure_preserves_without_restamping(self):
  old=seed();old['sources'][3]['lastSuccessAt']='2026-10-29T00:00:00Z'
  with patch.dict(os.environ,{'ISEGYE_NAVER_CLIENT_ID':'','ISEGYE_NAVER_CLIENT_SECRET':''}):v=f.collect(old,fetch=lambda u:(_ for _ in ()).throw(f.FeedError('http_503')),now=NOW)
  self.assertEqual(v['news'][0]['checkedAt'],old['news'][0]['checkedAt']);self.assertEqual(v['sources'][3]['lastSuccessAt'],old['sources'][3]['lastSuccessAt'])
 def test_fresh_changed_title_removes_old_date(self):
  old=seed();cur=copy.deepcopy(old);cur['generatedAt']=NOW
  target=cur['events'][0]['sourceUrl'];cur['events']=[r for r in cur['events'] if r['sourceUrl']!=target]
  for r in cur['news']:
   if r['sourceUrl']==target:r['checkedAt']=NOW;r['title']='일정 추후 공지'
  merged=f.merge(old,cur);self.assertFalse(any(r['sourceUrl']==target for r in merged['events']))
 def test_gateway_after_authorization(self):
  s=(ROOT/'auth/Gateway.php').read_text();self.assertLess(s.index("if (!$access['allowed'])"),s.index("if ($path === '/api/schedule')"))
 def test_only_four_private_files_writable(self):
  for n in ('current.json','previous.json','.owner','.lock'):self.assertTrue(pub.path(n).startswith('/web/_isegye_idol/.schedule-feed/'))
  for n in ('../.auth-private/accounts.json','/web/.htaccess','index.html'):
   with self.assertRaises(d.Stop):pub.path(n)
 def test_schedule_main_scoped(self):
  s=(ROOT/'.github/workflows/schedule-refresh.yml').read_text();self.assertIn("cron: '17 * * * *'",s);self.assertIn("github.ref == 'refs/heads/main'",s);self.assertIn('group: isegye-inour-production',s)
if __name__=='__main__':unittest.main()

from test_google_access_deploy import Remote,OLD
class FeedRemote(Remote):
 def __init__(self):
  super().__init__(True);self.files[d.ROOT+'/_isegye_releases/'+OLD+'/build-info.json']=b'{"scheduleFeed":{"schemaVersion":1}}'
 def remove_own(self,p,expected):
  d.require(self.files.get(p)==expected,'Changed lock');del self.files[p]
class Publication(unittest.TestCase):
 def test_atomic_publication_no_auth_writes(self):
  r=FeedRemote();auth={k:v for k,v in r.files.items() if '.auth-private' in k};v=pub.publish(r,lambda **kw:seed())
  self.assertEqual(v['status'],'published');self.assertTrue(all(x.startswith(pub.FOLDER+'/') for x in r.writes));self.assertEqual(auth,{k:v for k,v in r.files.items() if '.auth-private' in k})
  self.assertEqual(r.mode[pub.path('current.json')],0o600);self.assertNotIn(pub.path('.lock'),r.files)
 def test_update_retains_backup(self):
  r=FeedRemote();pub.publish(r,lambda **kw:seed());old=r.files[pub.path('current.json')]
  s=seed();s['generatedAt']=NOW;pub.publish(r,lambda **kw:s);self.assertEqual(r.files[pub.path('previous.json')],old)
 def test_collection_failure_keeps_snapshot(self):
  r=FeedRemote();pub.publish(r,lambda **kw:seed());old=r.files[pub.path('current.json')]
  with self.assertRaises(RuntimeError):pub.publish(r,lambda **kw:(_ for _ in ()).throw(RuntimeError('fixture failure')))
  self.assertEqual(r.files[pub.path('current.json')],old);self.assertNotIn(pub.path('.lock'),r.files)
 def test_existing_lock_preserved(self):
  r=FeedRemote();pub.publish(r,lambda **kw:seed());r.files[pub.path('.lock')]=b'other'
  with self.assertRaises(d.Stop):pub.publish(r,lambda **kw:seed())
  self.assertEqual(r.files[pub.path('.lock')],b'other')
 def test_unknown_folder_rejected(self):
  r=FeedRemote();r.dirs.add(pub.FOLDER)
  with self.assertRaises(d.Stop):pub.publish(r,lambda **kw:seed())
 def test_old_release_rejected_before_write(self):
  r=FeedRemote();r.files[d.ROOT+'/_isegye_releases/'+OLD+'/build-info.json']=b'{}'
  with self.assertRaises(d.Stop):pub.publish(r,lambda **kw:seed())
  self.assertFalse(r.writes)
