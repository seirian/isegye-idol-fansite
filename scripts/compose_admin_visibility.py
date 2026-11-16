"""Role-separated operating views and public data derivatives; source archives untouched."""
from pathlib import Path
import json,re,subprocess
from review_2nd_polish import one
import build_review_1st as first
ROOT=Path(__file__).resolve().parents[1]
POLICY=json.loads((ROOT/'auth/public-view-policy.json').read_text())

def project(value,context=''):
    if isinstance(value,list):
        child={'sources':'collector_source','channels':'channel'}.get(context,'')
        return [project(item,child) for item in value]
    if not isinstance(value,dict):return value
    if context=='providers':return {}
    allowed=POLICY.get({'collector_source':'sourceKeys','channel':'channelKeys'}.get(context,''))
    return {key:project(item,key) for key,item in value.items()
            if key not in POLICY['removeKeys'] and (allowed is None or key in allowed)}

def function(code,name):
    match=re.search(r'^function '+re.escape(name)+r'\(',code,re.M)
    if not match:raise ValueError('Missing function '+name)
    start=match.start();line_end=code.index('\n',start)
    if code[start:line_end].rstrip().endswith('}'):return code[start:line_end]
    end=re.search(r'^}',code[line_end:],re.M)
    if not end:raise ValueError('Missing function end '+name)
    return code[start:line_end+end.end()]

def javascript_projection(code):
    # Only whole JSON constants, never executable text or legal prose.
    def transform(match):
        name,raw=match.group(1),match.group(2)
        try:value=json.loads(raw)
        except (ValueError,TypeError):return match.group(0)
        return 'const '+name+'='+first.script_json(project(value))+';'
    return re.sub(r'^const ([A-Z_]+)=(.*);$',transform,code,flags=re.M)

def admin_module(provider,freshness):
    # ES modules must not depend on the application's classic-script globals.
    # Live getters keep diagnostics current when the runtime feed is replaced.
    body=(ROOT/'site/admin-operations.js').read_text()+'\n'+provider+'\n'+freshness+'\n'
    body=re.sub(r'\balbumInsights\b','context.albumInsights',body)
    body=re.sub(r'\balbumApiState\b','context.albumApiState',body)
    return ("export function createViews(context) {\n"
            "const {D,esc,stamp,badge,sourceNames,FeedValidators,patch,aiData,albumFreeServiceStatus,albumFreshness}=context;\n"
            +body+
            'return Object.freeze({status,coverage,notice,schedule,history,demoLink,providers:albumProviderPanel,flow:albumFlowFreshness,project:()=>`<p><a href="https://github.com/seirian/isegye-idol-fansite" target="_blank" rel="noopener noreferrer">관리자 · 프로젝트 저장소</a></p>`,editHistory:()=>`<p><a href="https://github.com/seirian/isegye-idol-fansite/commits/main/src/data.js" target="_blank" rel="noopener noreferrer">관리자 · 공개 편집 이력</a></p>`});\n}\n')

def compose(out):
    app=(out/'src/app.js').read_text();legacy=(out/'src/production-ui.js').read_text()
    if 'const IsegyeOps=' in app:raise ValueError('Visibility composition must run once')
    provider=function(app,'albumProviderPanel');freshness=function(app,'albumFlowFreshness')
    private=admin_module(provider,freshness)
    public=(ROOT/'site/public-status.js').read_text()
    app=one(app,function(app,'statusView'),function(public,'statusView'))
    app=one(app,provider,"function albumProviderPanel(s) { return IsegyeOps.panel('providers',s); }")
    app=one(app,freshness,"function albumFlowFreshness(kind) { return IsegyeOps.allowed()?IsegyeOps.panel('flow',kind):publicAlbumFreshness(kind); }")
    flow=function(app,'albumFlowView')
    changed=one(flow,"const demo=p.get('demo')==='1';","const demo=IsegyeOps.allowed()&&p.get('demo')==='1';")
    link='<a class="text-link small" href="${esc(patch({demo:demo?null:\'1\',metric:kind}))}" aria-pressed="${demo}">${demo?\'실제 데이터로 돌아가기\':\'그래프 예시 보기\'}</a>'
    changed=one(changed,link,"${IsegyeOps.panel('demoLink',demo,kind)}")
    changed=one(changed,'앨범 배치는 00시 및 07~23시 정각(KST)에 실행하며 01:00~06:59에는 중지합니다. 20분·40분에는 누락된 현재 시간만 보충합니다. 게시 실패 시 이전 데이터를 유지합니다.','확인되지 않은 시점의 순위는 추정하지 않습니다.')
    app=one(app,flow,changed)
    coverage='${D.scope.videoCoverageComplete===D.scope.videoChannelCount?"등록된 전체 공개 영상 검증 완료":`영상 ${rs.length}건 표시 · 전체 과거 영상 수집 ${D.scope.videoCoverageComplete||0}/${D.scope.videoChannelCount||22}채널 완료. 아직 일부만 수록됐을 수 있습니다.`}'
    app=one(app,coverage,'현재 확인된 공개 영상만 수록합니다. 일부 과거 영상이 포함되지 않았을 수 있습니다.')
    old=function(app,'contentView');app=one(app,old,old.replace('${pg.html}',"${pg.html}${IsegyeOps.panel('coverage')}",1))
    notice='<section class="section">${sectionHead(\'변경 이력\')}<div class="notice-box">공지의 수정 전·후 본문 이력은 아직 수집하지 않습니다. 현재 원문에서 최신 안내를 확인하세요. 변경 이력 기능은 다음 운영 연동 검토 항목입니다.</div></section>'
    app=one(app,notice,'<p class="data-note">공지 내용의 수정·취소 여부와 최신 안내는 공식 원문에서 확인해 주세요.</p>${IsegyeOps.panel(\'notice\')}')
    app=one(app,'${dateText(D.scope.historyCheckedAt)}에 확인한 주요 활동을 보여주는 검토 스냅샷입니다. 월간 활동 수집·이후 추가된 기록은 이 파일에서 실시간 갱신하지 않습니다.','자료 기준 ${dateText(D.scope.historyCheckedAt)} · 확인된 주요 활동을 정리한 목록입니다. 모든 활동을 포함한 목록은 아니며 자세한 내용은 각 기록의 출처를 확인해 주세요.')
    history=function(app,'historyView');app=one(app,history,history.replace('</div>`;}','</div>${IsegyeOps.panel(\'history\')}`;}',1))
    schedule=function(app,'scheduleView');app=one(app,schedule,schedule.replace('</div>`;\n}',"</div>${IsegyeOps.panel('schedule')}`;\n}",1))
    app=app.replace('검토 시점 수집 스냅샷','마지막 확인 자료').replace('공개 API 확인 전','확인된 정보 없음').replace('공개 응답 확인 전','확인된 정보 없음').replace('음원 정보 우선순위 적용','음원 제공처 기준')
    app=app.replace('기존 검증 목록을 통합한 검토본입니다.','확인된 공개 자료를 모은 목록입니다.').replace('개를 바탕으로 한 검토용 목록입니다.','개의 공개 자료를 모은 목록입니다.').replace('공개 API 확인값','공개 조회수·좋아요 기준').replace('YouTube Data API.','YouTube 공개 정보.').replace('Apple iTunes Search API ·','Apple 음악 정보 ·').replace('이전 스냅샷','이전 확인 자료').replace("'수집 전'","'확인된 기록 없음'").replace('API 확인 전</span>','재생시간 확인 전</span>')
    app=one(app,'로그인 계정과 동기화되지 않으며 운영 사이트의 기존 저장함은 변경하지 않습니다.','로그인 계정과 동기화되지 않습니다.')
    app=one(app,'수집 상태와 공식 원문을 함께 확인해 주세요.','공식 원문에서 최신 안내를 확인해 주세요.')
    legacy=one(legacy,'채널마다 수집 시점의 최근 공개 영상 3개를 보여줍니다.','채널마다 마지막으로 확인한 최근 공개 영상 3개를 보여줍니다.')
    legacy=one(legacy,'공식 채널의 공개 영상 기준으로 일배치에서 등록했습니다. 영상 공개일과 음반 발매일은 다를 수 있습니다.','공식 채널의 공개 영상 정보입니다. 영상 공개일과 앨범 발매일은 다를 수 있습니다.')
    legacy=legacy.replace('발매곡·커버·음반·공식 음악 영상','발매곡·커버·앨범·공식 음악 영상')
    app=(ROOT/'site/admin-access.js').read_text()+'\n'+app
    app=one(app,'if(!location.hash)history.replaceState',function(public,'publicAlbumFreshness')+'\nif(!location.hash)history.replaceState')
    old='전체 과거 영상 수집 완료 여부는 ${complete}/${channels}개 채널로 기록되어 있습니다. '
    legacy=one(legacy,old,'일부 과거 영상이 포함되지 않았을 수 있습니다. ')
    legacy=one(legacy,'${channels}개 채널을 대상으로 관리하며,','공개 채널에서 확인한 자료를 모으며,')
    legacy=one(legacy,' · <a href="https://github.com/seirian/isegye-idol-fansite">프로젝트 저장소</a>','')
    legacy=one(legacy,'<h2>자료 수집·갱신 기준</h2>',"${typeof IsegyeOps==='undefined'?'':IsegyeOps.panel('coverage')}<h2>자료 수집·갱신 기준</h2>")
    legacy=one(legacy,'<h2>출처와 검수 이력</h2>','<h2>자료 출처</h2>')
    legacy=one(legacy,'<div class="section">${external(`${SITE.repo}/commits/develop/src/data.js`,\'공개 편집 이력\')}</div>',"${typeof IsegyeOps==='undefined'?'':IsegyeOps.panel('editHistory')}")
    feeds=(out/'src/runtime-feeds.js').read_text()
    feeds=one(feeds,"const message=FeedValidators.scheduleCollectionMessage({sources:D.sources,collectionHealth:D.scope.collectionHealth});","const message='';")
    feeds=feeds.replace('갱신 확인 실패 · 마지막 검증 자료를 표시합니다. ','새 정보를 확인하지 못해 마지막 확인 자료를 표시합니다. ').replace("'자료 생성 '","'자료 기준 '")
    (out/'src/app.js').write_text(app)
    (out/'src/production-ui.js').write_text(legacy)
    (out/'src/runtime-feeds.js').write_text(feeds)
    (out/'src/admin-operations.js').write_text(private)
    with (out/'src/styles.css').open('a') as handle:handle.write('\n'+(ROOT/'site/admin-visibility.css').read_text())
    for original,target in POLICY['publicFiles'].items():
        path=out/original
        if not path.is_file():raise ValueError('Missing public projection input '+original)
        raw=path.read_text()
        result=json.dumps(project(json.loads(raw)),ensure_ascii=False,separators=(',',':'))+'\n' if path.suffix=='.json' else javascript_projection(raw)
        (out/target).write_text(result)
    meta=json.loads((out/'build-info.json').read_text());meta['adminVisibility']={'schemaVersion':1,'default':'public','serverEnforced':True,'protectedResources':POLICY['protectedPaths'],'projectedResources':POLICY['publicFiles']}
    (out/'build-info.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n')
    for name in ['app.js','admin-operations.js',*[Path(path).name for path in POLICY['publicFiles'].values() if path.endswith('.js')]]:
        subprocess.run(['node','--check',str(out/'src'/name)],check=True)
    return meta
