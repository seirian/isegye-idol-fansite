import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import monthly_history as h
import publish_monthly_history as p
import inour_sftp as d
from test_schedule_feed import FeedRemote, OLD, seed

NOW = datetime.now(timezone.utc).isoformat()

def notice(title='[안내] 이세계아이돌 테스트 앨범 발매 안내', published='2026-10-12T00:00:00+09:00', ident='999001'):
    return dict(id='berriz-notice-'+ident, sourceId='berriz-notice', sourceUrl='https://berriz.in/ko/isegyeidol/notice/'+ident+'/', title=title, members=list(h.music.NAMES), publishedAt=published, checkedAt=NOW, publicationPrecision='day')

def music_row():
    return dict(videoId='TESThist_01', channelKey='c2', title='월간 검증 음악', members=list(h.music.NAMES), type='official_track', kind='official_mv', publishedAt='2026-10-15T09:00:00Z', checkedAt=NOW)

def inputs(news=None, music=None):
    s=seed();s.update(generatedAt=NOW, news=news if news is not None else [notice()], events=[], forecasts=[])
    for item in s['sources']:item['state']='ok';item['lastSuccessAt']=NOW
    return {'generatedAt':NOW, 'schedule':s, 'music':{'schemaVersion':1,'generatedAt':NOW,'sources':{k:{'state':'ok'} for k in h.music.CHANNELS},'rows':music if music is not None else [music_row()]}}

def remote():
    r=FeedRemote();r.files[d.ROOT+'/_isegye_releases/'+OLD+'/build-info.json']=b'{"monthlyHistory":{"schemaVersion":1}}'
    return r

class History(unittest.TestCase):
    def test_kst_month_cutoff_leap_and_january(self):
        self.assertEqual(h.bounds(datetime.fromisoformat('2026-11-30T15:00:00+00:00'))[1].isoformat(),'2026-11-30')
        self.assertEqual(h.bounds(datetime.fromisoformat('2026-11-30T14:59:59+00:00'))[1].isoformat(),'2026-10-31')
        self.assertEqual(h.bounds(datetime.fromisoformat('2027-01-01T00:00:00+00:00'))[1].isoformat(),'2026-12-31')
        self.assertEqual(h.bounds(datetime.fromisoformat('2028-03-01T00:00:00+00:00'))[1].isoformat(),'2028-02-29')
    def test_published_dates_not_scheduled_event_dates(self):
        fresh=inputs();fresh['schedule']['events']=[{**notice(),'id':'future-event','date':'2026-11-09','type':'release','certainty':'confirmed','status':'scheduled'}]
        doc=h.combine_inputs(fresh)
        self.assertEqual(len(doc['events']),2)
        self.assertEqual(next(x for x in doc['events'] if x['type']=='release')['date'],'2026-10-12')
        video=next(x for x in doc['events'] if x['dateBasis']=='video_published')
        self.assertEqual(video['type'],'content');self.assertIn('발매일',video['note'])
    def test_future_current_month_and_cover_not_promoted(self):
        first=h.bounds(datetime.now(timezone.utc))[1]+h.timedelta(days=1)
        future=notice(published=first.isoformat()+'T00:00:00+09:00')
        doc=h.combine_inputs(inputs([future],[{**music_row(),'type':'cover'}]))
        self.assertFalse(doc['events'])
    def test_regular_broadcast_fan_and_sensitive_notices_excluded(self):
        for title in ['오늘 방송 안내','앨범 구매 배송 안내','아이네 휴뱅 공지','팬클럽 전용 앨범 안내','건강 관련 공연 안내']:
            self.assertIsNone(h.notice_type(title))
        row=notice();row.update(sourceId='naver-search',id='unverified')
        self.assertFalse(h.combine_inputs(inputs([row],[]))['events'])
    def test_existing_curated_history_unchanged(self):
        original=(ROOT/'visuals/history.json').read_bytes();a=h.combine_inputs(inputs());b=h.merge(a,a)
        self.assertEqual(len(b['events']),2);self.assertEqual((ROOT/'visuals/history.json').read_bytes(),original)
        self.assertEqual(len(h.base()['events']),55)
    def test_prior_success_retained_without_restamping(self):
        a=h.combine_inputs(inputs());empty=h.combine_inputs(inputs([],[]));b=h.merge(a,empty)
        self.assertEqual(b['events'],a['events']);self.assertEqual(b['sources'],a['sources'])
    def test_complete_upstream_failure_not_empty_success(self):
        f=inputs([],[])
        for s in f['schedule']['sources']:s['state']='error'
        for s in f['music']['sources'].values():s['state']='error'
        with self.assertRaises(ValueError):h.combine_inputs(f)
    def test_partial_reports_and_old_music_data_catchup(self):
        f=inputs([],[]);f['music']['sources']['c1']['state']='error'
        out=h.combine_inputs(f,stored_music=[music_row()]);self.assertEqual(len(out['events']),1);self.assertTrue(out['coverage']['partial'])
    def test_schema_source_and_future_injection_rejected(self):
        good=h.combine_inputs(inputs())
        for mutate in [lambda x:x['events'][0].update(date='2099-01-01'),lambda x:x['events'][0].update(title='<script>'),lambda x:x['sources'][next(iter(x['sources']))].update(url='https://evil.invalid/'),lambda x:x['events'][0].update(members=['outsider']),lambda x:x['events'][0].update(body='private body'),lambda x:x.update(through='2099-01-31')]:
            bad=copy.deepcopy(good);mutate(bad)
            with self.assertRaises(ValueError):h.validate(bad)
    def test_updates_keep_stable_id_and_only_new_observation(self):
        old=h.combine_inputs(inputs());f=inputs([notice(title='[수정] 이세계아이돌 테스트 앨범 발매 안내')]);new=h.combine_inputs(f)
        out=h.merge(old,new);self.assertEqual(len(out['events']),2)
        self.assertTrue(any(x['title'].startswith('[수정]') for x in out['events']))
    def test_atomic_only_history_written_and_idempotent(self):
        r=remote();out=p.publish(r,inputs());self.assertEqual(out['added'],2);self.assertEqual(out['totalDisplayed'],57)
        before=r.files[p.path('current.json')];out=p.publish(r,inputs());self.assertEqual(out['added'],0)
        self.assertEqual(out['curatedPreserved'],55);self.assertTrue(out['verifiedReadback'])
        self.assertEqual(r.files[p.path('current.json')],before);self.assertTrue(all(x.startswith(p.DIR+'/') for x in r.writes))
        self.assertEqual(r.mode[p.path('current.json')],0o600)
    def test_backup_preserve_and_failed_collection_never_clears(self):
        r=remote();p.publish(r,inputs());raw=r.files[p.path('current.json')]
        p.publish(r,inputs([notice(title='이세계아이돌 별도 공연 안내',ident='999002')],[]));self.assertEqual(r.files[p.path('previous.json')],raw)
        current=r.files[p.path('current.json')];f=inputs([],[])
        for s in f['schedule']['sources']:s['state']='error'
        for s in f['music']['sources'].values():s['state']='error'
        with self.assertRaises(ValueError):p.publish(r,f)
        self.assertEqual(current,r.files[p.path('current.json')])
    def test_owned_lock_and_release_guards(self):
        r=remote();r.files[d.ROOT+'/_isegye_releases/'+OLD+'/build-info.json']=b'{}'
        with self.assertRaises(d.Stop):p.publish(r,inputs())
        self.assertFalse(r.writes)
        r=remote();p.publish(r,inputs());r.files[p.path('.lock')]=b'other'
        with self.assertRaises(d.Stop):p.publish(r,inputs())
        self.assertEqual(r.files[p.path('.lock')],b'other')
        for n in ('../../.auth-private/accounts.json','/web/.htaccess','index.html'):
            with self.assertRaises(d.Stop):p.path(n)
    def test_weekly_workflow_and_gate(self):
        s=(ROOT/'.github/workflows/history-monthly.yml').read_text();self.assertIn("cron: '0 15 * * 6'",s)
        self.assertNotIn('workflow_run:',s);self.assertNotIn('  push:',s);self.assertIn('ISEGYE_HISTORY_PAUSED',s)
        self.assertIn('group: isegye-inour-production',s);self.assertIn("github.ref == 'refs/heads/main'",s)
        s=(ROOT/'auth/Gateway.php').read_text();self.assertLess(s.index("if (!$access['allowed'])"),s.index("if ($path === '/api/history')"))

if __name__=='__main__':unittest.main()
