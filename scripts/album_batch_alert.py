"""Credential-isolated, deduplicated GitHub incident reporting for album runs."""
from pathlib import Path
import json
import os
import subprocess
from album_hourly import ROOT, allowed

TITLE = '[배치] 앨범 시간별 차트 갱신 장애'
REPO = 'seirian/isegye-idol-fansite'

def read(name):
    path = ROOT/name
    return json.loads(path.read_text()) if path.is_file() else {}

def main():
    gate, pub, cov = read('albums-gate.json'), read('albums-publication.json'), read('albums-coverage.json')
    collection = read('albums-collection.json')
    if gate.get('allowed') is not True or not allowed() or collection.get('status') == 'paused' or pub.get('status') == 'paused':
        print('Album batch paused; no incident notification.')
        return 0
    failed = os.getenv('ALBUM_JOB_STATUS') == 'failure' or pub.get('status') == 'failed'
    good = not failed and (pub.get('verifiedReadback') is True or cov.get('currentComplete') is True)
    if not failed and not good:
        return 0
    missing = {k: v.get('missingSlots', []) for k, v in cov.get('charts', {}).items()}
    link = 'https://github.com/'+REPO+'/actions/runs/'+os.getenv('GITHUB_RUN_ID','')
    body = ('앨범 시간배치 '+('실패' if failed else '현재 시간 게시 확인')+'\n\n'+link+'\n\n'
            +'게시 상태: '+str(pub.get('status','already_current' if good else 'not_published'))+'\n'
            +'실패 단계: '+str(pub.get('failedStage','workflow' if failed else 'none'))+'\n'
            +'현재 시간 기준: '+str(cov.get('slot','not_checked'))+'\n'
            +'최근 24시간의 주간 관측 누락(01~06시 제외):\n```json\n'
            +json.dumps(missing, ensure_ascii=False, indent=2)+'\n```\n'
            +'복구는 검증된 기존 관측값만 병합합니다. 관측하지 못한 과거 순위는 추정하지 않습니다.\n')
    if os.getenv('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as out:
            out.write(body+'\n')
    if any(missing.values()):
        print('::warning::Historical daytime chart observation gaps remain; see albums-coverage.json.')
    if os.getenv('GITHUB_REPOSITORY') != REPO or os.getenv('GITHUB_REF') != 'refs/heads/main' or not os.getenv('GH_TOKEN'):
        raise ValueError('Main-only incident reporter')
    def gh(*args):
        return subprocess.run(['gh', *args, '--repo', REPO], check=True, text=True, capture_output=True, timeout=45).stdout
    try:
        rows = json.loads(gh('issue','list','--state','open','--limit','100','--json','number,title'))
        issue = next((r['number'] for r in rows if r['title'] == TITLE), None)
        if failed:
            if issue:
                gh('issue','edit',str(issue),'--body',body)
            else:
                gh('issue','create','--title',TITLE,'--body',body)
        elif issue:
            gh('issue','close',str(issue),'--comment',body)
        print('Album incident report reconciled; failure=' + str(failed))
    except Exception as exc:
        # Never print subprocess stderr (may contain authorization or signed URLs).
        print('::warning::Album incident reporting failed: '+type(exc).__name__)
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
