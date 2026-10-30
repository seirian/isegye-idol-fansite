"""Legal text stays canonical; presentation never opens protected application data."""
from pathlib import Path
import hashlib,json,re,subprocess,sys,unittest
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'scripts'))
import compose_legal_documents as legal
class LegalShell(unittest.TestCase):
 def test_canonical_bodies_unchanged(self):
  for kind,sha in [('terms','48702783988e07cd28a1d87a39347918b3b230a6'),('privacy','7f4dcef1368fe9ac94dd70c4ccfb7b6beda3cf5d')]:
   raw=(R/'auth'/f'{kind}.html').read_bytes()
   self.assertEqual(hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest(),sha)
 def test_composition(self):
  app="const views={privacy:privacyView}; const titles={privacy:'개인정보 안내'};function render(){if(focus)document.getElementById('main').focus({preventScroll:true});}shell();render();"
  meta={};out,css=legal.compose(app,'/* base */',meta)
  self.assertIn("terms:()=>legalDocumentView('terms')",out)
  self.assertIn("privacy:()=>legalDocumentView('privacy')",out)
  self.assertIn('queueMicrotask(legalDocumentMount)',out)
  self.assertTrue(meta['legalPresentation']['canonicalBodiesUnchanged'])
  for k in ('terms','privacy'):self.assertEqual(meta['legalPresentation']['sourceHashes'][k],hashlib.sha256((R/'auth'/f'{k}.html').read_bytes()).hexdigest())
  self.assertIn('var(--paper',css);self.assertNotIn('<iframe',out)
 def test_unexpected_render_anchor_rejected(self):
  with self.assertRaises(ValueError):legal.compose('different app','',{})
 def test_public_document_needs_no_session_or_javascript(self):
  for kind in ('terms','privacy'):
   html=subprocess.check_output(['php','-r',"require 'auth/View.php'; echo Isegye\\Access\\View::"+kind+'();'],cwd=R).decode()
   self.assertIn((R/'auth'/f'{kind}.html').read_text(),html)
   self.assertIn('legal-site-header',html);self.assertNotIn('<script',html)
   self.assertIn('value="dark"',html);self.assertIn('value="light"',html)
   self.assertNotIn('access-backdrop',html);self.assertNotIn('/auth/login',html)
 def test_existing_theme_and_clear_storage_contract(self):
  js=(R/'legal/ui.js').read_text()
  self.assertIn('data-action="clear-data"',js);self.assertNotIn('localStorage',js)
  self.assertNotIn('fetch(',js);self.assertIn('event.ctrlKey',js)
 def test_maintenance_render_is_unchanged(self):
  html=subprocess.check_output(['php','-r',"require 'auth/View.php'; echo Isegye\\Access\\View::maintenance();"],cwd=R).decode()
  self.assertIn('access-backdrop',html);self.assertNotIn('legal-tabs',html)
  self.assertNotIn('legal-public',html);self.assertNotIn('/auth/privacy',html)
if __name__=='__main__':unittest.main()
