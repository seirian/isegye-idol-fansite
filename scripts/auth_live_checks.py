"""Bounded retries for anonymous live-check GET transport failures only.
The existing request context is reused; no HTTP response or assertion is retried.
Diagnostics contain a fixed stage, public route and exception category, never a
Playwright message, headers, cookies, nonce or response body.
"""
import re
import time
from urllib.parse import urlparse

PUBLIC_ROUTES = {'/', '/auth/status', '/auth/login', '/auth/privacy', '/auth/terms',
    '/src/app.js', '/src/admin-operations.js', '/build-info.json', '/api/schedule',
    '/.schedule-feed/current.json', '/terms', '/privacy', '/.auth-private/accounts.json',
    '/.auth-private/config.json', '/access.php', '/_isegye_releases/r000000000000/index.html',
    '/_mir_site/index.html'}
OPERATIONS = {'start', 'get', 'navigation', 'screenshot', 'assertion', 'process_timeout'}


def transport_classification(exc, error_types, timeout_types):
    if isinstance(exc, timeout_types):
        return 'timeout'
    if not isinstance(exc, error_types):
        return 'not_transport'
    message = str(exc).lower()  # Classify locally; never log the message.
    for kind, patterns in (
        ('connection_reset', ('econnreset', 'err_connection_reset', 'connection reset by peer')),
        ('connection_closed', ('connection closed', 'connectionclosed', 'err_connection_closed', 'socket hang up', 'socket hangup', 'epipe')),
        ('timeout', ('etimedout', 'err_timed_out', 'request timed out')),
    ):
        if any(pattern in message for pattern in patterns):
            return kind
    if re.search(r'\btimeout \d+(?:\.\d+)?ms exceeded\b', message):
        return 'timeout'
    return 'not_transport'


def public_route(url):
    path = urlparse(url).path
    return path if path in PUBLIC_ROUTES else '[unlisted]'


class AnonymousReadChecks:
    def __init__(self, request, origin, error_types, timeout_types=(), pause=time.sleep):
        self.error_types, self.timeout_types = error_types, timeout_types
        self.request = request
        self.origin = origin.rstrip('/')
        self.pause = pause
        self.operation = 'start'
        self.route = '/'
        self.retries = []

    def stage(self, operation, url=None):
        if operation not in OPERATIONS:
            raise ValueError('Unrecognized live-check stage')
        self.operation = operation
        if url is not None:
            self.route = public_route(url)

    def get(self, url, **kwargs):
        parsed, origin = urlparse(url), urlparse(self.origin)
        if ((parsed.scheme, parsed.netloc) != (origin.scheme, origin.netloc) or parsed.query or parsed.fragment
                or parsed.path not in PUBLIC_ROUTES or kwargs.get('fail_on_status_code')):
            raise ValueError('Only same-origin public route GET checks are allowed')
        self.stage('get', url)
        for attempt in range(3):
            try:
                return self.request.get(url, **kwargs)
            except self.error_types as exc:
                kind = transport_classification(exc, self.error_types, self.timeout_types)
                if kind == 'not_transport' or attempt == 2:
                    raise
                self.retries.append({'stage': 'get', 'route': self.route,
                    'transport': kind, 'retry': attempt+1})
                self.pause(.5*(attempt+1))

    def failure(self, exc):
        return sanitized_failure({'errorType': type(exc).__name__, 'stage': self.operation,
            'route': self.route, 'transport': transport_classification(exc, self.error_types, self.timeout_types)})


def sanitized_failure(value):
    """Allowlist diagnostics again at the deployment log boundary."""
    value = value if isinstance(value, dict) else {}
    names = {'Error', 'TimeoutError', 'AssertionError', 'ValueError', 'JSONDecodeError',
        'KeyError', 'TypeError', 'OSError', 'RuntimeError', 'TargetClosedError', 'Exception'}
    kinds = {'not_transport', 'connection_reset', 'connection_closed', 'timeout'}
    def pick(key, allowed, fallback):
        candidate = value.get(key)
        return candidate if isinstance(candidate, str) and candidate in allowed else fallback
    return {'errorType': pick('errorType', names, 'Exception'), 'stage': pick('stage', OPERATIONS, 'start'),
        'route': pick('route', PUBLIC_ROUTES, '[unlisted]'), 'transport': pick('transport', kinds, 'not_transport')}
