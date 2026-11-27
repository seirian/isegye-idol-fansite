#!/usr/bin/env python3
"""Bind an explicit recovery-job rerun to its immediately previous audit.

Initial runs only audit. Rerunning the same successful audit job is the explicit
recovery request documented in the workflow. No dispatch, credentials, SFTP,
remote mutation or untrusted extraction occurs here. Apply still repeats all
live safety checks inside the shared writer queue.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import re
import stat
import zipfile

from batch_watchdog import api

REPO = 'seirian/isegye-idol-fansite'
WORKFLOW = '.github/workflows/production-lock-recovery.yml'
PREFIX = 'production-lock-audit'
REPORT = 'production-lock-audit.json'
MAX_ARCHIVE = 300_000


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode()


def identity(env):
    require(env.get('GITHUB_REPOSITORY') == REPO and env.get('GITHUB_REF') == 'refs/heads/main'
            and env.get('GITHUB_JOB') == 'recover', 'Exact main recovery job required')
    for key, pattern in (('GITHUB_RUN_ID', '[1-9][0-9]*'),
                         ('GITHUB_RUN_ATTEMPT', '[1-9][0-9]*'),
                         ('GITHUB_SHA', '[0-9a-f]{40}')):
        require(re.fullmatch(pattern, env.get(key, '')) is not None, 'Invalid recovery identity')
    return int(env['GITHUB_RUN_ID']), int(env['GITHUB_RUN_ATTEMPT']), env['GITHUB_SHA']


def same_run(run, run_id, attempt, sha, status):
    return (isinstance(run, dict) and run.get('id') == run_id and
            run.get('run_attempt') == attempt and run.get('head_sha') == sha and
            run.get('head_branch') == 'main' and run.get('path') == WORKFLOW and
            run.get('repository', {}).get('full_name') == REPO and
            run.get('head_repository', {}).get('full_name') == REPO and
            run.get('status') == status)


def decode_audit(raw, artifact, run_id, previous_attempt, sha, at):
    require(isinstance(raw, bytes) and len(raw) == artifact.get('size_in_bytes') and
            0 < len(raw) <= MAX_ARCHIVE and artifact.get('digest') ==
            'sha256:' + hashlib.sha256(raw).hexdigest(), 'Audit archive checksum mismatch')
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        entries = archive.infolist()
        require(len(entries) == 1 and entries[0].filename == REPORT and
                0 < entries[0].file_size <= 100_000 and not entries[0].is_dir() and
                not stat.S_ISLNK(entries[0].external_attr >> 16), 'Unexpected audit archive member')
        report = json.loads(archive.read(entries[0]))
    require(isinstance(report, dict) and report.get('schemaVersion') == 1 and
            report.get('runId') == run_id and report.get('runAttempt') == previous_attempt and
            report.get('commit') == sha and report.get('mode') == 'audit' and
            report.get('remoteWrites') is False and report.get('accountStoreAccessed') is False,
            'Audit producer identity or read-only status differs')
    stamp = datetime.fromisoformat(report['checkedAt'].replace('Z', '+00:00'))
    require(stamp.tzinfo is not None and at-timedelta(hours=24) <= stamp <= at+timedelta(minutes=2),
            'Reviewed audit is stale or future dated')
    stable = report.get('evidence')
    require(isinstance(stable, dict) and stable.get('repository') == REPO and
            stable.get('main') == sha and stable.get('activeWriterInspectionComplete') is True and
            report.get('diagnosticSha256') == hashlib.sha256(encoded(stable)).hexdigest(),
            'Audit diagnostic digest or source mismatch')
    return report


def select(env, getter=api, now=None):
    run_id, attempt, sha = identity(env)
    if attempt == 1 or env.get('ALLOW_RECOVERY_ON_RERUN') != 'true':
        return {'mode': 'audit', 'reason': 'initial_or_read_only_request'}, None
    require(same_run(getter(f'actions/runs/{run_id}'), run_id, attempt, sha, 'in_progress'),
            'Current recovery run identity differs')
    previous = getter(f'actions/runs/{run_id}/attempts/{attempt-1}')
    require(same_run(previous, run_id, attempt-1, sha, 'completed'),
            'Previous recovery attempt identity differs')
    if previous.get('conclusion') != 'success':
        return {'mode': 'audit', 'reason': 'previous_audit_not_successful'}, None
    name = f'{PREFIX}-{run_id}-{attempt-1}'
    found, seen = [], set()
    for page in range(1, 4):
        listing = getter(f'actions/runs/{run_id}/artifacts?per_page=100&page={page}')
        entries, total = listing.get('artifacts'), listing.get('total_count')
        require(isinstance(entries, list) and len(entries) <= 100 and type(total) is int
                and 0 <= total <= 300, 'Incomplete audit artifact listing')
        for artifact in entries:
            require(isinstance(artifact, dict) and type(artifact.get('id')) is int and
                    artifact['id'] > 0 and artifact['id'] not in seen, 'Invalid audit artifact identity')
            seen.add(artifact['id'])
            if artifact.get('name') == name:
                found.append(artifact)
        if len(entries) < 100:
            require(total == len(seen), 'Audit artifact listing truncated')
            break
    else:
        raise ValueError('Audit artifact pagination budget exhausted')
    require(len(found) == 1, 'Exactly one immediately previous audit required')
    artifact = found[0]
    provenance = artifact.get('workflow_run', {})
    require(artifact.get('expired') is False and provenance.get('id') == run_id and
            provenance.get('head_sha') == sha and provenance.get('head_branch') == 'main' and
            type(artifact.get('size_in_bytes')) is int and 0 < artifact['size_in_bytes'] <= MAX_ARCHIVE,
            'Audit artifact provenance differs')
    raw = getter(f"actions/artifacts/{artifact['id']}/zip", binary=True)
    audit = decode_audit(raw, artifact, run_id, attempt-1, sha, now or datetime.now(timezone.utc))
    if audit.get('status') == 'clear':
        return {'mode': 'audit', 'reason': 'previous_lock_already_clear'}, None
    require(audit.get('status') == 'recovery_candidate', 'Previous audit is not a recovery candidate')
    return {'mode': 'apply', 'reason': 'explicit_rerun_of_verified_audit',
            'auditSha256': audit['diagnosticSha256'], 'auditAttempt': attempt-1}, audit


def main():
    result, audit = select(os.environ)
    if audit:
        Path('reviewed-lock-audit.json').write_bytes(encoded(audit))
    if os.getenv('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'], 'a') as out:
            out.write('mode='+result['mode']+'\naudit-sha256='+result.get('auditSha256', '')+'\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
