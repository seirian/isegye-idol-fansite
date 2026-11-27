#!/usr/bin/env python3
"""Read-only lock audit, or explicitly hash-bound recovery inside the writer queue.

This does not deploy, dispatch, cancel a job, read account/session/config data,
or reclaim a lock by age. Legacy empty locks have an associated incident run,
not a provable owner. All uncertainty stops before removing the production lock.
"""
from __future__ import annotations

import argparse
import base64
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import stat
import subprocess
import sys

import auth_routing as routing
import inour_sftp as d
import production_lock as locks

SELF_WORKFLOW = '.github/workflows/production-lock-recovery.yml'
SHARED_GROUP = 'isegye-inour-production'
ACTIVE = ('in_progress', 'queued', 'waiting', 'pending', 'requested')
MAX_CALLS = 30
MAX_PAGES = 10
MAX_JOBS = 100


class GitHub:
    def __init__(self):
        self.calls = 0
        self.sources = {}

    def get(self, endpoint):
        d.require(self.calls < MAX_CALLS, 'Lock inspection API budget exhausted')
        d.require(endpoint.startswith(('actions/', 'git/ref/heads/main', 'contents/.github/workflows/')),
                  'Unsupported lock inspection endpoint')
        self.calls += 1
        try:
            result = subprocess.run(['gh', 'api', '--method', 'GET',
                                     'repos/' + locks.REPO + '/' + endpoint],
                                    capture_output=True, timeout=30)
        except (OSError, subprocess.TimeoutExpired):
            raise d.Stop('Lock inspection GitHub request failed') from None
        d.require(result.returncode == 0 and len(result.stdout) <= 2_000_000,
                  'Lock inspection GitHub response unavailable')
        try:
            return json.loads(result.stdout)
        except (ValueError, UnicodeError):
            raise d.Stop('Lock inspection GitHub JSON invalid') from None

    def source(self, path, sha):
        key = (path, sha)
        if key not in self.sources:
            d.require(re.fullmatch(r'\.github/workflows/[a-z0-9_-]+\.yml', path) is not None and
                      re.fullmatch(r'[0-9a-f]{40}', sha) is not None,
                      'Untrusted workflow identity')
            data = self.get('contents/' + path + '?ref=' + sha)
            d.require(data.get('path') == path and data.get('encoding') == 'base64',
                      'Workflow source response mismatch')
            try:
                raw = base64.b64decode(data['content'], validate=False)
                d.require(0 < len(raw) <= 100_000, 'Workflow source size invalid')
                blob_sha = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
                d.require(data.get('sha') == blob_sha, 'Workflow source blob hash mismatch')
                import yaml
                parsed = yaml.safe_load(raw)
            except (ValueError, KeyError):
                raise d.Stop('Workflow source decoding failed') from None
            d.require(isinstance(parsed, dict) and isinstance(parsed.get('jobs'), dict),
                      'Workflow definition incomplete')
            self.sources[key] = parsed
        return self.sources[key]


def run_identity(run):
    d.require(isinstance(run, dict) and type(run.get('id')) is int and run['id'] > 0 and
              type(run.get('run_attempt')) is int and run['run_attempt'] > 0 and
              run.get('repository', {}).get('full_name') == locks.REPO and
              run.get('head_repository', {}).get('full_name') == locks.REPO and
              re.fullmatch(r'[0-9a-f]{40}', run.get('head_sha', '')) is not None and
              re.fullmatch(r'\.github/workflows/[a-z0-9_-]+\.yml', run.get('path', '')) is not None,
              'Lock inspection run provenance invalid')
    return {key: run.get(key) for key in
            ('id', 'run_attempt', 'path', 'head_sha', 'head_branch', 'status', 'conclusion')}


def queued_writer_allowed(definition, job=None):
    policy = job.get('concurrency', definition.get('concurrency')) if job else definition.get('concurrency')
    return (isinstance(policy, dict) and policy.get('group') == SHARED_GROUP and
            policy.get('cancel-in-progress') is False)


def credential_bearing(value):
    # PyYAML's YAML 1.1 loader reads the Actions `on` key as boolean True.
    # Sorting mixed bool/string mapping keys raises before any real inspection.
    # This is only a conservative credential scan, not a canonical digest.
    raw = json.dumps(value)
    return any(name in raw for name in ('ISEGYE_SFTP_PASSWORD', 'YEOP_SFTP_PASSWORD',
                                         'secrets: inherit', '"secrets": "inherit"'))


def jobs_for(api, run):
    data = api.get(f"actions/runs/{run['id']}/jobs?filter=latest&per_page=100")
    jobs = data.get('jobs')
    d.require(isinstance(jobs, list) and len(jobs) <= MAX_JOBS and
              type(data.get('total_count')) is int and data['total_count'] == len(jobs),
              'Incomplete active writer job listing')
    d.require(all(j.get('run_id') == run['id'] for j in jobs), 'Writer job run identity mismatch')
    return jobs


def active_writers(api, self_run_id, expected_main):
    """Inspect current attempts, including reruns of arbitrarily old runs."""
    d.require(api.get('git/ref/heads/main').get('object', {}).get('sha') == expected_main,
              'Main changed during lock inspection')
    own = api.get(f'actions/runs/{self_run_id}')
    run_identity(own)
    d.require(own['path'] == SELF_WORKFLOW and own['head_branch'] == 'main' and
              own['head_sha'] == expected_main and own['status'] == 'in_progress',
              'Recovery must run on exact current main')
    definition = api.source(SELF_WORKFLOW, expected_main)
    self_job = definition['jobs'].get('recover')
    d.require(isinstance(self_job, dict) and queued_writer_allowed(definition, self_job),
              'Recovery does not hold the common production queue')
    own_jobs = jobs_for(api, own)
    d.require(any(job.get('name') == (self_job.get('name') or 'recover') and
                  job.get('status') == 'in_progress' for job in own_jobs),
              'Current recovery job is not executing in the writer queue')
    seen = {}
    for status in ACTIVE:
        expected = None
        count = 0
        for page in range(1, MAX_PAGES + 1):
            listing = api.get(f'actions/runs?status={status}&per_page=100&page={page}')
            total, rows = listing.get('total_count'), listing.get('workflow_runs')
            d.require(type(total) is int and 0 <= total <= MAX_PAGES * 100 and
                      isinstance(rows, list) and len(rows) <= 100,
                      'Incomplete active workflow listing')
            if expected is None:
                expected = total
            d.require(total == expected, 'Active workflow history changed during pagination')
            for run in rows:
                summary = run_identity(run)
                d.require(run.get('status') == status and run['id'] not in seen,
                          'Active workflow state changed during inspection')
                seen[run['id']] = run
                count += 1
            if len(rows) < 100:
                d.require(count == total, 'Active workflow listing truncated')
                break
        else:
            raise d.Stop('Active workflow history exceeds inspection budget')
    waiting = []
    for run_id, run in seen.items():
        if run_id == self_run_id:
            continue
        definition = api.source(run['path'], run['head_sha'])
        # An unknown/reusable job is never assumed to be a read-only writer.
        d.require(not any('uses' in value for value in definition['jobs'].values()),
                  'Reusable workflow requires explicit lock inspection support')
        if not credential_bearing(definition):
            continue
        jobs = jobs_for(api, run)
        if not jobs:
            inherited = {key: value for key, value in definition.items() if key != 'jobs'}
            writers = [spec for spec in definition['jobs'].values()
                       if credential_bearing(spec) or credential_bearing(inherited)]
            d.require(run.get('status') in ('queued', 'waiting', 'pending', 'requested') and
                      writers and all(queued_writer_allowed(definition, spec) for spec in writers),
                      'Writer queue cannot be verified')
            waiting.append({'runId': run_id, 'state': 'queued_common_group'})
            continue
        for job in jobs:
            if job.get('status') == 'completed':
                continue
            matches = [v for key, v in definition['jobs'].items()
                       if (v.get('name') or key) == job.get('name')]
            d.require(len(matches) == 1, 'Writer job definition cannot be matched')
            spec = matches[0]
            inherited = {key: value for key, value in definition.items() if key != 'jobs'}
            writer = credential_bearing(spec) or credential_bearing(inherited)
            if not writer:
                # Read-only build/inspection jobs may continue. In particular,
                # production.prepare has no SFTP credential or remote publisher.
                continue
            d.require(queued_writer_allowed(definition, spec), 'Writer lacks common production queue')
            d.require(job.get('status') in ('queued', 'waiting', 'pending', 'requested'),
                      'A production writer is still executing')
            waiting.append({'runId': run_id, 'jobId': job.get('id'), 'state': 'queued_common_group'})
    return {'complete': True, 'executingWriters': 0, 'waitingWriters': waiting,
            'checkedAt': locks.now()}


def terminal_run(api, run_id, attempt, expected_owner=None):
    run = api.get(f'actions/runs/{run_id}')
    summary = run_identity(run)
    d.require(run['status'] == 'completed' and run['run_attempt'] == attempt and
              run['head_branch'] == 'main' and run.get('conclusion') in
              ('success', 'failure', 'cancelled', 'timed_out', 'action_required', 'skipped', 'neutral', 'stale'),
              'Lock owner or associated incident run is not terminal')
    if expected_owner:
        d.require(run['head_sha'] == expected_owner['commit'] and
                  expected_owner['workflowRef'].startswith(locks.REPO + '/' + run['path'] + '@'),
                  'Lock owner execution identity differs')
    return summary


def lock_state(remote):
    info = remote.info(locks.LOCK)
    if info is None:
        return {'state': 'absent'}
    remote.directory(locks.LOCK)
    d.require(stat.S_ISDIR(info.st_mode) and info.st_uid == d.UID and
              stat.S_IMODE(info.st_mode) in (0o700, 0o755),
              'Untrusted production lock type owner or mode')
    entries = remote.s.listdir_attr(locks.LOCK)
    d.require(len(entries) <= 1, 'Unexpected production lock contents')
    result = {'state': 'legacy_empty' if not entries else 'attributed',
              'uid': info.st_uid, 'mode': stat.S_IMODE(info.st_mode),
              'mtime': info.st_mtime, 'size': info.st_size}
    if entries:
        entry = entries[0]
        d.require(entry.filename == locks.OWNER_NAME and stat.S_ISREG(entry.st_mode) and
                  entry.st_uid == d.UID and stat.S_IMODE(entry.st_mode) == 0o600,
                  'Untrusted production lock owner entry')
        raw = remote.read(locks.LOCK + '/' + locks.OWNER_NAME)
        owner = locks.decode_owner(raw)
        d.require(type(owner['runId']) is int and type(owner['runAttempt']) is int and
                  owner['runId'] > 0 and owner['runAttempt'] > 0 and
                  re.fullmatch(r'[0-9a-f]{40}', owner.get('commit') or '') is not None,
                  'Local or incomplete lock owner cannot be recovered')
        result.update(owner=locks.public_owner(owner), ownerSha256=d.digest(raw))
    return result


def snapshot(remote, guard=None):
    remote.directory('/web'); remote.directory(d.ROOT)
    d.require(remote.read(d.ROOT + '/.isegye-owner') == d.OWNER, 'Wrong isolated site owner')
    for path in ('/web/.yeop-migration-lock', d.ROOT + '/.auth-stage-lock'):
        d.require(remote.info(path) is None, 'Another maintenance operation is active')
    if guard is None:
        locks.assert_no_recovery(remote)
    else:
        d.require(remote.read(locks.RECOVERY_LOCK + '/' + locks.OWNER_NAME) == guard.raw,
                  'Recovery guard owner changed')
    router = remote.read(d.ROOT + '/.htaccess')
    release, gated = routing.release_of(router)
    d.require(gated, 'Existing administrator access gate required')
    entry = remote.read(d.ROOT + '/access.php')
    match = re.search(rb"/\.auth-runtime/(g[0-9a-f]{12})'", entry or b'')
    d.require(match is not None, 'Unrecognized active access entry')
    runtime = match[1].decode()
    template = remote.read(d.ROOT + '/.auth-runtime/' + runtime + '/access.php.template')
    d.require(entry == routing.entry(template, runtime), 'Access entry differs from its runtime')
    build_raw = remote.read(d.ROOT + '/_isegye_releases/' + release + '/build-info.json')
    build = json.loads(build_raw or b'{}')
    d.require(build.get('mode') == 'production' and
              re.fullmatch(r'[0-9a-f]{40}', build.get('commit', '')) is not None,
              'Active production release identity unverified')
    hashes = {'router': d.digest(router), 'entry': d.digest(entry),
              'build': d.digest(build_raw)}
    for name in ('.batch-monitoring/active.json', '.albums-feed/current.json',
                 '.schedule-feed/current.json', '.music-feed/current.json',
                 '.history-feed/current.json', '.playground-bank/current.json'):
        raw = remote.read(d.ROOT + '/' + name)
        hashes[name] = d.digest(raw) if raw is not None else None
    pointer = remote.read(d.ROOT + '/.batch-monitoring/active.json')
    d.require(pointer is not None, 'Existing monitor pointer required')
    from deploy_batch_monitor import old_snapshot
    old_snapshot(remote, pointer)  # Manifest, pointer and data integrity only.
    return {'lock': lock_state(remote), 'release': release, 'runtime': runtime,
            'hashes': hashes, 'protected': remote.snapshot(), 'accountStoreAccessed': False}


def evidence(remote, api, expected_main, self_run_id, *, legacy_run_id=None,
             legacy_attempt=None, allow_legacy=False, guard=None):
    first = active_writers(api, self_run_id, expected_main)
    state = snapshot(remote, guard)
    lock = state['lock']
    incident = None
    owner_confirmed = False
    if lock['state'] == 'attributed':
        owner = lock['owner']
        incident = terminal_run(api, owner['runId'], owner['runAttempt'], owner)
        owner_confirmed = True
    elif lock['state'] == 'legacy_empty':
        d.require(allow_legacy and type(legacy_run_id) is int and legacy_run_id > 0 and
                  type(legacy_attempt) is int and legacy_attempt > 0,
                  'Legacy empty lock requires explicit incident-scoped recovery')
        incident = terminal_run(api, legacy_run_id, legacy_attempt)
        d.require(incident['path'] in ('.github/workflows/production.yml',
                  '.github/workflows/batch-monitoring.yml') and
                  incident['conclusion'] in ('cancelled', 'timed_out', 'failure'),
                  'Legacy lock incident is not an interrupted production writer')
    second = active_writers(api, self_run_id, expected_main)
    d.require(snapshot(remote, guard) == state, 'Production state changed during lock inspection')
    stable = {'schemaVersion': 1, 'repository': locks.REPO, 'main': expected_main,
              'remote': state, 'incidentRun': incident, 'ownerConfirmed': owner_confirmed,
              'legacyRecoveryExplicit': allow_legacy,
              'activeWriterInspectionComplete': True}
    return {'schemaVersion': 1, 'checkedAt': locks.now(), 'mode': 'audit',
            'status': 'clear' if lock['state'] == 'absent' else 'recovery_candidate',
            'diagnosticSha256': d.digest(locks.encoded(stable)), 'evidence': stable,
            'inspections': [first, second], 'apiCalls': api.calls,
            'remoteWrites': False, 'accountStoreAccessed': False}


def apply_recovery(remote, api, args, audit, self_run_id, report):
    d.require(audit.get('status') == 'recovery_candidate' and
              re.fullmatch(r'[0-9a-f]{64}', args.audit_sha256 or '') is not None and
              audit.get('diagnosticSha256') == args.audit_sha256 and
              d.digest(locks.encoded(audit.get('evidence'))) == args.audit_sha256,
              'Explicit audit digest does not match the reviewed diagnostic')
    report.update(remoteWrites=True, guardAcquisitionAttempted=True, lockRetired=False)
    guard = locks.acquire(remote, purpose='lock_recovery', report=report,
                          commit=args.expected_main, recovery=True)
    try:
        current = evidence(remote, api, args.expected_main, self_run_id,
                           legacy_run_id=args.legacy_owner_run_id,
                           legacy_attempt=args.legacy_owner_attempt,
                           allow_legacy=args.allow_legacy_empty, guard=guard)
        d.require(current['diagnosticSha256'] == args.audit_sha256,
                  'Production lock or guarded state changed since the reviewed audit')
        state = current['evidence']['remote']
        quarantine = d.ROOT + '/.deploy-lock.recovered-' + guard.owner['nonce']
        remote.parents(quarantine)
        d.require(remote.info(quarantine) is None, 'Recovery quarantine already exists')
        d.require(snapshot(remote, guard) == state, 'Production state changed before lock retirement')
        # Standard rename has no overwrite fallback. The recovery guard blocks
        # new patched writers; the shared queue and two complete job inspections
        # exclude legacy writers. No TTL or unverified owner is used.
        remote.s.rename(locks.LOCK, quarantine)
        report.update(lockRetired=True, remoteWrites=True)
        remote.directory(quarantine)
        entries = remote.s.listdir_attr(quarantine)
        expected = state['lock']
        if expected['state'] == 'attributed':
            d.require(len(entries) == 1 and entries[0].filename == locks.OWNER_NAME,
                      'Retired lock contents changed')
            raw = remote.read(quarantine + '/' + locks.OWNER_NAME)
            d.require(d.digest(raw) == expected['ownerSha256'], 'Retired lock owner changed')
            remote.remove_own(quarantine + '/' + locks.OWNER_NAME, raw)
        else:
            d.require(not entries, 'Retired legacy lock is no longer empty')
        remote.s.rmdir(quarantine)
        after = snapshot(remote, guard)
        expected_after = dict(state, lock={'state': 'absent'})
        d.require(after == expected_after, 'Production state changed during recovery')
        report.update(status='recovered_and_verified', diagnosticSha256=args.audit_sha256,
                      ownerConfirmed=current['evidence']['ownerConfirmed'],
                      incidentRun=current['evidence']['incidentRun'], lockAbsent=True,
                      protectedFilesUnchanged=True, routingAndPointersUnchanged=True,
                      accountStoreAccessed=False, apiCalls=api.calls)
    finally:
        locks.release(remote, guard)


@contextmanager
def connection(password):
    import paramiko
    resources = []
    try:
        sock = socket.create_connection((d.HOST, d.PORT), timeout=15); resources.append(sock)
        transport = paramiko.Transport(sock); resources.append(transport)
        transport.banner_timeout = 15; transport.auth_timeout = 20
        transport.get_security_options().key_types = ('ssh-ed25519',)
        transport.start_client(timeout=15)
        key = transport.get_remote_server_key()
        fingerprint = 'SHA256:' + base64.b64encode(hashlib.sha256(key.asbytes()).digest()).decode().rstrip('=')
        d.require(key.get_name() == 'ssh-ed25519' and fingerprint == d.FINGERPRINT,
                  'Host key mismatch; credential not sent')
        transport.auth_password(d.USER, password); password = None
        d.require(transport.is_authenticated(), 'SFTP authentication incomplete')
        client = paramiko.SFTPClient.from_transport(transport); resources.append(client)
        client.get_channel().settimeout(20)
        yield d.Remote(client)
    finally:
        password = None
        for resource in reversed(resources):
            try: resource.close()
            except Exception: pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('audit', 'apply'))
    parser.add_argument('--expected-main', required=True)
    parser.add_argument('--audit-file')
    parser.add_argument('--audit-sha256')
    parser.add_argument('--allow-legacy-empty', action='store_true')
    parser.add_argument('--legacy-owner-run-id', type=int,
                        help='Associated incident run only; does not establish legacy lock ownership')
    parser.add_argument('--legacy-owner-attempt', type=int)
    parser.add_argument('--output', default='production-lock-audit.json')
    args = parser.parse_args()
    report = {'schemaVersion': 1, 'status': 'failed', 'mode': args.mode,
              'remoteWrites': False, 'accountStoreAccessed': False, 'checkedAt': locks.now()}
    password = os.environ.pop('ISEGYE_SFTP_PASSWORD', '')
    api = GitHub()
    try:
        d.require(os.getenv('GITHUB_ACTIONS') == 'true' and
                  os.getenv('GITHUB_REPOSITORY') == locks.REPO and
                  os.getenv('GITHUB_REF') == 'refs/heads/main' and
                  os.getenv('GITHUB_JOB') == 'recover' and
                  re.fullmatch(r'[0-9a-f]{40}', args.expected_main) is not None and
                  os.getenv('GITHUB_SHA') == args.expected_main,
                  'Lock recovery requires the exact current main Actions identity')
        d.require(os.getenv('PRODUCTION_PAUSED') != 'true' and
                  os.getenv('ISEGYE_MONITOR_PAUSED') != 'true', 'Production or monitor is paused')
        d.require(bool(password) and bool(os.getenv('GH_TOKEN')), 'Existing recovery credentials unavailable')
        run_id = int(os.environ['GITHUB_RUN_ID'])
        with connection(password) as remote:
            password = None
            if args.mode == 'audit':
                report = evidence(remote, api, args.expected_main, run_id,
                                  legacy_run_id=args.legacy_owner_run_id,
                                  legacy_attempt=args.legacy_owner_attempt,
                                  allow_legacy=args.allow_legacy_empty)
            else:
                d.require(bool(args.audit_file) and Path(args.audit_file).is_file() and
                          not Path(args.audit_file).is_symlink() and
                          Path(args.audit_file).stat().st_size <= 100_000,
                          'Verified audit artifact required')
                audit = json.loads(Path(args.audit_file).read_text())
                apply_recovery(remote, api, args, audit, run_id, report)
    except Exception as exc:
        report.update(status='failed', errorType=type(exc).__name__, apiCalls=api.calls)
        if isinstance(exc, d.Stop): report['reason'] = str(exc)
    finally:
        password = None
        run_text, attempt_text = os.getenv('GITHUB_RUN_ID', ''), os.getenv('GITHUB_RUN_ATTEMPT', '')
        report.update(runId=int(run_text) if run_text.isdigit() else None,
                      runAttempt=int(attempt_text) if attempt_text.isdigit() else None,
                      commit=os.getenv('GITHUB_SHA'), workflow=SELF_WORKFLOW)
        Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
        print(json.dumps(report, ensure_ascii=False))
    return 0 if report['status'] in ('clear', 'recovery_candidate', 'recovered_and_verified') else 1


if __name__ == '__main__':
    sys.exit(main())
