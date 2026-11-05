"""Owner-approved production promotion contracts; no network or remote writes."""
from pathlib import Path
import hashlib,os,sys,unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import promote_review_2nd as release
from build_review_2nd import adapt_app
import review_2nd_polish as polish
import review_2nd_cleanup as cleanup
class Promotion(unittest.TestCase):
 def source(self):return cleanup.app(polish.app(adapt_app((ROOT/'review-1st/app.js').read_text())))
 def test_acceptance_and_exact_backup(self):
  a=release.approval();self.assertEqual(a['backupBranch'],'backup_main261105');self.assertEqual(a['backupCommit'],release.BACKUP)
 def test_accepted_ui_not_rewritten(self):
  before=self.source();after=release.adapt_app(before)
  for a,b in [('function musicView(p)','function contentView(p)'),('function contentView(p)','function videoView('),('function historyView(p)','function historyDetail(')]:
   self.assertEqual(before[before.index(a):before.index(b)],after[after.index(a):after.index(b)])
 def test_only_main_can_package_production(self):
  with patch.dict(os.environ,DEPLOY_ENV='production',GITHUB_REF='refs/heads/develop'):
   with self.assertRaisesRegex(ValueError,'main-only'):release.build(ROOT/'missing')
 def test_authentication_gate_still_protects_data(self):
  code=(ROOT/'auth/Gateway.php').read_text()
  for endpoint in ('/api/schedule','/api/music','/api/history'):
   self.assertLess(code.index("if (!$access['allowed'])"),code.index("if ($path === '"+endpoint+"')"))
  self.assertIn("if ($access['role'] === null)",code)
 def test_existing_feed_endpoints_only(self):
  s=(ROOT/'site/runtime-feeds.js').read_text();self.assertIn("'/api/'+name",s);self.assertIn("['schedule',applySchedule",s)
  self.assertIn("credentials:'same-origin'",s);self.assertIn("redirect:'error'",s)
  self.assertNotIn("fetch('/auth/",s);self.assertNotIn("method:'POST'",s)
 def test_generation_and_evidence_checked(self):
  s=(ROOT/'site/runtime-feeds.js').read_text()
  for t in ('Older feed rejected','Invalid feed generation','scheduleValidate','scheduleApprovedRows','ProductionUI.applyMusic','FeedValidators.monthly','Oversized feed'):self.assertIn(t,s)
 def test_operating_guides_and_old_links_remain(self):
  s=release.adapt_app(self.source());self.assertIn('ProductionUI.record',s);self.assertIn('ProductionUI.report',s)
  self.assertIn('ProductionUI.guide()',s);self.assertIn('ProductionUI.footer(',s)
 def test_preferences_do_not_destroy_old_or_preview_values(self):
  s=(ROOT/'site/storage-migration.js').read_text();self.assertIn('isegye:bookmarks:v1',s);self.assertNotIn('removeItem',s);self.assertNotIn('review2',s)
 def test_no_preview_controls_in_operating_app(self):
  s=release.adapt_app(self.source());self.assertNotIn('href="#/settings"',s);self.assertNotIn('href="#/review"',s)
  self.assertNotIn('운영 사이트와 분리된 미리보기',s)
if __name__=='__main__':unittest.main()
