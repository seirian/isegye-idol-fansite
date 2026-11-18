"""Read-only transport retry and sanitized deployment diagnostics, no live calls."""
import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import Mock, patch
import unittest
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from auth_live_checks import AnonymousReadChecks, sanitized_failure
import deploy_google_access as deploy
import inour_sftp

class Error(Exception): pass
class TimeoutError(Error): pass

class LiveReadChecks(unittest.TestCase):
    def setup_reads(self, failures):
        request = Mock(); request.get.side_effect = failures
        pause = Mock()
        return request, pause, AnonymousReadChecks(request, 'https://isegye-idol.kr', (Error,), (TimeoutError,), pause)

    def test_connection_reset_retries_same_context_get_only(self):
        response = SimpleNamespace(status=200)
        request, pause, reads = self.setup_reads([Error('ECONNRESET Cookie=SECRET'), Error('socket hang up'), response])
        self.assertIs(reads.get('https://isegye-idol.kr/auth/privacy'), response)
        self.assertEqual(request.get.call_count, 3)
        self.assertEqual(pause.call_count, 2)
        self.assertEqual([row['transport'] for row in reads.retries], ['connection_reset', 'connection_closed'])
        self.assertNotIn('SECRET', json.dumps(reads.retries))
        self.assertEqual(request.method_calls, [unittest.mock.call.get('https://isegye-idol.kr/auth/privacy')]*3)

    def test_transport_retry_limit_is_two_additional_attempts(self):
        request, pause, reads = self.setup_reads([TimeoutError('nonce=SECRET')]*3)
        with self.assertRaises(TimeoutError) as caught: reads.get('https://isegye-idol.kr/auth/privacy')
        self.assertEqual(request.get.call_count, 3)
        self.assertEqual(reads.failure(caught.exception), {'errorType': 'TimeoutError', 'stage': 'get', 'route': '/auth/privacy', 'transport': 'timeout'})
        self.assertNotIn('SECRET', json.dumps(reads.failure(caught.exception)))

    def test_explicit_playwright_request_timeout_message_is_retryable(self):
        request, pause, reads = self.setup_reads([Error('APIRequestContext.get: Timeout 30000ms exceeded.'), SimpleNamespace(status=200)])
        self.assertEqual(reads.get('https://isegye-idol.kr/auth/privacy').status, 200)
        self.assertEqual(request.get.call_count, 2)
        self.assertEqual(reads.retries[0]['transport'], 'timeout')

    def test_http_error_response_is_never_retried(self):
        response = SimpleNamespace(status=503)
        request, pause, reads = self.setup_reads([response])
        self.assertIs(reads.get('https://isegye-idol.kr/auth/privacy'), response)
        self.assertEqual(request.get.call_count, 1); pause.assert_not_called()

    def test_assertion_content_and_nontransport_errors_are_not_retried(self):
        for error in (AssertionError('ECONNRESET'), ValueError('timeout'), Error('HTTP 503'), Error('Target page, context or browser has been closed')):
            request, pause, reads = self.setup_reads([error])
            with self.assertRaises(type(error)): reads.get('https://isegye-idol.kr/auth/privacy')
            self.assertEqual(request.get.call_count, 1); pause.assert_not_called()
        request, pause, reads = self.setup_reads([])
        reads.stage('assertion', 'https://isegye-idol.kr/auth/privacy')
        self.assertEqual(reads.failure(AssertionError('Cookie=SECRET'))['transport'], 'not_transport')

    def test_query_foreign_origin_unknown_routes_and_http_throw_mode_refused(self):
        request, pause, reads = self.setup_reads([])
        for url in ('https://evil.invalid/auth/privacy', 'https://isegye-idol.kr/auth/privacy?nonce=SECRET', 'https://isegye-idol.kr/unknown'):
            with self.assertRaises(ValueError): reads.get(url)
        with self.assertRaises(ValueError): reads.get('https://isegye-idol.kr/auth/privacy', fail_on_status_code=True)
        request.get.assert_not_called()

    def test_sanitizer_discards_messages_headers_and_unlisted_values(self):
        value = sanitized_failure({'errorType': ['SECRET'], 'stage': 'secret-stage', 'route': '/auth/privacy?token=SECRET',
            'transport': 'SECRET', 'message': 'Cookie=SECRET', 'headers': {'cookie': 'SECRET'}})
        self.assertEqual(value, {'errorType': 'Exception', 'stage': 'start', 'route': '[unlisted]', 'transport': 'not_transport'})

    def test_final_report_and_log_redact_stderr_and_keep_actual_stage(self):
        secret = 'SECRET-cookie-header-nonce'
        result = {'status': 'failed', 'commit': 'a'*40, 'passed': 14, 'total': 14,
            'failure': {'errorType': 'Error', 'stage': 'get', 'route': '/auth/privacy', 'transport': 'connection_reset', 'message': secret}, 'cookies': secret}
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)/'result.json'; output.write_text('{"stale":true}')
            def run(*args, **kwargs):
                self.assertFalse(output.exists())
                output.write_text(json.dumps(result))
                return SimpleNamespace(returncode=1, stdout=secret, stderr=secret)
            captured = io.StringIO()
            with patch.object(deploy, 'Path', return_value=output), patch.object(deploy.subprocess, 'run', side_effect=run), contextlib.redirect_stdout(captured):
                with self.assertRaises(inour_sftp.Stop): deploy.verify_browser('a'*40, 'fixture-public-client')
            logged = captured.getvalue()
            self.assertNotIn(secret, logged); self.assertIn('/auth/privacy', logged); self.assertIn('connection_reset', logged)
            self.assertEqual(json.loads(logged)['googleAccessBrowser']['passed'], 14)

    def test_process_timeout_does_not_print_captured_secrets(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)/'result.json'; captured = io.StringIO()
            error = subprocess.TimeoutExpired(['cmd'], 240, output='SECRET', stderr='SECRET')
            with patch.object(deploy, 'Path', return_value=output), patch.object(deploy.subprocess, 'run', side_effect=error), contextlib.redirect_stdout(captured):
                with self.assertRaises(inour_sftp.Stop): deploy.verify_browser('a'*40, 'fixture-public-client')
            self.assertNotIn('SECRET', captured.getvalue()); self.assertIn('timeout', captured.getvalue())

    def test_live_script_routes_all_request_gets_through_same_context_helper(self):
        source = (ROOT/'tests/auth/production_browser.py').read_text()
        self.assertNotIn('c.request.get(', source)
        self.assertIn('AnonymousReadChecks(c.request,URL,(PlaywrightError,),(PlaywrightTimeoutError,))', source)
        self.assertIn("report['failure']=reads.failure(exc)", source)
        self.assertIn('raise SystemExit(1) from None', source)

if __name__ == '__main__': unittest.main()
