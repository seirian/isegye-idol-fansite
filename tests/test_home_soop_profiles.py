"""Home-only SOOP profiles: fixed identities, safe sources and unchanged LIVE."""
from pathlib import Path
import copy,hashlib,io,json,sys,unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import home_soop_profiles as profiles
class SoopHomeTests(unittest.TestCase):
    def manifest(self):return json.loads((ROOT/'home-review/soop-profiles.json').read_text())
    def test_six_verified_identities(self):
        self.assertEqual(len(profiles.validate(self.manifest())),6)
    def test_wrong_member_rejected(self):
        m=self.manifest();m['members'][0]['channel']='someoneelse'
        with self.assertRaises(ValueError):profiles.validate(m)
    def test_duplicate_or_missing_member_rejected(self):
        m=self.manifest();m['members'][-1]=copy.deepcopy(m['members'][0])
        with self.assertRaises(ValueError):profiles.validate(m)
    def test_only_exact_official_source_allowed(self):
        for url in ('https://evil.invalid/test.jpg','http://profile.img.sooplive.co.kr/x.jpg','https://profile.img.sooplive.co.kr/LOGO/ji/jingburger1/jingburger1.jpg'):
            m=self.manifest();m['members'][0]['sourceImage']=url
            with self.assertRaises(ValueError):profiles.validate(m)
    def test_changed_image_is_never_silently_used(self):
        with self.assertRaises(ValueError):profiles.prepare(b'changed',self.manifest()['members'][0])
    def test_only_home_shortcuts_use_new_renderer(self):
        ui=(ROOT/'home-review/ui.js').read_text()
        self.assertEqual(ui.count('${homeShortcutPortrait(m)}'),1)
        self.assertIn('return liveHomeView() +',ui)
        self.assertNotIn('PORTRAITS[m.id] =',ui)
        self.assertNotIn('old-avatar',ui)
        self.assertIn('data-home-soop-image',ui)
    def test_original_global_images_and_live_sources_pinned(self):
        approval=json.loads((ROOT/'review/home-release.json').read_text())
        for path in ('live/core.js','live/ui.js','live/theme.css'):
            self.assertEqual(hashlib.sha256((ROOT/path).read_bytes()).hexdigest(),approval['sourceHashes'][path])
        self.assertEqual(json.loads((ROOT/'review/portraits.json').read_text())['source'],'Genie Music')
    def test_standalone_embeds_separate_profile_set(self):
        compiler=(ROOT/'scripts/build_home_review.py').read_text()
        self.assertIn('INLINE_SOOP_PROFILES',compiler)
        self.assertIn('INLINE_PORTRAITS',compiler)
        self.assertIn('home_soop_profiles.build(out)',compiler)
    def test_no_new_client_external_image_domain(self):
        ui=(ROOT/'home-review/ui.js').read_text()
        self.assertIn('./assets/soop-profiles/',ui)
        self.assertNotIn('https://profile.img.',ui)
        self.assertNotIn('https://stimg.',ui)
if __name__=='__main__':unittest.main()
