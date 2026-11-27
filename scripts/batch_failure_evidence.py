"""Emit fixed, non-secret failure evidence; never retries or changes production.

Recovery can suppress a repeated deterministic failure only after the exact
run/attempt artifact and these relevant code/input digests have been checked.
Unrelated catalog commits cannot silently reopen the same deployment failure.
"""
from datetime import datetime, timezone
from pathlib import Path
import argparse
import hashlib
import json
import os
import re

ROOT = Path(__file__).resolve().parents[1]
REPO = 'seirian/isegye-idol-fansite'
WORKFLOW = 'production.yml'
REASONS = {
    'production_directory_conflict': ('permanent', 'deploy'),
    'production_lock_busy': ('blocked', 'deploy'),
    'production_lock_recovery_busy': ('blocked', 'deploy'),
    'production_lock_owner_changed': ('permanent', 'deploy'),
    'production_lock_release_failed': ('permanent', 'deploy'),
    'production_recovery_required': ('permanent', 'deploy'),
    'production_lock_request_unknown': ('unknown', 'deploy'),
    'music_source_identity_changed': ('permanent', 'prepare'),
    'music_source_access_denied': ('permanent', 'prepare'),
    'required_music_source_unavailable': ('permanent', 'prepare'),
    'music_source_transport_failed': ('transient', 'prepare'),
    'music_source_inspection_unknown': ('unknown', 'prepare'),
}
DEPLOY_CODE = ('scripts/inour_sftp.py', 'scripts/production_lock.py',
               'scripts/deploy_google_access.py', 'scripts/batch_failure_evidence.py', '.github/workflows/production.yml')
PREPARE_CODE = ('scripts/check_music_video_sources.py', 'scripts/music_source_availability.py',
                'scripts/music_video_sources.py', 'scripts/batch_failure_evidence.py', '.github/workflows/production.yml')
MUSIC_INPUT = ('catalog/video-sources.json', 'catalog/video-sources.tsv')


def material_digest(root, paths):
    digest = hashlib.sha256()
    for name in sorted(paths):
        path = root/name
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 4_000_000:
            raise ValueError('Failure identity material unavailable')
        raw = path.read_bytes()
        digest.update(name.encode()+b'\0'+len(raw).to_bytes(8, 'big')+raw)
    return digest.hexdigest()


def identities(reason, root=ROOT):
    _, stage = REASONS[reason]
    return {'codeIdentity': material_digest(root, DEPLOY_CODE if stage == 'deploy' else PREPARE_CODE),
            'inputIdentity': material_digest(root, () if stage == 'deploy' else MUSIC_INPUT)}


def read_document(root, name):
    path = root/name
    if not path.exists():
        return None
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 2_000_000:
        raise ValueError('Unsafe failure source')
    value = json.loads(path.read_bytes())
    if not isinstance(value, dict):
        raise ValueError('Invalid failure source')
    return value


def classify(root, stage):
    if stage == 'deploy':
        report = read_document(root, 'auth-deployment.json')
        if not report:
            return None
        lock = report.get('productionLock') or {}
        if report.get('manualRecoveryRequired') is True:
            return 'production_recovery_required'
        if lock.get('state') == 'acquire_unknown':
            return 'production_lock_request_unknown'
        if lock.get('state') == 'cleanup_failed':
            return 'production_lock_release_failed'
        if report.get('status') == 'deployed_and_verified' and report.get('lockRemoved') is True:
            return None
        return {
            'Refusing existing directory': 'production_directory_conflict',
            'Production lock busy; existing owner preserved': 'production_lock_busy',
            'Production deployment in progress': 'production_lock_busy',
            'Production lock recovery in progress; writer stopped': 'production_lock_recovery_busy',
            'Production lock owner changed; cleanup refused': 'production_lock_owner_changed',
        }.get(report.get('reason'))
    report = read_document(root, 'test-results/music-sources/source-audit.json')
    if not report or report.get('deploymentAllowed') is True:
        return None
    failed = [r for r in report.get('results', []) if isinstance(r, dict) and r.get('ok') is False
              and r.get('availability') != 'unavailable']
    if not failed:
        return None
    codes = {r.get('reasonCode') for r in failed}
    if 'uploader_identity_changed' in codes:
        return 'music_source_identity_changed'
    if any(r.get('metadataStatus') in (401, 403) for r in failed):
        return 'music_source_access_denied'
    if all(r.get('stage') == 'metadata' and r.get('metadataStatus') == 404 for r in failed):
        return 'required_music_source_unavailable'
    if all(r.get('metadataStatus') in (429, 500, 502, 503, 504) for r in failed):
        return 'music_source_transport_failed'
    return 'music_source_inspection_unknown'


def build(root, stage, env, at=None):
    if (env.get('GITHUB_REPOSITORY') != REPO or env.get('GITHUB_REF') != 'refs/heads/main'
            or not re.fullmatch(r'[0-9a-f]{40}', env.get('GITHUB_SHA', ''))
            or not re.fullmatch(r'[1-9][0-9]*', env.get('GITHUB_RUN_ID', ''))
            or not re.fullmatch(r'[1-9][0-9]*', env.get('GITHUB_RUN_ATTEMPT', ''))):
        raise ValueError('Verified failure context required')
    reason = classify(root, stage)
    if reason is None:
        return None
    retry, expected_stage = REASONS[reason]
    if stage != expected_stage:
        raise ValueError('Failure stage mismatch')
    return {'schemaVersion': 1, 'kind': 'batch_failure', 'repository': REPO,
            'workflow': WORKFLOW, 'stage': stage, 'commit': env['GITHUB_SHA'],
            'runId': int(env['GITHUB_RUN_ID']), 'runAttempt': int(env['GITHUB_RUN_ATTEMPT']),
            'checkedAt': (at or datetime.now(timezone.utc)).isoformat(),
            'reasonCode': reason, 'retryClass': retry, **identities(reason, root)}


def trusted_failure(value, run, at, root=ROOT):
    from batch_publication_evidence import clock
    reason = value.get('reasonCode')
    if (value.get('schemaVersion') != 1 or value.get('kind') != 'batch_failure'
            or value.get('repository') != REPO or value.get('workflow') != WORKFLOW
            or value.get('commit') != run.get('head_sha') or value.get('runId') != run['id']
            or type(value.get('runId')) is not int or type(value.get('runAttempt')) is not int
            or value.get('runAttempt') != run['run_attempt'] or reason not in REASONS
            or (value.get('retryClass'), value.get('stage')) != REASONS[reason]):
        raise ValueError('Untrusted failure report')
    checked = clock(value['checkedAt'])
    started = clock(run.get('run_started_at') or run['created_at'])
    if not started <= checked <= at:
        raise ValueError('Failure evidence clock mismatch')
    current = identities(reason, root)
    if any(value.get(key) != digest for key, digest in current.items()):
        return None  # Related code or reviewed inputs changed; old block is not current.
    return {key: value[key] for key in ('reasonCode', 'retryClass', 'stage',
                                      'codeIdentity', 'inputIdentity', 'runId', 'runAttempt', 'checkedAt')}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workflow', choices=[WORKFLOW], required=True)
    parser.add_argument('--stage', choices=['prepare', 'deploy'], required=True)
    args = parser.parse_args(argv)
    report = build(ROOT, args.stage, os.environ)
    if report:
        (ROOT/'batch-failure.json').write_text(json.dumps(report, sort_keys=True, indent=2)+'\n')
        print(json.dumps(report, sort_keys=True))
    else:
        print(json.dumps({'state': 'no_classified_failure', 'stage': args.stage}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
