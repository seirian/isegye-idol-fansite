import unittest,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from compose_content_polish import TEASER,adapt_app
class ContentPolishTests(unittest.TestCase):
 def test_teaser_not_music(self):
  self.assertEqual(TEASER['id'],'1ELogGmCh9Q')
  self.assertEqual(TEASER['type'],'official_teaser')
  self.assertEqual(TEASER['date'],'2026-11-04')
  self.assertEqual(len(TEASER['members']),6)
 def test_operating_adapter(self):
  s=(ROOT/'review-1st/app.js').read_text()
  out=adapt_app(s)
  self.assertNotIn('data-watched=',out)
  self.assertNotIn('직접 시청 완료 표시',out)
  self.assertIn('content-origin-link',out)
  self.assertIn('REVIEW_DATA.videos.push(',out)
  self.assertIn('noopener noreferrer',out)
 def test_build_wiring(self):
  self.assertIn('content_polish.adapt_app(', (ROOT/'scripts/promote_review_2nd.py').read_text())
if __name__=='__main__':unittest.main()
