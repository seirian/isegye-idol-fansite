"""Bounded recovery of the monitor ONLY. Never dispatch a collection workflow.

Uses recent created runs to budget NEW recovery dispatches, separately enumerates
all active main runs (including reruns of old runs), and verifies the exact
publication artifact. It does not claim a global latest-attempt ordering.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode
import json, os, re, subprocess, sys
from batch_monitor_snapshot import extra_artifact, stamp, run_start, policy, REPO

WORKFLOW = 'batch-monitoring.yml'
PREFIX = 'actions/workflows/'+WORKFLOW
ROOT = Path(__file__).resolve().parents[1]
ACTIVE = sorted(policy.ACTIVE)


class API:
    def __init__(self): self.calls = 0
    def __call__(self, path, method='GET', payload=None, binary=False):
        self.calls += 1
        if self.calls > 70: raise ValueError('Monitor recovery read budget exceeded')
        if method == 'POST':
            if path != PREFIX+'/dispatches' or payload != {'ref':'main'}:
                raise ValueError('Only fixed main monitor dispatch is allowed')
        elif method == 'GET':
            allowed = path.startswith(PREFIX+'/runs?') or bool(re.fullmatch(
                r'actions/(?:runs/[1-9][0-9]*/artifacts\?per_page=100(?:&page=[1-9][0-9]*)?|artifacts/[1-9][0-9]*/zip)',path))
            if not allowed or payload is not None: raise ValueError('Unexpected monitoring endpoint')
        else: raise ValueError('Unexpected method')
        command=['gh','api','--method',method,'repos/'+REPO+'/'+path]
        if payload is not None: command+=['--input','-']
        response=subprocess.run(command,input=json.dumps(payload).encode() if payload else None,
                                capture_output=True,timeout=40)
        if response.returncode or len(response.stdout)>4_000_000: raise RuntimeError('Monitor recovery API unavailable')
        if method=='POST': return None
        return response.stdout if binary else json.loads(response.stdout)


def read_runs(api, params):
    runs=[];seen=set();total=None
    for page in range(1,11):
        doc=api(PREFIX+'/runs?'+urlencode(dict(params,branch='main',per_page=100,page=page)))
        entries=doc.get('workflow_runs');count=doc.get('total_count')
        if not isinstance(entries,list) or len(entries)>100 or type(count) is not int or not 0<=count<=1000:
            raise ValueError('Incomplete recovery history')
        if total is not None and total!=count: raise ValueError('Changing recovery history')
        total=count
        for run in entries:
            rid=run.get('id')
            if type(rid) is not int or rid<=0 or rid in seen: raise ValueError('Duplicate recovery history')
            seen.add(rid)
            if (run.get('head_branch')!='main' or run.get('path')!='.github/workflows/'+WORKFLOW or
                run.get('repository',{}).get('full_name')!=REPO or
                run.get('head_repository',{}).get('full_name')!=REPO or
                type(run.get('run_attempt')) is not int or run['run_attempt']<1):
                raise ValueError('Untrusted monitor run')
            run_start(run);runs.append(run)
        if len(seen)==total: return runs
        if len(entries)<100: raise ValueError('Truncated recovery history')
    raise ValueError('Recovery history budget exceeded')


def inspect(api, at):
    # Separate active filters include ancient runs rerun today.
    for status in ACTIVE:
        if read_runs(api,{'status':status}): return {'state':'active','reason':'existing_monitor_run'}
    runs=read_runs(api,{'created':'>='+(at-timedelta(hours=2)).isoformat()})
    if any(r.get('status') in policy.ACTIVE for r in runs): return {'state':'active','reason':'existing_monitor_run'}
    if any(run_start(r)>at+timedelta(minutes=2) for r in runs): raise ValueError('Future monitor clock')
    latest=max((run_start(r) for r in runs),default=at-timedelta(days=1))
    # A recent attempt gets time to publish its artifact, including a failed attempt.
    if at-latest<timedelta(minutes=15): return {'state':'cooldown','reason':'monitor_retry_cooldown'}
    complete=[r for r in runs if r.get('status')=='completed']
    for run in sorted(complete,key=run_start,reverse=True)[:5]:
        try:
            report=extra_artifact(api,run,'batch-monitor-production','batch-monitor-deployment.json')
        except policy.EvidenceUnavailable:
            continue
        try:
            checked=stamp(report['sourceCheckedAt']);verified=stamp(report['verifiedAt'])
            valid=(report.get('status')=='monitor_snapshot_verified' and report.get('commit')==run['head_sha'] and
                   report.get('anonymousUIAndAPIDenied') is True and report.get('privatePathsBlocked') is True and
                   report.get('requiresExistingAdministrator') is True and report.get('readOnly') is True and
                   checked<=verified<=at+timedelta(minutes=2) and checked>=at-timedelta(minutes=30))
        except (ValueError,TypeError,KeyError): valid=False
        if valid and (report.get('collectorHealth') or {}).get('state')=='ok':
            return {'state':'healthy','reason':'verified_monitor_fresh'}
    # Limit NEW manual/recovery requests, regardless of who requested them.
    requests=[r for r in runs if r.get('event')=='workflow_dispatch' and stamp(r['created_at'])>=at-timedelta(hours=1)]
    if len(requests)>=2: return {'state':'retry_budget','reason':'two_monitor_dispatches_per_hour'}
    return {'state':'dispatch','reason':'monitor_stale_or_inspection_failed'}


def recover(api, at, apply=False):
    first=inspect(api,at)
    if first['state']!='dispatch' or not apply: return first
    # Re-read immediately before a single bounded mutation, never use cached decisions.
    second=inspect(api,datetime.now(timezone.utc))
    if second['state']!='dispatch': return second
    api(PREFIX+'/dispatches',method='POST',payload={'ref':'main'})
    return {'state':'dispatched','reason':'monitor_only_recovery_requested'}


def main():
    report={'checkedAt':datetime.now(timezone.utc).isoformat(),'target':WORKFLOW,'state':'inspection_failed'}
    try:
        if os.getenv('GITHUB_REPOSITORY')!=REPO or os.getenv('GITHUB_REF')!='refs/heads/main':
            raise ValueError('Main repository required')
        if os.getenv('PRODUCTION_PAUSED')=='true' or os.getenv('ISEGYE_MONITOR_PAUSED')=='true':
            report['state']='paused'
        else: report.update(recover(API(),datetime.now(timezone.utc),apply='--apply' in sys.argv))
    except Exception as exc: report['errorCode']=type(exc).__name__
    (ROOT/'batch-monitor-recovery.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))
    return 0 if report['state'] in ('healthy','paused','active','cooldown') else 1


if __name__=='__main__': sys.exit(main())
