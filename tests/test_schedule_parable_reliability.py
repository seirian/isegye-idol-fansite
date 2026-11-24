"""Parable retry and failure evidence, with no live requests or production writes."""
import io
import json
from pathlib import Path
import socket
import ssl
import sys
import unittest
from urllib.error import HTTPError, URLError
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import schedule_feed as feed
import schedule_health as health
import publish_schedule_feed as publisher
from test_schedule_feed import FeedRemote, seed

NOW = '2026-11-24T04:19:17+00:00'
OLD = '2026-11-24T02:19:43+00:00'
ROBOTS = 'https://parable-asia.com/robots.txt'
NEWSROOM = 'https://parable-asia.com/newsroom/'
RSS = 'https://parable-asia.com/feed/'
ARTICLE = 'https://parable-asia.com/fixture-announcement/'
SECRET = 'fixture-private-message https://example.invalid/?token=never-log'


def fixtures():
    return {
        ROBOTS: b'User-agent: *\nDisallow:\n',
        NEWSROOM: b'<link rel="alternate" type="application/rss+xml" href="/feed/">',
        RSS: ('<rss><channel><item><title>이세계아이돌 2026년 11월 25일 공연 안내</title>'
              '<link>' + ARTICLE + '</link><pubDate>Mon, 23 Nov 2026 00:00:00 +0000</pubDate>'
              '</item></channel></rss>').encode(),
    }


def fallback_fixtures():
    result = fixtures()
    result[NEWSROOM] = ('<a href="' + ARTICLE + '">이세계아이돌 새 소식</a>').encode()
    result[ARTICLE] = b'<meta property="article:published_time" content="2026-11-23T00:00:00Z"><p>Announcement</p>'
    return result


class Fetch:
    def __init__(self, responses):
        self.responses = {url: list(value) if isinstance(value, list) else [value]
                          for url, value in responses.items()}
        self.calls = []

    def __call__(self, url):
        self.calls.append(url)
        remaining = self.responses[url]
        value = remaining.pop(0) if len(remaining) > 1 else remaining[0]
        if isinstance(value, Exception):
            raise value
        return value


class ParableRetry(unittest.TestCase):
    def assert_failure(self, responses, code, stage, count=0, calls=None):
        fetch = Fetch(responses)
        with patch.object(feed.time, 'sleep') as sleep, self.assertRaises(feed.ParableSourceError) as caught:
            feed.parable(fetch, NOW)
        self.assertEqual(caught.exception.code, code)
        self.assertEqual(caught.exception.stage, stage)
        self.assertEqual(caught.exception.retry_count, count)
        self.assertEqual(sleep.call_count, count)
        self.assertNotIn(SECRET, str(caught.exception))
        if calls is not None:
            self.assertEqual(fetch.calls, calls)
        return fetch

    def test_transient_newsroom_retries_exact_failed_get_and_reads_new_data(self):
        responses = fixtures()
        responses[NEWSROOM] = [feed.HTTPFeedError(503), responses[NEWSROOM]]
        fetch = Fetch(responses)
        with patch.object(feed.time, 'sleep') as sleep:
            news, events = feed.parable(fetch, NOW)
        self.assertEqual(fetch.calls, [ROBOTS, NEWSROOM, NEWSROOM, RSS])
        sleep.assert_called_once_with(feed.PARABLE_RETRY_DELAY)
        self.assertEqual(len(news), 1)
        self.assertEqual(news[0]['sourceUrl'], ARTICLE)
        self.assertEqual(news[0]['checkedAt'], NOW)
        self.assertEqual(events[0]['date'], '2026-11-25')

    def test_one_shared_retry_budget_for_all_source_stages(self):
        responses = fixtures()
        responses[ROBOTS] = [feed.HTTPFeedError(502), responses[ROBOTS]]
        responses[RSS] = [feed.HTTPFeedError(503), responses[RSS]]
        self.assert_failure(responses, 'http_503', 'feed', 1,
                            [ROBOTS, ROBOTS, NEWSROOM, RSS])

    def test_exhausted_transient_retries_once_at_every_read_stage(self):
        for stage, url, initial in (
                ('robots', ROBOTS, []), ('newsroom', NEWSROOM, [ROBOTS]),
                ('feed', RSS, [ROBOTS, NEWSROOM]), ('article', ARTICLE, [ROBOTS, NEWSROOM])):
            with self.subTest(stage=stage):
                responses = fallback_fixtures() if stage == 'article' else fixtures()
                responses[url] = feed.HTTPFeedError(503)
                self.assert_failure(responses, 'http_503', stage, 1, initial + [url, url])

    def test_only_selected_http_statuses_retry(self):
        for status in (500, 502, 503, 504):
            with self.subTest(status=status):
                responses = fixtures()
                responses[RSS] = feed.HTTPFeedError(status)
                self.assert_failure(responses, 'http_' + str(status), 'feed', 1,
                                    [ROBOTS, NEWSROOM, RSS, RSS])
        for status in (301, 302, 400, 401, 403, 404, 408, 429, 501, 505):
            with self.subTest(status=status):
                responses = fixtures()
                responses[RSS] = feed.HTTPFeedError(status)
                self.assert_failure(responses, 'http_' + str(status), 'feed', 0,
                                    [ROBOTS, NEWSROOM, RSS])

    def test_transient_network_types_retry_without_logging_messages(self):
        for error, code in ((TimeoutError(SECRET), 'request_timeout'),
                            (URLError(TimeoutError(SECRET)), 'request_timeout'),
                            (ConnectionResetError(SECRET), 'connection_reset'),
                            (URLError(ConnectionAbortedError(SECRET)), 'connection_aborted')):
            with self.subTest(code=code):
                responses = fixtures()
                responses[RSS] = error
                self.assert_failure(responses, code, 'feed', 1, [ROBOTS, NEWSROOM, RSS, RSS])

    def test_unclassified_tls_dns_and_text_errors_do_not_retry(self):
        for error, code in ((ssl.SSLError(SECRET), 'tls_error'),
                            (URLError(ssl.SSLCertVerificationError(SECRET)), 'tls_error'),
                            (socket.gaierror(SECRET), 'dns_error'),
                            (URLError(socket.gaierror(SECRET)), 'dns_error'),
                            (ConnectionRefusedError(SECRET), 'connection_refused'),
                            (URLError(SECRET), 'network_error'),
                            (ValueError(SECRET), 'upstream_unavailable'),
                            (feed.FeedError(SECRET), 'upstream_unavailable'),
                            (feed.FeedError('http_503'), 'http_503')):
            with self.subTest(error=type(error).__name__, code=code):
                responses = fixtures()
                responses[RSS] = error
                self.assert_failure(responses, code, 'feed', 0, [ROBOTS, NEWSROOM, RSS])

    def test_xml_and_policy_failures_never_retry(self):
        for response, code in ((b'<rss><broken>', 'feed_xml_invalid'),
                                (b'<!DOCTYPE rss><rss/>', 'unsafe_xml'),
                                (b'<feed/>', 'feed_schema_changed'),
                                (b'<rss><channel/></rss>', 'no_matching_items'),
                                (feed.FeedError('response_too_large'), 'response_too_large')):
            with self.subTest(code=code):
                responses = fixtures()
                responses[RSS] = response
                self.assert_failure(responses, code, 'feed', 0, [ROBOTS, NEWSROOM, RSS])
        responses = fixtures()
        responses[ROBOTS] = b'User-agent: *\nDisallow: /'
        self.assert_failure(responses, 'robots_disallowed', 'newsroom', 0, [ROBOTS])

    def test_html_fallback_reads_public_article_with_same_retry_budget(self):
        responses = fallback_fixtures()
        responses[ARTICLE] = [URLError(TimeoutError(SECRET)), responses[ARTICLE]]
        fetch = Fetch(responses)
        with patch.object(feed.time, 'sleep') as sleep:
            news, events = feed.parable(fetch, NOW)
        self.assertEqual(fetch.calls, [ROBOTS, NEWSROOM, ARTICLE, ARTICLE])
        sleep.assert_called_once()
        self.assertEqual(news[0]['sourceUrl'], ARTICLE)
        self.assertEqual(news[0]['checkedAt'], NOW)
        self.assertEqual(events, [])

    def test_http_reader_retains_only_safe_typed_status(self):
        for status in (302, 403, 503):
            with self.subTest(status=status):
                response = HTTPError(RSS + '?token=never-log', status, SECRET,
                                     {'X-Secret': SECRET}, io.BytesIO(SECRET.encode()))
                with patch.object(feed, 'build_opener') as opener:
                    opener.return_value.open.side_effect = response
                    with self.assertRaises(feed.HTTPFeedError) as caught:
                        feed.request(RSS)
                    self.assertEqual(caught.exception.status, status)
                    self.assertEqual(str(caught.exception), 'http_' + str(status))
                    self.assertNotIn(SECRET, repr(caught.exception.__dict__))
                    self.assertEqual(opener.return_value.open.call_args.kwargs['timeout'], 20)
                    self.assertTrue(any(arg is feed.NoRedirect for arg in opener.call_args.args))


class ParableFailureEvidence(unittest.TestCase):
    def collected_failure(self):
        previous = seed()
        previous_source = next(s for s in previous['sources'] if s['id'] == 'parable-web')
        previous_source.update(state='ok', lastSuccessAt=OLD)
        prior_row = feed.public_item('parable-web', ARTICLE, '이세계아이돌 이전 확인 소식', OLD, OLD)
        previous['news'].append(prior_row)
        responses = fixtures()
        responses[RSS] = HTTPError(RSS + '?token=never-log', 503, SECRET, {}, None)
        fetch = Fetch(responses)
        with patch.object(feed.time, 'sleep'):
            value = feed.collect(previous=previous, fetch=fetch, now=NOW)
        return value, prior_row

    def test_exhaustion_retains_old_observation_and_exact_safe_failure(self):
        value, prior_row = self.collected_failure()
        source = next(s for s in value['sources'] if s['id'] == 'parable-web')
        self.assertEqual(source['state'], 'error')
        self.assertEqual(source['lastAttemptAt'], NOW)
        self.assertEqual(source['lastSuccessAt'], OLD)
        self.assertEqual(next(r for r in value['news'] if r['sourceUrl'] == ARTICLE), prior_row)
        self.assertEqual(feed.source_failure_diagnostics(source),
                         {'errorCode': 'http_503', 'stage': 'feed', 'retryCount': 1})
        self.assertNotIn(SECRET, json.dumps(value))
        self.assertNotIn('token=never-log', json.dumps(value))

    def test_later_real_read_recovers_freshness_and_clears_old_error(self):
        previous, _ = self.collected_failure()
        responses = fixtures()
        responses[RSS] = [feed.HTTPFeedError(503), responses[RSS]]
        with patch.object(feed.time, 'sleep'):
            value = feed.collect(previous=previous, fetch=Fetch(responses), now=NOW)
        source = next(s for s in value['sources'] if s['id'] == 'parable-web')
        self.assertEqual(source['state'], 'ok')
        self.assertEqual(source['lastSuccessAt'], NOW)
        self.assertEqual(next(r for r in value['news'] if r['sourceUrl'] == ARTICLE)['checkedAt'], NOW)
        self.assertNotIn('errorCode', source)
        self.assertNotIn('errorStage', source)
        self.assertEqual(feed.source_failure_diagnostics(source), {})

    def test_successful_publication_still_fails_health_with_source_evidence(self):
        value, _ = self.collected_failure()
        # Isolate the observed Parable failure without changing production assessment rules.
        by_id = {s['id']: s for s in value['sources']}
        for sid in health.REQUIRED:
            if sid != 'parable-web':
                by_id[sid].update(state='ok', lastSuccessAt=NOW, coverage={'complete': True})
        remote = FeedRemote()
        report = publisher.publish(remote, lambda **kwargs: value)
        self.assertEqual(report['status'], 'published')
        self.assertTrue(report['verifiedReadback'])
        self.assertTrue(report['protectedFilesUnchanged'])
        self.assertFalse(report['accountStoreReadOrWritten'])
        result = health.publication_result(report)
        self.assertFalse(result['verified'])
        self.assertEqual(result['collectionHealth']['incompleteSources'], ['parable-web'])
        state = result['collectionHealth']['sources']['parable-web']
        self.assertEqual(state['state'], 'partial')
        self.assertEqual(state['ageSeconds'], 7174)
        self.assertEqual(state['lastSuccessAt'], OLD)
        self.assertEqual(state['reasons'], ['not_refreshed'])
        self.assertEqual(state['failure'], {'errorCode': 'http_503', 'stage': 'feed', 'retryCount': 1})
        stored = json.loads(remote.files[publisher.path('current.json')])
        self.assertEqual(stored['collectionHealth'], report['collectionHealth'])
        self.assertNotIn('token=never-log', json.dumps(report))
        self.assertNotIn(SECRET, json.dumps(report))
        self.assertTrue(all(path.startswith(publisher.FOLDER + '/') for path in remote.writes))
        self.assertNotIn(publisher.path('.lock'), remote.files)

    def test_diagnostic_selection_rejects_untrusted_fields_and_success_stale_errors(self):
        source = {'id': 'parable-web', 'state': 'error', 'errorCode': 'http_503',
                  'errorStage': 'feed', 'retryCount': 1, 'reason': SECRET, 'url': SECRET}
        self.assertEqual(feed.source_failure_diagnostics(source),
                         {'errorCode': 'http_503', 'stage': 'feed', 'retryCount': 1})
        for code in (SECRET, 'http_503 ' + SECRET, ['http_503'], None):
            self.assertEqual(feed.source_failure_diagnostics({**source, 'errorCode': code}), {})
        for stage in (SECRET, ['feed'], None):
            self.assertNotIn('stage', feed.source_failure_diagnostics({**source, 'errorStage': stage}))
        for count in (True, -1, 2, SECRET):
            self.assertNotIn('retryCount', feed.source_failure_diagnostics({**source, 'retryCount': count}))
        self.assertEqual(feed.source_failure_diagnostics({**source, 'state': 'ok'}), {})
        self.assertEqual(feed.source_failure_diagnostics({**source, 'id': 'berriz-notice'}), {})

    def test_uncaught_typed_failure_reports_source_stage_without_raw_reason(self):
        report = publisher.failure_report(feed.ParableSourceError('feed', 'feed_xml_invalid'), 'source_collection')
        self.assertEqual(report['stage'], 'source_collection')
        self.assertEqual(report['sourceStage'], 'feed')
        self.assertEqual(report['sourceId'], 'parable-web')
        self.assertEqual(report['errorCode'], 'feed_xml_invalid')
        self.assertNotIn('reason', report)
        result = health.publication_result(report)
        self.assertFalse(result['verified'])
        self.assertEqual(result['collectionHealth']['state'], 'unknown')
        self.assertEqual(result['publicationFailure']['sourceStage'], 'feed')


if __name__ == '__main__':
    unittest.main()
