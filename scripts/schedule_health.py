"""Separate successful publication from freshness of each required source."""
from datetime import datetime, timezone
from pathlib import Path
import json
import os

REQUIRED = ('cafe-members', 'cafe-agency', 'fan-roundup', 'parable-web', 'berriz-notice', 'berriz-calendar')
MAX_AGE_SECONDS = 3 * 60 * 60


def assess(snapshot, now=None):
    now = now or snapshot.get('generatedAt')
    clock = datetime.fromisoformat(now.replace('Z', '+00:00'))
    if clock.tzinfo is None:
        raise ValueError('health requires an aware clock')
    sources = {s['id']: s for s in snapshot.get('sources', [])}
    rows, problems = {}, []
    for sid in REQUIRED:
        s = sources.get(sid, {})
        at = s.get('lastSuccessAt')
        try:
            dt = datetime.fromisoformat(at.replace('Z', '+00:00'))
            if dt.tzinfo is None: raise ValueError('naive')
            age = (clock - dt).total_seconds()
        except (AttributeError, ValueError, TypeError):
            age = None
        reasons = []
        if s.get('state') != 'ok': reasons.append('not_refreshed')
        if age is None: reasons.append('never_verified')
        elif age < 0: reasons.append('future_observation')
        elif age > MAX_AGE_SECONDS: reasons.append('stale')
        if sid in ('cafe-members', 'cafe-agency') and s.get('coverage', {}).get('complete') is not True:
            reasons.append('window_incomplete')
        if s.get('coverage', {}).get('gapFromKst'): reasons.append('uncovered_gap')
        state = 'complete' if not reasons else 'stale' if 'stale' in reasons else 'partial'
        rows[sid] = {'state': state, 'lastSuccessAt': at, 'lastAttemptAt': s.get('lastAttemptAt'),
                     'ageSeconds': round(age) if age is not None else None, 'reasons': reasons}
        if reasons: problems.append(sid)
    return {'state': 'complete' if not problems else 'partial', 'assessedAt': now,
            'maxAgeSeconds': MAX_AGE_SECONDS, 'sources': rows, 'incompleteSources': problems,
            'scope': 'current approved public windows; fan references are not confirmed schedules or an exhaustive history'}


def main():
    path = Path('schedule-publication.json')
    report = json.loads(path.read_text()) if path.exists() else {}
    published = report.get('status') == 'published'
    health = report.get('collectionHealth') or {'state': 'partial', 'incompleteSources': list(REQUIRED)}
    result = {'publicationStatus': report.get('status', 'not_published'), 'collectionHealth': health,
              'verified': published and health['state'] == 'complete'}
    Path('schedule-health.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    message = ('게시: ' + ('성공' if published else '실패') + ' / 필수 출처 갱신: ' +
               ('완료' if result['verified'] else '미완료') + '\n')
    print(message)
    for sid in health.get('incompleteSources', []):
        print('::warning::' + sid + ' — collection incomplete; previous verified data retained')
    summary = os.getenv('GITHUB_STEP_SUMMARY')
    if summary:
        with open(summary, 'a') as f:
            f.write('### 소식·일정 수집 상태\n' + message)
            for sid, state in health.get('sources', {}).items():
                f.write(f"- {sid}: {state['state']}; 마지막 검증 {state['lastSuccessAt'] or '없음'}\n")
    return 0 if result['verified'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
