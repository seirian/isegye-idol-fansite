/* Publication records are explicitly separate from inferred/confirmed event dates. */
let scheduleSnapshot=SCHEDULE_SEED, scheduleLoading=false, scheduleLastFetch=0, scheduleLoadFailed=false;
const scheduleLabels={'cafe-members':'멤버 공지','cafe-agency':'패러블 공지','fan-roundup':'지정 뱅온정보','parable-web':'패러블 공식','archive':'등록 기록'};
const scheduleKinds={broadcast:'방송',break:'휴방',release:'음악 발매',event:'행사',notice:'공지 게시'};
const noticeHistoryRows=NOTICE_ARCHIVE.rows.map(([id,menu,author,members,title,publishedAt,generalized])=>({id:'notice-source-'+id,sourceId:menu===345?'cafe-members':'cafe-agency',sourceUrl:'https://cafe.naver.com/steamindiegame/'+id,members,title,publishedAt,checkedAt:NOTICE_ARCHIVE.checkedAt,detail:generalized?'세부 내용은 원문에서 확인하세요.':'공개 목록의 작성자·게시일 확인 · 본문 일정 미확인'}));
const noticeApprovedSources=new Map(noticeHistoryRows.map(r=>[r.sourceUrl,r.sourceId]));
const noticeByArticle=new Map(noticeHistoryRows.map(r=>[Number(r.sourceUrl.split('/').pop()),r]));
const noticeHistoryEvents=NOTICE_ARCHIVE.events.map(([id,date,time,type,certainty,status,detail])=>({...noticeByArticle.get(id),id:'notice-event-'+id+'-'+date,date,time,type,certainty,status,detail}));
let scheduleNewsCache=null,scheduleNewsInput=null;
function scheduleAllNews(){
 if(scheduleNewsInput===scheduleSnapshot)return scheduleNewsCache;
 const byUrl=new Map(noticeHistoryRows.map(r=>[r.sourceUrl,r]));
 for(const r of scheduleApprovedRows(scheduleSnapshot.news,noticeApprovedSources)){
  const known=byUrl.get(r.sourceUrl);
  if(!known||Date.parse(r.checkedAt)>=Date.parse(known.checkedAt))byUrl.set(r.sourceUrl,r);
 }
 scheduleNewsInput=scheduleSnapshot;scheduleNewsCache=[...byUrl.values()];return scheduleNewsCache;
}
function scheduleArchiveEvents(){
 return records.filter(r=>['event','music'].includes(r.kind)&&scheduleValidDate(r.date)).map(r=>({id:'archive-'+r.id,title:r.title,date:r.date,time:null,type:r.kind==='music'?'release':'event',certainty:'confirmed',status:'scheduled',sourceId:'archive',sourceUrl:SOURCES[r.sourceIds?.[0]]?.url||'',internal:recordUrl(r.id),members:r.members||[],checkedAt:SITE.reviewedAt+'T00:00:00+09:00'}));
}
function schedulePill(r){
 const fan=r.sourceId==='fan-roundup',unknown=r.certainty==='unknown',cancelled=r.status==='cancelled';
 return `<span class="sc-badge ${fan?'fan':''} ${r.certainty==='tentative'?'tentative':''}">${e(scheduleLabels[r.sourceId]||'출처 확인')}</span>${cancelled?'<span class="sc-badge cancelled">취소·변경</span>':unknown?'<span class="sc-badge tentative">미정</span>':r.certainty==='tentative'?'<span class="sc-badge tentative">미확정</span>':''}`;
}
function scheduleItem(r){
 const url=r.internal||scheduleSafeUrl(r.sourceUrl);const externalAttrs=r.internal?'':' target="_blank" rel="noopener noreferrer"';
 return `<article class="sc-event ${r.type==='notice'?'sc-notice-record ':''}${r.status==='cancelled'?'cancelled':''}" data-schedule-record-type="${e(r.type)}"><div class="sc-event-meta">${schedulePill(r)}<span>${e(scheduleKinds[r.type]||'소식')}${r.type==='notice'?' · 게시일 기준':r.time?' · '+e(r.time):r.type==='break'?'':' · 시간 미정'}</span></div><h3>${url?`<a href="${e(url)}"${externalAttrs}>${e(r.title)} ${icon(r.internal?'arrow':'external')}</a>`:e(r.title)}</h3><p>${e(memberNames(r.members))}</p>${r.detail?`<small>${e(r.detail)}</small>`:''}</article>`;
}
function scheduleNews(r){
 const url=scheduleSafeUrl(r.sourceUrl);return `<article class="sc-news-item"><div>${schedulePill(r)}<span>${r.publishedAt?'게시 '+e(formatDate(schedulePostedDate(r.publishedAt))):'게시일 미확인'}</span></div><h3><a href="${e(url||'#')}" target="_blank" rel="noopener noreferrer">${e(r.title)} ${icon('external')}</a></h3><p>${e(r.detail||'날짜를 확인할 수 없는 소식은 캘린더 일정으로 확정하지 않습니다.')}</p></article>`;
}
function scheduleFreshness(){
 const s=scheduleSnapshot.sources.find(x=>x.id==='parable-web');const last=s?.lastSuccessAt;
 const formatTime=x=>x?new Intl.DateTimeFormat('ko-KR',{timeZone:'Asia/Seoul',month:'numeric',day:'numeric',hour:'2-digit',minute:'2-digit',hour12:false}).format(new Date(x))+' KST':'아직 확인 전';
 const age=last?Date.now()-Date.parse(last):Infinity;
 return `<div class="sc-sync"><div><b>${scheduleLoading?'저장된 소식 확인 중':scheduleLoadFailed?'갱신 확인 실패 · 이전 자료 표시':age>7200000?'자동 수집 정보 확인 필요':'소식 자동 확인'}</b><span>패러블 최근 성공 ${e(formatTime(last))} · 작성자 미확인 검색글은 제외</span></div><button class="filter-button" type="button" data-schedule-refresh ${scheduleLoading?'disabled':''}>${scheduleLoading?'확인 중…':'새로고침'}</button></div>`;
}
function scheduleFeedView(params){
 const today=kstDate();let month=params.get('month')||today.slice(0,7);
 if(!/^20\d{2}-(0[1-9]|1[0-2])$/.test(month))month=today.slice(0,7);
 const [year,m]=month.split('-').map(Number);
 const chosen=params.get('date');const day=scheduleValidDate(chosen)&&chosen.startsWith(month)?chosen:month===today.slice(0,7)?today:month+'-01';
 const member=MEMBERS.some(x=>x.id===params.get('member'))?params.get('member'):'all';
 const source=['official','fan'].includes(params.get('source'))?params.get('source'):'all';
 const kind=Object.hasOwn(scheduleKinds,params.get('kind'))?params.get('kind'):'all';
 const filters={member,source,kind};const allNews=scheduleAllNews();
 const noticeRecords=allNews.filter(r=>['cafe-members','cafe-agency'].includes(r.sourceId)&&r.publishedAt).map(scheduleNoticeEvent);
 const events=scheduleFiltered(scheduleMergeEvents([...scheduleArchiveEvents(),...noticeHistoryEvents,...noticeRecords],scheduleApprovedRows(scheduleSnapshot.events,noticeApprovedSources)),filters);
 const forecasts=scheduleFiltered(scheduleApprovedRows(scheduleSnapshot.forecasts,noticeApprovedSources),filters);
 const selected=events.filter(r=>r.date===day),monthItems=events.filter(r=>r.date.startsWith(month));
 const noticeCount=selected.filter(r=>r.type==='notice').length;
 const daily=scheduleCurrentForecasts(forecasts,day);
 const news=scheduleFiltered(allNews,{member,source}).sort((a,b)=>Date.parse(b.publishedAt||b.checkedAt)-Date.parse(a.publishedAt||a.checkedAt));
 const page=Math.max(1,Math.min(Math.ceil(news.length/8)||1,Math.floor(Number(params.get('page')))||1));
 return heading('소식·일정','날짜별 일정과 멤버들의 공지 기록을 한눈에 확인하세요.','CALENDAR & NEWS')+`<div class="sc-page">${scheduleFreshness()}<div class="sc-filters"><a class="filter-button" href="#/schedule">오늘</a><label>연월<input type="month" id="schedule-month" data-schedule-month value="${month}" min="2021-08" aria-label="보고 싶은 연월"></label><a class="filter-button" data-first-notices href="#/schedule?month=${e(NOTICE_ARCHIVE.start.slice(0,7))}&date=${e(NOTICE_ARCHIVE.start)}&kind=notice">첫 공지</a><label>멤버<select id="schedule-member" data-filter="member">${memberOptions(member)}</select></label><label>출처<select data-filter="source">${[['all','전체 출처'],['official','멤버·소속사 공지'],['fan','지정 뱅온정보']].map(([v,t])=>`<option value="${v}" ${source===v?'selected':''}>${t}</option>`).join('')}</select></label><label>종류<select data-filter="kind">${[['all','모든 일정·공지'],...Object.entries(scheduleKinds)].map(([v,t])=>`<option value="${v}" ${kind===v?'selected':''}>${t}</option>`).join('')}</select></label></div>
 <p class="sc-coverage" data-notice-history><b>공지 기록 ${NOTICE_ARCHIVE.rows.length.toLocaleString('ko-KR')}건</b><span>${e(NOTICE_ARCHIVE.start.replaceAll('-','.'))} ~ ${e(NOTICE_ARCHIVE.end.replaceAll('-','.'))} · 공지 게시일과 실제 일정을 구분합니다.</span></p>
 <div class="calendar-layout sc-layout"><section class="calendar sc-calendar" aria-label="월별 달력"><div class="calendar-header"><h2>${year}년 ${m}월</h2><div class="calendar-controls"><button class="icon-btn" data-action="month" data-offset="-1" data-year="${year}" data-month="${m}" aria-label="이전 달">${icon('back')}</button><button class="icon-btn" data-action="month" data-offset="1" data-year="${year}" data-month="${m}" aria-label="다음 달">${icon('arrow')}</button></div></div><div class="week-grid" aria-hidden="true">${['일','월','화','수','목','금','토'].map(n=>`<span>${n}</span>`).join('')}</div><div class="calendar-grid sc-grid">${calendarCells(year,m).map(d=>{
  if(!d)return '<span class="blank" aria-hidden="true"></span>';
  const list=events.filter(x=>x.date===d),refs=forecasts.filter(x=>x.date===d),nc=list.filter(x=>x.type==='notice').length;return `<button class="sc-day ${d===today?'today ':''}${d===day?'selected ':''}${list.length?'has-event':''}" data-action="date" data-date="${d}" aria-label="${e(formatDate(d))}, 일정 ${list.length-nc}건, 공지 ${nc}건${refs.length?', 팬 참고 '+refs.length+'건':''}" aria-pressed="${d===day}" ${d===today?'aria-current="date"':''}><span class="sc-day-number">${Number(d.slice(-2))}</span><span class="sc-day-events">${list.slice(0,2).map(x=>`<span class="sc-chip ${x.type==='notice'?'notice ':''}${x.certainty==='tentative'?'tentative':''}">${e((x.members.length===1?memberNames(x.members)+' ':'')+(scheduleKinds[x.type]||'일정'))}</span>`).join('')}${list.length>2?`<span class="sc-extra">+${list.length-2}</span>`:''}${refs.length?'<span class="sc-chip fan">팬 참고</span>':''}</span><span class="sc-day-count">${list.length?list.length+'건':refs.length?'참고':''}</span></button>`;
 }).join('')}</div><p class="source-note">한국 시간(KST) · ‘공지 게시’는 글을 올린 날의 기록이며 방송 예정일을 뜻하지 않습니다.</p></section>
 <section class="sc-agenda" aria-live="polite"><header><p>${day===today?'TODAY':'SELECTED DAY'}</p><h2>${e(formatDate(day))}</h2><span>일정 ${selected.length-noticeCount}건 · 공지 ${noticeCount}건</span></header><div class="sc-day-list">${selected.length?selected.map(scheduleItem).join(''):'<div class="sc-empty"><b>등록된 일정·공지가 없어요</b><p>자료가 없다고 방송·활동이 없었다는 뜻은 아닙니다.</p></div>'}</div>${daily.length?`<section class="sc-forecast"><h3>방송 참고 <span>팬 정리 · 미확정</span></h3><p>실제 방송 상태는 <a href="#/live">LIVE</a>에서 확인하세요. ${day<today?'지난 날짜의 참고 기록입니다.':''}</p>${daily.map(r=>`<div class="sc-forecast-row"><b>${e(memberNames(r.members))}</b><span>${e(r.title.replace(memberNames(r.members)+' · ',''))}</span></div>`).join('')}<a class="text-link" href="${e(daily[0].sourceUrl)}" target="_blank" rel="noopener noreferrer">팬 정리 원문 ${icon('external')}</a><small>확인 ${e(formatDate(daily[0].checkedAt.slice(0,10)))} · 자동 갱신 자료 아님</small></section>`:''}</section></div>
 <details class="sc-month"><summary>이달의 일정·공지 모아보기 <span>${monthItems.length}건</span></summary>${monthItems.map(r=>`<div class="sc-month-row"><time>${e(r.date.slice(5))}</time>${scheduleItem(r)}</div>`).join('')||'<p>이달에 등록된 일정·공지가 없습니다.</p>'}</details>
 <section class="sc-news"><header class="section-head"><h2>최근 소식 <small>작성자가 확인된 공지만 모았어요</small></h2><span>${news.length.toLocaleString('ko-KR')}건</span></header><div class="sc-news-grid">${news.slice((page-1)*8,page*8).map(scheduleNews).join('')||'<p>조건에 맞는 소식이 없습니다.</p>'}</div>${news.length>8?`<div class="sc-pagination"><button type="button" class="filter-button" data-schedule-page="${page-1}" ${page<=1?'disabled':''}>이전</button><span>${page} / ${Math.ceil(news.length/8)}</span><button type="button" class="filter-button" data-schedule-page="${page+1}" ${page>=Math.ceil(news.length/8)?'disabled':''}>다음</button></div>`:''}</section>
 <details class="sc-sources"><summary>수집 상태와 표시 기준</summary><p>여섯 멤버·소속사가 작성한 것으로 확인된 공지와 지정된 뱅온정보만 표시합니다. 작성자가 확인되지 않은 검색 결과는 노출하지 않습니다.</p><p>과거 공지는 공개 목록의 제목·작성자·게시일을 대조한 기록입니다. 본문 전체를 검토한 일정표가 아니며, 일정일이 명확한 제목만 별도 일정으로 분류합니다. 삭제·비공개 글은 포함하지 않습니다. ${NOTICE_ARCHIVE.completePublicListings?'대상 공개 목록의 끝까지 확인했습니다.':'공개 목록 확인 범위에 아직 누락 구간이 있습니다.'}</p>${scheduleSnapshot.sources.filter(s=>s.id!=='naver-search').map(s=>`<div><b>${e(s.label)}</b><span>${e(s.detail||'확인 중')}</span></div>`).join('')}<p>카페 본문 정기 크롤링은 사용하지 않습니다. 패러블 공식 뉴스룸은 자동 갱신하며, 새로고침은 사이트에 저장된 결과를 다시 읽습니다.</p></details></div>`;
}
async function scheduleRefresh(force=false){
 if(scheduleLoading||location.protocol==='file:'||(!force&&Date.now()-scheduleLastFetch<300000))return;
 scheduleLoading=true;scheduleLastFetch=Date.now();const control=new AbortController();const timeout=setTimeout(()=>control.abort(),10000);
 try{const response=await fetch('/api/schedule',{credentials:'same-origin',cache:'no-store',signal:control.signal});if(!response.ok)throw new Error('snapshot unavailable');const value=scheduleValidate(await response.json());if(Date.parse(value.generatedAt)>=Date.parse(scheduleSnapshot.generatedAt))scheduleSnapshot=value;scheduleLoadFailed=false;}
 catch{scheduleLoadFailed=true;}
 finally{clearTimeout(timeout);scheduleLoading=false;if(parseRoute(location.hash).parts[0]==='schedule')render({scroll:false});}
}
document.addEventListener('click',event=>{if(event.target.closest('[data-schedule-refresh]'))scheduleRefresh(true);const b=event.target.closest('[data-schedule-page]');if(b)setRouteParam('page',String(Math.max(1,Number(b.dataset.schedulePage))));});
document.addEventListener('change',event=>{if(event.target.matches('[data-schedule-month]')&&/^20\d{2}-(0[1-9]|1[0-2])$/.test(event.target.value)){const p=new URLSearchParams(parseRoute(location.hash).params);p.set('month',event.target.value);p.delete('date');p.delete('page');location.hash='#/schedule?'+p;}});
window.addEventListener('hashchange',()=>{if(parseRoute(location.hash).parts[0]==='schedule')scheduleRefresh();});
document.addEventListener('visibilitychange',()=>{if(!document.hidden&&parseRoute(location.hash).parts[0]==='schedule')scheduleRefresh();});
setInterval(()=>{if(!document.hidden&&parseRoute(location.hash).parts[0]==='schedule')scheduleRefresh();},300000);
queueMicrotask(()=>{if(parseRoute(location.hash).parts[0]==='schedule')scheduleRefresh();});
