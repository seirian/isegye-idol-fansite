"""Narrow-scope regressions for the three requested removals."""
from pathlib import Path
import sys
import unittest
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build_review_2nd as build
import review_2nd_polish as polish
import review_2nd_cleanup as cleanup

class Cleanup(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.before = polish.app(build.adapt_app((ROOT / 'review-1st/app.js').read_text()))
        cls.after = cleanup.app(cls.before)

    def test_removed_links_and_screen_are_absent(self):
        for text in ('class="nav-tools"', 'href="#/settings"', 'function settingsView(',
                     '나에게 맞는 화면', 'data-setting=', '같은 합방, 다른 시점', '맥락을 더 살펴보기'):
            self.assertNotIn(text, self.after)
        self.assertIn("if(r.parts[0]==='settings'){history.replaceState(null,'','#/home')", self.after)

    def test_operating_footer_guide_and_theme_stay(self):
        for text in ('${ProductionUI.footer(', 'return ProductionUI.guide();',
                     "else if(root==='guide')html=guideView(r.params);", 'aria-label="색상 테마 변경"',
                     'aria-label="저장함"'):
            self.assertIn(text, self.after)

    def test_other_major_views_are_identical(self):
        for start, end in [('function homeView(p)', 'function membersView()'),
                           ('function membersView()', 'function scheduleView(p)'),
                           ('function scheduleView(p)', 'function eventView('),
                           ('function musicView(p)', 'function contentView('),
                           ('function historyView(p)', 'function guideView()')]:
            self.assertEqual(polish.between(self.before, start, end), polish.between(self.after, start, end))

    def test_series_records_and_cards_are_retained(self):
        self.assertIn("D.series.map(seriesCard).join('')", self.after)
        before = polish.between(self.before, 'function seriesView(', 'function historyView(')
        after = polish.between(self.after, 'function seriesView(', 'function historyView(')
        self.assertIn("${mediaGrid([...vs,...ss])}", after)
        self.assertIn("D.history.filter(h=>h.title.includes('이세계페스티벌')).slice(-3).map(rowCard).join('')", after)
        self.assertIn('.length?`<section class="section">', after)
        self.assertEqual(before.split('${mediaGrid')[0], after.split('${mediaGrid')[0])

    def test_no_inaccessible_settings_left_active(self):
        self.assertIn("prefs.gallery=true;prefs.spoilers=false;prefs.density='cards';prefs.notifications=false;", self.after)
        self.assertNotIn('event.target.dataset.setting', self.after)
        self.assertNotIn("action==='reset-review'", self.after)
        self.assertIn("action==='export-saved'", self.after)
        self.assertIn('prefs.favorites', self.after)
        self.assertIn('prefs.watched', self.after)

    def test_unknown_source_is_rejected(self):
        with self.assertRaises(ValueError):
            cleanup.app('unknown markup')
        with self.assertRaises(ValueError):
            cleanup.app(self.before.replace('같은 합방, 다른 시점', 'unexpected text'))

if __name__ == '__main__':
    unittest.main()
