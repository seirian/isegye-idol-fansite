"""Artifact integrity and preview isolation checks for the replacement fan game."""
import base64, hashlib, json, os, re, subprocess, sys, tempfile, unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import build_fangames as builder
import deploy_fangames as deploy
from inour_sftp import Stop

class Fangames(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw=(ROOT/'fangames-dist/review.html').read_bytes()
        cls.html=cls.raw.decode()
        cls.meta=json.loads((ROOT/'fangames-dist/build-info.json').read_text())

    def test_replacement_game_only(self):
        self.assertEqual(self.meta['counts'],{'games':1,'characters':6,'stages':3})
        self.assertEqual(self.meta['game'],'starlight-courier')
        self.assertIn('별빛 배송부',self.html)
        for old_game in ('우당탕 이세돌','세돌 원정대','이세돌 합방 탈출'):
            self.assertNotIn(old_game,self.html)

    def test_exact_hashed_offline_document(self):
        self.assertEqual(hashlib.sha256(self.raw).hexdigest(),self.meta['htmlSha256'])
        self.assertEqual(len(self.raw),self.meta['htmlBytes'])
        self.assertLessEqual(len(self.raw),builder.MAX_HTML_BYTES)
        self.assertEqual(self.raw,(ROOT/'fangames-dist/index.html').read_bytes())
        for policy in ("connect-src 'none'","img-src data:","media-src 'none'","object-src 'none'",'noindex,nofollow,noarchive'):
            self.assertIn(policy,self.html)
        self.assertNotIn("'unsafe-inline'",self.html)
        self.assertNotIn("'unsafe-eval'",self.html)
        scripts=re.findall(r'<script>([\s\S]*?)</script>',self.html)
        styles=re.findall(r'<style>([\s\S]*?)</style>',self.html)
        self.assertEqual((len(scripts),len(styles)),(1,1))
        for part in scripts+styles:
            digest=base64.b64encode(hashlib.sha256(part.encode()).digest()).decode()
            self.assertIn('sha256-'+digest,self.html)

    def test_new_art_is_packed_and_matches_manifest(self):
        self.assertTrue(self.meta['generatedArtwork'])
        art=json.loads(re.search(r'const COURIER_ART=Object.freeze\((\{[^\n]*\})\);',self.html)[1])
        self.assertTrue(set(builder.REQUIRED_ART)<=set(art))
        self.assertEqual(len(art),self.meta['artworkPacked'])
        for name,value in art.items():
            self.assertTrue(value.startswith('data:image/webp;base64,'))
            raw=base64.b64decode(value.split(',',1)[1],validate=True)
            source='fangames/assets/'+name+'.webp'
            self.assertEqual(raw,(ROOT/source).read_bytes())
            self.assertEqual(hashlib.sha256(raw).hexdigest(),self.meta['sourceHashes'][source])
        for source,digest in self.meta['sourceHashes'].items():
            self.assertTrue(source.startswith('fangames/'))
            self.assertEqual(hashlib.sha256((ROOT/source).read_bytes()).hexdigest(),digest)
        self.assertFalse(any('review/portraits' in source for source in self.meta['sourceHashes']))

    def test_game_sources_have_no_network_or_dynamic_code(self):
        for path in builder.SOURCES:
            source=(ROOT/path).read_text()
            self.assertIsNone(re.search(r'\b(?:fetch|eval|getUserMedia)\s*\(',source))
            for capability in ('XMLHttpRequest','WebSocket','sendBeacon'):
                self.assertNotIn(capability,source)
            result=subprocess.run(['node','--check',str(ROOT/path)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)

    def test_review_storage_and_host_limit(self):
        self.assertEqual(self.meta['storageKey'],'isegye:review:courier:v2')
        for setting in ('productionWrites','liveFeedsConnected','externalMediaUsed'):
            self.assertIs(self.meta[setting],False)
        handler=(ROOT/'playground/hosting/PlaygroundPreview.php').read_text()
        self.assertIn("self::read($dir.'/review.html', 9*1024*1024)",handler)
        self.assertLess(builder.MAX_HTML_BYTES,9*1024*1024)

    def test_build_refuses_operating_branches_and_production(self):
        for settings in ({'GITHUB_REF':'refs/heads/main'}, {'GITHUB_REF':'refs/heads/develop'}, {'DEPLOY_ENV':'production'}):
            env=dict(os.environ)
            env.update(GITHUB_REF='refs/heads/feature/isegye-fangames',DEPLOY_ENV='preview')
            env.update(settings)
            result=subprocess.run([sys.executable,str(ROOT/'scripts/build_fangames.py')],env=env,capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0)
            self.assertIn('Preview only',result.stderr)

    def test_rebuild_preserves_browser_tested_html_bytes(self):
        env=dict(os.environ)
        env.update(GITHUB_REF='refs/heads/feature/isegye-fangames',DEPLOY_ENV='preview')
        result=subprocess.run([sys.executable,str(ROOT/'scripts/build_fangames.py')],env=env,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(self.raw,(ROOT/'fangames-dist/review.html').read_bytes())

class PublicationPayload(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.folder=Path(self.temp.name)
        self.raw=(ROOT/'fangames-dist/review.html').read_bytes()
        self.meta=json.loads((ROOT/'fangames-dist/build-info.json').read_text())
        self.commit='a'*40
        self.meta['commit']=self.commit
        self.write()
        self.env=patch.dict(os.environ,{'VERIFIED_HTML_SHA256':hashlib.sha256(self.raw).hexdigest()})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def write(self):
        (self.folder/'review.html').write_bytes(self.raw)
        (self.folder/'build-info.json').write_text(json.dumps(self.meta))

    def test_publish_accepts_exact_tested_game_and_private_pointer(self):
        release,html,metadata,pointer=deploy.payload(self.folder,self.commit)
        self.assertEqual(html,self.raw)
        self.assertRegex(release,r'^p[0-9a-f]{12}$')
        active=json.loads(pointer)
        self.assertEqual(active['sha256'],hashlib.sha256(html).hexdigest())
        self.assertEqual(active['metadataSha256'],hashlib.sha256(metadata).hexdigest())
        self.assertFalse(json.loads(metadata)['productionUIReplaced'])
        self.assertLessEqual(len(metadata),8192)

    def test_publish_rejects_game_or_isolation_changes(self):
        cases=(('counts',{'games':3,'characters':6,'stages':3}),('storageKey','isegye:playground:production:v1'),
               ('generatedArtwork',False),('productionWrites',True),('externalMediaUsed',True),('liveFeedsConnected',True))
        for field,value in cases:
            with self.subTest(field=field):
                previous=self.meta[field];self.meta[field]=value;self.write()
                with self.assertRaises(Stop):deploy.payload(self.folder,self.commit)
                self.meta[field]=previous

    def test_publish_rejects_unverified_or_corrupt_content(self):
        with patch.dict(os.environ,{'VERIFIED_HTML_SHA256':'0'*64}):
            with self.assertRaisesRegex(Stop,'Browser-tested artifact differs'):
                deploy.payload(self.folder,self.commit)
        self.raw+=b'\n'
        self.write()
        with self.assertRaisesRegex(Stop,'Artifact checksum'):
            deploy.payload(self.folder,self.commit)

    def test_publish_rejects_reused_or_incorrect_art_manifest(self):
        self.meta['sourceHashes']['fangames/assets/characters.webp']='0'*64
        self.write()
        with self.assertRaisesRegex(Stop,'Generated artwork checksum'):
            deploy.payload(self.folder,self.commit)
        self.meta['sourceHashes']['review/portraits/ine.webp']='0'*64
        self.write()
        with self.assertRaisesRegex(Stop,'Source manifest'):
            deploy.payload(self.folder,self.commit)

    def test_write_scope_excludes_live_app_accounts_and_other_previews(self):
        root=deploy.d.ROOT
        for path in (root+'/.deploy-lock',root+'/.review-playground/active.json',root+'/.review-playground/releases/p123456789abc/review.html'):
            self.assertEqual(deploy.allowed_write(path),path)
        for path in (root+'/index.html',root+'/access.php',root+'/.auth-runtime/g123456789abc/PlaygroundPreview.php',
                     root+'/.review-fanmade/active.json',root+'/.accounts/users.json',root+'/.review-playground/../index.html','/web/.htaccess'):
            with self.subTest(path=path),self.assertRaises(Stop):deploy.allowed_write(path)

if __name__=='__main__':unittest.main()
