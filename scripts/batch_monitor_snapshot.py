#!/usr/bin/env python3
"""Read-only monitoring projection. Never dispatches, retries, or scrapes sources.

Only allow-listed GitHub GETs; no logs, credentials, account data, or artifact
code enter the UI. Original collection/publication policy remains authoritative.
"""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from pathlib import Path
import hashlib, io, json, os, re, stat, subprocess, sys, zipfile
from batch_monitor_health import inspection_health, preserve_verified
from batch_slot_ledger import merge_slot_ledger
import batch_watchdog as policy
from batch_publication_evidence import (read_json_artifact, read_capture_evidence,
                                        production_evidence_ok, read_production_evidence)

ROOT = Path(__file__).resolve().parents[1]
UTC = timezone.utc
KST = timezone(timedelta(hours=9))
REPO = 'seirian/isegye-idol-fansite'
META = {
    'albums': ('음반 · 멜론 차트', '00시 및 07~23시 정각 · 20/40분 조건부 보충'),
    'music': ('음악 영상', '매일 06:00'),
    'schedule': ('공지 · 일정', '짝수 시각 05분 · 하루 12회'),
    'catalog': ('콘텐츠 목록', '매일 07:15'),
    'playground': ('놀이터 문제은행', '매일 08:00'),
    'history': ('활동기록', '매주 일요일 00:00'),
    'production': ('운영 배포', '현재 main 커밋 · 배포 이벤트'),
    'watchdog': ('배치 복구 점검', '매시 12/32/52분 · 일부 완료 이벤트'),
    'capture': ('멜론 독립 관측', '00시 및 07~23시 · 11/37분 예약 · 게시와 별도 검증'),
}
SPECS = dict(policy.SPECS, watchdog=('batch-watchdog.yml', 'batch-watchdog', 'PRODUCTION_PAUSED'))
ALLOWED_WORKFLOWS = {v[0] for v in SPECS.values()}
FAILURES = {'failure', 'timed_out', 'action_required', 'startup_failure'}
MAX_PAGES = 20
MAX_CALLS = 200


def stamp(value):
    if not isinstance(value, str):
        raise ValueError('Timestamp required')
    at = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if at.tzinfo is None:
        raise ValueError('Timezone required')
    return at.astimezone(UTC)


def iso(value):
    return value.astimezone(UTC).isoformat() if value else None


def safe_time(value):
    try:
        return iso(stamp(value))
    except (ValueError, TypeError):
        return None


class ReadOnlyGitHub:
    def __init__(self):
        self.calls = 0
        self.cache = {}

    def __call__(self, path, method='GET', payload=None, binary=False):
        if method != 'GET' or payload is not None:
            raise ValueError('Monitoring is GET-only')
        allowed = path == 'git/ref/heads/main'
        match = re.fullmatch(r'actions/workflows/([a-z0-9-]+\.yml)/runs\?per_page=100(?:&page=[1-9][0-9]*)?', path)
        allowed |= bool(match and match[1] in ALLOWED_WORKFLOWS)
        allowed |= bool(re.fullmatch(r'actions/runs/[1-9][0-9]*/artifacts\?per_page=100(?:&page=[1-9][0-9]*)?', path))
        allowed |= bool(re.fullmatch(r'actions/runs/[1-9][0-9]*/attempts/[1-9][0-9]*/jobs\?per_page=100', path))
        allowed |= bool(re.fullmatch(r'actions/runs/[1-9][0-9]*/attempts/[1-9][0-9]*', path))
        allowed |= bool(re.fullmatch(r'actions/artifacts/[1-9][0-9]*/zip', path))
        if not allowed:
            raise ValueError('Endpoint not permitted')
        key = (path, binary)
        if key in self.cache:
            return self.cache[key]
        self.calls += 1
        if self.calls > MAX_CALLS:
            raise RuntimeError('Inspection call budget exceeded')
        result = subprocess.run(['gh', 'api', '--method', 'GET', 'repos/'+REPO+'/'+path],
                                capture_output=True, timeout=45)
        limit = 48_000_000 if binary else 4_000_000
        if result.returncode or len(result.stdout) > limit:
            raise RuntimeError('GitHub read unavailable')
        value = result.stdout if binary else json.loads(result.stdout)
        self.cache[key] = value
        return value


def run_start(run):
    if run.get('run_attempt', 1) > 1 and not run.get('run_started_at'):
        raise ValueError('Attempt start missing')
    return stamp(run.get('run_started_at') or run['created_at'])


def listing(getter, filename):
    """A bounded incomplete listing must never establish the globally latest run."""
    runs, seen, total, complete = [], set(), None, False
    for page in range(1, MAX_PAGES+1):
        result = getter('actions/workflows/'+filename+'/runs?per_page=100'+(f'&page={page}' if page > 1 else ''))
        entries = result.get('workflow_runs')
        count = result.get('total_count')
        if not isinstance(entries, list) or len(entries) > 100 or type(count) is not int or count < 0:
            raise ValueError('Malformed run listing')
        if total is not None and total != count:
            return runs, False
        total = count
        for run in entries:
            rid = run.get('id')
            if type(rid) is not int or rid <= 0 or rid in seen:
                return runs, False
            seen.add(rid)
            if run.get('head_branch') != 'main':
                continue
            if (run.get('path') != '.github/workflows/'+filename or
                run.get('repository', {}).get('full_name') != REPO or
                run.get('head_repository', {}).get('full_name') != REPO or
                type(run.get('run_attempt')) is not int or run['run_attempt'] < 1):
                raise ValueError('Untrusted run')
            if run.get('status') not in policy.ACTIVE | {'completed'}:
                raise ValueError('Unknown execution status')
            run_start(run)
            runs.append(run)
        if len(entries) < 100 or len(seen) == total:
            complete = len(seen) == total
            break
    return sorted(runs, key=run_start, reverse=True), complete


def extra_artifact(getter, run, prefix, filename):
    """The same provenance/digest verifier is used by monitoring and recovery."""
    return read_json_artifact(getter, run, prefix, filename)


def run_view(run):
    return {'id': run['id'], 'attempt': run['run_attempt'], 'status': run.get('status'),
            'conclusion': run.get('conclusion'), 'event': run.get('event'),
            'createdAt': safe_time(run.get('created_at')), 'startedAt': iso(run_start(run)),
            'updatedAt': safe_time(run.get('updated_at')), 'commit': run.get('head_sha'),
            'url': f"https://github.com/{REPO}/actions/runs/{run['id']}/attempts/{run['run_attempt']}"}


def next_due(kind, at):
    if kind == 'production':
        return None
    after = at.replace(second=0, microsecond=0)
    current = policy.due_slot(kind, at) if kind != 'watchdog' else None
    for minute in range(1, 10081):
        candidate = after+timedelta(minutes=minute)
        if kind == 'watchdog':
            if candidate.minute in (12, 32, 52):
                return iso(candidate)
        else:
            due = policy.due_slot(kind, candidate)
            if due is not None and due == candidate and due != current:
                return iso(due)
    return None


def watchdog_state(report, at):
    checked = stamp(report['checkedAt'])
    if checked > at+timedelta(minutes=2) or at-checked > timedelta(minutes=45):
        return 'unknown'
    state = report.get('state')
    if state == 'paused':
        return 'paused'
    if state in ('attention', 'inspection_failed'):
        return 'attention'
    if state == 'pending':
        return 'running'
    if state != 'checked':
        return 'unknown'
    rows = report.get('batches')
    if not isinstance(rows, list) or len(rows) != len(policy.SPECS):
        return 'unknown'
    if any(not isinstance(row, dict) for row in rows):
        return 'unknown'
    if {row.get('batch') for row in rows} != set(policy.SPECS):
        return 'unknown'
    if any(row.get('state') not in ('healthy','paused','night_pause','not_due') for row in rows):
        return 'unknown'
    return 'healthy'


def row_state(row):
    if row.get('paused'):
        return 'paused'
    if not row.get('listingComplete', False):
        return 'unknown'
    run = row.get('run') or {}
    if run.get('status') in policy.ACTIVE:
        return 'running'
    if row.get('key') == 'production' and row.get('publicationVerified') is True:
        return 'healthy'
    if run.get('conclusion') in FAILURES:
        return 'attention'
    if row.get('growth',{}).get('alerts'):
        return 'attention'
    return row.get('dataState', 'unknown')


def inspect(kind, at, head, getter):
    filename, prefix, pause = SPECS[kind]
    due = policy.due_slot(kind, at) if kind not in ('production', 'watchdog') else None
    row = {'key': kind, 'name': META[kind][0], 'schedule': META[kind][1], 'workflow': filename,
           'dueAt': iso(due), 'nextDueAt': next_due(kind, at), 'checkedAt': iso(at),
           'dataState': 'unknown', 'state': 'unknown', 'run': None, 'sources': [], 'steps': [],
           'evidence': {}, 'note': '', 'history': [], 'listingComplete': False,
           'paused': os.getenv('PRODUCTION_PAUSED') == 'true' or os.getenv(pause) == 'true' or
                     (kind in ('albums', 'capture') and due is None)}
    stage = 'execution_query'
    try:
        runs, complete = listing(getter, filename)
        row['listingComplete'] = complete
        row['history'] = [run_view(r) for r in runs[:30]]
        latest = runs[0] if runs else None
        if latest:
            row['run'] = run_view(latest)
            try:
                jobs = getter(f"actions/runs/{latest['id']}/attempts/{latest['run_attempt']}/jobs?per_page=100")
                if not isinstance(jobs.get('jobs'), list) or jobs.get('total_count') != len(jobs['jobs']):
                    raise ValueError('Incomplete job listing')
                starts, ends = [], []
                for job in jobs['jobs']:
                    if job.get('run_id') != latest['id']:
                        raise ValueError('Job run mismatch')
                    if job.get('started_at'):
                        starts.append(stamp(job['started_at']))
                    if job.get('completed_at'):
                        ends.append(stamp(job['completed_at']))
                    for step in job.get('steps', []):
                        row['steps'].append({'name': str(step.get('name', ''))[:180],
                                             'status': step.get('status'), 'conclusion': step.get('conclusion'),
                                             'startedAt': safe_time(step.get('started_at')),
                                             'completedAt': safe_time(step.get('completed_at'))})
                if starts:
                    row['run']['jobStartedAt'] = iso(min(starts))
                    row['run']['queueSeconds'] = max(0, int((min(starts)-run_start(latest)).total_seconds()))
                if starts and ends and latest.get('status') == 'completed':
                    row['run']['durationSeconds'] = max(0, int((max(ends)-min(starts)).total_seconds()))
            except Exception:
                row['jobEvidenceUnavailable'] = True
        if not complete:
            row['inspectionError'] = 'incomplete_execution_history'
            row['note'] = '이력 조회가 불완전하여 최신 실행·정상 여부를 확정하지 않습니다.'
            return row
        # The new main build must not be judged against the previous release's
        # publication artifact. Keep it pending until its own job completes.
        if (kind == 'production' and latest and latest.get('head_sha') == head and
                latest.get('status') in policy.ACTIVE):
            row['dataState'] = 'running'
            row['note'] = '현재 main 배포가 진행 중입니다. 해당 커밋의 서버 반영 및 검증을 기다립니다.'
            return row
        if kind == 'capture':
            row['readOnly'] = True
            row['observationOnly'] = True
            if row['paused']:
                row['dataState'] = 'paused'
                return row
            candidate = next((r for r in runs if r.get('status') == 'completed'), None)
            if candidate:
                stage = 'observation_evidence'
                candidate, capture = policy.current_capture_evidence(runs, due, at, getter)
                row['evidenceRun'] = run_view(candidate)
                row['evidence'] = capture
                row['sourceTimes'] = capture['sourceTimes']
                row['counts'] = {'chartsComplete': capture['chartsComplete'], 'requiredCharts': 2}
                row['lastVerifiedAt'] = capture['checkedAt'] if capture['currentComplete'] else None
                row['dataState'] = 'healthy' if capture['currentComplete'] else 'attention'
                row['note'] = '원문 시각과 두 차트 100개 순위를 검증한 독립 관측입니다. 사이트 게시 완료와 별도입니다.'
            else:
                row['dataState'] = 'attention'
                row['note'] = '현재 독립 관측 증거가 없습니다. 미관측 시간의 순위는 생성하지 않습니다.'
            return row
        success = next((r for r in runs if r.get('status') == 'completed' and r.get('conclusion') == 'success'), None)
        if kind == 'production':
            success = next((r for r in runs if r.get('status') == 'completed' and r.get('head_sha') == head), None)
        if not success:
            row['note'] = '검증 가능한 성공 실행이 없습니다.'
            row['dataState'] = 'attention' if runs else 'unknown'
            return row
        row['evidenceRun'] = run_view(success)
        stage = 'publication_evidence'
        if kind == 'watchdog':
            report = extra_artifact(getter, success, 'batch-watchdog', 'batch-watchdog.json')
            row['evidence'] = {'checkedAt': iso(stamp(report['checkedAt'])), 'status': report.get('state')}
            row['dataState'] = watchdog_state(report, at)
            row['recoveryStates'] = [{'batch': item.get('batch'), 'state': item.get('state'),
                'dueAt': safe_time(item.get('dueAt')), 'dispatchedAt': safe_time(item.get('dispatchedAt'))}
                for item in report.get('batches', []) if isinstance(item, dict) and item.get('batch') in policy.SPECS]
            row['note'] = '복구 점검 결과이며 개별 배치 게시 완료를 의미하지 않습니다.'
        elif kind == 'production':
            report, evidence_run, lineage = read_production_evidence(getter, success, at)
            good = production_evidence_ok(report, evidence_run, head, at)
            row['evidenceRun'] = run_view(evidence_run)
            row['publicationLineage'] = lineage
            row['publicationVerified'] = good
            row['ancillaryFailure'] = bool(good and success.get('conclusion') != 'success')
            row['lastVerifiedAt'] = safe_time(report.get('verifiedAt')) if good else None
            row['dataState'] = 'healthy' if good else 'attention'
            row['evidence'] = {'status': report.get('status'), 'checkedAt': safe_time(report.get('checkedAt')),
                               'commit': report.get('commit'), 'currentMain': head, 'browserVerified': report.get('browserVerified') is True}
            row['note'] = ('운영 배포·재조회는 검증됐지만 같은 실행의 후속 작업이 실패/취소됐습니다. 전체 재배포와 구분합니다.'
                           if row['ancillaryFailure'] else '현재 main의 배포·재조회·접근 차단·쓰기 잠금 반환 증거를 대조했습니다.')
        elif kind == 'catalog':
            row['dataState'] = 'unknown'
            row['note'] = '수집 실행과 사이트 배포는 별개입니다. 콘텐츠 전용 게시 증거가 없어 반영 완료로 표시하지 않습니다.'
        elif due is None:
            row['dataState'] = 'paused'
            row['note'] = '예정된 수집 제외 시간입니다.'
        else:
            files = policy.artifact_files(success, prefix, filename, getter)
            pubname = {'albums':'albums-publication.json', 'music':'music-publication.json',
                       'schedule':'schedule-publication.json', 'history':'history-publication.json',
                       'playground':'playground-publication.json'}[kind]
            pub = files.get(pubname, {})
            good = policy.evidence_ok(kind, files, due, at)
            if kind == 'schedule' and pub.get('verifiedReadback') is not True:
                good = False
            row['dataState'] = 'healthy' if good else 'attention'
            row['evidence'] = {k: pub[k] for k in ('status','generatedAt','publishedAt','readbackAt','verifiedReadback','evidenceVersion') if k in pub}
            row['lastVerifiedAt'] = safe_time(pub.get('readbackAt')) if pub.get('verifiedReadback') is True else None
            sources = pub.get('collectionHealth', {}).get('sources', {}) if kind == 'schedule' else pub.get('sourceStates', {})
            for key, value in sources.items():
                row['sources'].append({'name': str(key)[:80], 'state': str(value.get('state', 'unknown') if isinstance(value, dict) else value)[:40],
                                       'lastSuccessAt': safe_time(value.get('lastSuccessAt')) if isinstance(value, dict) else None})
            row['counts'] = {k: pub[k] for k in ('questionCount','added','updated','collectedCount') if type(pub.get(k)) is int and pub[k] >= 0}
            if kind == 'playground' and good and isinstance(pub.get('growth'),dict):
                growth=pub['growth']
                row['growth']={key:growth[key] for key in ('state','lastAdditionAt','todayAdded','addedThisRun','dailyTarget','readyCount','reserveDays','consecutiveZeroDays','alerts','candidateCounts') if key in growth}
                row['counts'].update({key:growth[key] for key in ('todayAdded','readyCount','consecutiveZeroDays') if type(growth.get(key)) is int and growth[key]>=0})
                row['note']='게시 검증과 신규 문제 확보를 별도로 표시합니다. 신규 추가 0건을 정상 증설로 간주하지 않습니다.'
            if kind == 'albums':
                from album_hourly import coverage, allowed
                cov = coverage(files.get('albums/snapshot.json', {}), at, hours=168)
                persisted = ((pub.get('status') == 'published' and pub.get('verifiedReadback') is True) or
                             (files.get('albums-restore.json', {}).get('status') == 'restored' and
                              files.get('albums-restore.json', {}).get('source') == 'cumulative-feed'))
                row['evidence']['persisted'] = persisted
                row['chartSlots'] = []
                missing = {k: set(v['missingSlots']) for k,v in cov['charts'].items()}
                current = at.replace(minute=0, second=0, microsecond=0)
                for i in reversed(range(168)):
                    hour = current-timedelta(hours=i)
                    count = sum(iso(hour) not in slots for slots in missing.values())
                    state = ('paused' if not allowed(hour) else 'unknown' if not persisted else
                             'healthy' if count == len(missing) else 'partial' if count else 'missing')
                    row['chartSlots'].append({'at': iso(hour), 'state': state})
                row['sourceTimes'] = {k: safe_time(v['sourceAt']) for k,v in cov['charts'].items()}
                row['historicalGapCount'] = sum(v['state'] in ('partial','missing') for v in row['chartSlots'])
                row['note'] = '과거 관측 공백은 현재 회차 장애와 별도로 표시합니다. 미관측 순위는 생성하지 않습니다.'
            elif not good:
                row['note'] = '현재 예정 회차의 수집·게시·서버 재조회 증거가 모두 충족되지 않았습니다.'
            if at-due < timedelta(minutes=5) and not good:
                row['dataState'] = 'running'
                row['note'] = '예정 시각 직후 5분 유예 중입니다. 아직 누락으로 판정하지 않습니다.'
    except Exception as exc:
        row['inspectionError'] = ('publication_evidence_missing' if isinstance(exc, policy.EvidenceUnavailable)
                                  else stage+'_failed')
        row['dataState'] = 'unknown'
        row['note'] = '실행 또는 결과 증거를 확인하지 못했습니다. 정상으로 간주하지 않습니다.'
        row['errorCode'] = type(exc).__name__
    finally:
        if row['paused']:
            row['dataState'] = 'paused'
        row['state'] = row_state(row)
    return row


def merge_observations(previous, current):
    """Keep only schema-known observations, never raw artifacts or made-up backfill."""
    at = stamp(current['checkedAt'])
    observations = {}
    old = previous.get('observations', []) if isinstance(previous, dict) and previous.get('schemaVersion') == 1 else []
    if not isinstance(old, list) or len(old) > 30000:
        raise ValueError('Invalid observation history')
    for item in old:
        if not isinstance(item, dict) or item.get('batch') not in META or item.get('state') not in ('healthy','attention','unknown','paused','running'):
            continue
        try:
            checked = stamp(item['checkedAt'])
            slot = stamp(item['dueAt'])
        except (KeyError, ValueError):
            continue
        if at-timedelta(days=90) <= checked <= at and slot <= checked:
            observations[(item['batch'], iso(slot))] = {k:item.get(k) for k in ('batch','dueAt','checkedAt','state','runId')}
    for row in current['batches']:
        if row.get('dueAt'):
            # A failed inspection cannot erase an already verified slot outcome.
            key = (row['key'], row['dueAt'])
            if row.get('dataState') == 'unknown' and key in observations:
                continue
            observations[key] = {'batch':row['key'],'dueAt':row['dueAt'],
                'checkedAt':current['checkedAt'],'state':row['dataState'],
                'runId':(row.get('evidenceRun') or {}).get('id')}
    current['observations'] = sorted(observations.values(), key=lambda v:v['dueAt'])[-30000:]
    merge_slot_ledger(previous, current, policy.due_slot)
    return preserve_verified(previous, current)


def attach_catalog_publication(doc, at, getter):
    """Bind catalog freshness to the exact verified deployed build, not a green job."""
    row=next(r for r in doc['batches'] if r['key']=='catalog')
    production=next(r for r in doc['batches'] if r['key']=='production')
    if row.get('paused') or not row.get('listingComplete'):
        return
    # This is a known publication wait, not an inspector failure or a verified
    # catalog release. No old successful deployment may certify the new commit.
    prod_run = production.get('run') or {}
    if (production.get('dataState') == 'running' and prod_run.get('status') in policy.ACTIVE and
            prod_run.get('commit') == doc['mainCommit']):
        row['dataState'] = 'running'
        row['note'] = '현재 main 운영 배포가 진행 중입니다. 새 콘텐츠 게시 증거 검증을 기다립니다.'
        row['state'] = row_state(row)
        return
    if production.get('dataState') != 'healthy':
        return
    evidence=production.get('evidenceRun') or {}
    try:
        run={'id':evidence['id'],'run_attempt':evidence['attempt'],'head_sha':evidence['commit']}
        lineage=production.get('publicationLineage') or {}
        if lineage.get('viaReference'):
            # Reassert the immutable source artifact binding for catalog content
            # rather than resolving the same name to a replacement artifact.
            expected={'expected_artifact_id':lineage['sourceArtifactId'],
                      'expected_artifact_digest':lineage['sourceArtifactDigest']}
            pub=read_json_artifact(getter,run,'isegye-production-evidence','auth-deployment.json',**expected)
            catalog=read_json_artifact(getter,run,'isegye-production-evidence','catalog-publication.json',**expected)
        else:
            pub=extra_artifact(getter,run,'isegye-production-evidence','auth-deployment.json')
            catalog=extra_artifact(getter,run,'isegye-production-evidence','catalog-publication.json')
        raw=(json.dumps(catalog,ensure_ascii=False,sort_keys=True)+'\n').encode()
        if (pub.get('catalogBundleVerified') is not True or pub.get('catalogEvidenceSha256')!=hashlib.sha256(raw).hexdigest()
            or catalog.get('schemaVersion')!=1 or catalog.get('mode')!='production'
            or catalog.get('buildCommit')!=doc['mainCommit'] or catalog.get('publicationClaimed') is not False):
            raise ValueError('Unverified deployed catalog')
        from refresh_catalog_videos import channels
        expected={c['key'] for c in channels()}
        sources=catalog.get('sources',[])
        if len(sources)!=len(expected) or {c.get('name') for c in sources}!=expected:
            raise ValueError('Incomplete catalog source identity')
        due=stamp(row['dueAt'])
        good=policy.recent(catalog.get('sourceAt'),due,at) and all(c.get('state')=='ok' and
            policy.recent(c.get('lastSuccessAt'),due,at) for c in sources)
        verified=stamp(pub['verifiedAt'])
        if verified>at+timedelta(minutes=2) or stamp(catalog['builtAt'])>verified:
            raise ValueError('Invalid catalog publication order')
        row['dataState']='healthy' if good else 'attention'
        row['sources']=[{'name':c['name'],'state':c.get('state','unknown'),
            'lastSuccessAt':safe_time(c.get('lastSuccessAt'))} for c in sources]
        row['evidenceRun']=evidence
        if lineage:
            row['publicationLineage']=lineage
        row['lastVerifiedAt']=iso(verified)
        row['evidence']={'status':'deployed_and_verified','generatedAt':safe_time(catalog['sourceAt']),
            'readbackAt':iso(verified),'verifiedReadback':True,'commit':catalog['buildCommit']}
        row['counts']={k:catalog[k] for k in ('channelCount','videoCount') if type(catalog.get(k)) is int}
        row['note']='콘텐츠 실행 기록과 별도로, 운영 배포의 실제 파일 해시 및 채널별 확인 시각을 대조했습니다.'
        if not all(c.get('historicalComplete') is True for c in sources):
            row['note']+=' 일부 채널의 전체 과거 영상 수집은 아직 완료되지 않았습니다.'
    except Exception as exc:
        row['dataState']='unknown'
        row['inspectionError']='catalog_evidence_failed'
        row['note']='콘텐츠 게시 근거가 없거나 검증되지 않았습니다. 실행 성공을 반영 완료로 간주하지 않습니다.'
        row['errorCode']=type(exc).__name__
    row['state']=row_state(row)


def collect(getter=None, at=None):
    getter = getter or ReadOnlyGitHub()
    at = at or datetime.now(UTC)
    head_error = False
    try:
        head = getter('git/ref/heads/main')['object']['sha']
        if not re.fullmatch('[0-9a-f]{40}', head):
            raise ValueError('Invalid main identity')
    except Exception:
        # Keep the exact checked-out identity; never pretend the remote lookup succeeded.
        head = os.getenv('MONITOR_COMMIT') or os.getenv('GITHUB_SHA', '')
        if not re.fullmatch('[0-9a-f]{40}', head):
            raise ValueError('Main identity unavailable')
        head_error = True
    doc = {'schemaVersion':1, 'mode':'production', 'checkedAt':iso(at), 'timezone':'Asia/Seoul',
           'source':'GitHub Actions + verified artifacts', 'repository':REPO, 'mainCommit':head,
           'staleAfterSeconds':2700, 'readOnly':True, 'scheduledRefreshEnabled':True, 'refreshEverySeconds':600,
           'collectorRunId':os.getenv('GITHUB_RUN_ID'), 'collectorCommit':os.getenv('MONITOR_COMMIT') or os.getenv('GITHUB_SHA'),
           'batches':[inspect(kind, at, head, getter) for kind in META]}
    if head_error:
        for row in doc['batches']:
            row.update(dataState='unknown', state='unknown', inspectionError='main_identity_query_failed',
                       note='현재 운영 커밋을 확인하지 못했습니다. 이전 검증 결과와 구분합니다.')
    else:
        attach_catalog_publication(doc, at, getter)
    doc['collectorHealth'] = inspection_health(doc)
    doc['finishedAt'] = iso(datetime.now(UTC))
    doc['apiCalls'] = getattr(getter, 'calls', None)
    return merge_observations({}, doc)


def main():
    if os.getenv('GITHUB_REPOSITORY') != REPO or os.getenv('GITHUB_REF') != 'refs/heads/main':
        raise ValueError('Main branch required')
    output = ROOT/'monitoring-dist'
    output.mkdir(exist_ok=True)
    doc = collect()
    (output/'data.json').write_text(json.dumps(doc, ensure_ascii=False, separators=(',',':'))+'\n')
    # Public Actions artifacts contain aggregate diagnostics only, never data.json.
    report = {'checkedAt':doc['checkedAt'], 'commit':doc['collectorCommit'],
              'apiCalls':doc['apiCalls'], 'collectorHealth':doc['collectorHealth']}
    (ROOT/'batch-monitor-inspection.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report, ensure_ascii=False))
    return 1 if doc['collectorHealth']['state'] == 'failed' else 0

if __name__ == '__main__':
    sys.exit(main())
