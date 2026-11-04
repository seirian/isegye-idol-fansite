"""No production network requests; verify isolated review packaging and data."""
from pathlib import Path
from unittest import TestCase, main, mock
import base64, hashlib, importlib.util, json, os, re, sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import build_review_1st as build

class ReviewBuildContract(TestCase):
    def test_script_json_escapes_script_terminator(self):
        self.assertNotIn('<',build.script_json({'title':'</script>','x':'\u2028'}))
    def test_extract_refuses_missing_anchor(self):
        with self.assertRaises(ValueError):build.extract('','CATALOG')
    def test_date_boundary_is_kst(self):
        self.assertEqual(build.day('2026-11-02T16:00:00Z'),'2026-11-03')
        self.assertEqual(build.day('2026-11-03'),'2026-11-03')
    def test_production_and_shared_branches_refused(self):
        for env in [{'DEPLOY_ENV':'production'},{'GITHUB_REF':'refs/heads/main'},{'GITHUB_REF':'refs/heads/develop'}]:
            with self.subTest(env=env),mock.patch.dict(os.environ,env):
                with self.assertRaises(RuntimeError):build.build(Path('/does-not-exist'))
    def test_no_credentials_in_review_workflow(self):
        text=(ROOT/'.github/workflows/review-1st.yml').read_text()
        self.assertNotIn('secrets.',text)
        self.assertNotIn('environment: production',text)
        self.assertNotIn('deploy_google_access',text)
        self.assertIn("branches: ['feature/review-1st']",text)
    def test_preferences_do_not_use_production_keys(self):
        text=(ROOT/'review-1st/app.js').read_text()
        self.assertIn('isegye:review1:prefs',text)
        self.assertNotIn('isegye:bookmarks:v1',text)
        self.assertNotIn('isegye:theme:v1',text)
    def test_no_production_api_or_auth_writes(self):
        text=(ROOT/'review-1st/app.js').read_text()
        self.assertNotIn('/api/schedule',text)
        self.assertNotIn('method:',text)
        self.assertNotIn('Notification.requestPermission',text)
    def test_snapshot_identifies_observation_time(self):
        data=json.loads((ROOT/'review-1st/fixtures/schedule-observed.json').read_text())
        self.assertEqual(data['generatedAt'],'2026-11-04T10:00:04+00:00')
        self.assertEqual(len(data['news']),61)

class ReviewArtifact(TestCase):
    @classmethod
    def setUpClass(cls):
        folder=ROOT/'review-1st-dist'
        if not folder.exists():
            from unittest import SkipTest
            raise SkipTest('Run scripts/build_review_1st.py before artifact tests')
        cls.folder=folder
        cls.html=(folder/'review.html').read_text()
        cls.data=json.loads((folder/'data.js').read_text().removeprefix('const REVIEW_DATA=').rstrip(';\n'))
    def test_registry_unique(self):
        rows=[r for k in ['songs','albums','videos','notices','events','history'] for r in self.data[k]]
        self.assertEqual(len(rows),len({r['key'] for r in rows}))
    def test_data_counts_not_padded(self):
        for key,count in [('members',6),('songs',154),('albums',15),('videos',96),('notices',7280),('events',10),('history',55),('series',2)]:
            with self.subTest(key=key):self.assertEqual(len(self.data[key]),count)
    def test_six_original_local_gallery_images(self):
        self.assertEqual(len(self.data['gallery']),6)
        for image in self.data['gallery']:
            self.assertTrue((self.folder/image['src'].split('?')[0]).is_file())
    def test_no_unverified_date_or_new_collection_claim(self):
        self.assertFalse(self.data['scope']['historicalComplete'])
        self.assertEqual(self.data['snapshotAt'],'2026-11-04T10:00:04+00:00')
    def test_restored_notices_in_kst(self):
        rows={r['id']:r for r in self.data['notices']}
        self.assertEqual(rows['22160973']['date'],'2026-11-03')
        self.assertIn('휴방',rows['22160973']['title'])
    def test_album_song_references_resolve(self):
        songs={s['id'] for s in self.data['songs']}
        self.assertTrue(all(set(a['songIds'])<=songs for a in self.data['albums']))
    def test_series_references_resolve(self):
        videos={s['id'] for s in self.data['videos']};songs={s['id'] for s in self.data['songs']}
        self.assertTrue(all(set(s.get('videoIds',[]))<=videos and set(s.get('songIds',[]))<=songs for s in self.data['series']))
    def test_standalone_uses_hash_csp_not_unsafe_inline(self):
        self.assertNotIn("'unsafe-inline'",self.html)
        self.assertNotIn("'unsafe-eval'",self.html)
        self.assertIn('noindex,nofollow',self.html)
        for tag in ['style','script']:
            text=re.search('<'+tag+'>([\\s\\S]*?)</'+tag+'>',self.html)[1]
            sha=base64.b64encode(hashlib.sha256(text.encode()).digest()).decode()
            self.assertIn('sha256-'+sha,self.html)
    def test_no_unresolved_relative_assets_in_standalone(self):
        self.assertNotRegex(self.html,r'<script src=')
        self.assertNotIn('<link rel="stylesheet"',self.html)
        self.assertIn('data:image/webp;base64,',self.html)
    def test_manifest_never_claims_public_deployment(self):
        d=json.loads((self.folder/'build-info.json').read_text())
        self.assertFalse(d['publicDeployment']);self.assertFalse(d['productionWrites'])
        self.assertEqual(d['mode'],'isolated-preview')
        self.assertEqual(d['branch'],'feature/review-1st')

if __name__=='__main__':main()
