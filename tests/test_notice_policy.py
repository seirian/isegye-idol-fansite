"""Fail-closed approved author publication and historical notice provenance."""
from pathlib import Path
from unittest.mock import patch
import copy,json,os,sys,unittest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import notice_policy as p
import schedule_feed as f
import publish_schedule_feed as pub
from test_schedule_feed import seed,FeedRemote
NOW='2026-10-30T06:00:00Z'

def injected(source='naver-search',aid='22133027'):
 return f.public_item(source,'https://cafe.naver.com/steamindiegame/'+aid,'아이네 일반 사용자 글',None,NOW)

class Approval(unittest.TestCase):
 def test_archive_valid_and_unique(self):p.validate_archive(p.archive())
 def test_reviewed_members_only(self):
  for r in p.archive()['notices']:
   self.assertIn(r['author'],p.MEMBERS|{'parable'})
   self.assertIn(r['menuId'],(345,1250));self.assertTrue(r['public'])
 def test_other_board_rejected(self):
  d=copy.deepcopy(p.archive());d['notices'][0]['menuId']=24
  with self.assertRaises(ValueError):p.validate_archive(d)
 def test_member_name_without_role_rejected(self):
  d=copy.deepcopy(p.archive());d['notices'][0].update(menuId=345,author='ine',members=['ine'],verifiedRole='member')
  with self.assertRaises(ValueError):p.validate_archive(d)
 def test_no_private_fields(self):
  for k in ('memberKey','userId','body','comments','email','cookie'):
   d=copy.deepcopy(p.archive());d['notices'][0][k]='not stored'
   with self.assertRaises(ValueError):p.validate_archive(d)
 def test_explicit_examples_rejected(self):
  for aid in ('22133027','22133865'):
   for source in ('naver-search','cafe-members','cafe-agency','fan-roundup'):
    self.assertFalse(p.is_publishable(injected(source,aid)))
 def test_keyword_or_source_label_not_proof(self):self.assertFalse(p.is_publishable(injected('cafe-members','99999999')))
 def test_other_fan_author_not_allowed(self):self.assertFalse(p.is_publishable(injected('fan-roundup','99999999')))
 def test_only_designated_fan_post_allowed(self):self.assertTrue(p.is_publishable(injected('fan-roundup','22137397')))
 def test_reviewed_seed_retained(self):
  s=seed();clean=p.clean_snapshot(s)
  for bucket in ('news','events','forecasts'):self.assertEqual(clean[bucket],s[bucket])
 def test_no_search_request_in_hourly_collection(self):
  calls=[]
  def fetch(u,**kw):calls.append(u);raise f.FeedError('http_503')
  with patch.dict(os.environ,{'ISEGYE_NAVER_CLIENT_ID':'fixture','ISEGYE_NAVER_CLIENT_SECRET':'fixture'}):result=f.collect(fetch=fetch,now=NOW)
  self.assertFalse(any('naver' in u for u in calls));self.assertEqual(next(s for s in result['sources'] if s['id']=='naver-search')['state'],'restricted')
 def test_previous_search_rows_do_not_survive_merge(self):
  old=seed();old['news'] += [injected(),injected('cafe-members','99999999')]
  value=f.merge(old,seed());self.assertFalse(any(r['id'] in {x['id'] for x in old['news'][-2:]} for r in value['news']))
 def test_original_canonical_urls_preserved(self):
  for r in p.archive()['notices']:self.assertIn('https://cafe.naver.com/steamindiegame/'+str(r['articleId']),p.reviewed_sources())
 def test_data_does_not_claim_body_review(self):
  import compose_schedule
  bundle=compose_schedule.history_bundle();self.assertIs(bundle['bodiesReviewed'],False)
  self.assertEqual(len(bundle['rows']),len(p.archive()['notices']))
 def test_initial_date_is_2021_08_26(self):
  import compose_schedule
  self.assertEqual(compose_schedule.history_bundle()['start'],'2021-08-26')
 def test_no_plain_search_hits_republished_even_by_custom_collector(self):
  value=seed();value['news'].append(injected());r=FeedRemote();result=pub.publish(r,lambda **kw:value)
  self.assertEqual(result['unverifiedSearchRowsPublished'],0);self.assertTrue(result['explicitlyExcludedUrlsAbsent'])
 def test_current_and_backup_both_purged(self):
  r=FeedRemote();pub.publish(r,lambda **kw:seed())
  dirty=seed();dirty['news'] += [injected(),injected(aid='22133865')]
  raw=(json.dumps(dirty,ensure_ascii=False,indent=2)+'\n').encode()
  r.files[pub.path('current.json')]=raw;r.files[pub.path('previous.json')]=raw
  result=pub.publish(r,lambda **kw:seed())
  self.assertEqual(result['removedUnapprovedRows']['news'],2)
  for name in ('current.json','previous.json'):
   d=json.loads(r.files[pub.path(name)])
   self.assertTrue(all(p.is_publishable(x) for k in ('news','events','forecasts') for x in d[k]))
   self.assertNotIn(b'22133027',r.files[pub.path(name)]);self.assertNotIn(b'22133865',r.files[pub.path(name)])
  self.assertFalse(result['accountStoreReadOrWritten']);self.assertTrue(result['protectedFilesUnchanged'])
 def test_duplicate_archive_id_rejected(self):
  d=copy.deepcopy(p.archive());d['notices'].append(d['notices'][0])
  with self.assertRaises(ValueError):p.validate_archive(d)

if __name__=='__main__':unittest.main()
