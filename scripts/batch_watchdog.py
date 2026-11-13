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
    listing = getter(f"actions/runs/{int(run['id'])}/artifacts?per_page=100")
    name = prefix+'-'+str(run['id'])+'-'+str(run['run_attempt'])
    matches = [a for a in listing.get('artifacts',[]) if a.get('name') == name and not a.get('expired')]
    if not matches:
        raise EvidenceUnavailable('Missing current-attempt evidence')
    if len(matches) != 1:
        raise ValueError('Duplicate current-attempt evidence')
    entry = matches[0]
    provenance = entry.get('workflow_run', {})
    if (run.get('head_branch') != 'main' or run.get('path') != '.github/workflows/'+filename
            or run.get('repository',{}).get('full_name') != REPO
            or provenance.get('id') != run['id'] or provenance.get('head_sha') != run['head_sha']
            or not 0 < entry.get('size_in_bytes',0) <= MAX_ARCHIVE):
        raise ValueError('Untrusted evidence')
    raw = getter(f"actions/artifacts/{int(entry['id'])}/zip", binary=True)
    if entry.get('digest') != 'sha256:'+hashlib.sha256(raw).hexdigest():
        raise ValueError('Evidence checksum mismatch')
    allowed = {'albums/snapshot.json','albums-restore.json','albums-publication.json',
               'schedule-publication.json','schedule-health.json','music-publication.json',
               'test-results/music-sources/source-audit.json','history-publication.json'}
    files = {}
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        for info in z.infolist():
            if info.filename in allowed:
                if info.filename in files or info.file_size > MAX_ARCHIVE:
                    raise ValueError('Duplicate or oversized evidence')
                files[info.filename] = json.loads(z.read(info))
    return files

def started(run):
    return clock(run.get('run_started_at') or run['created_at'])

def recovery_action(runs, at, due, healthy, grace=timedelta(minutes=5)):
    if healthy:
        return 'healthy'
    if any(r.get('status') in ACTIVE for r in runs):
        return 'active'
    if at < due+grace:
        return 'grace'
    recent_runs = [r for r in runs if timedelta(0) <= at-started(r) < timedelta(minutes=15)]
    if recent_runs:
        return 'cooldown'
    # At most two dispatch retries per rolling hour, independent of schedule arrivals.
    retries = [r for r in runs if r.get('event') == 'workflow_dispatch'
               and timedelta(0) <= at-started(r) < timedelta(hours=1)]
    return 'retry_budget' if len(retries) >= 2 else 'dispatch'

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
        head = api('git/ref/heads/main')['object']['sha']
        for kind,(filename,prefix,pause) in SPECS.items():
            row = {'batch':kind,'workflow':filename}
            report['batches'].append(row)
            if os.getenv(pause) == 'true':
                row['state']='paused'
                continue
            due = due_slot(kind, at) if kind != 'production' else at-timedelta(days=1)
            if due is None:
                row['state']='night_pause' if kind == 'albums' else 'not_due'
                continue
            row['dueAt']=due.isoformat()
            try:
                runs = api('actions/workflows/'+filename+'/runs?branch=main&per_page=10')['workflow_runs']
                runs = sorted(runs, key=started, reverse=True)
                if any(r.get('status') in ACTIVE for r in runs):
                    row['state']='active'
                    row['activeRuns']=[r['id'] for r in runs if r.get('status') in ACTIVE]
                    continue
                success = next((r for r in runs if r.get('conclusion') == 'success'), None)
                good = False
                if success:
                    row['evidenceRun']=success['id']
                    row['evidenceAttempt']=success['run_attempt']
                    if kind == 'production':
                        good = success.get('head_sha') == head
                    elif kind == 'catalog':
                        good = recent(success.get('run_started_at'),due,at)
                    else:
                        try:
                            files = artifact_files(success,prefix,filename)
                        except EvidenceUnavailable:
                            files = {}
                            row['evidenceState'] = 'unavailable'
                        good = evidence_ok(kind, files, due, at)
                        if kind == 'albums':
                            from album_hourly import coverage
                            cov = coverage(files.get('albums/snapshot.json',{}),at)
                            row['missingHours']={k:len(v['missingSlots']) for k,v in cov['charts'].items()}
                action = recovery_action(runs,at,due,good)
                row['state']=action
                # Recheck immediately before dispatch; do not enqueue duplicates from stale listings.
                if action == 'dispatch' and args.apply:
                    latest = api('actions/workflows/'+filename+'/runs?branch=main&per_page=10')['workflow_runs']
                    if any(r.get('status') in ACTIVE for r in latest):
                        row['state']='active'
                        continue
                    api('actions/workflows/'+filename+'/dispatches','POST',{'ref':'main'})
                    row['state']='dispatched'
                    row['dispatchedAt']=datetime.now(UTC).isoformat()
            except Exception as exc:
                row['state']='inspection_failed'
                row['error']=type(exc).__name__
        report['state']='attention' if any(r['state'] in ('dispatch','dispatched','inspection_failed','retry_budget')
                                           or any(r.get('missingHours',{}).values())
                                           for r in report['batches']) else 'checked'
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
    return int(any(r.get('state')=='inspection_failed' for r in report['batches']))

if __name__ == '__main__':
    raise SystemExit(main())
