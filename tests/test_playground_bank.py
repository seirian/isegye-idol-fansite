import copy,json,os,sys,unittest
from pathlib import Path
from datetime import datetime,timedelta,timezone
from types import SimpleNamespace
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import playground_bank as b
import publish_playground_bank as p
import collect_playground as c
import batch_watchdog as w
class Remote:
 def __init__(self):self.s=self;self.files={p.d.ROOT+'/.isegye-owner':p.d.OWNER,p.d.ROOT+'/.htaccess':p.routing.router('r111111111111'),p.d.ROOT+'/_isegye_releases/r111111111111/build-info.json':json.dumps({'playground':{'schemaVersion':1,'seedVersion':b.seed()['version']}}).encode()};self.dirs={'/web',p.d.ROOT};self.writes=[]
 def directory(self,n):
  if n not in self.dirs:raise p.d.Stop('Missing directory')
 def read(self,n):return self.files.get(n)
 def info(self,n):return SimpleNamespace() if n in self.files or n in self.dirs else None
 def mkdir(self,n):self.dirs.add(n)
 def chmod(self,*args):pass
 def new(self,n,v):
  if n in self.files:raise p.d.Stop('Exists')
  self.files[n]=v;self.writes.append(n)
 def replace(self,n,v,old):
  if self.read(n)!=old:raise p.d.Stop('Concurrent change')
  self.files[n]=v;self.writes.append(n)
 def remove_own(self,n,v):
  if self.read(n)!=v:raise p.d.Stop('Concurrent change')
  del self.files[n];self.writes.append(n)
def proposal(i,now):return b.auto_question({'videoId':str(i).zfill(11),'title':'테스트 곡 '+str(i),'type':'cover','members':['ine']},{'member':'ine'},now)
class Bank(unittest.TestCase):
 def setUp(self):self.now=datetime.now(timezone.utc)
 def report(self,f,old=None,added=0):return {'status':'checked','generatedAt':f['generatedAt'],'previousSha256':old['sha256'] if old else None,'automaticAdded':added,'referenceWarnings':[]}
 def test_seed_immutable(self):
  f,_=b.assemble(None,[],self.now);f['catalog']['questions'][0]['answer']=1
  with self.assertRaises(ValueError):b.validate_feed(f)
 def test_daily_limit_and_retry_idempotent(self):
  f,added=b.assemble(None,[proposal(i,self.now) for i in range(15)],self.now);self.assertEqual(len(added),8)
  again,a=b.assemble(f,[proposal(i,self.now) for i in range(20)],self.now);self.assertEqual(a,[]);self.assertEqual(again['sha256'],f['sha256'])
  later,a=b.assemble(again,[proposal(i,self.now+timedelta(days=1)) for i in range(20)],self.now+timedelta(days=1));self.assertEqual(len(a),8)
 def test_next_day_daily_eligibility(self):
  q,_,_=proposal(1,self.now);self.assertEqual(q['eligibleFrom'],(self.now.astimezone(b.KST).date()+timedelta(days=1)).isoformat())
 def test_fact_duplicate_not_added(self):
  q=proposal(1,self.now);f,a=b.assemble(None,[q,q],self.now);self.assertEqual(len(a),1)
 def test_same_title_different_id_not_duplicate_fact(self):
  q,sid,source=proposal(1,self.now);q2=copy.deepcopy(q);q2['id']='other';f,a=b.assemble(None,[(q,sid,source),(q2,sid,source)],self.now);self.assertEqual(len(a),1)
 def test_no_performer_inference(self):self.assertIsNone(b.auto_question({'title':'x','type':'cover','members':['ine','lilpa'],'videoId':'12345678901'},{'member':'ine'},self.now))
 def test_oembed_requires_exact_official_author(self):
  row={'videoId':'12345678901','channelUrl':'https://www.youtube.com/@INE','title':'테스트','owner':'ine'}
  self.assertEqual(c.verify(row,lambda u:{'type':'video','author_url':'https://www.youtube.com/@INE','title':'테스트 cover'})['member'],'ine')
  with self.assertRaises(ValueError):c.verify(row,lambda u:{'type':'video','author_url':'https://www.youtube.com/@fan','title':'테스트 cover'})
 def test_title_mismatch_is_not_verified(self):
  with self.assertRaises(ValueError):c.verify({'videoId':'12345678901','channelUrl':'https://www.youtube.com/@INE','title':'다른 곡','owner':'ine'},lambda u:{'type':'video','author_url':'https://www.youtube.com/@INE','title':'테스트'})
 def test_publish_only_owned_bank_paths(self):
  r=Remote();before=dict(r.files);f,a=b.assemble(None,[proposal(1,self.now)],self.now);res=p.publish(r,f,self.report(f,added=1),{})
  self.assertEqual(res['added'],1);self.assertTrue(res['verifiedReadback']);self.assertEqual(len(json.loads(r.read(p.path('current.json')))['catalog']['questions']),33)
  for k,v in before.items():self.assertEqual(r.read(k),v)
  self.assertTrue(all(x.startswith(p.FOLDER+'/') for x in r.writes))
 def test_bad_evidence_never_publishes(self):
  r=Remote();f,a=b.assemble(None,[],self.now);d=self.report(f);d['status']='sources_unavailable'
  with self.assertRaises(p.d.Stop):p.publish(r,f,d,{})
  self.assertEqual(r.writes,[])
 def test_concurrent_bank_is_not_overwritten(self):
  r=Remote();f,a=b.assemble(None,[proposal(1,self.now)],self.now);p.publish(r,f,self.report(f,added=1),{})
  other,a=b.assemble(None,[],self.now)
  with self.assertRaises(p.d.Stop):p.publish(r,other,self.report(other),{})
  self.assertEqual(json.loads(r.read(p.path('current.json')))['sha256'],f['sha256'])
 def test_rollback_restores_previous_bank_on_readback_failure(self):
  r=Remote();old,_=b.assemble(None,[],self.now);p.publish(r,old,self.report(old),{});new,added=b.assemble(old,[proposal(1,self.now)],self.now)
  original=r.read;seen={'n':0}
  def read(n):
   if n==p.d.ROOT+'/.htaccess':
    seen['n']+=1
    if seen['n']==3:return b'concurrent'
   return original(n)
  r.read=read
  with self.assertRaises(p.d.Stop):p.publish(r,new,self.report(new,old,1),{})
  self.assertEqual(json.loads(original(p.path('current.json')))['sha256'],old['sha256'])
 def test_main_only_and_pause(self):
  for ref in ('develop','feature/playground'):
   with patch.dict(os.environ,{'GITHUB_REPOSITORY':'seirian/isegye-idol-fansite','GITHUB_REF':'refs/heads/'+ref}):
    with self.assertRaises(p.d.Stop):p.guard()
  with patch.dict(os.environ,{'GITHUB_REPOSITORY':'seirian/isegye-idol-fansite','GITHUB_REF':'refs/heads/main','ISEGYE_PLAYGROUND_PAUSED':'true'}):
   with self.assertRaises(p.d.Stop):p.guard()
 def test_daily_watchdog_uses_korean_0737(self):
  due=w.due_slot('playground',self.now).astimezone(b.KST);self.assertEqual(due.strftime('%H:%M'),'07:37')
  self.assertFalse(w.evidence_ok('playground',{},due,self.now))
  pub={'status':'published','generatedAt':self.now.isoformat(),'readbackAt':self.now.isoformat(),'verifiedReadback':True,'bankVerified':True,'questionCount':32}
  self.assertTrue(w.evidence_ok('playground',{'playground-publication.json':pub},due,self.now));pub['verifiedReadback']=False;self.assertFalse(w.evidence_ok('playground',{'playground-publication.json':pub},due,self.now))
if __name__=='__main__':unittest.main()
