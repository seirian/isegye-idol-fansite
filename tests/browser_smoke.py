"""Browser smoke tests. Run after npm run build. Requires playwright==1.56.0.
BASE_URL may target an already running preview; otherwise starts our local dist server.
No account, submission, outside navigation, or production writes are performed.
"""
import os
import time
import unittest
import subprocess
from pathlib import Path
from urllib.request import urlopen
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / os.environ.get('SMOKE_OUT', 'test-results')
OUT.mkdir(parents=True, exist_ok=True)

class BrowserSmoke(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = None
        cls.url = os.environ.get('BASE_URL', 'http://127.0.0.1:4173/').rstrip('/') + '/'
        if 'BASE_URL' not in os.environ:
            cls.server = subprocess.Popen(['node', 'scripts/serve.mjs', '--dist'], cwd=ROOT, stdout=subprocess.DEVNULL)
            for _ in range(50):
                try:
                    with urlopen(cls.url, timeout=1) as response:
                        if response.status == 200:
                            break
                except Exception:
                    time.sleep(0.1)
            else:
                raise RuntimeError('Preview server did not start')
        cls.pw = sync_playwright().start()
        opts = {'headless': True}
        executable = os.environ.get('CHROMIUM_PATH')
        if executable:
            opts['executable_path'] = executable
        cls.browser = cls.pw.chromium.launch(**opts)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()
        if cls.server:
            cls.server.terminate()
            cls.server.wait(timeout=5)

    def setUp(self):
        self.context = self.browser.new_context(viewport={'width': 1440, 'height': 1100}, locale='ko-KR', timezone_id='Asia/Seoul', color_scheme='light', reduced_motion='reduce')
        self.page = self.context.new_page()
        self.errors = []
        self.page.on('pageerror', lambda error: self.errors.append(str(error)))
        self.page.goto(self.url, wait_until='networkidle')
        self.page.locator('#main h1').wait_for()

    def tearDown(self):
        self.assertEqual(self.errors, [], 'Uncaught browser errors')
        self.context.close()

    def go(self, route):
        self.page.evaluate('(route) => { location.hash = route; }', route)
        self.page.wait_for_timeout(100)

    def test_01_home_and_navigation(self):
        self.assertIn('오늘도', self.page.locator('#main h1').inner_text())
        self.assertEqual(self.page.locator('.nav a').count(), 7)
        self.assertEqual(self.page.locator('.member-card').count(), 6)
        self.assertEqual(self.page.locator('.music-card').count(), 3)
        self.page.screenshot(path=str(OUT / 'home-desktop.png'), full_page=True)
        for route in ['members', 'schedule', 'music', 'videos', 'dictionary', 'history', 'guide', 'about', 'privacy', 'report', 'saved']:
            self.go('#/' + route)
            self.assertEqual(self.page.locator('#main h1').count(), 1)
            self.assertNotIn('기록을 찾을 수 없습니다', self.page.locator('#main h1').inner_text())

    def test_02_search_and_xss(self):
        self.go('#/search')
        self.page.get_by_label('통합 검색어', exact=True).fill('ㅇㅇㄴ')
        self.page.locator('#search-form button').click()
        self.page.wait_for_timeout(100)
        self.assertIn('아이네', self.page.locator('.result-row').first.inner_text())
        self.page.get_by_label('통합 검색어', exact=True).fill('<img src=x onerror=alert(1)>')
        self.page.locator('#search-form button').click()
        self.page.wait_for_timeout(100)
        self.assertEqual(self.page.locator('#main img').count(), 0)
        self.assertIn('찾는 기록이 아직 없어요', self.page.locator('#main').inner_text())

    def test_03_music_filters_detail(self):
        self.go('#/music?type=original&scope=solo')
        self.assertEqual(self.page.locator('[data-song]').count(), 3)
        self.page.locator('[data-song="cat-save-world"] a').click()
        self.page.wait_for_timeout(100)
        self.assertEqual(self.page.locator('.catalog-tracklist li').count(), 3)
        self.assertIn('고양이가 세상을 구한다!', self.page.locator('#main h1').inner_text())
        self.assertGreater(self.page.locator('.catalog-detail-sources a').count(), 0)
        self.page.screenshot(path=str(OUT / 'music-detail.png'), full_page=True)
        self.go('#/music?member=ine')
        self.assertGreater(self.page.locator('[data-song]').count(), 0)
        self.go('#/music?type=cover')
        self.assertEqual(self.page.locator('.catalog-result-heading strong').inner_text(), '133')
        self.assertEqual(self.page.locator('[data-song]').count(), 24)

    def test_04_bookmarks_persist_and_remove(self):
        self.go('#/record/no-cat-no-life')
        self.page.locator('.detail-actions .save-button').click()
        self.go('#/saved')
        self.assertEqual(self.page.locator('.result-row').count(), 1)
        self.page.reload(wait_until='networkidle')
        self.assertEqual(self.page.locator('.result-row').count(), 1)
        self.page.locator('.save-button').click()
        self.assertEqual(self.page.locator('.result-row').count(), 0)

    def test_05_calendar(self):
        self.go('#/schedule?month=2026-09&date=2026-09-28')
        self.assertIn('2026년 9월', self.page.locator('.calendar-header').inner_text())
        self.assertIn('NO CAT, NO LIFE!', self.page.locator('.calendar-layout').inner_text())
        self.page.get_by_role('button', name='다음 달', exact=True).click()
        self.page.wait_for_timeout(100)
        self.assertIn('2026년 10월', self.page.locator('.calendar-header').inner_text())
        self.assertIn('등록된 일정이 없어요', self.page.locator('.calendar-layout').inner_text())

    def test_06_mobile_and_theme(self):
        self.page.set_viewport_size({'width': 390, 'height': 844})
        self.assertLessEqual(self.page.evaluate('document.documentElement.scrollWidth'), 390)
        self.page.get_by_role('button', name='메뉴 열기', exact=True).click()
        self.assertIn('open', self.page.locator('#sidebar').get_attribute('class'))
        self.page.locator('.nav a[data-nav="music"]').click()
        self.page.wait_for_timeout(100)
        self.assertNotIn('open', self.page.locator('#sidebar').get_attribute('class'))
        self.go('#/home')
        self.page.screenshot(path=str(OUT / 'home-mobile.png'), full_page=True)
        self.page.get_by_role('button', name='색상 테마 변경', exact=True).click()
        self.assertEqual(self.page.locator('html').get_attribute('data-theme'), 'dark')
        self.page.reload(wait_until='networkidle')
        self.assertEqual(self.page.locator('html').get_attribute('data-theme'), 'dark')
        self.page.screenshot(path=str(OUT / 'home-dark-mobile.png'), full_page=True)

    def test_07_direct_link_and_invalid_record(self):
        self.page.goto(self.url + '#/record/white', wait_until='networkidle')
        self.assertIn('화이트', self.page.locator('#main h1').inner_text())
        self.go('#/record/not-a-record')
        self.assertIn('기록을 찾을 수 없습니다', self.page.locator('#main h1').inner_text())

    def test_08_report_validation_and_outbound_draft(self):
        self.go('#/report?record=no-cat-no-life')
        self.page.locator('#report-body').fill('공식 발매 안내의 수록곡 표기를 확인해주세요. 공개 근거를 함께 첨부합니다.')
        self.page.locator('.check-label input').check()
        self.page.locator('#report-form button[type=submit]').click()
        self.assertIn('HTTPS', self.page.locator('#toast').inner_text())
        self.page.locator('#report-source').fill('https://parable-asia.com/portfolio-item/no-cat-no-life/')
        requested = []
        self.page.route('https://github.com/**', lambda route: (requested.append(route.request.url), route.fulfill(status=200, content_type='text/html', body='<h1>Intercepted draft, not submitted</h1>')))
        self.page.locator('#report-form button[type=submit]').click()
        self.page.wait_for_timeout(200)
        self.assertTrue(requested)
        self.assertIn('/issues/new?', requested[0])

    def test_09_all_links_safe_and_no_automatic_playback(self):
        for route in ['#/home', '#/music', '#/guide', '#/record/no-cat-no-life']:
            self.go(route)
            for href in self.page.locator('a').evaluate_all('(links) => links.map(a => a.getAttribute("href"))'):
                self.assertTrue(href.startswith('#') or href.startswith('https://'), href)
        self.assertEqual(self.page.locator('iframe, audio, video').count(), 0)
        from urllib.parse import urlsplit
        for src in self.page.locator('img[src^="http"]').evaluate_all('(xs)=>xs.map(x=>x.src)'):
            self.assertIn(urlsplit(src).hostname, {'i.ytimg.com','liveimg.sooplive.com',urlsplit(self.url).hostname})

if __name__ == '__main__':
    unittest.main(verbosity=2)
