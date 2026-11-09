from pathlib import Path
import sys,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from albums_composer import preserved_root_metadata

def fixture(ref='a'*40,version='dev-feature/review-2nd',library='7.1.0.0'):
    block=lambda name: f"    '{name}' => array(\n        'name' => 'isegye/private-google-access',\n        'pretty_version' => '{version}',\n        'version' => '{version}',\n        'reference' => '{ref}',\n        'type' => 'project',\n        'aliases' => array(),\n    ),\n"
    return ("<?php return array(\n"+block('root')+"    'versions' => array(\n        'firebase/php-jwt' => array(\n            'version' => '"+library+"',\n            'reference' => '"+'d'*40+"',\n        ),\n"+block('isegye/private-google-access')+"    ),\n);\n").encode()
class ComposerPreservationTests(unittest.TestCase):
    def test_root_vcs_labels_preserve_exact_deployed_bytes(self):
        old=fixture();self.assertEqual(preserved_root_metadata(old,fixture('b'*40,'1.0.0+no-version-set')),old)
    def test_dependency_change_rejected(self):
        with self.assertRaises(ValueError):preserved_root_metadata(fixture(),fixture(library='7.2.0.0'))
    def test_dependency_reference_change_rejected(self):
        with self.assertRaises(ValueError):preserved_root_metadata(fixture(),fixture().replace(('d'*40).encode(),('e'*40).encode()))
    def test_php_injection_rejected(self):
        with self.assertRaises(ValueError):preserved_root_metadata(fixture(),fixture().replace(b"'type' => 'project'",b"'type' => system('bad')"))
    def test_reference_must_be_literal_commit(self):
        with self.assertRaises(ValueError):preserved_root_metadata(fixture(),fixture(ref='bad-ref'))
if __name__=='__main__':unittest.main()
