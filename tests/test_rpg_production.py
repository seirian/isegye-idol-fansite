import unittest,tempfile,json,os,sys
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import build_rpg_production as builder
import deploy_google_access as deploy
import inour_sftp as transfer
import build_playground_production_host as host
class RPGProductionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.out=Path(self.temp.name);(self.out/'build-info.json').write_text('{"mode":"preview"}')
        self.game=builder.build(self.out)
        self.payload={p.relative_to(self.out).as_posix():p.read_bytes() for p in self.out.rglob('*') if p.is_file()}
        self.payload['build-info.json']=json.dumps({'rpgGame':self.game}).encode()
    def test_exact_artifact_and_sources_bound_to_release(self):
        self.assertEqual(deploy.rpg_artifact(self.payload),self.game)
        self.assertIn(b'data-rpg-return',self.payload[builder.HTML_PATH])
        for file in (builder.HTML_PATH,*self.game['cardAssets']):
            payload=dict(self.payload);payload[file]+=b'changed'
            with self.assertRaises(transfer.Stop):deploy.rpg_artifact(payload)
        payload=dict(self.payload);payload['build-info.json']=b'{}'
        with self.assertRaises(transfer.Stop):deploy.rpg_artifact(payload)
    def test_csp_tampering_is_rejected_even_with_updated_manifest_hash(self):
        import hashlib
        payload=dict(self.payload);raw=payload[builder.HTML_PATH].replace(b"connect-src 'none'",b'connect-src https:')
        payload[builder.HTML_PATH]=raw;game=dict(self.game,htmlSha256=hashlib.sha256(raw).hexdigest(),htmlBytes=len(raw))
        payload['build-info.json']=json.dumps({'rpgGame':game}).encode()
        with self.assertRaises(transfer.Stop):deploy.rpg_artifact(payload)
    def test_production_is_main_only_and_output_cannot_escape(self):
        (self.out/'build-info.json').write_text('{"mode":"production"}')
        with patch.dict(os.environ,{'GITHUB_REF':'refs/heads/develop'}):
            with self.assertRaisesRegex(ValueError,'Main-only'):builder.build(self.out)
        with tempfile.TemporaryDirectory() as t:
            out=Path(t);(out/'build-info.json').write_text('{"mode":"preview"}')
            (out/'games').symlink_to(self.out/'games',target_is_directory=True)
            with self.assertRaisesRegex(ValueError,'symlink'):builder.build(out)
    def test_existing_gate_precedes_both_exact_game_routes(self):
        patched=host.patched((ROOT/'auth/Gateway.php').read_text())
        self.assertLess(patched.index("if (!$access['allowed'])"),patched.index("$path === '/games/ipari-chronicle'"))
        for path in ('games/ipari-chronicle/index.html','games/starlight-courier/index.html','/review-playground'):
            self.assertIn(path,patched)
        self.assertNotIn("games/.*",patched)
    def test_live_gate_checks_game_document_and_card_images(self):
        from compose_admin_visibility import POLICY
        calls=[]
        def response(url):
            path=url.removeprefix(transfer.ORIGIN);calls.append(path)
            if path in POLICY['protectedPaths']:return 401,b'Administrator access required'
            return 503,'현재 사이트는 공사중입니다.'.encode()
        report={}
        with patch.object(deploy,'status',return_value={'maintenance':True}),patch.object(transfer,'http',side_effect=response),patch('batch_monitor_storage.verify_anonymous'):
            deploy.verify_public(self.payload,report)
        self.assertTrue(report['rpgExistingAccessPolicyVerified'])
        for path in (builder.ROUTE,'/'+builder.HTML_PATH,*('/'+p for p in self.game['cardAssets'])):self.assertIn(path,calls)
    def test_legacy_payload_is_preserved(self):
        self.assertIsNone(deploy.rpg_artifact({}))
if __name__=='__main__':unittest.main()
