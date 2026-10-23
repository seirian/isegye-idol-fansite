"""Approved v0.4 source/metadata and rollback integration; no network writes."""
import copy,json,os,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import build_release_v04 as r
class LiveReleaseTests(unittest.TestCase):
    def fixture(self):
        a=json.loads((ROOT/'review/live-release.json').read_text())
        m={'commit':'a'*40,'verifiedPortraitCount':6,'profileSource':'Genie Music','groupHero':{'sha256':a['groupImageSha256']},'live':{'members':6,'failureMeansOffline':False},'catalog':{'songs':154,'channels':21},'musicVideoAudit':{'linked':151},'visualHistory':{'historyItems':55,'navigationCount':7}}
        return m,a
    def test_approved_features(self):r.validate(*self.fixture())
    def test_missing_catalog_rejected(self):
        m,a=self.fixture();m['catalog']['songs']=6
        with self.assertRaises(RuntimeError):r.validate(m,a)
    def test_offline_error_regression_rejected(self):
        m,a=self.fixture();m['live']['failureMeansOffline']=True
        with self.assertRaises(RuntimeError):r.validate(m,a)
    def test_backup_still_first_main(self):
        m,a=self.fixture();self.assertEqual(a['sourceBackup']['commit'],'885e818063eeccedf468d52ce148a4760819c97d')
        self.assertEqual(a['previousProductionCommit'],'b422a1653fef48bf2eb91663a99c767279bb48d1')
        self.assertFalse(a['rightsPermissionVerified'])
    def test_feature_cannot_produce_production(self):
        with patch.dict(os.environ,DEPLOY_ENV='production',GITHUB_REF='refs/heads/feature/live'):
            with self.assertRaisesRegex(RuntimeError,'main-only'):r.main()
    def test_review_wording_transformed(self):
        text=r.production_text('멤버·음악 개선 검토 hero-group function liveView( const CATALOG= const HISTORY= 읽기 편하게, 더 가까이')
        self.assertIn('공개 베타',text);self.assertNotIn('개선 검토',text)
    def test_legacy_artifact_rejected(self):
        with self.assertRaises(RuntimeError):r.production_text('old site')
    def test_production_bundle(self):
        m,a=self.fixture()
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'src';out=Path(tmp)/'out';(source/'src').mkdir(parents=True)
            (source/'index.html').write_text('<head><title>Review</title><meta name="robots" content="noindex,nofollow"></head>')
            (source/'src/app.js').write_text('// 멤버·음악 개선 검토 hero-group function liveView( const CATALOG= const HISTORY=')
            (source/'src/data.js').write_text("const SITE={version:'0.3.0'};")
            (source/'src/styles.css').write_text('body{}');(source/'build-info.json').write_text(json.dumps(m));(source/'review.html').write_text('offline');(source/'robots.txt').write_text('Disallow: /')
            with patch.dict(os.environ,GITHUB_SHA='a'*40,GITHUB_REF_NAME='main'):meta=r.package(source,out,'production',a)
            self.assertEqual(meta['mode'],'production');self.assertFalse((out/'review.html').exists())
            self.assertIn('index,follow',(out/'index.html').read_text());self.assertIn('noindex,nofollow',(source/'index.html').read_text())
            self.assertIn('0.4.0',(out/'src/data.js').read_text());self.assertIn('rel="canonical"',(out/'index.html').read_text())
    def test_rollback_wraps_current_suites(self):
        entry=(ROOT/'scripts/deploy_release_v04.py').read_text();text=(ROOT/'scripts/production_release.py').read_text();self.assertIn('scripts/verify_release_v04.py',entry);self.assertIn('release.verify_live=verify_live',entry);self.assertIn('verify(commit)',text);self.assertIn("report['rollback_restored_previous']",text)
if __name__=='__main__':unittest.main()
