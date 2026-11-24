"""Real artifact, exact route and deployment checks for the operating mini-game."""
import base64
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import build_courier_production as builder
from build_rpg import FONT_FAMILIES
import build_playground_production_host as host
import deploy_google_access as deploy
import inour_sftp as transfer


class CourierProduction(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='courier-production-unit-')
        cls.out=Path(cls.temp.name)
        (cls.out/'src').mkdir()
        for name,text in {'index.html':'<!doctype html><title>Existing site</title>',
                          'src/app.js':'const existingSite=true;', 'src/styles.css':'body{}',
                          'build-info.json':json.dumps({'mode':'production','commit':'a'*40})}.items():
            (cls.out/name).write_text(text)
        cls.before={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in builder.SOURCES}
        with patch.dict(os.environ,{'GITHUB_REF':'refs/heads/main'}):cls.game=builder.build(cls.out)
        cls.raw=(cls.out/builder.HTML_PATH).read_bytes()
        cls.html=cls.raw.decode()
        meta=json.loads((cls.out/'build-info.json').read_text());meta['courierGame']=cls.game
        (cls.out/'build-info.json').write_text(json.dumps(meta))
        cls.payload=transfer.load_payload(cls.out,'a'*40)

    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()

    def test_operating_identity_and_original_preview_preserved(self):
        self.assertEqual(self.game['baseCommit'],'34f26ed647453050c38d6c1df004ecacb0f0dbb7')
        self.assertEqual(self.game['version'],3)
        self.assertEqual(self.game['counts'],{'games':1,'characters':6,'stages':10,'bosses':3})
        self.assertIn('<a class="wordmark" href="/#/playground">← 놀이터</a>',self.html)
        self.assertIn(builder.STORAGE_KEY,self.html)
        for old in ('isegye:review:courier:v2','검토본','검토 전용'):self.assertNotIn(old,self.html)
        self.assertEqual(self.before,{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in builder.SOURCES})
        self.assertIn("isegye:review:courier:v2",(ROOT/'fangames/app.js').read_text())
        self.assertEqual((self.out/'src/app.js').read_text(),'const existingSite=true;')

    def test_hashed_offline_game_and_exact_generated_art(self):
        self.assertEqual(self.game['htmlSha256'],hashlib.sha256(self.raw).hexdigest())
        self.assertEqual(self.game['htmlBytes'],len(self.raw))
        self.assertLess(len(self.raw),builder.MAX_HTML_BYTES)
        for tag in ('script','style'):
            blocks=re.findall('<'+tag+'>([\\s\\S]*?)</'+tag+'>',self.html)
            self.assertEqual(len(blocks),1)
            digest=base64.b64encode(hashlib.sha256(blocks[0].encode()).digest()).decode()
            self.assertIn('sha256-'+digest,self.html)
        self.assertIn("connect-src 'none'",self.html)
        self.assertNotIn("'unsafe-inline'",self.html)
        art=json.loads(re.search(r'const COURIER_ART=Object.freeze\((\{[^\n]*\})\);',self.html)[1])
        self.assertEqual(set(art),set(builder.ART_NAMES))
        self.assertIn('gear',art)
        self.assertIn('standing',art)
        self.assertIn('walk',art)
        self.assertNotEqual(art['walk'],art['characters'])
        self.assertNotIn('districts',art)
        stage_keys=['plaza',*(f'stage{i:02d}' for i in range(2,11))]
        self.assertEqual(len({art[name] for name in stage_keys}),10)
        for name,value in art.items():
            self.assertEqual(base64.b64decode(value.split(',',1)[1],validate=True),(ROOT/f'fangames/assets/{name}.webp').read_bytes())
        for name in builder.CARD_ASSETS:
            self.assertEqual((self.out/f'assets/courier/{name}.webp').read_bytes(),(ROOT/f'fangames/assets/{name}.webp').read_bytes())

    def test_six_walk_cycles_have_distinct_poses_and_share_the_idle_baseline(self):
        from PIL import Image
        for filename, columns, rows in [('walk',4,6),('standing',3,2)]:
            with Image.open(ROOT/f'fangames/assets/{filename}.webp') as atlas:
                size=atlas.width//columns
                self.assertEqual(atlas.size,(columns*size,rows*size))
                for row in range(rows):
                    steps=set()
                    for col in range(columns):
                        frame=atlas.crop((col*size,row*size,(col+1)*size,(row+1)*size))
                        shape=frame.getchannel('A').point(lambda a: 255 if a>=100 else 0)
                        left,top,right,bottom=shape.getbbox()
                        self.assertGreater(left,0)
                        self.assertLess(right,size)
                        self.assertLess(top,size*.3)
                        self.assertAlmostEqual(bottom,size*.94,delta=3)
                        feet=shape.crop((0,size*2//3,size,size)).resize((24,12))
                        steps.add(feet.tobytes())
                    self.assertEqual(len(steps),columns)

    def test_rpg_fonts_and_full_notices_travel_with_the_game(self):
        fonts=json.loads(re.search(r'const RPG_FONT = Object\.freeze\(([^\n]+)\);',self.html)[1])
        notices=json.loads(re.search(r'const RPG_FONT_NOTICES = Object\.freeze\(([^\n]+)\);',self.html)[1])
        self.assertEqual(set(fonts),{'Gowun Dodum','Jua'})
        self.assertEqual(set(notices),set(fonts))
        for family,basename in FONT_FAMILIES.items():
            font=f'rpg/fonts/{basename}-Regular.woff2'
            notice=f'rpg/fonts/{basename}-OFL.txt'
            self.assertEqual(base64.b64decode(fonts[family],validate=True),(ROOT/font).read_bytes())
            self.assertEqual(notices[family],(ROOT/notice).read_text(encoding='utf-8-sig'))
            for path in (font,notice):
                self.assertEqual(self.game['sourceHashes'][path],hashlib.sha256((ROOT/path).read_bytes()).hexdigest())

    def test_rebuild_is_byte_identical(self):
        with patch.dict(os.environ,{'GITHUB_REF':'refs/heads/main'}):again=builder.build(self.out)
        self.assertEqual(again,self.game)
        self.assertEqual(self.raw,(self.out/builder.HTML_PATH).read_bytes())

    def test_operating_build_refuses_nonmain_and_output_symlink(self):
        with patch.dict(os.environ,{'GITHUB_REF':'refs/heads/develop'}):
            with self.assertRaisesRegex(ValueError,'Main-only'):builder.build(self.out)
        with tempfile.TemporaryDirectory() as temp:
            dest=Path(temp);(dest/'build-info.json').write_text('{"mode":"preview"}')
            if os.name=='nt':
                # Directory junctions exercise output redirection without developer-mode privileges.
                import _winapi
                _winapi.CreateJunction(str(self.out/'games'),str(dest/'games'))
            else:
                (dest/'games').symlink_to(self.out/'games',target_is_directory=True)
            with self.assertRaisesRegex(ValueError,'symlink'):builder.build(dest)

    def test_deployment_accepts_only_the_single_approved_html_path(self):
        self.assertIn(builder.HTML_PATH,self.payload)
        self.assertEqual(deploy.courier_artifact(self.payload),self.game)
        for relative in ('games/other/index.html','games/starlight-courier/extra.html','src/arbitrary.html'):
            with self.subTest(path=relative),tempfile.TemporaryDirectory() as temp:
                out=Path(temp)
                for name,raw in self.payload.items():
                    dest=out/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw)
                bad=out/relative;bad.parent.mkdir(parents=True,exist_ok=True);bad.write_text('<html>Unexpected</html>')
                with self.assertRaisesRegex(transfer.Stop,'Unexpected build file'):transfer.load_payload(out,'a'*40)

    def test_publication_rejects_document_art_or_identity_mismatch(self):
        for file in (builder.HTML_PATH,'assets/courier/plaza.webp'):
            with self.subTest(file=file):
                payload=dict(self.payload);payload[file]+=b'\n'
                with self.assertRaises(transfer.Stop):deploy.courier_artifact(payload)
        for field,value in (('storageKey','isegye:review:courier:v2'),('route','/review-playground/'),('generatedArtwork',False),('baseCommit','0'*40),('sourceHashes',{})):
            with self.subTest(field=field):
                meta=json.loads(self.payload['build-info.json']);meta['courierGame'][field]=value
                payload=dict(self.payload);payload['build-info.json']=json.dumps(meta).encode()
                with self.assertRaises(transfer.Stop):deploy.courier_artifact(payload)

    def test_legacy_payloads_without_game_keep_existing_deployment_path(self):
        for payload in ({},{'index.html':b'Existing site'},
                        {'build-info.json':b'PRIVATE_BUILD'},
                        {'build-info.json':b'{"mode":"production"}'}):
            with self.subTest(payload=payload):self.assertIsNone(deploy.courier_artifact(payload))

    def test_game_requires_release_metadata(self):
        for metadata in (None,b'PRIVATE_BUILD',b'{}',b'[]'):
            with self.subTest(metadata=metadata):
                payload=dict(self.payload)
                if metadata is None:payload.pop('build-info.json')
                else:payload['build-info.json']=metadata
                with self.assertRaisesRegex(transfer.Stop,'Courier metadata/document missing'):deploy.courier_artifact(payload)

    def test_publication_requires_actual_enforced_csp(self):
        meta_tag=re.search(r'<meta http-equiv="Content-Security-Policy"[^>]*>',self.html)[0]
        for changed in (meta_tag.replace('http-equiv=','name='),
                        '<!--'+meta_tag+'-->',meta_tag+meta_tag,
                        '<template>'+meta_tag+'</template>',
                        meta_tag.replace("connect-src 'none'","connect-src https:"),
                        meta_tag.replace("script-src 'sha256-","script-src 'disabled-")):
            with self.subTest(change=changed[:120]):
                payload=dict(self.payload)
                payload[builder.HTML_PATH]=self.html.replace(meta_tag,changed).encode()
                metadata=json.loads(payload['build-info.json'])
                metadata['courierGame']['htmlSha256']=hashlib.sha256(payload[builder.HTML_PATH]).hexdigest()
                metadata['courierGame']['htmlBytes']=len(payload[builder.HTML_PATH])
                payload['build-info.json']=json.dumps(metadata).encode()
                with self.assertRaises(transfer.Stop):deploy.courier_artifact(payload)

    def test_host_patch_keeps_gate_and_only_adds_exact_game_document(self):
        original=(ROOT/'auth/Gateway.php').read_text();patched=host.patched(original)
        self.assertEqual(original,(ROOT/'auth/Gateway.php').read_text())
        self.assertLess(patched.index("if (!$access['allowed'])"),patched.index('// ISEGYE-COURIER:'))
        self.assertIn("'games/starlight-courier/index.html'",patched)
        self.assertIn("$path === '/games/starlight-courier/'",patched)
        self.assertIn("header('X-Frame-Options: DENY')",patched)
        self.assertIn("'html'=>'text/html; charset=utf-8'",patched)
        self.assertIn("['index.html','robots.txt','build-info.json','games/starlight-courier/index.html','games/ipari-chronicle/index.html']",patched)
        self.assertIn("(?:js|css|svg|png|webp|jpg|json)",patched)
        for preview in ('/review-playground','/review-fanmade','/review-albums'):
            self.assertIn(preview,patched)

    def test_live_verification_checks_game_and_card_maintenance_gate(self):
        from compose_admin_visibility import POLICY
        called=[]
        def response(url):
            path=url.removeprefix(transfer.ORIGIN);called.append(path)
            if path in POLICY['protectedPaths']:return 401,b'Administrator access required'
            return 503,'현재 사이트는 공사중입니다.'.encode()
        report={}
        with patch.object(deploy,'status',return_value={'maintenance':True}),patch.object(transfer,'http',side_effect=response),patch('batch_monitor_storage.verify_anonymous'):
            deploy.verify_public(self.payload,report)
        self.assertTrue(report['courierExistingAccessPolicyVerified'])
        for path in (builder.ROUTE,'/'+builder.HTML_PATH,'/assets/courier/characters.webp','/assets/courier/plaza.webp'):
            self.assertIn(path,called)

    def test_maintenance_response_cannot_contain_hidden_game(self):
        def response(url):
            raw='현재 사이트는 공사중입니다.'.encode()
            if url.endswith(builder.ROUTE):raw+=b'const COURIER_ART='
            return 503,raw
        with patch.object(deploy,'status',return_value={'maintenance':True}),patch.object(transfer,'http',side_effect=response),patch('batch_monitor_storage.verify_anonymous'):
            with self.assertRaisesRegex(transfer.Stop,'Maintenance gate'):deploy.verify_public(self.payload,{})

if __name__=='__main__':unittest.main()
