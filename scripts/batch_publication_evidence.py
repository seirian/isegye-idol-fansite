"""Shared, bounded evidence checks for recovery and read-only monitoring.

Only JSON data is read. Artifacts are bound to a main run, its exact attempt,
size and SHA-256 before any outcome can be considered verified.
"""
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
import re
import stat
import zipfile

REPO = 'seirian/isegye-idol-fansite'
UTC = timezone.utc


class EvidenceUnavailable(ValueError):
    """Absent or expired evidence is unknown, never a successful publication."""


class ArtifactUnavailable(EvidenceUnavailable):
    """No exact-name artifact exists; distinct from a missing/expired member."""


def clock(value):
    if not isinstance(value, str):
        raise ValueError('Evidence clock required')
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise ValueError('Evidence timezone required')
    return result.astimezone(UTC)


def read_json_artifact(getter, run, prefix, filename, *, fixed_name=False,
                       max_archive=48_000_000, max_member=2_000_000,
                       expected_artifact_id=None, expected_artifact_digest=None):
    expected = prefix if fixed_name else f"{prefix}-{run['id']}-{run['run_attempt']}"
    entries, seen, total = [], set(), None
    for page in range(1, 11):
        path = f"actions/runs/{run['id']}/artifacts?per_page=100" + (f'&page={page}' if page > 1 else '')
        result = getter(path)
        batch = result.get('artifacts')
        count = result.get('total_count')
        if (not isinstance(batch, list) or len(batch) > 100 or type(count) is not int or count < 0
                or (total is not None and total != count)):
            raise ValueError('Incomplete or changed artifact listing')
        total = count
        for artifact in batch:
            if not isinstance(artifact, dict):
                raise ValueError('Invalid artifact entry')
            aid = artifact.get('id')
            if type(aid) is not int or aid <= 0 or aid in seen:
                raise ValueError('Invalid artifact identity')
            seen.add(aid)
            if artifact.get('name') == expected:
                entries.append(artifact)
        if len(batch) < 100 or len(seen) == total:
            if total != len(seen):
                raise ValueError('Incomplete artifact listing')
            break
    else:
        raise ValueError('Artifact listing budget exceeded')
    if not entries:
        raise ArtifactUnavailable('Current attempt evidence unavailable')
    if len(entries) != 1:
        raise ValueError('Ambiguous current attempt evidence')
    artifact = entries[0]
    if artifact.get('expired'):
        raise EvidenceUnavailable('Current attempt evidence expired')
    if ((expected_artifact_id is not None and artifact['id'] != expected_artifact_id)
            or (expected_artifact_digest is not None and artifact.get('digest') != expected_artifact_digest)):
        raise ValueError('Referenced artifact identity mismatch')
    provenance = artifact.get('workflow_run', {})
    if (provenance.get('id') != run['id'] or provenance.get('head_sha') != run['head_sha']
            or provenance.get('head_branch') != 'main'
            or (run.get('head_branch') is not None and run['head_branch'] != 'main')
            or (run.get('repository') is not None and run['repository'].get('full_name') != REPO)
            or (run.get('head_repository') is not None and run['head_repository'].get('full_name') != REPO)
            or type(artifact.get('size_in_bytes')) is not int
            or not 0 < artifact['size_in_bytes'] <= max_archive):
        raise ValueError('Artifact provenance mismatch')
    raw = getter(f"actions/artifacts/{artifact['id']}/zip", binary=True)
    if (not isinstance(raw, bytes) or len(raw) != artifact['size_in_bytes']
            or artifact.get('digest') != 'sha256:' + hashlib.sha256(raw).hexdigest()):
        raise ValueError('Artifact digest mismatch')
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        selected = [item for item in archive.infolist() if item.filename == filename]
        if not selected:
            raise EvidenceUnavailable('Evidence member unavailable')
        if (len(selected) != 1 or not 0 < selected[0].file_size <= max_member
                or stat.S_ISLNK(selected[0].external_attr >> 16)):
            raise ValueError('Invalid evidence member')
        value = json.loads(archive.read(selected[0]))
    if not isinstance(value, dict):
        raise ValueError('Invalid evidence JSON')
    return value


def _production_run_identity(run, current, attempt):
    if (not isinstance(run, dict) or type(run.get('id')) is not int or run['id'] != current['id']
            or type(run.get('run_attempt')) is not int or run['run_attempt'] != attempt
            or run.get('status') != 'completed' or run.get('head_sha') != current['head_sha']
            or run.get('head_branch') != 'main' or run.get('path') != '.github/workflows/production.yml'
            or run.get('repository', {}).get('full_name') != REPO
            or run.get('head_repository', {}).get('full_name') != REPO
            or (current.get('workflow_id') is not None and run.get('workflow_id') != current['workflow_id'])
            or not run.get('run_started_at')):
        raise ValueError('Referenced production attempt provenance mismatch')
    clock(run['run_started_at'])


def read_production_evidence(getter, run, at):
    """Read this attempt, or its explicit monitor-only rerun publication lineage.

    An older successful run is never searched. Only absence of the exact current
    deployment artifact permits a reference; an existing failed, corrupt, expired
    or incomplete artifact cannot be replaced by previous publication evidence.
    """
    prefix = 'isegye-production-evidence'
    lineage = {'runId': run['id'], 'executionAttempt': run['run_attempt'],
               'sourceAttempt': run['run_attempt'], 'viaReference': False}
    try:
        report = read_json_artifact(getter, run, prefix, 'auth-deployment.json')
        return report, run, lineage
    except ArtifactUnavailable:
        if run['run_attempt'] <= 1:
            raise
    _production_run_identity(run, run, run['run_attempt'])
    reference = read_json_artifact(getter, run, 'isegye-production-monitor-evidence',
                                  'production-publication-reference.json', max_member=20_000)
    attempt, prepare = reference.get('sourceAttempt'), reference.get('sourcePrepareAttempt')
    artifact_id, digest = reference.get('sourceArtifactId'), reference.get('sourceArtifactDigest')
    if (reference.get('schemaVersion') != 1 or reference.get('repository') != REPO
            or reference.get('workflow') != 'production.yml' or reference.get('runId') != run['id']
            or type(reference.get('runId')) is not int or reference.get('runAttempt') != run['run_attempt']
            or type(reference.get('runAttempt')) is not int or reference.get('commit') != run['head_sha']
            or not isinstance(run['head_sha'], str) or not re.fullmatch(r'[0-9a-f]{40}', run['head_sha'])
            or type(attempt) is not int or not 1 <= attempt < run['run_attempt']
            or type(prepare) is not int or not 1 <= prepare <= attempt
            or type(reference.get('currentPrepareAttempt')) is not int
            or reference['currentPrepareAttempt'] != prepare
            or type(artifact_id) is not int or artifact_id <= 0
            or not isinstance(digest, str) or not re.fullmatch(r'sha256:[0-9a-f]{64}', digest)):
        raise ValueError('Invalid production publication reference')
    referred_at = clock(reference['createdAt'])
    current_start = clock(run['run_started_at'])
    if not current_start-timedelta(minutes=2) <= referred_at <= at+timedelta(minutes=2):
        raise ValueError('Production reference clock mismatch')
    source = getter(f"actions/runs/{run['id']}/attempts/{attempt}")
    _production_run_identity(source, run, attempt)
    if clock(source['run_started_at']) > current_start:
        raise ValueError('Production reference attempt order mismatch')
    expected = {'expected_artifact_id': artifact_id, 'expected_artifact_digest': digest}
    candidate = read_json_artifact(getter, source, prefix, 'production-candidate-verified.json', **expected)
    if (candidate.get('status') != 'candidate_verified' or candidate.get('repository') != REPO
            or candidate.get('commit') != run['head_sha'] or type(candidate.get('runId')) is not int
            or candidate['runId'] != run['id'] or type(candidate.get('prepareAttempt')) is not int
            or candidate['prepareAttempt'] != prepare or type(candidate.get('consumerAttempt')) is not int
            or candidate['consumerAttempt'] != attempt
            or not re.fullmatch(r'[0-9a-f]{64}', str(candidate.get('archiveSha256', '')))):
        raise ValueError('Production reference candidate lineage mismatch')
    report = read_json_artifact(getter, source, prefix, 'auth-deployment.json', **expected)
    if (not production_evidence_ok(report, source, run['head_sha'], at)
            or clock(report['verifiedAt']) > referred_at+timedelta(minutes=2)):
        raise ValueError('Referenced production publication is not verified')
    lineage.update(sourceAttempt=attempt, sourcePrepareAttempt=prepare, viaReference=True,
                   sourceArtifactId=artifact_id, sourceArtifactDigest=digest)
    return report, source, lineage


def production_evidence_ok(report, run, head, at):
    """An ancillary job failure cannot erase a verified completed deployment.

maintenanceActive is the existing account/access policy, NOT the deploy lock;
it must never be forced false by a reliability checker.
"""
    if (run.get('status') != 'completed' or report.get('status') != 'deployed_and_verified'
            or report.get('commit') != head or run.get('head_sha') != head
            or not isinstance(head, str) or not re.fullmatch(r'[0-9a-f]{40}', head)
            or any(report.get(key) is not True for key in
                   ('browserVerified', 'privatePathsBlocked', 'protectedFilesUnchanged', 'lockRemoved'))
            or report.get('manualRecoveryRequired') or report.get('previousReleaseRestored')):
        return False
    try:
        checked, verified = clock(report['checkedAt']), clock(report['verifiedAt'])
        started = clock(run.get('run_started_at') or run['created_at'])
        return started-timedelta(minutes=2) <= checked <= verified <= at+timedelta(minutes=2)
    except (KeyError, ValueError, TypeError):
        return False


CAPTURE_SOURCES = {
    'melon_top100': 'https://www.melon.com/chart/index.htm',
    'melon_hot100': 'https://www.melon.com/chart/hot100/index.htm?chartType=D100',
}


def capture_summary(data, run, due, at):
    """Validate capture observations including partial/failed outcomes.

The fixed historical artifact name is safe only with the document's exact
run/attempt binding. Never expose its full original 100-song tables in the UI.
"""
    if (data.get('schemaVersion') != 1 or data.get('repository') != REPO
            or data.get('workflow') != 'melon-chart-capture.yml'
            or data.get('sourceType') != 'melon_public_full_chart'
            or type(data.get('runId')) is not int or data['runId'] != run['id']
            or type(data.get('runAttempt')) is not int or data['runAttempt'] != run['run_attempt']
            or not isinstance(data.get('charts'), dict)
            or set(data['charts']) - set(CAPTURE_SOURCES)):
        raise ValueError('Untrusted capture metadata')
    checked = clock(data['checkedAt'])
    started = clock(run.get('run_started_at') or run['created_at'])
    if not started-timedelta(minutes=2) <= checked <= at+timedelta(minutes=2):
        raise ValueError('Untrusted capture clock')
    charts = data['charts']
    expected = 'complete' if len(charts) == 2 else 'partial' if charts else 'failed'
    if data.get('status') == 'scheduled_night_pause':
        local = checked.astimezone(timezone(timedelta(hours=9)))
        if charts or not 1 <= local.hour < 7:
            raise ValueError('Invalid capture night pause')
    elif data.get('status') != expected:
        raise ValueError('Capture health mismatch')
    source_times = {}
    for kind, chart in charts.items():
        if not isinstance(chart, dict):
            raise ValueError('Invalid capture chart')
        source_at = clock(chart['sourceAt'])
        local_hour = source_at.astimezone(timezone(timedelta(hours=9))).hour
        rows = chart.get('rows')
        if (chart.get('source') != CAPTURE_SOURCES[kind]
                or not re.fullmatch(r'[0-9a-f]{64}', str(chart.get('responseSha256', '')))
                or source_at != checked.replace(minute=0, second=0, microsecond=0)
                or 1 <= local_hour < 7 or not isinstance(rows, list) or len(rows) != 100):
            raise ValueError('Invalid capture source or hour')
        ids, ranks = set(), set()
        for item in rows:
            if (not isinstance(item, list) or len(item) != 2
                    or not isinstance(item[0], str) or not re.fullmatch(r'[0-9]{1,12}', item[0])
                    or type(item[1]) is not int or not 1 <= item[1] <= 100
                    or item[0] in ids or item[1] in ranks):
                raise ValueError('Invalid or duplicate chart rank')
            ids.add(item[0]); ranks.add(item[1])
        source_times[kind] = source_at.isoformat()
    complete = (data.get('status') == 'complete' and due is not None
                and all(clock(value) == due for value in source_times.values()))
    return {'status': data['status'], 'checkedAt': checked.isoformat(),
            'sourceTimes': source_times, 'chartsComplete': len(charts),
            'currentComplete': complete, 'observationOnly': True,
            'publicationVerified': False}


def read_capture_evidence(getter, run, due, at):
    data = read_json_artifact(getter, run, 'melon-chart-capture', 'melon-chart-capture.json',
                              fixed_name=True, max_archive=150_000, max_member=100_000)
    return capture_summary(data, run, due, at)
