from pathlib import Path
import sys, unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from build_review_host import HOOK,patched

class ReviewHost(unittest.TestCase):
    def test_patch_does_not_change_original_flow(self):
        original=(ROOT/'auth/Gateway.php').read_text()
        value=patched(original)
        self.assertEqual(value.replace(HOOK,''),original)
        self.assertLess(value.index("if (!$access['allowed'])"),value.index(HOOK))
    def test_anchor_change_rejected(self):
        with self.assertRaises(ValueError):patched('other gateway')
        with self.assertRaises(ValueError):patched(patched((ROOT/'auth/Gateway.php').read_text()))
    def test_private_handler_does_not_write_data(self):
        source=(ROOT/'review-1st/hosting/ReviewPreview.php').read_text()
        for unsafe in ('file_put_contents','unlink(','accounts.json','config.json','exec('):self.assertNotIn(unsafe,source)
        self.assertIn("$role !== 'admin'",source)
        self.assertIn('hash_equals',source)
        self.assertIn('realpath',source)
    def test_deployment_is_branch_scoped(self):
        source=(ROOT/'scripts/deploy_review_1st.py').read_text()
        self.assertIn("refs/heads/feature/review-1st",source)
        self.assertIn('PRODUCTION_PAUSED',source)
        self.assertIn('rollbackRestoredPreviousEntry',source)
        self.assertNotIn('/accounts.json',source)
        self.assertNotIn('/config.json',source)
        self.assertNotIn('remote.replace(d.ROOT+\'/.htaccess\'',source)

if __name__=='__main__':unittest.main()
