"""Real PHP session storage with a deterministic test-only clock; no real accounts."""
from pathlib import Path
import json
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PHP = r'''
namespace Isegye\Access {
    function time(): int { return $GLOBALS['session_test_now']; }
}
namespace {
    require $argv[1];
    $case = json_decode($argv[3], true, 8, JSON_THROW_ON_ERROR);
    $GLOBALS['session_test_now'] = 2000000000;
    \Isegye\Access\Session::start($argv[2]);
    if (!($case['anonymous'] ?? false)) {
        \Isegye\Access\Session::login(str_repeat('a', 64));
        $_SESSION['issued'] = $GLOBALS['session_test_now'] - $case['age'];
        $_SESSION['activity'] = $GLOBALS['session_test_now'] - $case['idle'];
    }
    $before = session_id();
    $csrf = \Isegye\Access\Session::csrf();
    session_write_close();
    session_id($before);
    \Isegye\Access\Session::start($argv[2]);
    $expired = \Isegye\Access\Session::account() === null;
    if ($case['touch'] ?? false) \Isegye\Access\Session::touch();
    $after = session_id();
    $result = [
        'authenticated' => !$expired,
        'rotated' => $before !== $after,
        'csrfChanged' => $csrf !== \Isegye\Access\Session::csrf(),
        'csrfLength' => strlen(\Isegye\Access\Session::csrf()),
        'issued' => $_SESSION['issued'] ?? null,
        'activity' => $_SESSION['activity'] ?? null,
        'cookieName' => session_name(),
        'cookie' => session_get_cookie_params(),
        'gcLifetime' => ini_get('session.gc_maxlifetime')
    ];
    if ($case['logout'] ?? false) {
        \Isegye\Access\Session::logout();
        $result['afterLogout'] = \Isegye\Access\Session::account();
        $result['sessionFileRemoved'] = !file_exists($argv[2] . '/sess_' . $after);
    } else {
        session_write_close();
    }
    echo json_encode($result, JSON_THROW_ON_ERROR);
}
'''


class SessionIdleTimeout(unittest.TestCase):
    def probe(self, *, idle=0, age=0, **options):
        with tempfile.TemporaryDirectory(prefix='isegye-session-test-') as directory:
            process = subprocess.run(
                ['php', '-r', PHP, str(ROOT / 'auth/Session.php'), directory,
                 json.dumps(dict(idle=idle, age=age, **options))],
                capture_output=True, text=True, timeout=15, check=True)
        self.assertEqual(process.stderr, '')
        return json.loads(process.stdout)

    def test_active_session_survives_old_30_minute_boundary(self):
        for idle in (1799, 1800, 1801, 3600, 7140, 7199):
            with self.subTest(idle=idle):
                result = self.probe(idle=idle, age=idle)
                self.assertTrue(result['authenticated'])
                self.assertFalse(result['rotated'])
                self.assertFalse(result['csrfChanged'])
                self.assertEqual(result['activity'], 2000000000 - idle)

    def test_exactly_120_minutes_and_later_expire(self):
        for idle in (7200, 7201, 10800):
            with self.subTest(idle=idle):
                result = self.probe(idle=idle, age=idle)
                self.assertFalse(result['authenticated'])
                self.assertTrue(result['rotated'])
                self.assertTrue(result['csrfChanged'])
                self.assertEqual(result['csrfLength'], 64)
                self.assertIsNone(result['issued'])
                self.assertIsNone(result['activity'])

    def test_absolute_12_hour_limit_is_not_extended(self):
        self.assertTrue(self.probe(age=43199, idle=0)['authenticated'])
        for age in (43200, 43201):
            with self.subTest(age=age):
                result = self.probe(age=age, idle=0)
                self.assertFalse(result['authenticated'])
                self.assertTrue(result['rotated'])

    def test_touch_updates_activity_not_issue_time(self):
        result = self.probe(age=10000, idle=7199, touch=True)
        self.assertTrue(result['authenticated'])
        self.assertEqual(result['activity'], 2000000000)
        self.assertEqual(result['issued'], 1999990000)

    def test_touch_cannot_revive_expired_or_logged_out_session(self):
        for options in ({'age': 7200, 'idle': 7200}, {'anonymous': True}):
            with self.subTest(options=options):
                result = self.probe(touch=True, **options)
                self.assertFalse(result['authenticated'])
                self.assertIsNone(result['activity'])

    def test_server_checks_do_not_implicitly_refresh_activity(self):
        result = self.probe(age=4000, idle=3600)
        self.assertEqual(result['activity'], 1999996400)
        self.assertEqual(result['issued'], 1999996000)

    def test_cookie_and_garbage_collection_settings_remain(self):
        result = self.probe()
        self.assertEqual(result['cookieName'], '__Host-ISEGYE')
        self.assertEqual(result['cookie'], {'lifetime': 0, 'path': '/', 'domain': '',
                                          'secure': True, 'httponly': True, 'samesite': 'Lax'})
        self.assertEqual(result['gcLifetime'], '43200')

    def test_logout_still_removes_session(self):
        result = self.probe(logout=True)
        self.assertIsNone(result['afterLogout'])
        self.assertTrue(result['sessionFileRemoved'])

    def test_disclosures_match_two_hour_idle_policy(self):
        for path in ('auth/privacy.html', 'docs/GOOGLE-ACCESS.md', 'docs/LEGAL-POLICIES.md'):
            with self.subTest(path=path):
                text = (ROOT / path).read_text().replace(' ', '')
                self.assertIn('비활동120분', text)
                self.assertNotIn('비활동30분', text)
                self.assertIn('12시간', text)


if __name__ == '__main__':
    unittest.main()
