#!/usr/bin/env python3
"""A narrow, guarded wake-up for the existing main watchdog.

The external connector need not enumerate unrelated repository history. This
job reads the complete WATCHDOG workflow history inside Actions, then requests
only that fixed controller. It cannot dispatch collection/deployment workflows,
access SFTP, cancel jobs, or turn an incomplete read into permission to write.
Seed executions are audit-only; reruns/manual executions still pass every gate.
"""
from datetime import datetime, timedelta
from pathlib import Path
import argparse
import json
import os
import re
import subprocess
import time
from urllib.parse import parse_qs

import batch_watchdog as policy
from batch_monitor_snapshot import extra_artifact

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = 'batch-watchdog.yml'
SELF = 'batch-watchdog-wakeup.yml'
PREFIX = 'actions/workflows/' + WORKFLOW
MAX_CALLS = 80
MAX_SECONDS = 300
REPORT_MAX_AGE = timedelta(minutes=45)
GRACE = timedelta(minutes=5)
COOLDOWN = timedelta(minutes=15)
SEED_WORKFLOW = 'video-catalog.yml'
SEED_NAME = 'Content - verified channel video catalog'


class WakeupError(ValueError):
    def __init__(self, code):
        super().__init__('Guarded watchdog inspection failed')
        self.code = code


class API:
    """No GET cache, no arbitrary targets, one POST attempt, finite read budget."""
    def __init__(self, apply=False, getter=None, monotonic=time.monotonic):
        self.apply = apply
        self.getter = getter or policy.api
        self.monotonic = monotonic
        self.deadline = monotonic() + MAX_SECONDS
        self.calls = 0
        self.post_attempted = False

    def __call__(self, path, method='GET', payload=None, binary=False):
        if self.calls >= MAX_CALLS or self.monotonic() >= self.deadline:
            raise WakeupError('wakeup_inspection_budget_exceeded')
        if method == 'POST':
            if (not self.apply or path != PREFIX + '/dispatches' or
                    payload != {'ref': 'main'} or binary or self.post_attempted):
                raise WakeupError('wakeup_mutation_not_allowed')
            # Record before sending: a timeout must never result in a second POST.
            self.post_attempted = True
        elif method == 'GET':
            allowed = path == 'git/ref/heads/main'
            allowed |= bool(re.fullmatch(re.escape(PREFIX) + r'/runs\?per_page=100&page=[1-9][0-9]*', path))
            # Partition traffic is diagnostic only and unavailable in apply mode.
            if not self.apply and path.startswith(PREFIX+'/runs?'):
                params = parse_qs(path.partition('?')[2], keep_blank_values=True)
                allowed |= (set(params) == {'branch', 'created', 'per_page', 'page'} and
                            params.get('branch') == ['main'] and params.get('per_page') == ['100'] and
                            len(params.get('created', [])) == 1 and
                            bool(re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\.\.\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z', params['created'][0])) and
                            len(params.get('page', [])) == 1 and
                            bool(re.fullmatch(r'[1-9][0-9]*', params['page'][0])))
            allowed |= bool(re.fullmatch(r'actions/runs/[1-9][0-9]*', path))
            allowed |= bool(re.fullmatch(r'actions/runs/[1-9][0-9]*/artifacts\?per_page=100(?:&page=[1-9][0-9]*)?', path))
            archive = bool(re.fullmatch(r'actions/artifacts/[1-9][0-9]*/zip', path))
            allowed |= archive
            if not allowed or payload is not None or binary != archive:
                raise WakeupError('wakeup_read_not_allowed')
        else:
            raise WakeupError('wakeup_method_not_allowed')
        self.calls += 1
        return self.getter(path, method=method, payload=payload, binary=binary)


def current_head(getter):
    value = getter('git/ref/heads/main').get('object', {}).get('sha')
    if not isinstance(value, str) or not re.fullmatch(r'[0-9a-f]{40}', value):
        raise WakeupError('invalid_main_revision')
    return value


def paused():
    return os.getenv('PRODUCTION_PAUSED') == 'true'


def slots(at):
    result = {}
    for kind, (_, _, pause) in policy.SPECS.items():
        if kind == 'production' or os.getenv(pause) == 'true':
            continue
        due = policy.due_slot(kind, at)
        result[kind] = due.isoformat() if due else None
    return result


def require_trusted_seed(getter):
    if os.getenv('GITHUB_EVENT_NAME') != 'workflow_run':
        return
    event = json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_text())
    source = event.get('workflow_run', {})
    if (event.get('action') != 'completed' or source.get('name') != SEED_NAME or
            source.get('head_branch') != 'main' or
            source.get('head_repository', {}).get('full_name') != policy.REPO or
            type(source.get('id')) is not int or source['id'] <= 0):
        raise WakeupError('untrusted_wakeup_seed')
    run = getter('actions/runs/' + str(source['id']))
    if (run.get('id') != source['id'] or run.get('name') != SEED_NAME or
            run.get('path') != '.github/workflows/' + SEED_WORKFLOW or
            run.get('head_branch') != 'main' or
            run.get('repository', {}).get('full_name') != policy.REPO or
            run.get('head_repository', {}).get('full_name') != policy.REPO or
            run.get('status') != 'completed' or
            run.get('event') not in {'push', 'schedule', 'workflow_dispatch'}):
        raise WakeupError('untrusted_wakeup_seed')


def report_is_current(report, run, at, head, due_slots):
    """Only a verified current-attempt report can suppress a needed wake-up."""
    if not isinstance(report, dict):
        raise WakeupError('invalid_controller_report')
    if (run.get('status') != 'completed' or run.get('conclusion') != 'success' or
            report.get('incidentError') or report.get('incidentFailure') or report.get('triggerError') or
            report.get('state') not in {'checked', 'pending', 'attention', 'paused'}):
        return False
    checked = policy.clock(report['checkedAt'])
    if checked < policy.started(run) or checked > at + timedelta(minutes=2):
        raise WakeupError('invalid_controller_report_clock')
    if at - checked > REPORT_MAX_AGE or report.get('mode') != 'apply':
        return False
    if report.get('state') == 'paused':
        return False  # A previous pause must not become a current healthy result.
    rows = report.get('batches')
    # A trusted pre-rollout report legitimately has the old seven targets. It
    # cannot certify the new independent capture and must not deadlock rollout.
    if (isinstance(rows, list) and len(rows) == len(policy.SPECS)-1
            and all(isinstance(row, dict) for row in rows)
            and {row.get('batch') for row in rows} == set(policy.SPECS)-{'capture'}
            and all(row.get('workflow') == policy.SPECS[row['batch']][0] for row in rows)):
        return False
    if not isinstance(rows, list) or len(rows) != len(policy.SPECS):
        raise WakeupError('invalid_controller_report')
    by_kind = {}
    for row in rows:
        if (not isinstance(row, dict) or row.get('batch') not in policy.SPECS or
                row['batch'] in by_kind or row.get('workflow') != policy.SPECS[row['batch']][0]):
            raise WakeupError('invalid_controller_report')
        by_kind[row['batch']] = row
    for kind, (_, _, pause) in policy.SPECS.items():
        if os.getenv(pause) == 'true':
            continue
        row = by_kind[kind]
        if kind == 'production':
            if (row.get('state') != 'healthy' or row.get('expectedHead') != head
                    or row.get('publicationVerified') is not True):
                return False
            continue
        due_value = due_slots[kind]
        if due_value is None:
            continue
        due = policy.clock(due_value)
        if at < due + GRACE:
            continue
        if row.get('state') != 'healthy' or row.get('dueAt') != due_value:
            return False
        row_checked = policy.clock(row['checkedAt'])
        if not due + GRACE <= row_checked <= at + timedelta(minutes=2):
            return False
    return True


def inspect(getter, at, policy_revision):
    row = {'checkedAt': at.isoformat(), 'target': WORKFLOW, 'dueSlots': slots(at)}
    if paused():
        return dict(row, state='paused')
    head = current_head(getter)
    row['expectedHead'] = head
    if head != policy_revision:
        return dict(row, state='policy_changed')
    result = policy.read_workflow_runs(WORKFLOW, getter)
    runs = result['runs']
    row['inspection'] = result['inspection']
    for run in runs:
        if (run.get('head_repository', {}).get('full_name') != policy.REPO or
                run.get('event') not in {'push', 'schedule', 'workflow_dispatch', 'workflow_run'}):
            raise WakeupError('untrusted_controller_run')
        if policy.started(run) > at + timedelta(minutes=2):
            raise WakeupError('future_controller_attempt')
    if runs:
        last = runs[0]
        row['latestAttempt'] = {'runId': last['id'], 'attempt': last['run_attempt'],
                                'startedAt': policy.started(last).isoformat(), 'status': last['status']}
    if any(run['status'] in policy.ACTIVE for run in runs):
        return dict(row, state='active')
    if any(-timedelta(minutes=2) <= at-policy.started(run) < COOLDOWN for run in runs):
        return dict(row, state='cooldown')
    requests = [run for run in runs if run.get('event') == 'workflow_dispatch' and
                (at-timedelta(hours=1) <= policy.clock(run['created_at']) <= at+timedelta(minutes=2) or
                 -timedelta(minutes=2) <= at-policy.started(run) < timedelta(hours=1))]
    row['controllerRequestsInHour'] = len(requests)
    if len(requests) >= 2:
        return dict(row, state='retry_budget')
    if runs:
        last = runs[0]
        try:
            report = extra_artifact(getter, last, 'batch-watchdog', 'batch-watchdog.json')
        except policy.EvidenceUnavailable:
            row['controllerEvidence'] = 'unavailable'
        else:
            row['controllerEvidence'] = 'verified_current_attempt_archive'
            row['controllerReportCheckedAt'] = policy.clock(report.get('checkedAt')).isoformat()
            if report_is_current(report, last, at, head, row['dueSlots']):
                return dict(row, state='healthy')
    return dict(row, state='dispatch')


def recover(getter, policy_revision, apply=False, now=None):
    now = now or (lambda: datetime.now(policy.UTC))
    row = inspect(getter, now(), policy_revision)
    if not apply or row['state'] != 'dispatch':
        return row
    row = inspect(getter, now(), policy_revision)
    row['recheckedBeforeDispatch'] = True
    if row['state'] != 'dispatch':
        return row
    if current_head(getter) != row['expectedHead']:
        return dict(row, state='policy_changed')
    # The head read can cross a slot boundary. No GET follows these final gates.
    final_at = now()
    if paused():
        return dict(row, state='paused')
    if slots(final_at) != row['dueSlots']:
        return dict(row, state='slot_changed')
    row['requestAttemptedAt'] = final_at.isoformat()
    try:
        getter(PREFIX+'/dispatches', method='POST', payload={'ref': 'main'})
    except Exception as exc:
        row.update(policy.error_details(exc))
        if isinstance(exc, WakeupError):
            row['reasonCode'] = exc.code
        return dict(row, state='request_unknown', requestOutcome='unconfirmed')
    return dict(row, state='dispatched', dispatchedAt=now().isoformat(), requestOutcome='accepted')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    report = {'schemaVersion': 1, 'kind': 'guarded_watchdog_wakeup', 'target': WORKFLOW,
              'checkedAt': datetime.now(policy.UTC).isoformat(),
              'mode': 'apply' if args.apply else 'audit', 'state': 'inspection_failed'}
    client = API(apply=args.apply)
    try:
        if (os.getenv('GITHUB_REPOSITORY') != policy.REPO or os.getenv('GITHUB_REF') != 'refs/heads/main' or
                not os.getenv('GH_TOKEN') or os.getenv('GITHUB_EVENT_NAME') not in {'push', 'workflow_run', 'workflow_dispatch'}):
            raise WakeupError('untrusted_wakeup_context')
        attempt = int(os.environ['GITHUB_RUN_ATTEMPT'])
        if attempt < 1 or (args.apply and os.getenv('GITHUB_EVENT_NAME') != 'workflow_dispatch' and attempt == 1):
            raise WakeupError('seed_is_audit_only')
        policy_revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
        if not re.fullmatch(r'[0-9a-f]{40}', policy_revision):
            raise WakeupError('invalid_policy_revision')
        report['policyRevision'] = policy_revision
        report['runHeadSha'] = os.getenv('GITHUB_SHA')
        report['runId'] = int(os.environ['GITHUB_RUN_ID'])
        report['runAttempt'] = attempt
        require_trusted_seed(client)
        report.update(recover(client, policy_revision, apply=args.apply))
        if not args.apply and report.get('inspection', {}).get('complete') is True:
            from batch_watchdog_shadow import compare_shadow
            report['shadowComparison'] = compare_shadow(getter=client)
    except Exception as exc:
        report.update(policy.error_details(exc))
        if isinstance(exc, WakeupError):
            report['reasonCode'] = exc.code
    report['apiCalls'] = client.calls
    report['apiCallBudget'] = MAX_CALLS
    report['requestAttempted'] = client.post_attempted
    report['recoveryRequestSent'] = report['state'] == 'dispatched'
    report['publicationVerified'] = False  # A wake-up never proves publication.
    raw = json.dumps(report, ensure_ascii=False, indent=2)+'\n'
    (ROOT/'batch-watchdog-wakeup.json').write_text(raw)
    print(raw)
    if os.getenv('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as output:
            output.write('```json\n'+raw+'```\n')
    return int(report['state'] in {'inspection_failed', 'request_unknown'})


if __name__ == '__main__':
    raise SystemExit(main())
