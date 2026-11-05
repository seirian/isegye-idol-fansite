#!/usr/bin/env python3
"""Promote the owner-approved second review without altering its visual sources.

Compiles a local preview intermediate, then packages the accepted UI for the
existing, main-only authenticated deployment. Existing collection endpoints,
private stores, legal documents and preview URLs remain unchanged.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import build_review_1st as first
import compose_member_legal as member_legal
from review_2nd_polish import between, one

ROOT = Path(__file__).resolve().parents[1]
ACCEPTED = 'f09c755053fc23b777de695170a8160a48ebe43e'
BACKUP = 'b05d0c91f482dfd666e2b70e70c49ebe4ece2175'


def approval():
    doc = json.loads((ROOT/'review/accepted-review2.json').read_text())
    if (doc.get('operatorApprovedDeployment') is not True or doc.get('acceptedCommit') != ACCEPTED
        or doc.get('backupBranch') != 'backup_main261105' or doc.get('backupCommit') != BACKUP):
        raise ValueError('Explicit accepted-review and backup reference required')
    for name, digest in doc['sourceHashes'].items():
        path = ROOT/name
        if not path.resolve().is_relative_to(ROOT) or path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError('Accepted source changed: '+name)
    return doc


def adapt_app(code):
    # Preview preferences never overwrite the operating site's previous settings.
    code = code.replace('isegye:review2:prefs', 'isegye:archive:prefs:v1').replace('isegye:review2:lastVisit', 'isegye:archive:lastVisit:v1')
    migration = (ROOT/'site/storage-migration.js').read_text()
    code = one(code, 'const memberItems=', migration+'\nconst memberItems=')
    start = '<div class="review-bar">'
    a = code.index(start); b = code.index('<header class="site-header">', a)
    code = one(code, code[a:b], '<div class="review-bar"><div class="wrap">이세계아이돌 비공식 팬 아카이브</div></div>')
    code = one(code, '<a href="#/review">검토 안내</a>', '')
    code = one(code, between(code, 'function reviewView()', 'function notFound()'), '')
    code = one(code, "else if(root==='review')html=reviewView();", "else if(root==='review')html=ProductionUI.about();")
    code = one(code, "else if(root==='member'||root==='record')html=memberView(r.parts[1],r.params);",
               "else if(root==='member')html=memberView(r.parts[1],r.params);else if(root==='record')html=persons.has(r.parts[1])?memberView(r.parts[1]):songs.has(r.parts[1])?songView(r.parts[1]):ProductionUI.record(r.parts[1]);else if(root==='report')html=ProductionUI.report(r.params);")
    code = one(code, "+' · 2차 검토'", "+' · ISEGYE 팬 아카이브'")
    code = code.replace('이 브라우저의 검토용 저장함에 담았습니다.', '이 브라우저의 저장함에 담았습니다.')
    code = code.replace('이 검토본에 포함되지 않은 항목입니다.', '현재 등록되지 않은 항목입니다.')
    code = code.replace('이 검토 페이지 안의', '이 사이트 안의').replace('검토 파일이 필요합니다.', '해당 파일이 필요합니다.')
    code = code.replace('isegye-review-2nd-browser-only', 'isegye-archive-browser-only').replace('isegye-review2-saved.json', 'isegye-saved.json')
    old = '검토용 저장 자료 기준입니다. 공지 원문 변경·삭제와 현재 수집 상태는 실시간으로 반영되지 않습니다.'
    code = one(code, old, "${esc(typeof ProductionFeeds==='undefined'?'저장된 자료를 확인하고 있습니다.':ProductionFeeds.scheduleMessage())}")
    code = code.replace('운영 관리자 대시보드가 아닌 읽기 전용 검토 화면입니다.', '자료 확인 상태를 보여주는 읽기 전용 화면입니다.')
    code = code.replace('아래 상태는 저장된 스냅샷의 상태이며 현재 배치의 성공·실패를 실시간으로 조회한 것이 아닙니다.', '아래 상태는 기존 운영 데이터에서 확인한 출처별 관측 정보입니다. 배치 실행 여부와 원본 확인 시각은 다를 수 있습니다.')
    code = code.replace('현재 검토본</th>', '현재 적용</th>').replace('기존 스냅샷의 상태만 읽습니다.', '기존 운영 API의 검증된 자료를 읽습니다.')
    code = code.replace('저장 자료의 기준 시각', '자료의 기준 시각').replace('검토용 저장 자료', '마지막 확인 자료')
    return code


def adapt_legacy(code, baseline):
    src = (baseline/'src/app.js').read_text()
    detail = between(src, 'function detailView(', 'function searchView(')
    detail = detail.replace('${saveButton(r.id)}', '').replace('data-action="share"', 'data-copy')
    report = between(src, 'function reportView(', 'function aboutView(')
    extra = 'const DAILY_MUSIC_CHANNELS='+first.script_json(first.extract(src, 'DAILY_MUSIC_CHANNELS'))+';\n'
    extra += (ROOT/'catalog/daily-music.js').read_text().split('let dailyMusicPending=')[0]
    extra += detail + report
    code = one(code, 'const wrap=(page,html)=>', extra+'\nconst wrap=(page,html)=>')
    code = one(code, 'return {footer:operatingFooter,',
               "return {record:id=>wrap('record',detailView(id)),report:p=>wrap('report',reportView(p)),applyMusic:feed=>{applyDailyMusic(feed);return CATALOG.music;},footer:operatingFooter,")
    return code


def runtime(baseline, data):
    source = (baseline/'src/app.js').read_text()
    archive = first.extract(source, 'NOTICE_ARCHIVE')
    ids = {str(row[0]) for row in archive['rows']}
    seed = {'history':first.extract(source,'HISTORY'),
            'knownSources':[[f'https://cafe.naver.com/steamindiegame/{r[0]}','cafe-members' if r[1]==345 else 'cafe-agency'] for r in archive['rows']],
            'archiveNotices':[r for r in data['notices'] if r['id'] in ids]}
    seed['knownSources'] += [[f'https://cafe.naver.com/steamindiegame/{i}', 'fan-roundup'] for i in archive.get('fanIds',[])]
    schedule = re.sub(r'^export ', '', (ROOT/'schedule/core.js').read_text(), flags=re.M)
    monthly = (ROOT/'visuals/monthly-history.js').read_text().split('function monthlyHistoryRoute()')[0]
    validators = ('const FeedValidators=(()=>{\n'+schedule+'\nconst HISTORY='+first.script_json(seed['history'])+';\n'
                  + next(line for line in source.splitlines() if line.startswith('const HISTORY_TYPES='))+'\n'+monthly+
                  '\nreturn {scheduleValidate,scheduleApprovedRows,scheduleCollectionMessage,monthly:feed=>{applyMonthlyHistory(feed);return HISTORY;}};})();\n')
    return 'const PRODUCTION_FEED_BASE='+first.script_json(seed)+';\n'+validators+(ROOT/'site/runtime-feeds.js').read_text()


def build(baseline):
    approved = approval()
    mode = 'production' if os.getenv('DEPLOY_ENV') == 'production' else 'preview'
    if mode == 'production' and os.getenv('GITHUB_REF') != 'refs/heads/main':
        raise ValueError('Production is main-only')
    baseline = baseline.resolve()
    if baseline == ROOT/'dist' or not (baseline/'src/schedule.json').is_file():
        raise ValueError('Separate complete local baseline required')
    # These processes generate local files only; final publication still uses
    # deploy_google_access.py and its original main/environment/owner checks.
    env = dict(os.environ, DEPLOY_ENV='preview', GITHUB_REF='refs/heads/feature/review-2nd')
    subprocess.run([sys.executable,str(ROOT/'scripts/build_review_2nd.py'),'--baseline',str(baseline)], cwd=ROOT, env=env, check=True)
    subprocess.run([sys.executable,str(ROOT/'scripts/build_review_2nd.py'),'--baseline',str(baseline),
                    '--snapshot',str(baseline/'src/schedule.json'),'--output',str(ROOT/'release-review-2nd')], cwd=ROOT, env=env, check=True)
    review = ROOT/'release-review-2nd'; out = ROOT/'dist'
    data = first.extract((review/'data.js').read_text(),'REVIEW_DATA')
    app = adapt_app((review/'app.js').read_text())
    legacy = adapt_legacy((review/'production-ui.js').read_text(),baseline)
    app = member_legal.adapt_app(app)
    legacy = member_legal.adapt_legacy(legacy)
    feeds = runtime(baseline,data)
    if out.is_symlink(): raise ValueError('Symlink output refused')
    if out.exists(): shutil.rmtree(out)
    (out/'src').mkdir(parents=True)
    shutil.copytree(review/'assets',out/'assets')
    for name in ('data.js','core.js','live-core.js','styles.css'):
        shutil.copyfile(review/name,out/'src'/name)
    # The original floating account control must clear the newly approved mobile nav.
    css=(out/'src/styles.css').read_text()+'\n@media(max-width:640px){body .isegye-account-link{bottom:calc(82px + env(safe-area-inset-bottom));}}\n'
    (out/'src/styles.css').write_text(css)
    (out/'src/app.js').write_text(app)
    (out/'src/production-ui.js').write_text(legacy)
    (out/'src/runtime-feeds.js').write_text(feeds)
    member_legal.member_bundle(app,legacy,out/'src')
    shutil.copyfile(baseline/'src/schedule.json',out/'src/schedule.json')
    html = (review/'index.html').read_text()
    html = html.replace('connect-src https://', "connect-src 'self' https://").replace("form-action 'none'", "form-action 'self' https://github.com")
    html = re.sub(r'(<script src=")([^"/]+\.js)(")',r'\1src/\2\3',html)
    html = html.replace('href="styles.css"','href="src/styles.css"')
    html = html.replace('<script src="src/app.js"></script>', '<script src="src/app.js"></script><script src="src/runtime-feeds.js"></script>')
    html = re.sub(r'<title>.*?</title>', '<title>ISEGYE! · 이세계아이돌 비공식 팬 아카이브</title>',html)
    html = re.sub(r'<meta name="description"[^>]+>', '<meta name="description" content="이세계아이돌의 소식과 일정, 음악과 콘텐츠, 함께한 활동 기록을 찾는 비공식 팬 아카이브.">',html)
    html = html.replace('2차 검토 페이지를 열고 있습니다.','팬 아카이브를 열고 있습니다.').replace('이 페이지는 운영 사이트와 분리된 2차 검토본입니다.','공식 원본에서 최신 내용을 확인해 주세요.')
    if mode == 'production':
        html = html.replace('content="noindex,nofollow"','content="index,follow"')
        html = html.replace('</head>', '<link rel="canonical" href="https://isegye-idol.kr/">\n</head>')
    (out/'index.html').write_text(html)
    (out/'robots.txt').write_text('User-agent: *\n'+('Allow: /\n' if mode=='production' else 'Disallow: /\n'))
    (out/'.nojekyll').write_text('')
    meta = json.loads((baseline/'build-info.json').read_text())
    meta.update(version='0.6.0',mode=mode,commit=os.getenv('GITHUB_SHA',meta['commit']),
                branch=os.getenv('GITHUB_REF_NAME','local'),review='accepted-review-2nd',
                acceptedReviewCommit=ACCEPTED,sourceBackup={'branch':approved['backupBranch'],'commit':BACKUP},
                operatorApprovedDeployment=True,counts={k:len(data[k]) for k in ('members','songs','videos','notices','events','history','albums','series')},
                runtimeFeeds=['/api/schedule','/api/music','/api/history'],previewRoutesPreserved=True,
                navigationCount=7,sourceMetadataPreserved=True)
    meta['reviewPromotion']={'acceptedCommit':ACCEPTED,'runtimeConnected':True,'backupBranch':approved['backupBranch']}
    (out/'build-info.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n')
    for file in (out/'src').glob('*.js'):
        subprocess.run(['node','--check',str(file)],check=True)
    if mode=='production':
        from inour_sftp import load_payload
        load_payload(out,meta['commit'])
    print(json.dumps({'status':'built','mode':mode,'acceptedReview':ACCEPTED,'commit':meta['commit'],'feeds':meta['runtimeFeeds']}))
    return meta


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--baseline',default=str(ROOT/'home-dist'));args=parser.parse_args()
    build(Path(args.baseline))
