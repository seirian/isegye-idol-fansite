"""Separate official daily publication from reviewed backup-link availability.

Only a full same-run v2 audit/candidate can authorize the narrow backup warning.
Legacy evidence still requires every selected link to pass. No links are edited.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import os

from batch_publication_evidence import clock
from daily_music import CHANNELS
from music_video_sources import selections
from music_source_availability import POLICY, REPOSITORY, validate_candidate

AUDIT = 'test-results/music-sources/source-audit.json'
AVAILABILITY = 'test-results/music-sources/source-availability.json'
ROOT = Path(__file__).resolve().parents[1]


class ArtifactFiles(dict):
    """Parsed JSON plus original audit bytes, kept out of serialized UI data."""
    def __init__(self, run=None):
        super().__init__()
        self.run = run or {}
        self.audit_bytes = None


def audit_result(files, at):
    report = files.get(AUDIT, {})
    result = {'state': 'unverified', 'verified': False, 'available': None,
              'selected': None, 'unavailable': None, 'blocked': None, 'unresolved': None}
    if report.get('policy') == POLICY:
        try:
            run, raw = files.run, files.audit_bytes
            if (not isinstance(raw, bytes) or len(raw) > 2_000_000
                    or type(run.get('id')) is not int or run['id'] <= 0
                    or type(run.get('run_attempt')) is not int or run['run_attempt'] <= 0
                    or run.get('head_branch') != 'main'
                    or run.get('path') != '.github/workflows/music-daily.yml'
                    or run.get('repository', {}).get('full_name') != REPOSITORY
                    or run.get('head_repository', {}).get('full_name') != REPOSITORY):
                return result
            expected = {'repository': REPOSITORY, 'commit': run.get('head_sha'),
                        'runId': str(run['id']), 'runAttempt': str(run['run_attempt'])}
            config, rows = selections()
            candidate = validate_candidate(report, raw, files.get(AVAILABILITY, {}),
                                           config, rows, expected_context=expected, now=at)
            started = run.get('run_started_at') or run.get('created_at')
            if started and clock(report['checkedAt']) < clock(started)-timedelta(minutes=2):
                return result
            return {'state': candidate['state'], 'verified': True, 'policy': POLICY,
                    'checkedAt': candidate['checkedAt'], 'available': candidate['available'],
                    'selected': candidate['selected'], 'unavailable': candidate['unavailable'],
                    'blocked': candidate['blocked'], 'unresolved': len(candidate['unresolved'])}
        except (AttributeError, KeyError, TypeError, ValueError):
            return result
    # No candidate, a changed policy or a short count cannot gain the exception.
    if report.get('policy') not in (None, 'strict-all-selected-v1'):
        return result
    selected, passed = report.get('selected'), report.get('passed')
    if type(selected) is int and selected > 0 and type(passed) is int and passed == selected:
        return {'state': 'complete', 'verified': True, 'policy': 'legacy-strict',
                'available': passed, 'selected': selected, 'unavailable': 0, 'blocked': 0,
                'unresolved': len(report.get('unresolved', []))}
    return result


def music_evidence(files, due, at):
    pub = files.get('music-publication.json', {})
    states = pub.get('sourceStates', {})
    new_policy = files.get(AUDIT, {}).get('policy') == POLICY
    published = (pub.get('status') == 'published' and pub.get('verifiedReadback') is True
                 and isinstance(states, dict) and len(states) == 9
                 and all(value == 'ok' for value in states.values()))
    try:
        generated = clock(pub['generatedAt'])
        published = published and due <= generated <= at+timedelta(minutes=2)
        if new_policy:
            readback = clock(pub['readbackAt'])
            publication_clock_ok = ((pub.get('publicationAction') == 'written'
                                     and generated <= clock(pub['publishedAt']) <= readback)
                                    or (pub.get('publicationAction') == 'unchanged_verified'
                                        and pub.get('publishedAt') is None))
            published = (published and set(states) == set(CHANNELS) and pub.get('evidenceVersion') == 2
                         and publication_clock_ok and generated <= readback <= at+timedelta(minutes=2))
    except (KeyError, TypeError, ValueError):
        published = False
    availability = audit_result(files, at)
    ready = bool(published and availability['verified'])
    return {'officialPublicationVerified': bool(published), 'backupAvailability': availability,
            'recoverySatisfied': ready, 'state': 'healthy' if ready and availability['state']=='complete' else 'attention'}


def main():
    root = ROOT
    if os.getenv('GITHUB_REF') != 'refs/heads/main':
        raise ValueError('Main daily summary required')
    run = {'id': int(os.environ['GITHUB_RUN_ID']), 'run_attempt': int(os.environ['GITHUB_RUN_ATTEMPT']),
           'head_sha': os.environ['GITHUB_SHA'], 'head_branch': 'main',
           'path': '.github/workflows/music-daily.yml',
           'repository': {'full_name': os.environ['GITHUB_REPOSITORY']},
           'head_repository': {'full_name': os.environ['GITHUB_REPOSITORY']}}
    files = ArtifactFiles(run)
    for name in ('music-publication.json', 'music-discovery.json', AUDIT, AVAILABILITY):
        path = root/name
        if path.is_file() and not path.is_symlink() and path.stat().st_size <= 2_000_000:
            raw = path.read_bytes(); files[name] = json.loads(raw)
            if name == AUDIT:
                files.audit_bytes = raw
    at = datetime.now(timezone.utc)
    local = at.astimezone(timezone(timedelta(hours=9)))
    due = local.replace(hour=6, minute=0, second=0, microsecond=0)
    if due > local:
        due -= timedelta(days=1)
    result = music_evidence(files, due, at)
    if os.getenv('AUDIT_OUTCOME') != 'success':
        result.update(recoverySatisfied=False, state='attention')
    pub, backup = files.get('music-publication.json', {}), result['backupAvailability']
    sources = files.get('music-discovery.json', {}).get('sources', {})
    source_states = {key: sources.get(key, {}).get('state', 'unknown') for key in CHANNELS}
    checked = sum(state == 'ok' for state in source_states.values())
    pending = sum(len(source.get('review', [])) for source in sources.values()
                  if isinstance(source, dict) and isinstance(source.get('review', []), list))
    result['officialSourceCoverage'] = {'completeChannels': checked, 'requiredChannels': len(CHANNELS),
                                       'needsReview': pending, 'states': source_states}
    result.update(checkedAt=at.isoformat(), sourceAt=pub.get('sourceAt'), generatedAt=pub.get('generatedAt'),
                  publishedAt=pub.get('publishedAt'), readbackAt=pub.get('readbackAt'))
    summary = (f"Official music publication verified: {result['officialPublicationVerified']}; "
               f"new {pub.get('added', 'unknown')}, total auto {pub.get('totalAuto', 'unknown')}; "
               f"fully checked channels {checked}/{len(CHANNELS)}, needs review {pending}; "
               f"reviewed-link availability {backup['state']}: {backup['available']}/{backup['selected']}, "
               f"unavailable {backup['unavailable']}, unresolved {backup['unresolved']}. "
               "Backup warnings are separate from official collection/publication.")
    print(summary)
    if os.getenv('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as output:
            output.write(summary+'\n')
    if backup['state'] == 'partial':
        print('::warning::Reviewed backup availability remains partial; failed links were not counted as passed.')
    if checked != len(CHANNELS):
        print('::warning::Incomplete official source coverage: '+','.join(key for key, state in source_states.items() if state != 'ok'))
    (root/'music-batch-result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    return int(not result['recoverySatisfied'])


if __name__ == '__main__':
    raise SystemExit(main())
