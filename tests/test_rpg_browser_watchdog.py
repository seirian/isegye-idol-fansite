"""Exercise real worker processes without starting a browser or modifying a game."""
from importlib.util import module_from_spec, spec_from_file_location
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest

spec = spec_from_file_location('rpg_browser_watchdog_subject', Path(__file__).with_name('rpg_browser.py'))
rpg = module_from_spec(spec)
spec.loader.exec_module(rpg)


@unittest.skipUnless(os.name == 'posix', 'Production browser verification uses POSIX process groups')
class BrowserWatchdog(unittest.TestCase):
    def test_worker_success_runs_once(self):
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / 'attempts'
            command = [sys.executable, '-c',
                       f'from pathlib import Path; p=Path({str(marker)!r}); p.write_text(p.read_text()+"x" if p.exists() else "x")']
            outcome = rpg.run_guarded(command, timeout=3, cwd=directory)
            self.assertEqual(outcome['exitCode'], 0)
            self.assertFalse(outcome['timedOut'])
            self.assertEqual(marker.read_text(), 'x')

    def test_failed_worker_is_not_retried_or_converted_to_success(self):
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / 'attempts'
            command = [sys.executable, '-c',
                       f'from pathlib import Path; import sys; p=Path({str(marker)!r}); p.write_text(p.read_text()+"x" if p.exists() else "x"); sys.exit(7)']
            outcome = rpg.run_guarded(command, timeout=3, cwd=directory)
            self.assertEqual(outcome['exitCode'], 7)
            self.assertFalse(outcome['timedOut'])
            self.assertEqual(marker.read_text(), 'x')
            self.assertEqual(rpg.supervised_report(Path(directory), outcome)['status'], 'failed')

    def test_deadline_kills_hung_worker_and_its_child(self):
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / 'child-pid'
            grandchild = 'import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); time.sleep(60)'
            worker = (
                'import signal,subprocess,sys,time; from pathlib import Path; '
                'signal.signal(signal.SIGTERM,signal.SIG_IGN); '
                f'child=subprocess.Popen([sys.executable,"-c",{grandchild!r}]); '
                f'Path({str(marker)!r}).write_text(str(child.pid)); time.sleep(60)'
            )
            before = time.monotonic()
            outcome = rpg.run_guarded([sys.executable, '-c', worker], timeout=1, grace=.15, cwd=directory)
            self.assertTrue(outcome['timedOut'])
            self.assertEqual(outcome['exitCode'], 124)
            self.assertLess(time.monotonic() - before, 5)
            child = int(marker.read_text())
            # A killed orphan may briefly remain as a zombie before init reaps it.
            def running():
                try:
                    return Path(f'/proc/{child}/stat').read_text().split()[2] != 'Z'
                except (FileNotFoundError, ProcessLookupError):
                    return False
            for _ in range(20):
                if not running():
                    break
                time.sleep(.05)
            self.assertFalse(running(), 'The hung browser-like descendant survived the watchdog')

    def test_timeout_preserves_partial_checks_and_screenshot_progress(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            partial = {'status': 'running', 'checks': ['settings close verified'],
                       'screenshots': ['07-settings-390.png'],
                       'lastProgress': {'phase': 'context:layout-390:close'}}
            rpg.write_json(path / 'progress.json', partial)
            result = rpg.supervised_report(path, {'exitCode': 124, 'timedOut': True, 'elapsedSeconds': 300})
            self.assertEqual(result['status'], 'failed')
            self.assertEqual(result['failureCode'], 'browser_watchdog_timeout')
            for key in ('checks', 'screenshots', 'lastProgress'):
                self.assertEqual(result[key], partial[key])

    def test_timeout_cannot_publish_a_late_passing_report(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            rpg.write_json(path / 'report.json', {'status': 'passed', 'checks': ['completed']})
            result = rpg.supervised_report(path, {'exitCode': 124, 'timedOut': True, 'elapsedSeconds': 300})
            self.assertEqual(result['status'], 'failed')
            self.assertEqual(result['failureCode'], 'browser_watchdog_timeout')

    def test_success_requires_worker_exit_and_a_passing_report(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            clean = {'exitCode': 0, 'timedOut': False, 'elapsedSeconds': 1}
            self.assertEqual(rpg.supervised_report(path, clean)['status'], 'failed')
            rpg.write_json(path / 'report.json', {'status': 'passed', 'checks': ['completed']})
            self.assertEqual(rpg.supervised_report(path, clean)['status'], 'passed')
            self.assertEqual(rpg.supervised_report(path, dict(clean, exitCode=7))['status'], 'failed')


if __name__ == '__main__':
    unittest.main()
