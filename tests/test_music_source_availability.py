"""Unavailable backups stay recorded but cannot become playable or hide hard failures."""
import copy
from datetime import datetime, timedelta, timezone
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import check_music_video_sources as audit
import music_source_availability as policy
from music_video_sources import selections, apply_video_sources
from enhance_catalog import load_music
from verify_music_source_availability import verify_bundle


class MusicSourceAvailabilityTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {'MUSIC_SOURCE_AUDIT_REQUIRED': '',
            'GITHUB_REPOSITORY': policy.REPOSITORY, 'GITHUB_SHA': 'a'*40,
            'GITHUB_RUN_ID': '12345', 'GITHUB_RUN_ATTEMPT': '1'}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)
        self.config, self.rows = selections()
        self.at = datetime(2026, 11, 27, 13, 0, tzinfo=timezone.utc)
        self.backup = next(sid for sid, row in self.rows.items() if row['kind'] == 'fan_backup')
        self.official = next(sid for sid, row in self.rows.items() if row['kind'].startswith('official'))
        self.results = [{'songId': sid, **row, 'stage': 'complete', 'ok': True,
            'metadataStatus': 200, 'authorUrl': self.config['channels'][row['channelKey']]['url'],
            'thumbnailWidth': 480, 'thumbnailHeight': 360}
            for sid, row in self.rows.items() if row['videoId']]
        self.base = load_music()

    def replace(self, sid, result):
        self.results = [result if row['songId'] == sid else row for row in self.results]

    def unavailable(self, sid=None):
        sid = sid or self.backup
        with patch.object(audit, 'get', side_effect=HTTPError('https://www.youtube.com/oembed', 404, '', {}, None)):
            result = audit.inspect((sid, self.rows[sid]), self.config)
        self.replace(sid, result)
        return result

    def thumbnail_unavailable(self, sid=None):
        sid = sid or self.backup
        row = self.rows[sid]
        response = json.dumps({'author_url': self.config['channels'][row['channelKey']]['url']}).encode()
        with patch.object(audit, 'get', side_effect=[response, HTTPError('https://i.ytimg.com', 404, '', {}, None)]):
            result = audit.inspect((sid, row), self.config)
        self.replace(sid, result)
        return result

    def candidate(self):
        report = audit.make_report(self.config, self.rows, self.results, True, self.at.isoformat())
        raw = json.dumps(report).encode()
        candidate = policy.availability_candidate(report, raw, self.config, self.rows)
        return report, raw, candidate

    def validate(self, report, raw, candidate, **kwargs):
        return policy.validate_candidate(report, raw, candidate, self.config, self.rows,
            expected_context=policy.context(), now=kwargs.pop('now', self.at), **kwargs)

    def test_fixed_backup_404_is_partial_not_success(self):
        result = self.unavailable()
        report, raw, candidate = self.candidate()
        self.validate(report, raw, candidate)
        self.assertFalse(result['ok'])
        self.assertEqual((report['state'], report['passed'], report['failed'], report['unavailable']),
            ('partial', 150, 1, 1))
        self.assertEqual(len(report['unresolved']), 3)
        self.assertFalse(report['fullPlaybackVerified'])
        self.assertTrue(candidate['deploymentAllowed'])

    def test_observed_three_channel_outage_keeps_79_records_and_72_links(self):
        # Incident-shaped fixture, not a claim of fresh network observations.
        ids = [sid for sid, row in self.rows.items() if row['channelKey'] in {'c3', 'c6', 'c16'}]
        self.assertEqual(len(ids), 79)
        for sid in ids:
            self.unavailable(sid)
        report, raw, candidate = self.candidate()
        self.validate(report, raw, candidate)
        self.assertEqual((report['passed'], report['unavailable'], report['blockingFailures']), (72, 79, 0))
        self.assertEqual({key: report['sourceStates'][key]['unavailable'] for key in ('c3', 'c6', 'c16')},
                         {'c3': 44, 'c6': 16, 'c16': 19})
        with patch.object(policy, 'load_candidate', return_value=candidate):
            music = apply_video_sources(self.base)
        self.assertEqual(len(music['songs']), 154)
        self.assertEqual(sum(bool(song.get('videoId')) for song in music['songs']), 72)
        self.assertEqual(sum(song['videoSource'].get('availability') == 'unavailable' for song in music['songs']), 79)
        self.assertEqual(sum(song['videoSource']['kind'] == 'unavailable' for song in music['songs']), 3)

    def test_default_strict_mode_still_blocks_backup_404(self):
        self.unavailable()
        report = audit.make_report(self.config, self.rows, self.results)
        self.assertFalse(report['deploymentAllowed'])
        self.assertEqual(report['blockingFailures'], 1)

    def test_official_404_still_blocks_publication(self):
        self.unavailable(self.official)
        report, raw, candidate = self.candidate()
        self.assertEqual(candidate['blocked'], 1)
        with self.assertRaisesRegex(ValueError, 'Incomplete'):
            self.validate(report, raw, candidate)

    def test_changed_uploader_is_hard_failure_even_for_backup(self):
        response = json.dumps({'author_url': 'https://www.youtube.com/@wrong-uploader'}).encode()
        with patch.object(audit, 'get', return_value=response) as get:
            result = audit.inspect((self.backup, self.rows[self.backup]), self.config)
        self.assertEqual(get.call_count, 1)
        self.assertEqual(result['reasonCode'], 'uploader_identity_changed')
        self.replace(self.backup, result)
        self.assertFalse(self.candidate()[2]['deploymentAllowed'])

    def test_verified_backup_thumbnail_404_is_quarantined_with_its_actual_reason(self):
        result = self.thumbnail_unavailable()
        self.assertEqual(result['reasonCode'], 'thumbnail_http_404')
        self.assertEqual(result['metadataStatus'], 200)
        report, raw, candidate = self.candidate()
        self.validate(report, raw, candidate)
        self.assertEqual((report['state'], report['unavailable'], report['blockingFailures']), ('partial', 1, 0))
        quarantined = candidate['unavailableSelections'][0]
        self.assertEqual((quarantined['stage'], quarantined['reasonCode']), ('thumbnail', 'thumbnail_http_404'))
        with patch.object(policy, 'load_candidate', return_value=candidate):
            song = next(song for song in apply_video_sources(self.base)['songs'] if song['id'] == self.backup)
        self.assertNotIn('videoId', song)
        self.assertNotIn('url', song)
        self.assertEqual(song['videoSource']['availabilityReason'], 'thumbnail_http_404')
        self.assertEqual(song['videoSource']['availabilityStage'], 'thumbnail')
        self.assertEqual(song['videoSource']['kind'], 'fan_backup')

    def test_mixed_metadata_and_thumbnail_incident_keeps_both_failure_reasons(self):
        ids = [sid for sid, row in self.rows.items() if row['channelKey'] in {'c3', 'c6', 'c16'}]
        for sid in ids:
            self.unavailable(sid)
        self.thumbnail_unavailable('cover-eEPmx_JZCkY')
        report, raw, candidate = self.candidate()
        self.validate(report, raw, candidate)
        self.assertEqual((report['passed'], report['failed'], report['unavailable'], report['blockingFailures']), (72, 79, 79, 0))
        self.assertEqual(sum(r['reasonCode'] == 'metadata_http_404' for r in candidate['unavailableSelections']), 78)
        self.assertEqual(sum(r['reasonCode'] == 'thumbnail_http_404' for r in candidate['unavailableSelections']), 1)

    def test_default_strict_mode_still_blocks_thumbnail_404(self):
        self.thumbnail_unavailable()
        report = audit.make_report(self.config, self.rows, self.results)
        self.assertEqual(report['blockingFailures'], 1)
        self.assertFalse(report['deploymentAllowed'])

    def test_thumbnail_404_cannot_hide_unverified_or_changed_uploader(self):
        result = self.thumbnail_unavailable()
        for author, status in [('https://www.youtube.com/@wrong-uploader', 200), (None, 200),
                               (result['authorUrl'], 404), (result['authorUrl'], None)]:
            with self.subTest(author=author, status=status):
                self.replace(self.backup, {**result, 'authorUrl': author, 'metadataStatus': status})
                candidate = self.candidate()[2]
                self.assertEqual(candidate['unavailable'], 0)
                self.assertFalse(candidate['deploymentAllowed'])

    def test_official_thumbnail_404_remains_hard_failure(self):
        self.thumbnail_unavailable(self.official)
        self.assertFalse(self.candidate()[2]['deploymentAllowed'])

    def test_new_selection_with_thumbnail_404_requires_review(self):
        self.rows[self.backup]['videoId'] = 'NEWVIDEO123'
        self.thumbnail_unavailable()
        with self.assertRaisesRegex(ValueError, 'Unreviewed'):
            self.candidate()

    def test_thumbnail_errors_other_than_404_remain_hard_failures(self):
        row = self.rows[self.backup]
        response = json.dumps({'author_url': self.config['channels'][row['channelKey']]['url']}).encode()
        errors = [URLError('timed out')] + [HTTPError('url', code, '', {}, None) for code in (401, 403, 429, 500, 503)]
        for error in errors:
            with self.subTest(error=str(error)), patch.object(audit, 'get', side_effect=[response, error]):
                self.replace(self.backup, audit.inspect((self.backup, row), self.config))
                self.assertEqual(self.candidate()[2]['unavailable'], 0)
                self.assertFalse(self.candidate()[2]['deploymentAllowed'])

    def test_timeout_forbidden_and_server_error_stay_unknown_or_blocked(self):
        for error in (URLError('timed out'), HTTPError('url', 403, '', {}, None), HTTPError('url', 503, '', {}, None)):
            with self.subTest(error=type(error).__name__), patch.object(audit, 'get', side_effect=error):
                result = audit.inspect((self.backup, self.rows[self.backup]), self.config)
                self.replace(self.backup, result)
                candidate = self.candidate()[2]
                self.assertEqual(candidate['unavailable'], 0)
                self.assertFalse(candidate['deploymentAllowed'])

    def test_new_or_modified_selection_cannot_claim_reviewed_status(self):
        self.rows[self.backup]['videoId'] = 'NEWVIDEO123'
        for result in self.results:
            if result['songId'] == self.backup:
                result['videoId'] = 'NEWVIDEO123'
        with self.assertRaisesRegex(ValueError, 'Unreviewed'):
            self.candidate()

    def test_changed_channel_config_cannot_use_exception(self):
        self.config['channels']['c3']['url'] = 'https://www.youtube.com/@another'
        with self.assertRaisesRegex(ValueError, 'Unreviewed'):
            self.candidate()

    def test_missing_duplicate_and_wrong_selected_id_fail(self):
        original = copy.deepcopy(self.results)
        for values in (original[:-1], original[:-1]+[original[0]],
                       [{**original[0], 'videoId': 'OTHERID1234'}, *original[1:]]):
            with self.subTest(values=len(values)):
                self.results = values
                with self.assertRaises(ValueError):
                    self.candidate()

    def test_stale_future_wrong_run_attempt_and_commit_rejected(self):
        self.unavailable()
        report, raw, candidate = self.candidate()
        for now in (self.at+timedelta(hours=24, seconds=1), self.at-timedelta(minutes=3)):
            with self.subTest(now=now), self.assertRaisesRegex(ValueError, 'stale|future'):
                self.validate(report, raw, candidate, now=now)
        for key, value in [('runId', '999'), ('runAttempt', '2'), ('commit', 'b'*40)]:
            altered = copy.deepcopy(report)
            altered['provenance'][key] = value
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'mismatch'):
                self.validate(altered, raw, candidate)

    def test_archive_digest_and_partial_state_cannot_be_relabelled(self):
        self.unavailable()
        report, raw, candidate = self.candidate()
        with self.assertRaisesRegex(ValueError, 'digest'):
            self.validate(report, raw+b' ', candidate)
        report['state'] = 'complete'
        raw = json.dumps(report).encode()
        candidate = policy.availability_candidate(report, raw, self.config, self.rows)
        with self.assertRaisesRegex(ValueError, 'inconsistent'):
            self.validate(report, raw, candidate)

    def test_unknown_is_never_available_despite_success_flag(self):
        self.results[0]['stage'] = 'unknown'
        self.assertFalse(self.candidate()[2]['deploymentAllowed'])

    def test_failure_counts_and_playback_claim_cannot_be_hidden(self):
        self.unavailable()
        original, _, _ = self.candidate()
        for key, value in [('failed', 0), ('fullPlaybackVerified', True)]:
            report = copy.deepcopy(original)
            report[key] = value
            raw = json.dumps(report).encode()
            candidate = policy.availability_candidate(report, raw, self.config, self.rows)
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'inconsistent'):
                self.validate(report, raw, candidate)

    def test_quarantine_keeps_song_history_and_removes_only_playback(self):
        self.unavailable()
        report, raw, candidate = self.candidate()
        self.validate(report, raw, candidate)
        with patch.object(policy, 'load_candidate', return_value=candidate):
            result = apply_video_sources(self.base)
        before = next(song for song in self.base['songs'] if song['id'] == self.backup)
        after = next(song for song in result['songs'] if song['id'] == self.backup)
        self.assertNotIn('videoId', after)
        self.assertNotIn('url', after)
        self.assertEqual(after['videoSource']['reviewedVideoId'], before['videoId'])
        self.assertEqual(after['videoSource']['kind'], 'fan_backup')
        for key in set(before)-{'videoId', 'url', 'videoSource'}:
            self.assertEqual(before[key], after[key], key)
        self.assertEqual(result['videoAudit']['linked'], 150)
        self.assertEqual(result['videoAudit']['selected'], 151)
        self.assertEqual(len(result['songs']), len(self.base['songs']))

    def test_existing_collectors_do_not_implicitly_consume_candidate_files(self):
        with patch.object(Path, 'read_bytes', side_effect=AssertionError('unexpected candidate read')):
            self.assertIsNone(policy.load_candidate(self.config, self.rows))

    def test_origin_attempt_is_only_a_positive_prior_same_run_attempt(self):
        with patch.dict(os.environ, GITHUB_RUN_ATTEMPT='3', MUSIC_SOURCE_AUDIT_ORIGIN_ATTEMPT='1'):
            self.assertEqual(policy.publication_context()['runAttempt'], '1')
            self.assertEqual(policy.context()['runAttempt'], '3')
        for origin in ('0', '-1', '4', 'unknown'):
            with patch.dict(os.environ, GITHUB_RUN_ATTEMPT='3', MUSIC_SOURCE_AUDIT_ORIGIN_ATTEMPT=origin):
                with self.assertRaises(ValueError):
                    policy.publication_context()

    def test_final_bundle_and_runtime_baseline_both_keep_quarantine(self):
        self.unavailable()
        report, raw, candidate = self.candidate()
        with patch.object(policy, 'load_candidate', return_value=candidate):
            music = apply_video_sources(self.base)
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp)
            (out/'src').mkdir()
            (out/'build-info.json').write_text(json.dumps({'commit': 'a'*40, 'musicVideoAudit': music['videoAudit']}))
            (out/'src/data.js').write_text('const REVIEW_DATA='+json.dumps({'songs': music['songs']})+';\n')
            legacy = {'music': copy.deepcopy(music)}
            (out/'src/production-ui.js').write_text('const CATALOG='+json.dumps(legacy)+';\n')
            (out/'src/app.js').write_text('function sourceAvailabilityAction(){};sourceAvailabilityNotice(s);')
            with patch('verify_music_source_availability.load_candidate', return_value=candidate):
                self.assertTrue(verify_bundle(out)['verified'])
                song = next(s for s in legacy['music']['songs'] if s['id'] == self.backup)
                song['videoSource']['availabilityReason'] = 'thumbnail_http_404'
                (out/'src/production-ui.js').write_text('const CATALOG='+json.dumps(legacy)+';\n')
                with self.assertRaisesRegex(ValueError, 'failure stage or reason'):
                    verify_bundle(out)
                song['videoSource']['availabilityReason'] = 'metadata_http_404'
                song['videoId'] = self.rows[self.backup]['videoId']
                (out/'src/production-ui.js').write_text('const CATALOG='+json.dumps(legacy)+';\n')
                with self.assertRaisesRegex(ValueError, 'reintroduced.*runtime'):
                    verify_bundle(out)


if __name__ == '__main__':
    unittest.main()
