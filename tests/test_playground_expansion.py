import copy,json,sys,unittest,subprocess
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import playground_bank as b
import promote_playground as ui
from test_playground_bank import Remote,proposal
import publish_playground_bank as p

def legacy_feed(now):
 d=b.legacy_seed()
 for i in range(8):
  q,sid,s=proposal(i,now);d['questions'].append(q);d['sources'][sid]=s
 f={'schemaVersion':1,'feed':'playground','baseVersion':d['version'],'generatedAt':now.isoformat(),'batchDate':now.astimezone(b.KST).date().isoformat(),'addedToday':8,'sha256':b.digest(d),'catalog':d}
 return b.validate_feed(f,b.legacy_seed())
class Expansion(unittest.TestCase):
 def test_eighty_balanced_unique_reviewed_questions(self):
  d=b.seed();self.assertEqual(len(d['questions']),80)
  self.assertEqual({k:sum(q['category']==k for q in d['questions']) for k in d['categories']},{'music':20,'members':20,'covers':22,'stories':18})
  self.assertEqual(len({q['stem'] for q in d['questions']}),80)
  self.assertEqual(d['questions'][:32],b.legacy_seed()['questions']);self.assertEqual(d['version'],b.legacy_seed()['version'])
 def test_sources_are_reopenable_and_claims_keep_provenance(self):
  d=b.seed();manifest=json.loads((ROOT/'playground/expansion-review.json').read_text())
  self.assertEqual(len(manifest['addedIds']),48)
  for q in d['questions'][32:]:
   self.assertEqual(q['eligibleFrom'],'2026-11-18')
   self.assertTrue(q['sources']);self.assertNotIn('namu-group',q['sources'])
   if q['category']=='stories':self.assertEqual(q['status'],'community');self.assertIn('공식 발표로 검증했다는 뜻은 아닙니다',q['explanation'])
 def test_current_and_legacy_snapshots_have_strict_integrity(self):
  old=legacy_feed(datetime.now(timezone.utc));b.validate_stored_feed(old)
  bad=copy.deepcopy(old);bad['catalog']['questions'][0]['answer']=3;bad['sha256']=b.digest(bad['catalog'])
  with self.assertRaises(ValueError):b.validate_stored_feed(bad)
 def test_upgrade_preserves_all_forty_and_daily_cap(self):
  now=datetime.now(timezone.utc);old=legacy_feed(now);before=copy.deepcopy(old)
  new,auto=b.assemble(old,[proposal(99,now)],now)
  self.assertEqual(len(new['catalog']['questions']),88);self.assertEqual(new['reviewedAdded'],48);self.assertEqual(auto,[])
  self.assertEqual(old,before);self.assertEqual(new['catalog']['questions'][:40],old['catalog']['questions'])
  again,auto=b.assemble(new,[],now);self.assertEqual(again['sha256'],new['sha256']);self.assertEqual(again['reviewedAdded'],0)
 def test_publisher_migrates_real_previous_snapshot_without_overwrite(self):
  now=datetime.now(timezone.utc);old=legacy_feed(now);r=Remote();r.mkdir(p.FOLDER);r.new(p.path('.owner'),p.OWNER);r.new(p.path('current.json'),b.encoded(old))
  new,auto=b.assemble(old,[],now);report={'status':'checked','generatedAt':new['generatedAt'],'previousSha256':old['sha256'],'automaticAdded':0,'referenceWarnings':[]}
  result=p.publish(r,new,report,{})
  self.assertEqual(result['questionCount'],88);self.assertEqual(result['reviewedAdded'],48);self.assertTrue(result['verifiedReadback'])
  self.assertEqual(r.read(p.path('previous.json')),b.encoded(old))
 def test_compiled_public_app_excludes_reference_overview_markup(self):
  js,css,d=ui.component();self.assertNotIn('pg-tools',js);self.assertNotIn('어떤 자료를 참고했나요?',js);self.assertIn("import('/src/playground-admin.js')",js)
  self.assertIn('어떤 자료를 참고했나요?',ui.reference_module());self.assertIn('padding:0 0 32px',css)
  policy=json.loads((ROOT/'auth/public-view-policy.json').read_text());self.assertIn('/src/playground-admin.js',policy['protectedPaths'])
 def test_php_overlay_preserves_old_questions_and_digest(self):
  now=datetime.now(timezone.utc);old=legacy_feed(now)
  code='require $argv[1];$i=json_decode(stream_get_contents(STDIN),true);$m=new ReflectionMethod("Isegye\\\\Access\\\\PlaygroundBank","expand");echo json_encode($m->invoke(null,$i[0],$i[1]),JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES);'
  code=code.replace('\\\\','\\')
  raw=subprocess.check_output(['php','-r',code,str(ROOT/'playground/hosting/PlaygroundBank.php')],input=json.dumps([old,b.seed()],ensure_ascii=False).encode())
  actual=json.loads(raw);self.assertEqual(len(actual['catalog']['questions']),88);self.assertEqual(actual['catalog']['questions'][:40],old['catalog']['questions']);b.validate_feed(actual)
if __name__=='__main__':unittest.main()
