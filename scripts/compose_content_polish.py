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
    a=code.index('function mediaCard(r)');b=code.index('function rowCard(r)',a)
    card=code[a:b]
    card=one(card,'function mediaCard(r){const masked=',"""function mediaCard(r){const original=r.kind==='video'?safeExternal(r.url):null;
 const direct=original?'<a class="content-origin-link" href="'+esc(original)+'" target="_blank" rel="noopener noreferrer" aria-label="원본 영상 새 탭에서 보기: '+esc(r.title)+'" title="원본 영상 바로가기">'+icon('external')+'</a>':'';
 const masked=""")
    card=one(card,"${prefs.watched.includes(r.key)?badge('직접 시청 표시','good'):''}","")
    card=one(card,"${saveButton(r,masked)}</div></div>","${direct}${saveButton(r,masked)}</div></div>")
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
    return code[:a]+code[b:]
def css():
    return """
.content-origin-link{display:inline-flex;align-items:center;justify-content:center;flex:0 0 36px;width:36px;height:36px;border:1px solid var(--line,#61536b);border-radius:11px;color:inherit;text-decoration:none}
.content-origin-link svg{width:18px;height:18px}
.content-origin-link:hover,.content-origin-link:focus-visible{border-color:#ef99b7;background:rgba(238,150,183,.12);outline-offset:2px}
"""
