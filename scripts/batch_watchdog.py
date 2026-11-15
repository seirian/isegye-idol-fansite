"""Recover missed schedules from VERIFIED outcomes, never from a green badge alone.

This controller only reads Actions evidence and dispatches fixed main workflows.
It never receives SFTP credentials, writes production files, cancels active jobs,
or invents historical chart observations. An independent caller may rerun this
workflow when GitHub's schedule event delivery itself is delayed.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import argparse
import hashlib
import io
import json
import os
import re
import subprocess
import stat
import zipfile

REPO = 'seirian/isegye-idol-fansite'
ROOT = Path(__file__).resolve().parents[1]
KST = timezone(timedelta(hours=9))
UTC = timezone.utc
FIRST_WEEKLY = datetime(2026, 11, 15, tzinfo=KST)
SPECS = {
    'albums': ('albums-daily.yml', 'daily-albums', 'ISEGYE_ALBUMS_PAUSED'),
    'schedule': ('schedule-refresh.yml', 'schedule-publication', 'ISEGYE_SCHEDULE_PAUSED'),
    'music': ('music-daily.yml', 'daily-music', 'ISEGYE_MUSIC_PAUSED'),
    'history': ('history-monthly.yml', 'weekly-history', 'ISEGYE_HISTORY_PAUSED'),
    'catalog': ('video-catalog.yml', None, 'ISEGYE_VIDEO_CATALOG_PAUSED'),
    'production': ('production.yml', None, 'PRODUCTION_PAUSED'),
}
MAX_ARCHIVE = 8_000_000
RUN_PAGE_SIZE = 100
MAX_RUN_PAGES = 20
MAX_ARTIFACT_PAGES = 10
COMPLETION_WORKFLOWS = {
    'Albums - hourly verified metadata and chart refresh': 'albums-daily.yml',
    'Schedule - hourly permitted-source refresh': 'schedule-refresh.yml',
    'Production - isolated inour SFTP deployment': 'production.yml',
}
ACTIVE = {'queued', 'pending', 'in_progress', 'waiting', 'requested'}
REQUIRED_SCHEDULE = {'cafe-members','cafe-agency','fan-roundup',
                     'parable-web','berriz-notice','berriz-calendar'}

class EvidenceUnavailable(ValueError):
    """Absent or expired evidence is not success, but permits bounded recollection."""

def clock(value):
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise ValueError('Timezone required')
    return result.astimezone(UTC)

def due_slot(kind, at):
    local = at.astimezone(KST)
    if kind == 'albums':
        if 1 <= local.hour < 7:
            return None
        return local.replace(minute=0, second=0, microsecond=0).astimezone(UTC)
    if kind == 'schedule':
        due = local.replace(minute=5, second=0, microsecond=0)
        return (due if due <= local else due-timedelta(hours=1)).astimezone(UTC)
    if kind in ('music', 'catalog'):
        hour, minute = (6, 0) if kind == 'music' else (7, 15)
        due = local.replace(hour=hour, minute=minute, second=0, microsecond=0)
        return (due if due <= local else due-timedelta(days=1)).astimezone(UTC)
    if kind == 'history':
        if local < FIRST_WEEKLY:
            return None
        due = (local-timedelta(days=(local.weekday()+1)%7)).replace(hour=0, minute=0, second=0, microsecond=0)
        return due.astimezone(UTC)
    raise ValueError('Unknown batch')

def recent(value, due, at):
    try:
        return due <= clock(value) <= at+timedelta(minutes=2)
    except (ValueError, TypeError, AttributeError):
        return False

def evidence_ok(kind, files, due, at):
    """Publish and source clocks must both be current. Missing evidence is NOT success."""
    if kind == 'albums':
        from album_hourly import coverage
        data = files.get('albums/snapshot.json', {})
        cov = coverage(data, at)
        pub = files.get('albums-publication.json', {})
        restore = files.get('albums-restore.json', {})
        # A no-op run must have read the currently published server feed.
        persisted = ((pub.get('status') == 'published' and pub.get('verifiedReadback') is True)
                     or (restore.get('status') == 'restored' and restore.get('source') == 'cumulative-feed'))
        return persisted and cov['currentComplete']
    pub = files.get({'music':'music-publication.json','schedule':'schedule-publication.json',
                     'history':'history-publication.json'}[kind], {})
    if pub.get('status') != 'published' or not recent(pub.get('generatedAt'), due, at):
        return False
    if kind == 'schedule':
        health = pub.get('collectionHealth', {})
        sources = health.get('sources', {})
        return (files.get('schedule-health.json', {}).get('verified') is True
                and health.get('state') == 'complete'
                and schedule_readback_ok(pub, due, at)
                and all(sources.get(k, {}).get('state') == 'complete'
                        and recent(sources.get(k, {}).get('lastSuccessAt'), due, at)
                        for k in REQUIRED_SCHEDULE))
    if pub.get('verifiedReadback') is not True:
        return False
    if kind == 'music':
        states = pub.get('sourceStates', {})
        audit = files.get('test-results/music-sources/source-audit.json', {})
        return (len(states) == 9 and all(v == 'ok' for v in states.values())
                and audit.get('selected', 0) > 0 and audit.get('passed') == audit.get('selected'))
    return (pub.get('cadence') == 'weekly'
            and pub.get('through') == (due.astimezone(KST)-timedelta(days=1)).date().isoformat()
            and not pub.get('coverage', {}).get('partial', True))

def schedule_readback_ok(pub, due, at):
    """Keep legacy reports compatible without mistaking them for explicit readback."""
    if pub.get('verifiedReadback', True) is not True:
        return False
    if 'evidenceVersion' not in pub:
        return True
    if type(pub['evidenceVersion']) is not int or pub['evidenceVersion'] != 2:
        return False
    if pub.get('verifiedReadback') is not True:
        return False
    try:
        generated = clock(pub['generatedAt'])
        published = clock(pub['publishedAt'])
        readback = clock(pub['readbackAt'])
        return due <= generated <= published <= readback <= at+timedelta(minutes=2)
    except (KeyError, ValueError, TypeError, AttributeError):
        return False


def api(path, method='GET', payload=None, binary=False):
    if not path.startswith(('actions/', 'git/ref/heads/main', 'issues')):
        raise ValueError('Unapproved endpoint')
    args = ['gh','api','--method',method,'repos/'+REPO+'/'+path]
    if payload is not None:
        args += ['--input','-']
    result = subprocess.run(args, input=json.dumps(payload).encode() if payload is not None else None,
                            capture_output=True, timeout=70)
    if result.returncode:
        raise RuntimeError('GitHub API request failed')  # never expose signed URLs or credentials
    if len(result.stdout) > (MAX_ARCHIVE if binary else 2_000_000):
        raise ValueError('Oversized GitHub response')
    return result.stdout if binary else json.loads(result.stdout) if result.stdout.strip() else {}

def artifact_files(run, prefix, filename, getter=api):
    name = prefix+'-'+str(run['id'])+'-'+str(run['run_attempt'])
    matches = []
    seen = set()
    for page in range(1, MAX_ARTIFACT_PAGES+1):
        endpoint = f"actions/runs/{int(run['id'])}/artifacts?per_page=100"
        listing = getter(endpoint if page == 1 else endpoint+f'&page={page}')
        entries = listing.get('artifacts')
        if not isinstance(entries, list) or len(entries) > 100:
            raise ValueError('Invalid artifact listing')
        for entry in entries:
            if not isinstance(entry, dict):
                raise ValueError('Invalid artifact entry')
            ident = entry.get('id')
            # Some old empty/expired fixtures lack IDs; accepted only if unusable.
            if ident is not None:
                if type(ident) is not int or ident <= 0 or ident in seen:
                    raise ValueError('Duplicate or invalid artifact ID')
                seen.add(ident)
            if entry.get('name') == name and not entry.get('expired'):
                matches.append(entry)
        total = listing.get('total_count')
        if total is not None and (type(total) is not int or total < 0):
            raise ValueError('Invalid artifact count')
        if len(entries) < 100:
            if total is not None and total > len(seen):
                raise ValueError('Incomplete artifact listing')
            break
    else:
        raise ValueError('Artifact history exceeds inspection budget')
    if not matches:
        raise EvidenceUnavailable('Missing current-attempt evidence')
    if len(matches) != 1:
        raise ValueError('Duplicate current-attempt evidence')
    entry = matches[0]
    provenance = entry.get('workflow_run', {})
    if (run.get('head_branch') != 'main' or run.get('path') != '.github/workflows/'+filename
            or run.get('repository',{}).get('full_name') != REPO
            or provenance.get('id') != run['id'] or provenance.get('head_sha') != run['head_sha']
            or type(entry.get('id')) is not int or entry['id'] <= 0
            or not 0 < entry.get('size_in_bytes',0) <= MAX_ARCHIVE):
        raise ValueError('Untrusted evidence')
    raw = getter(f"actions/artifacts/{int(entry['id'])}/zip", binary=True)
    if len(raw) != entry['size_in_bytes'] or entry.get('digest') != 'sha256:'+hashlib.sha256(raw).hexdigest():
        raise ValueError('Evidence checksum mismatch')
    allowed = {'albums/snapshot.json','albums-restore.json','albums-publication.json',
               'schedule-publication.json','schedule-health.json','music-publication.json',
               'test-results/music-sources/source-audit.json','history-publication.json'}
    files = {}
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        if sum(info.file_size for info in z.infolist() if info.filename in allowed) > MAX_ARCHIVE:
            raise ValueError('Oversized expanded evidence')
        for info in z.infolist():
            if info.filename in allowed:
                if (info.filename in files or info.file_size > MAX_ARCHIVE
                        or stat.S_ISLNK(info.external_attr >> 16)):
                    raise ValueError('Duplicate or oversized evidence')
                value = json.loads(z.read(info))
                if not isinstance(value, dict):
                    raise ValueError('Evidence must be a JSON object')
                files[info.filename] = value
    return files

def started(run):
    if run.get('run_attempt', 1) > 1 and not run.get('run_started_at'):
        raise ValueError('Latest attempt start time required')
    return clock(run.get('run_started_at') or run['created_at'])

def recovery_action(runs, at, due, healthy, grace=timedelta(minutes=5)):
    if healthy:
        return 'healthy'
    if any(r.get('status') in ACTIVE for r in runs):
        return 'active'
    if at < due+grace:
        return 'grace'
    if any(started(r) > at+timedelta(minutes=2) for r in runs):
        raise ValueError('Future workflow clock')
    # A run may start while this inspection is reading the API. Treat small
    # positive clock deltas conservatively, never as an expired cooldown.
    recent_runs = [r for r in runs if -timedelta(minutes=2) <= at-started(r) < timedelta(minutes=15)]
    if recent_runs:
        return 'cooldown'
    # At most two dispatch retries per rolling hour, independent of schedule arrivals.
    retries = [r for r in runs if r.get('event') == 'workflow_dispatch'
               and -timedelta(minutes=2) <= at-started(r) < timedelta(hours=1)]
    return 'retry_budget' if len(retries) >= 2 else 'dispatch'

def workflow_runs(filename, getter=None, max_pages=MAX_RUN_PAGES):
    """Read bounded, complete history; old run IDs can have a recent attempt.

    GitHub orders runs by creation, not latest attempt. Never dispatch based on
    an incomplete page of runs. A limit/API/provenance error fails closed.
    """
    getter = getter or api
    if filename not in {spec[0] for spec in SPECS.values()}:
        raise ValueError('Unapproved workflow')
    found = {}
    expected_total = None
    for page in range(1, max_pages+1):
        # Do not use branch/status/created filters: GitHub caps filtered searches
        # at 1,000 results, and an old run can have a new attempt. Filter locally.
        listing = getter('actions/workflows/'+filename+
                         f'/runs?per_page={RUN_PAGE_SIZE}&page={page}')
        runs = listing.get('workflow_runs')
        total = listing.get('total_count')
        if (not isinstance(runs, list) or len(runs) > RUN_PAGE_SIZE
                or type(total) is not int or total < 0):
            raise ValueError('Invalid workflow run listing')
        if expected_total is None:
            expected_total = total
        elif total != expected_total:
            raise ValueError('Workflow run listing changed during inspection')
        for run in runs:
            if (not isinstance(run, dict) or type(run.get('id')) is not int or run['id'] <= 0
                    or run.get('repository', {}).get('full_name') != REPO
                    or run['id'] in found):
                raise ValueError('Untrusted or duplicate workflow run')
            found[run['id']] = run
            if run.get('head_branch') != 'main':
                continue
            if (run.get('path') != '.github/workflows/'+filename
                    or type(run.get('run_attempt')) is not int or run['run_attempt'] < 1
                    or run.get('status') not in ACTIVE | {'completed'}):
                raise ValueError('Untrusted workflow run')
            started(run)
            clock(run['created_at'])
        if len(runs) < RUN_PAGE_SIZE or total <= len(found):
            if total != len(found):
                raise ValueError('Incomplete workflow run listing')
            return sorted((r for r in found.values() if r.get('head_branch') == 'main'),
                          key=started, reverse=True)
    raise ValueError('Workflow run history exceeds inspection budget')


def require_trusted_completion(getter=None):
    """A workflow_run wake-up must never import PR/fork code or evidence."""
    if os.getenv('GITHUB_EVENT_NAME') != 'workflow_run':
        return
    getter = getter or api
    event = json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_text())
    source = event.get('workflow_run', {})
    if (event.get('action') != 'completed'
            or source.get('head_branch') != 'main'
            or source.get('head_repository', {}).get('full_name') != REPO
            or source.get('name') not in COMPLETION_WORKFLOWS
            or type(source.get('id')) is not int or source['id'] <= 0):
        raise ValueError('Untrusted completion event')
    run = getter('actions/runs/'+str(source['id']))
    filename = COMPLETION_WORKFLOWS[source['name']]
    if (run.get('id') != source['id'] or run.get('name') != source['name']
            or run.get('head_branch') != 'main'
            or run.get('repository', {}).get('full_name') != REPO
            or run.get('head_repository', {}).get('full_name') != REPO
            or run.get('path') != '.github/workflows/'+filename
            or run.get('event') not in ('push', 'schedule', 'workflow_dispatch')
            or run.get('status') != 'completed'):
        raise ValueError('Untrusted completion run')


def inspect_batch(kind, at, getter=None):
    """Recompute the due slot, pauses, active attempts, budget and evidence."""
    getter = getter or api
    filename, prefix, pause = SPECS[kind]
    row = {'batch':kind, 'workflow':filename, 'checkedAt':at.isoformat()}
    if os.getenv('PRODUCTION_PAUSED') == 'true' or os.getenv(pause) == 'true':
        row['state'] = 'paused'
        return row
    due = due_slot(kind, at) if kind != 'production' else at-timedelta(days=1)
    if due is None:
        row['state'] = 'night_pause' if kind == 'albums' else 'not_due'
        return row
    row['dueAt'] = due.isoformat()
    runs = workflow_runs(filename, getter)
    row['inspectedRuns'] = len(runs)
    if runs:
        last = runs[0]
        row['latestAttempt'] = {'runId':last['id'], 'attempt':last['run_attempt'],
                               'startedAt':started(last).isoformat(),
                               'status':last['status'], 'event':last['event']}
    scheduled = [r for r in runs if r.get('event') == 'schedule']
    if scheduled:
        last = max(scheduled, key=lambda r: clock(r['created_at']))
        # Creation is diagnostic for event delivery, NEVER the retry clock.
        row['lastScheduledEvent'] = {'runId':last['id'], 'createdAt':last['created_at']}
    if any(r.get('status') in ACTIVE for r in runs):
        row['state'] = 'active'
        row['activeRuns'] = [r['id'] for r in runs if r.get('status') in ACTIVE]
        return row
    success = next((r for r in runs if r.get('conclusion') == 'success'), None)
    good = False
    if success:
        row['evidenceRun'] = success['id']
        row['evidenceAttempt'] = success['run_attempt']
        if kind == 'production':
            head = getter('git/ref/heads/main')['object']['sha']
            row['expectedHead'] = head
            good = success.get('head_sha') == head
        elif kind == 'catalog':
            good = recent(success.get('run_started_at'), due, at)
        else:
            try:
                files = artifact_files(success, prefix, filename, getter)
            except EvidenceUnavailable:
                files = {}
                row['evidenceState'] = 'unavailable'
            good = evidence_ok(kind, files, due, at)
            pub = files.get({'albums':'albums-publication.json',
                             'schedule':'schedule-publication.json',
                             'music':'music-publication.json',
                             'history':'history-publication.json'}[kind], {})
            row['publicationEvidence'] = {key:pub[key] for key in
                ('status','generatedAt','publishedAt','verifiedReadback','readbackAt','evidenceVersion') if key in pub}
            if kind == 'schedule':
                row['readbackEvidence'] = ('explicit' if pub.get('verifiedReadback') is True
                                           else 'legacy_report' if 'verifiedReadback' not in pub
                                           else 'failed')
            if kind == 'albums':
                from album_hourly import coverage
                cov = coverage(files.get('albums/snapshot.json', {}), at)
                row['missingHours'] = {k:len(v['missingSlots']) for k,v in cov['charts'].items()}
                row['historicalGapsOnly'] = bool(good and any(row['missingHours'].values()))
    row['state'] = recovery_action(runs, at, due, good)
    return row


def recover_batch(kind, apply=False, getter=None, now=None):
    getter = getter or api
    now = now or (lambda: datetime.now(UTC))
    row = inspect_batch(kind, now(), getter)
    if apply and row['state'] == 'dispatch':
        # A job can finish between reads. Rechecking only ACTIVE is insufficient:
        # a new successful/failed completion must also affect evidence/cooldown.
        row = inspect_batch(kind, now(), getter)
        row['recheckedBeforeDispatch'] = True
        if row['state'] == 'dispatch':
            at = now()
            filename, _, pause = SPECS[kind]
            if os.getenv('PRODUCTION_PAUSED') == 'true' or os.getenv(pause) == 'true':
                row['state'] = 'paused'
                return row
            due = due_slot(kind, at) if kind != 'production' else None
            if kind != 'production' and (due is None or due.isoformat() != row['dueAt']):
                # Do not act on an old decision if an API read crossed a slot/night boundary.
                row['state'] = ('night_pause' if kind == 'albums' else 'not_due') if due is None else 'slot_changed'
                row['nextDueAt'] = due.isoformat() if due else None
                return row
            getter('actions/workflows/'+filename+'/dispatches', 'POST', {'ref':'main'})
            row['state'] = 'dispatched'
            row['dispatchedAt'] = now().isoformat()
    return row


def report_state(rows):
    if any(r['state'] in ('dispatch','dispatched','inspection_failed','retry_budget') for r in rows):
        return 'attention'
    if any(r['state'] in ('active','cooldown','grace','slot_changed') for r in rows):
        return 'pending'
    # Historical observation gaps stay in the report, not a perpetual live incident.
    return 'checked'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    if (os.getenv('GITHUB_REPOSITORY') != REPO or os.getenv('GITHUB_REF') != 'refs/heads/main'
            or not os.getenv('GH_TOKEN')):
        raise ValueError('Main-only watchdog')
    at = datetime.now(UTC)
    report = {'checkedAt':at.isoformat(),'mode':'apply' if args.apply else 'audit','batches':[]}
    if os.getenv('PRODUCTION_PAUSED') == 'true':
        report['state'] = 'paused'
    else:
        try:
            require_trusted_completion()
        except Exception as exc:
            report.update(state='inspection_failed', triggerError=type(exc).__name__)
            (ROOT/'batch-watchdog.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
            print(json.dumps(report, ensure_ascii=False))
            return 1
        for kind,(filename,prefix,pause) in SPECS.items():
            try:
                row = recover_batch(kind, args.apply)
            except Exception as exc:
                row = {'batch':kind, 'workflow':filename, 'state':'inspection_failed',
                       'error':type(exc).__name__}
            report['batches'].append(row)
        report['state'] = report_state(report['batches'])
        if args.apply:
            try:
                title='[배치] 예약 누락·게시 지연·배포 복구 점검'
                issues=api('issues?state=open&per_page=100')
                issue=next((i for i in issues if i.get('title')==title and not i.get('pull_request')),None)
                unhealthy=report['state']=='attention'
                body='실제 성공 산출물 기준 점검입니다. 실행 요청은 게시 성공이 아닙니다.\n\n```json\n'+json.dumps(report,ensure_ascii=False,indent=2)+'\n```\n'
                if unhealthy:
                    api('issues/'+str(issue['number']) if issue else 'issues',
                        'PATCH' if issue else 'POST', {'body':body,**({} if issue else {'title':title})})
                elif issue and all(r['state'] in ('healthy','night_pause','not_due','paused') for r in report['batches']):
                    api('issues/'+str(issue['number']),'PATCH',{'state':'closed','body':body})
            except Exception as exc:
                report['incidentError']=type(exc).__name__
    (ROOT/'batch-watchdog.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False))
    if os.getenv('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'],'a') as out:
            out.write('```json\n'+json.dumps(report,ensure_ascii=False,indent=2)+'\n```\n')
    return int(bool(report.get('incidentError')) or any(r.get('state')=='inspection_failed' for r in report['batches']))

if __name__ == '__main__':
    raise SystemExit(main())
