/* Publication records are explicitly separate from actual event dates. */
let scheduleSnapshot=SCHEDULE_SEED,scheduleLoading=false,scheduleLastFetch=0,scheduleLoadFailed=false;
const scheduleLabels={'cafe-members':'멤버 공지','cafe-agency':'패러블 공지','fan-roundup':'지정 뱅온정보','parable-web':'패러블 공식','archive':'등록 기록'};
const scheduleKinds={broadcast:'방송',release:'음악 발매',event:'행사',notice:'공지 게시'};
const noticeHistoryRows=NOTICE_ARCHIVE.rows.map(([id,menu,author,members,title,publishedAt,generalized])=>({id:'notice-source-'+id,sourceId:menu===345?'cafe-members':'cafe-agency',sourceUrl:'https://cafe.naver.com/steamindiegame/'+id,members,title,publishedAt,checkedAt:NOTICE_ARCHIVE.checkedAt,detail:generalized?'세부 내용은 원문에서 확인하세요.':'공개 목록의 작성자·게시일 확인 · 본문 일정 미확인'}));
const noticeApprovedSources=new Map(noticeHistoryRows.map(r=>[r.sourceUrl,r.sourceId]));
const noticeByArticle=new Map(noticeHistoryRows.map(r=>[Number(r.sourceUrl.split('/').pop()),r]));
const noticeHistoryEvents=NOTICE_ARCHIVE.events.map(([id,date,time,type,certainty,status,detail])=>({...noticeByArticle.get(id),id:'notice-event-'+id+'-'+date,date,time,type,certainty,status,detail}));
let scheduleNewsCache=null,scheduleNewsInput=null,scheduleEventsCache=null,scheduleEventsInput=null;
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
function scheduleAllEvents(){
 if(scheduleEventsInput===scheduleSnapshot)return scheduleEventsCache;
 // Official newsroom posts without an event date remain visible on publication day.
 const notices=scheduleAllNews().filter(r=>['cafe-members','cafe-agency','parable-web'].includes(r.sourceId)&&r.publishedAt).map(scheduleNoticeEvent);
 scheduleEventsInput=scheduleSnapshot;
 scheduleEventsCache=scheduleCalendarItems(scheduleMergeEvents([...scheduleArchiveEvents(),...noticeHistoryEvents,...notices],scheduleApprovedRows(scheduleSnapshot.events,noticeApprovedSources)));
 return scheduleEventsCache;
}
function scheduleModel(params){
 const today=kstDate();let month=params.get('month')||today.slice(0,7);
 if(!/^20\d{2}-(0[1-9]|1[0-2])$/.test(month))month=today.slice(0,7);
 const chosen=params.get('date');const day=scheduleValidDate(chosen)&&chosen.startsWith(month)?chosen:month===today.slice(0,7)?today:month+'-01';
 const member=MEMBERS.some(x=>x.id===params.get('member'))?params.get('member'):'all';
 const source=['official','fan'].includes(params.get('source'))?params.get('source'):'all';
 // Old bookmarked break filters now open the combined notice category.
 const requested=params.get('kind')==='break'?'notice':params.get('kind');
 const kind=Object.hasOwn(scheduleKinds,requested)?requested:'all';
 const filters={member,source,kind},events=scheduleFiltered(scheduleAllEvents(),filters);
 const forecasts=scheduleFiltered(scheduleApprovedRows(scheduleSnapshot.forecasts,noticeApprovedSources),{member,source});
 return {today,month,day,member,source,kind,events,forecasts,selected:events.filter(r=>r.date===day),daily:scheduleCurrentForecasts(forecasts,day),monthItems:events.filter(r=>r.date.startsWith(month)),key:[month,member,source,kind].join('|')};
}
function schedulePill(r){
 return `<span class="sc-badge ${r.sourceId==='fan-roundup'?'fan':''}">${e(scheduleLabels[r.sourceId]||'출처 확인')}</span>${r.status==='cancelled'?'<span class="sc-badge cancelled">취소·변경</span>':r.certainty==='unknown'?'<span class="sc-badge tentative">미정</span>':r.certainty==='tentative'?'<span class="sc-badge tentative">미확정</span>':''}`;
}
function scheduleMemberLabel(r){
 return r.members.length===1?memberNames(r.members):r.members.length===6?'이세돌':r.members.length>1?'유닛':'공통';
}
function scheduleItem(r){
 const url=r.internal||scheduleSafeUrl(r.sourceUrl),externalAttrs=r.internal?'':' target="_blank" rel="noopener noreferrer"';
 const annotations=(r.relatedSchedule||[]).filter(x=>x.type!=='break'||x.date!==r.date).map(x=>`${x.type==='break'?'휴방 안내':scheduleKinds[x.type]||'일정'} · ${formatDate(x.date)}${x.time?' '+x.time:''}${x.certainty==='tentative'?' · 미확정':''}${x.status==='cancelled'?' · 취소·변경':''}`);
 return `<article class="sc-event ${r.type==='notice'?'sc-notice-record ':''}${r.status==='cancelled'?'cancelled':''}" data-member-tone="${scheduleMemberTone(r.members)}" data-schedule-record-type="${e(r.type)}" data-schedule-source="${e(r.sourceUrl)}"><div class="sc-event-meta">${schedulePill(r)}<span>${e(scheduleKinds[r.type]||'소식')}${r.type==='notice'?' · 게시일 기준':r.time?' · '+e(r.time):' · 시간 미정'}</span></div><h3>${url?`<a href="${e(url)}"${externalAttrs}>${e(r.title)} ${icon(r.internal?'arrow':'external')}</a>`:e(r.title)}</h3><p class="sc-members">${r.members.map(id=>`<span data-member-tone="${scheduleMemberTone([id])}"><i class="sc-dot" aria-hidden="true"></i>${e(memberNames([id]))}</span>`).join('')}</p>${annotations.length?`<p class="sc-related">${annotations.map(e).join('<br>')}</p>`:''}${r.detail?`<small>${e(r.detail)}</small>`:''}</article>`;
}
function scheduleFreshness(){
 const s=scheduleSnapshot.sources.find(x=>x.id==='parable-web'),last=s?.lastSuccessAt;
 const formatTime=x=>x?new Intl.DateTimeFormat('ko-KR',{timeZone:'Asia/Seoul',month:'numeric',day:'numeric',hour:'2-digit',minute:'2-digit',hour12:false}).format(new Date(x))+' KST':'아직 확인 전';
 const age=last?Date.now()-Date.parse(last):Infinity;
 return `<div class="sc-sync"><div><b>${scheduleLoading?'저장된 소식 확인 중':scheduleLoadFailed?'갱신 확인 실패 · 이전 자료 표시':age>7200000?'자동 수집 정보 확인 필요':'소식 자동 확인'}</b><span>패러블 최근 성공 ${e(formatTime(last))} · 작성자 미확인 검색글은 제외</span></div><button class="filter-button" type="button" data-schedule-refresh ${scheduleLoading?'disabled':''}>${scheduleLoading?'확인 중…':'새로고침'}</button></div>`;
}
function scheduleAgenda(model){
 const {day,today,selected,daily}=model,noticeCount=selected.filter(r=>r.type==='notice').length;
 return `<header><div><p>선택한 날짜${day===today?' · 오늘':''}</p><h2 id="schedule-selected-title">${e(formatDate(day))}</h2></div><span>일정 ${selected.length-noticeCount}건 · 공지 ${noticeCount}건</span></header><div class="sc-day-list">${selected.length?selected.map(scheduleItem).join(''):'<div class="sc-empty"><b>등록된 일정·공지가 없어요</b><p>자료가 없다고 방송·활동이 없었다는 뜻은 아닙니다.</p></div>'}</div>${daily.length?`<section class="sc-forecast"><h3>방송 참고 <span>팬 정리 · 미확정</span></h3><p>실제 방송 상태는 <a href="#/live">LIVE</a>에서 확인하세요. ${day<today?'지난 날짜의 참고 기록입니다.':''}</p>${daily.map(r=>`<div class="sc-forecast-row" data-member-tone="${scheduleMemberTone(r.members)}"><b><i class="sc-dot" aria-hidden="true"></i>${e(memberNames(r.members))}</b><span>${e(r.title.replace(memberNames(r.members)+' · ',''))}</span></div>`).join('')}<a class="text-link" href="${e(daily[0].sourceUrl)}" target="_blank" rel="noopener noreferrer">팬 정리 원문 ${icon('external')}</a><small>확인 ${e(formatDate(schedulePostedDate(daily[0].checkedAt)))} · 자동 갱신 자료 아님</small></section>`:''}`;
}
function scheduleFeedView(params){
 const model=scheduleModel(params),{today,month,day,member,source,kind,events,forecasts,monthItems}=model,[year,m]=month.split('-').map(Number);
 return heading('소식·일정','날짜별 일정과 멤버들의 공지 기록을 한눈에 확인하세요.','CALENDAR & NEWS')+`<div class="sc-page" data-calendar-key="${e(model.key)}" data-selected-date="${day}">${scheduleFreshness()}<div class="sc-filters"><a class="filter-button" href="#/schedule">오늘</a><label>연월<input type="month" id="schedule-month" data-schedule-month value="${month}" min="2021-08" aria-label="보고 싶은 연월"></label><a class="filter-button" data-first-notices href="#/schedule?month=${e(NOTICE_ARCHIVE.start.slice(0,7))}&date=${e(NOTICE_ARCHIVE.start)}&kind=notice">첫 공지</a><label>멤버<select id="schedule-member" data-filter="member">${memberOptions(member)}</select></label><label>출처<select data-filter="source">${[['all','전체 출처'],['official','멤버·소속사 공지'],['fan','지정 뱅온정보']].map(([v,t])=>`<option value="${v}" ${source===v?'selected':''}>${t}</option>`).join('')}</select></label><label>종류<select data-filter="kind">${[['all','모든 일정·공지'],...Object.entries(scheduleKinds)].map(([v,t])=>`<option value="${v}" ${kind===v?'selected':''}>${t}</option>`).join('')}</select></label></div>
 <p class="sc-coverage" data-notice-history><b>공지 기록 ${NOTICE_ARCHIVE.rows.length.toLocaleString('ko-KR')}건</b><span>${e(NOTICE_ARCHIVE.start.replaceAll('-','.'))} ~ ${e(NOTICE_ARCHIVE.end.replaceAll('-','.'))} · 공지 게시일과 실제 일정을 구분합니다.</span></p>
 <div class="sc-legend" aria-label="멤버별 표시 색상">${MEMBERS.map(x=>`<span data-member-tone="${x.id}"><i class="sc-dot" aria-hidden="true"></i>${e(x.name)}</span>`).join('')}<span data-member-tone="group"><i class="sc-dot" aria-hidden="true"></i>단체·공통</span></div>
 <div class="calendar-layout sc-layout"><section class="calendar sc-calendar" aria-label="월별 달력"><div class="calendar-header"><h2>${year}년 ${m}월</h2><div class="calendar-controls"><button class="icon-btn" data-action="month" data-offset="-1" data-year="${year}" data-month="${m}" aria-label="이전 달">${icon('back')}</button><button class="icon-btn" data-action="month" data-offset="1" data-year="${year}" data-month="${m}" aria-label="다음 달">${icon('arrow')}</button></div></div><p class="sc-calendar-hint">날짜를 선택하면 아래에서 상세 내용을 볼 수 있어요.<span class="sc-scroll-hint"> 달력은 좌우로 움직여 볼 수 있어요.</span></p>
 <div class="sc-calendar-scroll" tabindex="0" role="region" aria-label="월간 달력. 작은 화면에서는 좌우로 이동할 수 있습니다."><div class="sc-calendar-canvas"><div class="week-grid" aria-hidden="true">${['일','월','화','수','목','금','토'].map(n=>`<span>${n}</span>`).join('')}</div><div class="calendar-grid sc-grid">${calendarCells(year,m).map(d=>{
  if(!d)return '<span class="blank" aria-hidden="true"></span>';
  const list=events.filter(x=>x.date===d),refs=forecasts.filter(x=>x.date===d),nc=list.filter(x=>x.type==='notice').length;
  return `<button class="sc-day ${d===today?'today ':''}${d===day?'selected ':''}${list.length?'has-event':''}" data-action="date" data-date="${d}" aria-label="${e(formatDate(d))}, 일정 ${list.length-nc}건, 공지 ${nc}건${refs.length?', 팬 참고 '+refs.length+'건':''}" aria-pressed="${d===day}" ${d===today?'aria-current="date"':''}><span class="sc-day-number">${Number(d.slice(-2))}${d===today?'<small>오늘</small>':''}</span><span class="sc-day-events">${list.slice(0,4).map(x=>`<span class="sc-chip ${x.type==='notice'?'notice ':''}${x.certainty==='tentative'?'tentative':''}" data-member-tone="${scheduleMemberTone(x.members)}" title="${e(scheduleMemberLabel(x)+' · '+x.title)}"><span class="sc-chip-member">${e(scheduleMemberLabel(x))}</span><span class="sc-chip-title">${e(x.title.replace(/^\[[^\]]+\]\s*/,''))}</span></span>`).join('')}${list.length>4?`<span class="sc-extra">외 ${list.length-4}건</span>`:''}${refs.length?'<span class="sc-chip fan">팬 참고</span>':''}</span></button>`;
 }).join('')}</div></div></div><p class="source-note">한국 시간(KST) · ‘공지 게시’는 글을 올린 날의 기록입니다. 휴방 안내는 원문 공지에 함께 표시합니다.</p></section>
 <section class="sc-agenda" aria-labelledby="schedule-selected-title" aria-live="polite">${scheduleAgenda(model)}</section></div>
 <details class="sc-month"><summary>이달의 일정·공지 모아보기 <span>${monthItems.length}건</span></summary>${monthItems.map(r=>`<div class="sc-month-row"><time>${e(r.date.slice(5))}</time>${scheduleItem(r)}</div>`).join('')||'<p>이달에 등록된 일정·공지가 없습니다.</p>'}</details>
 <details class="sc-sources"><summary>수집 상태와 표시 기준</summary><p>여섯 멤버·소속사가 작성한 것으로 확인된 공지와 지정된 뱅온정보만 표시합니다. 작성자가 확인되지 않은 검색 결과는 노출하지 않습니다.</p><p>공지 게시일과 실제 일정일은 구분하며, 같은 원문의 같은 날짜 항목은 하나로 합칩니다. 휴방은 별도 일정 없이 원문 공지에 포함합니다. 날짜가 다른 방송·행사는 해당 일정일에도 표시합니다. 본문 전체와 이미지 속 세부 일정을 전수 검토한 자료는 아닙니다. ${NOTICE_ARCHIVE.completePublicListings?'대상 공개 목록의 끝까지 확인했습니다.':'공개 목록 확인 범위에 아직 누락 구간이 있습니다.'}</p>${scheduleSnapshot.sources.filter(s=>s.id!=='naver-search').map(s=>`<div><b>${e(s.label)}</b><span>${e(s.detail||'확인 중')}</span></div>`).join('')}<p>카페 본문 정기 크롤링은 사용하지 않습니다. 패러블 공식 뉴스룸은 자동 갱신하며, 새로고침은 사이트에 저장된 결과를 다시 읽습니다.</p></details></div>`;
}
// Keep the clicked date DOM node, focus and both scroll positions on date changes.
function scheduleRenderInPlace(full=false){
 const root=document.querySelector('.sc-page');if(!root)return false;
 const model=scheduleModel(parseRoute(location.hash).params),x=window.scrollX,y=window.scrollY;
 const scroller=root.querySelector('.sc-calendar-scroll'),left=scroller?.scrollLeft||0;
 if(!full&&root.dataset.calendarKey===model.key){
  root.dataset.selectedDate=model.day;
  root.querySelectorAll('.sc-day').forEach(button=>{const selected=button.dataset.date===model.day;button.classList.toggle('selected',selected);button.setAttribute('aria-pressed',String(selected));});
  root.querySelector('.sc-agenda').innerHTML=scheduleAgenda(model);
  root.querySelector('.sc-sync').outerHTML=scheduleFreshness();
 }else{
  const active=document.activeElement;
  const selector=active?.dataset.date?`[data-date="${active.dataset.date}"]`:active?.matches('[data-schedule-refresh]')?'[data-schedule-refresh]':active?.dataset.filter?`[data-filter="${active.dataset.filter}"]`:active?.matches('[data-schedule-month]')?'[data-schedule-month]':active?.dataset.action==='month'?`[data-action="month"][data-offset="${active.dataset.offset}"]`:null;
  const openDetails=[...root.querySelectorAll('details[open]')].map(x=>x.className);
  render({focus:false,scroll:false});
  for(const name of openDetails){const detail=document.querySelector('.'+name);if(detail)detail.open=true;}
  const newScroll=document.querySelector('.sc-calendar-scroll');if(newScroll)newScroll.scrollLeft=left;
  if(selector)document.querySelector(selector)?.focus({preventScroll:true});
 }
 if(window.scrollX!==x||window.scrollY!==y)window.scrollTo({left:x,top:y,behavior:'instant'});
 return true;
}
function scheduleRouteChanged(event){
 const oldHash=event.oldURL?.split('#').slice(1).join('#')||'';
 if(parseRoute('#'+oldHash).parts[0]!=='schedule'||parseRoute(location.hash).parts[0]!=='schedule')return false;
 return scheduleRenderInPlace();
}
async function scheduleRefresh(force=false){
 if(scheduleLoading||location.protocol==='file:'||(!force&&Date.now()-scheduleLastFetch<300000))return;
 const previous=scheduleSnapshot;scheduleLoading=true;scheduleLastFetch=Date.now();const control=new AbortController(),timeout=setTimeout(()=>control.abort(),10000);
 try{const response=await fetch('/api/schedule',{credentials:'same-origin',cache:'no-store',signal:control.signal});if(!response.ok)throw new Error('snapshot unavailable');const value=scheduleValidate(await response.json());if(Date.parse(value.generatedAt)>=Date.parse(scheduleSnapshot.generatedAt))scheduleSnapshot=value;scheduleLoadFailed=false;}
 catch{scheduleLoadFailed=true;}
 finally{clearTimeout(timeout);scheduleLoading=false;if(parseRoute(location.hash).parts[0]==='schedule')scheduleRenderInPlace(previous!==scheduleSnapshot);}
}
document.addEventListener('click',event=>{if(event.target.closest('[data-schedule-refresh]'))scheduleRefresh(true);});
document.addEventListener('change',event=>{if(event.target.matches('[data-schedule-month]')&&/^20\d{2}-(0[1-9]|1[0-2])$/.test(event.target.value)){const p=new URLSearchParams(parseRoute(location.hash).params);p.set('month',event.target.value);p.delete('date');p.delete('page');location.hash='#/schedule?'+p;}});
window.addEventListener('hashchange',()=>{if(parseRoute(location.hash).parts[0]==='schedule')scheduleRefresh();});
document.addEventListener('visibilitychange',()=>{if(!document.hidden&&parseRoute(location.hash).parts[0]==='schedule')scheduleRefresh();});
setInterval(()=>{if(!document.hidden&&parseRoute(location.hash).parts[0]==='schedule')scheduleRefresh();},300000);
queueMicrotask(()=>{if(parseRoute(location.hash).parts[0]==='schedule')scheduleRefresh();});
