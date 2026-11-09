"""Operating-only content links and verified official teaser."""
import json
from review_2nd_polish import one
TEASER={
'id':'1ELogGmCh9Q','key':'video:1ELogGmCh9Q','kind':'video',
'title':'ISEGYE IDOL (이세계아이돌) ‘REBELS’ MV TEASER',
'date':'2026-11-04','publishedAt':'2026-11-04T09:00:00+00:00',
'dateBasis':'official_video_published','dateLabel':'영상 공개일',
'url':'https://www.youtube.com/watch?v=1ELogGmCh9Q',
'members':['ine','jingburger','lilpa','jururu','gosegu','viichan'],
'memberBasis':'explicit_group','channelName':'ISEGYE IDOL','channelKey':'c2',
'channelUrl':'https://www.youtube.com/@isegyeidol_ofcl',
'category':'group','format':'공식 MV 티저','type':'official_teaser',
'summary':'2026년 11월 4일 공개된 REBELS 공식 MV 티저입니다. 정식 음원·MV와 구분합니다.',
'tags':['REBELS','Across Dimensions','공식 티저','MV TEASER']}
def adapt_app(code):
    snippet=("if(!REVIEW_DATA.videos.some(v=>v.id==='1ELogGmCh9Q'))"
      "REVIEW_DATA.videos.push("+json.dumps(TEASER,ensure_ascii=False,separators=(',',':'))+");\n")
    code=one(code,'const D=REVIEW_DATA,',snippet+'const D=REVIEW_DATA,')
    code=one(code,'function mediaCard(r)',"""function videoLengthClass(v){
 if(v.kind!=='video')return 'other';
 if(/(?:^|\\s)#shorts(?=\\s|$|[^a-z])/iu.test(v.title||''))return 'tagged';
 if(Number.isInteger(v.durationSeconds)&&v.durationSeconds>=0)return v.durationSeconds<=180?'candidate':'long';
 return 'unknown';
}
function mediaCard(r)""")
    a=code.index('function mediaCard(r)');b=code.index('function rowCard(r)',a)
    card=code[a:b]
    card=one(card,'function mediaCard(r){const masked=',"""function mediaCard(r){const original=r.kind==='video'?safeExternal(r.url):null;
 const direct=original?'<a class="content-origin-link" href="'+esc(original)+'" target="_blank" rel="noopener noreferrer" aria-label="원본 영상 새 탭에서 보기: '+esc(r.title)+'" title="원본 영상 바로가기">'+icon('external')+'</a>':'';
 const masked=""")
    card=one(card,"${prefs.watched.includes(r.key)?badge('직접 시청 표시','good'):''}","")
    card=one(card,"${badge(r.kind==='song'?(songTypes[r.type]||r.type):(r.format||'영상'),'neutral')}",
     "${badge(r.kind==='song'?(songTypes[r.type]||r.type):(r.format||'영상'),'neutral')}${r.kind==='video'&&videoLengthClass(r)==='tagged'?badge('쇼츠 #shorts','neutral'):r.kind==='video'&&videoLengthClass(r)==='candidate'?badge('짧은 영상 · 쇼츠 여부 미확인','neutral'):''}")
    card=one(card,"${saveButton(r,masked)}</div></div>","<span class=\"content-card-actions\">${direct}${saveButton(r,masked)}</span></div></div>")
    code=code[:a]+card+code[b:]
    a=code.index('function videoView(id)');b=code.index('function seriesView(id)',a)
    video=code[a:b]
    marker='<button class="button" data-watched='
    if video.count(marker)!=1:raise ValueError('Watched UI anchor moved')
    pos=video.index(marker);end=video.index('</button>',pos)+len('</button>')
    video=video[:pos]+video[end:]
    video=one(video,'<p class="data-note">링크를 열었다고 시청 완료로 처리하지 않습니다. 시청 표시는 이 브라우저에만 저장됩니다.</p>','')
    code=code[:a]+video+code[b:]
    a=code.index(" const watched=event.target.closest('[data-watched]');")
    b=code.index(" const reveal=event.target.closest('[data-reveal]');",a)
    code=code[:a]+code[b:]
    if 'function contentView(p)' not in code:
        return code  # The first-review fixture has only liveView.
    a=code.index('function contentView(p)');b=code.index('function videoView(id)',a)
    section=code[a:b]
    select="${choose('멤버 조건','match',[['any','선택 멤버 중 누구나'],['all','자료에 선택 멤버 모두 표기']],p.get('match')||'any')}"
    if section.count(select)!=1:raise ValueError('Content filter slot changed')
    section=section.replace(select,select+"${choose('영상 유형','length',[['all','전체 영상'],['shorts','쇼츠·짧은 영상'],['long','일반 길이 영상'],['unknown','길이 미확인']],p.get('length')||'all')}${choose('채널','channel',[['all','전체 채널'],...D.channels.filter(c=>tab==='replay'?c.kind==='다시보기':c.kind!=='다시보기').map(c=>[c.key,c.name])],p.get('channel')||'all')}${choose('정렬','sort',[['new','영상 공개 최신순'],['registered','아카이브 등록 최신순']],order)}")
    anchor='const pg=paginate(rs,p);body='
    if section.count(anchor)!=1:raise ValueError('Content sort slot changed')
    replacement="""rs=p.get('channel')&&p.get('channel')!=='all'?rs.filter(v=>v.channelKey===p.get('channel')):rs;
 const length=p.get('length')||'all';
 if(length==='shorts')rs=rs.filter(v=>['tagged','candidate'].includes(videoLengthClass(v)));
 else if(length==='long')rs=rs.filter(v=>videoLengthClass(v)==='long');
 else if(length==='unknown')rs=rs.filter(v=>videoLengthClass(v)==='unknown');
 const order=p.get('sort')==='registered'?'registered':'new';
 const dateValue=(v,property)=>Date.parse(property==='registered'?(v.firstSeenAt||v.checkedAt||v.publishedAt||v.date):(v.publishedAt||v.date))||0;
 rs.sort((x,y)=>dateValue(y,order)-dateValue(x,order)||x.id.localeCompare(y.id));
 const pg=paginate(rs,p);body="""
    section=section.replace(anchor,replacement,1)
    old_display='${pg.html}`;'
    new_display="${pg.html}<p class=\"data-note\">${D.scope.videoCoverageComplete===D.scope.videoChannelCount?\"등록된 전체 공개 영상 검증 완료\":`영상 ${rs.length}건 표시 · 전체 과거 영상 수집 ${D.scope.videoCoverageComplete||0}/${D.scope.videoChannelCount||22}채널 완료. 아직 일부만 수록됐을 수 있습니다.`}</p>`;"
    if section.count(old_display)!=1:raise ValueError('Video listing tail changed')
    section=section.replace(old_display,new_display,1)
    return code[:a]+section+code[b:]
def css():
    return """
.content-card-actions{display:inline-flex;align-items:center;gap:10px;margin-left:auto;flex-shrink:0}
.content-card-actions .content-origin-link{margin:0}
.content-card .card-bottom>span:first-child{min-width:0}
.content-origin-link{display:inline-flex;align-items:center;justify-content:center;flex:0 0 36px;width:36px;height:36px;border:1px solid var(--line,#61536b);border-radius:11px;color:inherit;text-decoration:none}
.content-origin-link svg{width:18px;height:18px}
.content-origin-link:hover,.content-origin-link:focus-visible{border-color:#ef99b7;background:rgba(238,150,183,.12);outline-offset:2px}
"""
