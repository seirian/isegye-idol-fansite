from pathlib import Path
import sys, unittest
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build_review_2nd as build
import review_2nd_polish as polish

class PresentationOnly(unittest.TestCase):
 def test_accepted_views_are_identical(self):
  before=build.adapt_app((ROOT/'review-1st/app.js').read_text());after=polish.app(before)
  pairs=[('function homeView(p)','function membersView()'),('function membersView()','function scheduleView(p)'),
         ('function scheduleView(p)','function musicView(p)'),('function musicView(p)','function contentView(p)'),
         ('function contentView(p)','function guideView'),('function settingsView()','function notFound()')]
  for start,end in pairs:
   self.assertEqual(polish.between(before,start,end),polish.between(after,start,end),start)
 def test_footer_and_guide_only_replace_requested_fragments(self):
  code=polish.app(build.adapt_app((ROOT/'review-1st/app.js').read_text()))
  self.assertIn('ProductionUI.footer(',code);self.assertIn('ProductionUI.guide()',code);self.assertIn('ProductionUI.about()',code)
  self.assertNotIn('입문·복귀·참여를 돕는 짧은 길잡이.',code)
  self.assertIn("else if(root==='review')html=reviewView();",code)
 def test_footer_css_filter_keeps_other_selectors(self):
  self.assertEqual(polish.without_review_footer('.x,.footer{color:red}@media(max-width:1px){.footer a{color:red}.y{display:grid}}'),'.x{color:red}@media (max-width:1px){.y{display:grid}}')
 def test_fail_closed_on_unknown_markup(self):
  with self.assertRaises(ValueError):polish.app('changed markup')
  with self.assertRaises(ValueError):polish.adapter('changed markup','no footer')
 def test_css_scope_does_not_change_live_body_or_gallery(self):
  css=(ROOT/'review-2nd/polish.css').read_text()
  for x in ('.live-card','.catalog-member-card','.gallery','.day-chip','.card-body'):self.assertNotIn(x,css)
if __name__=='__main__':unittest.main()
