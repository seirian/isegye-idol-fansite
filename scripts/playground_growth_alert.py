"""One deduplicated content-supply incident, separate from execution failures.

No hosting/search credentials are accepted here. Only verified publication
results can open or resolve an incident. Repeated runs never add comments.
"""
from pathlib import Path
import json
import os
import subprocess

ROOT = Path(__file__).resolve().parents[1]
REPO = 'seirian/isegye-idol-fansite'
TITLE = '[놀이터] 신규 문제 확보 및 검수 대기분 확인'


def reconcile(publication, gh):
    if publication.get('status') != 'published' or publication.get('verifiedReadback') is not True:
        return 'unverified_no_change'
    growth = publication.get('growth', {})
    if growth.get('schemaVersion') != 1:
        return 'legacy_no_change'
    rows = json.loads(gh('issue', 'list', '--state', 'open', '--limit', '100',
                         '--search', '"'+TITLE+'" in:title', '--json', 'number,title'))
    existing = next((row['number'] for row in rows if row['title'] == TITLE), None)
    alerts = growth.get('alerts', [])
    if alerts and not existing:
        body = ('검증된 일배치 게시 결과에서 문제 공급 점검이 필요합니다.\n\n'
                f"유형: {', '.join(alerts)}\n"
                f"오늘 신규 추가: {growth['todayAdded']}문제\n"
                f"검수 완료 대기: {growth['readyCount']}문제\n"
                f"연속 추가 0일: {growth['consecutiveZeroDays']}일\n\n"
                '관리자 배치 모니터링의 문제은행 증설 상태에서 최신 수치를 확인합니다.\n'
                '검수된 사실을 reserve.json에 보충하고 중복·근거·지문 검사를 통과시켜야 합니다.\n'
                '실행 빈도를 높이거나 미확인 커뮤니티 답안을 자동 게시하지 마세요.\n'
                '같은 문제가 계속되는 동안 이 이슈를 반복 생성하거나 댓글로 알리지 않습니다.')
        gh('issue', 'create', '--title', TITLE, '--body', body)
        return 'opened'
    if not alerts and existing and growth.get('todayAdded', 0) > 0:
        gh('issue', 'close', str(existing), '--comment',
           '신규 문제가 실제 게시되었고 검수 대기분 부족 경고도 해소되었습니다. 서버 재조회 검증 완료.')
        return 'resolved'
    return 'unchanged'


def main():
    if os.getenv('PRODUCTION_PAUSED') == 'true' or os.getenv('ISEGYE_PLAYGROUND_PAUSED') == 'true':
        return 0
    p = ROOT/'playground-publication.json'
    if not p.exists():
        return 0
    pub = json.loads(p.read_text())
    growth = pub.get('growth', {})
    if growth.get('alerts'):
        print('::warning::Playground content supply needs review: '+', '.join(growth['alerts']))
    if (os.getenv('GITHUB_REPOSITORY') != REPO or os.getenv('GITHUB_REF') != 'refs/heads/main'
            or not os.getenv('GH_TOKEN')):
        raise ValueError('Main-only incident reporter')
    def gh(*args):
        return subprocess.run(['gh', *args, '--repo', REPO], check=True, text=True,
                              capture_output=True, timeout=45).stdout
    try:
        print('Playground content incident: '+reconcile(pub, gh))
    except Exception as exc:
        # Incident transport failures must not turn successful persistence into
        # a failure/recovery loop. They remain explicit workflow warnings.
        print('::warning::Playground incident reporting unavailable: '+type(exc).__name__)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
