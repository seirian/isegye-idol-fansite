"""No network or deployment: enforce the selected production packaging contract."""
import importlib.util
import json
from pathlib import Path
import unittest
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('selected', ROOT/'scripts/build_selected.py')
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)

class SelectedBuildTests(unittest.TestCase):
    def test_backup_points_to_original_main(self):
        approval = json.loads((ROOT/'second/release.json').read_text())
        self.assertEqual(approval['sourceBackup'], {'branch':'backup/main1st', 'commit':'885e818063eeccedf468d52ce148a4760819c97d'})
        self.assertIs(approval['operatorApprovedDeployment'], True)

    def test_owner_approval_is_not_image_license(self):
        for filename in ['release.json', 'portraits.json']:
            data=json.loads((ROOT/'second'/filename).read_text())
            self.assertIs(data['rightsPermissionVerified'], False)
        self.assertIs(json.loads((ROOT/'second/portraits.json').read_text())['namuMatchVerified'], False)

    def test_changed_composition_fails_closed(self):
        with self.assertRaisesRegex(RuntimeError, 'anchor missing'):
            s.production_app('unrelated template')

    def test_deployment_paths_are_not_expanded(self):
        source=(ROOT/'scripts/build_selected.py').read_text()
        self.assertIn("inour_sftp.load_payload(OUT, meta['commit'])", source)
        self.assertNotIn('paramiko', source)

    def test_production_has_no_offline_payload(self):
        source=(ROOT/'scripts/build_selected.py').read_text()
        self.assertIn("ignore=shutil.ignore_patterns('review-second.html', 'image-sources.json')",source)
        self.assertIn("OUT / 'assets/portraits/sources.json'", source)

if __name__ == '__main__': unittest.main()
