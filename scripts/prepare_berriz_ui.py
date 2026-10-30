"""One-use explicit UI transformation; removed before the integration commit."""
from pathlib import Path
import json,hashlib
p=Path(__file__).resolve().parents[1]
f=p/'schedule/core.js';s=f.read_text()
s=s.replace("u.hostname==='parable-asia.com'||", "u.hostname==='parable-asia.com'||(u.hostname==='berriz.in'&&!u.search&&!u.hash&&/^\\/ko\\/isegyeidol\\/(?:notice\\/[1-9]\\d*|calendar)\\/?$/.test(u.pathname))||")
s=s.replace("'parable-web','naver-search'];", "'parable-web','naver-search','berriz-notice','berriz-calendar'];")
s=s.replace('data.sources.length!==5||new Set(data.sources.map(x=>x.id)).size!==5','data.sources.length<5||data.sources.length>7||new Set(data.sources.map(x=>x.id)).size!==data.sources.length||sourceIds.slice(0,5).some(id=>!data.sources.some(x=>x.id===id))')
s=s.replace('   ids.add(r.id);',"   if(r.sourceId.startsWith('berriz-')&&!scheduleBerrizApproved(r))throw new Error('invalid official Berriz item');\n   ids.add(r.id);")
s=s.replace("(source==='official'?!['fan-roundup','naver-search'].includes(r.sourceId):r.sourceId==='fan-roundup')", "(source==='berriz'?['berriz-notice','berriz-calendar'].includes(r.sourceId):source==='official'?!['fan-roundup','naver-search'].includes(r.sourceId):r.sourceId==='fan-roundup')")
s=s.replace("const key=r.sourceUrl+'|'", "const key=(r.calendarId||r.sourceUrl)+'|'")
s=s.replace(" return rows.filter(r=>r.sourceId==='parable-web'", " return rows.filter(r=>scheduleBerrizApproved(r)||r.sourceId==='parable-web'")
s=s.replace('  const identity=r.internal||r.sourceUrl||r.id;', '  const identity=r.internal||r.calendarId||r.sourceUrl||r.id;')
s=s.replace("a.date.localeCompare(b.date)||(a.time||'99:99')", "a.date.localeCompare(b.date)||schedulePriority(a)-schedulePriority(b)||(a.time||'99:99')")
s+='''
// Berriz is authoritative only for the two selected official menus, never fan posts.
export function scheduleBerrizApproved(r) {
 const url=scheduleSafeUrl(r.sourceUrl);if(!url||!url.startsWith('https://berriz.in/ko/isegyeidol/'))return false;
 if(r.sourceId==='berriz-notice'){const match=url.match(/\\/notice\\/([1-9]\\d*)\\/$/);return !!match&&r.id==='berriz-notice-'+match[1];}
 return r.sourceId==='berriz-calendar'&&url==='https://berriz.in/ko/isegyeidol/calendar/'&&typeof r.calendarId==='string'&&/^[A-Za-z0-9_-]{1,80}$/.test(r.calendarId)&&r.id==='berriz-calendar-'+r.calendarId&&r.dateBasis==='official_calendar';
}
export function schedulePriority(r) {
 const url=scheduleSafeUrl(r.sourceUrl);
 if(url?.startsWith('https://berriz.in/ko/isegyeidol/notice/')&&r.sourceId==='berriz-notice')return 0;
 if(url==='https://berriz.in/ko/isegyeidol/calendar/'&&r.sourceId==='berriz-calendar')return 1;
 return 2;
}
''';f.write_text(s)
f=p/'schedule/ui.js';s=f.read_text()
s=s.replace('const scheduleLabels={',"const scheduleLabels={'berriz-notice':'베리즈 · 소속사 공지','berriz-calendar':'베리즈 · 공식 캘린더',")
s=s.replace('const scheduleKinds={',"const scheduleKinds={anniversary:'생일·기념일',")
s=s.replace("['cafe-members','cafe-agency','parable-web'].includes(r.sourceId)", "['cafe-members','cafe-agency','parable-web','berriz-notice'].includes(r.sourceId)")
s=s.replace("['official','fan'].includes(params.get('source'))", "['official','fan','berriz'].includes(params.get('source'))")
s=s.replace(' return `<span class="sc-badge', ' return `${r.sourceId===\'berriz-notice\'?\'<span class="sc-important">★ 소속사 중요 공지</span>\':\'\'}<span class="sc-badge',1)
s=s.replace('data-schedule-record-type="${e(r.type)}"','data-priority="${schedulePriority(r)}" data-schedule-record-type="${e(r.type)}"')
s=s.replace("${r.type==='notice'?' · 게시일 기준':r.time?' · '+e(r.time):' · 시간 미정'}", "${r.type==='notice'?' · 게시일 기준':r.time?' · '+e(r.time):r.allDay?' · 종일':' · 시간 미정'}")
s=s.replace('${annotations.length?', '${r.endAt?`<p class="sc-related">기간: ${e(formatDate(r.date))} ~ ${e(formatDate(schedulePostedDate(r.endAt)))} · 세부 종료 시각은 원문 확인</p>`:\'\'}${annotations.length?')
a=s.index('function scheduleFreshness(){');b=s.index('function scheduleAgenda(',a)
s=s[:a]+'''function scheduleFreshness(){
 const formatTime=x=>x?new Intl.DateTimeFormat('ko-KR',{timeZone:'Asia/Seoul',month:'numeric',day:'numeric',hour:'2-digit',minute:'2-digit',hour12:false}).format(new Date(x))+' KST':'확인 전';
 const ids=['berriz-notice','berriz-calendar','parable-web'],names=['베리즈 공지','베리즈 캘린더','패러블 뉴스룸'];
 const states=ids.map((id,i)=>{const s=scheduleSnapshot.sources.find(x=>x.id===id);const stale=!s?.lastSuccessAt||Date.now()-Date.parse(s.lastSuccessAt)>7200000;return names[i]+' '+formatTime(s?.lastSuccessAt)+(s?.state!=='ok'?' · 갱신 확인 필요':stale?' · 확인 지연':'');});
 return `<div class="sc-sync"><div><b>${scheduleLoading?'저장된 소식 확인 중':scheduleLoadFailed?'갱신 확인 실패 · 이전 자료 표시':'공식 소식 확인 현황'}</b><span>${states.map(e).join('<br>')}</span></div><button class="filter-button" type="button" data-schedule-refresh ${scheduleLoading?'disabled':''}>${scheduleLoading?'확인 중…':'새로고침'}</button></div>`;
}
'''+s[b:]
s=s.replace("['all','전체 출처'],['official','멤버·소속사 공지']", "['all','전체 출처'],['berriz','베리즈 공식만'],['official','멤버·소속사 공지']")
s=s.replace('단체·공통</span></div>','단체·공통</span><span class="sc-important">★ 소속사 중요 공지 우선</span></div>')
s=s.replace('data-member-tone="${scheduleMemberTone(x.members)}" title=', 'data-member-tone="${scheduleMemberTone(x.members)}" data-priority="${schedulePriority(x)}" title=')
s=s.replace('<span class="sc-chip-member">${e(scheduleMemberLabel(x))}', '<span class="sc-chip-member">${x.sourceId===\'berriz-notice\'?\'★ \':\'\'}${e(scheduleMemberLabel(x))}')
s=s.replace('여섯 멤버·소속사가 작성한 것으로 확인된 공지와 지정된 뱅온정보만 표시합니다.','베리즈의 이세계아이돌 공식 공지·캘린더, 여섯 멤버·소속사가 작성한 것으로 확인된 공지와 지정된 뱅온정보만 표시합니다. 베리즈 소속사 공지를 같은 날짜의 최우선 항목으로 안내합니다.')
s=s.replace('카페 본문 정기 크롤링은 사용하지 않습니다. 패러블 공식 뉴스룸은 자동 갱신하며, 새로고침은 사이트에 저장된 결과를 다시 읽습니다.','베리즈는 로그인 없이 공개된 두 메뉴만 확인하며 팬 게시판·회원 전용 본문·이미지는 수집하지 않습니다. 캘린더는 지난달부터 다음 두 달까지 확인하고 기존 기록은 보존합니다. 카페 본문 정기 크롤링은 사용하지 않습니다. 베리즈와 패러블 공식 뉴스룸은 매시간 갱신을 시도하며 실행이 지연될 수 있습니다. 새로고침은 사이트에 저장된 결과를 다시 읽습니다.')
f.write_text(s)
f=p/'schedule/theme.css';f.write_text(f.read_text()+'''
/* Source priority augments, never replaces, the six member colors. */
.sc-important{display:inline-flex;align-items:center;font-size:14px;font-weight:750;color:#794c00;background:#fff1c7;border:1px solid #c29a45;border-radius:6px;padding:3px 8px;line-height:1.5}
.sc-chip[data-priority="0"]{box-shadow:inset 0 0 0 1px #b18429;font-weight:700}
.sc-event[data-priority="0"]{border-top:3px solid #b18429}
[data-theme=dark] .sc-important{color:#ffe4a0;background:#413619;border-color:#cfab58}
[data-theme=dark] .sc-chip[data-priority="0"]{box-shadow:inset 0 0 0 1px #cfab58}
[data-theme=dark] .sc-event[data-priority="0"]{border-top-color:#cfab58}
''')
f=p/'review/home-release.json';d=json.loads(f.read_text());d['sourceHashes']={k:hashlib.sha256((p/k).read_bytes()).hexdigest() for k in d['sourceHashes']};d['sourceHashes']['scripts/berriz_feed.py']=hashlib.sha256((p/'scripts/berriz_feed.py').read_bytes()).hexdigest();d['presentationUpdates'].append({'requestedAt':'2026-10-30','scope':'Berriz public official notices and calendar, highest agency notice priority within the existing full-width calendar; no fan posts, membership content, login changes or recent-news panel.'});f.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
