/* Source snapshots are read from our gated origin, not visitor-to-Cafe crawling. */
let scheduleSnapshot=SCHEDULE_SEED, scheduleLoading=false, scheduleLastFetch=0, scheduleLoadFailed=false;
const scheduleLabels={'cafe-members':'멤버 공지','cafe-agency':'패러블 공지','fan-roundup':'팬 정리','parable-web':'패러블 공식','naver-search':'검색·미검증','archive':'등록 기록'};
const scheduleKinds={broadcast:'방송',break:'휴방',release:'음악 발매',event:'행사'};
function scheduleArchiveEvents(){
 return records.filter(r=>['event','music'].includes(r.kind)&&scheduleValidDate(r.date)).map(r=>({id:'archive-'+r.id,title:r.title,date:r.date,time:null,type:r.kind==='music'?'release':'event',certainty:'confirmed',status:'scheduled',sourceId:'archive',sourceUrl:SOURCES[r.sourceIds?.[0]]?.url||'',internal:recordUrl(r.id),members:r.members||[],checkedAt:SITE.reviewedAt+'T00:00:00+09:00'}));
}
function schedulePill(r){
 const fan=r.sourceId==='fan-roundup',unknown=r.certainty==='unknown',cancelled=r.status==='cancelled';
 return `<span class="sc-badge ${fan?'fan':''} ${r.certainty==='tentative'?'tentative':''}">${e(scheduleLabels[r.sourceId]||'출처 확인')}</span>${cancelled?'<span class="sc-badge cancelled">취소·변경</span>':unknown?'<span class="sc-badge tentative">미정</span>':r.certainty==='tentative'?'<span class="sc-badge tentative">미확정</span>':''}`;
}
function scheduleItem(r){
 const url=r.internal||scheduleSafeUrl(r.sourceUrl);const externalAttrs=r.internal?'':' target="_blank" rel="noopener noreferrer"';
 return `<article class="sc-event ${r.status==='cancelled'?'cancelled':''}"><div class="sc-event-meta">${schedulePill(r)}<span>${e(scheduleKinds[r.type]||'소식')}${r.time?' · '+e(r.time):r.type==='break'?'':' · 시간 미정'}</span></div><h3>${url?`<a href="${e(url)}"${externalAttrs}>${e(r.title)} ${icon(r.internal?'arrow':'external')}</a>`:e(r.title)}</h3><p>${e(memberNames(r.members))}${r.sourceId.startsWith('cafe-')?' · 초기 확인 자료':''}</p>${r.detail?`<small>${e(r.detail)}</small>`:''}</article>`;
}
function scheduleNews(r){
 const url=scheduleSafeUrl(r.sourceUrl);return `<article class="sc-news-item"><div>${schedulePill(r)}<span>${r.publishedAt?'게시 '+e(formatDate(new Date(r.publishedAt).toLocaleDateString('sv-SE',{timeZone:'Asia/Seoul'}))):'게시일 미확인'}</span></div><h3><a href="${e(url||'#')}" target="_blank" rel="noopener noreferrer">${e(r.title)} ${icon('external')}</a></h3><p>${e(r.detail||'날짜를 확인할 수 없는 소식은 캘린더 일정으로 확정하지 않습니다.')}${r.sourceId.startsWith('cafe-')?' · '+e(r.checkedAt.slice(0,10))+' 확인본':''}</p></article>`;
}
function scheduleFreshness(){
 const s=scheduleSnapshot.sources.find(x=>x.id==='parable-web');const last=s?.lastSuccessAt;
 const formatTime=x=>x?new Intl.DateTimeFormat('ko-KR',{timeZone:'Asia/Seoul',month:'numeric',day:'numeric',hour:'2-digit',minute:'2-digit',hour12:false}).format(new Date(x))+' KST':'아직 확인 전';
 const age=last?Date.now()-Date.parse(last):Infinity;
 return `<div class="sc-sync"><div><b>${scheduleLoading?'저장된 소식 확인 중':scheduleLoadFailed?'갱신 확인 실패 · 이전 자료 표시':age>7200000?'자동 수집 정보 확인 필요':'소식 자동 확인'}</b><span>패러블 최근 성공 ${e(formatTime(last))} · 매시간 자동 확인 · 실행 지연 가능</span></div><button class="filter-button" type="button" data-schedule-refresh ${scheduleLoading?'disabled':''}>${scheduleLoading?'확인 중…':'새로고침'}</button></div>`;
}
function scheduleFeedView(params){
 const today=kstDate();let month=params.get('month')||today.slice(0,7);
 if(!/^20\d{2}-(0[1-9]|1[0-2])$/.test(month))month=today.slice(0,7);
 const [year,m]=month.split('-').map(Number);
 const chosen=params.get('date');const day=scheduleValidDate(chosen)&&chosen.startsWith(month)?chosen:month===today.slice(0,7)?today:month+'-01';
 const member=MEMBERS.some(x=>x.id===params.get('member'))?params.get('member'):'all';
 const source=['official','fan'].includes(params.get('source'))?params.get('source'):'all';
 const kind=Object.hasOwn(scheduleKinds,params.get('kind'))?params.get('kind'):'all';
 const filters={member,source,kind};
 const events=scheduleFiltered(scheduleMergeEvents(scheduleArchiveEvents(),scheduleSnapshot.events),filters);
 const forecasts=scheduleFiltered(scheduleSnapshot.forecasts,filters);
 const selected=events.filter(r=>r.date===day),monthItems=events.filter(r=>r.date.startsWith(month));
 const daily=scheduleCurrentForecasts(forecasts,day);
 const news=scheduleFiltered(scheduleSnapshot.news,{member,source}).sort((a,b)=>(b.publishedAt||b.checkedAt).localeCompare(a.publishedAt||a.checkedAt));
 const page=Math.max(1,Math.min(Math.ceil(news.length/8)||1,Math.floor(Number(params.get('page')))||1));
 return heading('소식·일정','날짜별 일정과 멤버들의 새 소식을 한눈에 확인하세요.','CALENDAR & NEWS')+`<div class="sc-page">${scheduleFreshness()}<div class="sc-filters"><a class="filter-button" href="#/schedule">오늘</a><label>멤버<select id="schedule-member" data-filter="member">${memberOptions(member)}</select></label><label>출처<select data-filter="source">${[['all','전체 출처'],['official','공식 공지·등록 기록'],['fan','팬 정리']].map(([v,t])=>`<option value="${v}" ${source===v?'selected':''}>${t}</option>`).join('')}</select></label><label>종류<select data-filter="kind">${[['all','모든 일정'],...Object.entries(scheduleKinds)].map(([v,t])=>`<option value="${v}" ${kind===v?'selected':''}>${t}</option>`).join('')}</select></label></div>
 <div class="calendar-layout sc-layout"><section class="calendar sc-calendar" aria-label="월별 달력"><div class="calendar-header"><h2>${year}년 ${m}월</h2><div class="calendar-controls"><button class="icon-btn" data-action="month" data-offset="-1" data-year="${year}" data-month="${m}" aria-label="이전 달">${icon('back')}</button><button class="icon-btn" data-action="month" data-offset="1" data-year="${year}" data-month="${m}" aria-label="다음 달">${icon('arrow')}</button></div></div><div class="week-grid" aria-hidden="true">${['일','월','화','수','목','금','토'].map(n=>`<span>${n}</span>`).join('')}</div><div class="calendar-grid sc-grid">${calendarCells(year,m).map(d=>{
  if(!d)return '<span class="blank" aria-hidden="true"></span>';
  const list=events.filter(x=>x.date===d),refs=forecasts.filter(x=>x.date===d);return `<button class="sc-day ${d===today?'today ':''}${d===day?'selected ':''}${list.length?'has-event':''}" data-action="date" data-date="${d}" aria-label="${e(formatDate(d))}, 일정 ${list.length}건${refs.length?', 팬 참고 '+refs.length+'건':''}" aria-pressed="${d===day}" ${d===today?'aria-current="date"':''}><span class="sc-day-number">${Number(d.slice(-2))}</span><span class="sc-day-events">${list.slice(0,2).map(x=>`<span class="sc-chip ${x.certainty==='tentative'?'tentative':''}">${e((x.members.length===1?memberNames(x.members)+' ':'')+(scheduleKinds[x.type]||'일정'))}</span>`).join('')}${list.length>2?`<span class="sc-extra">+${list.length-2}</span>`:''}${refs.length?'<span class="sc-chip fan">팬 참고</span>':''}</span><span class="sc-day-count">${list.length?list.length+'건':refs.length?'참고':''}</span></button>`;
 }).join('')}</div><p class="source-note">한국 시간(KST) · 빈 날짜는 방송·활동이 없다는 뜻이 아닙니다. 팬 정리는 확정 일정과 구분합니다.</p></section>
 <section class="sc-agenda" aria-live="polite"><header><p>${day===today?'TODAY':'SELECTED DAY'}</p><h2>${e(formatDate(day))}</h2><span>등록 일정 ${selected.length}건</span></header><div class="sc-day-list">${selected.length?selected.map(scheduleItem).join(''):'<div class="sc-empty"><b>등록된 일정이 없어요</b><p>확인되지 않은 날짜나 시간은 임의로 채우지 않습니다.</p></div>'}</div>${daily.length?`<section class="sc-forecast"><h3>방송 참고 <span>팬 정리 · 미확정</span></h3><p>실제 방송 상태는 <a href="#/live">LIVE</a>에서 확인하세요. ${day<today?'지난 날짜의 참고 기록입니다.':''}</p>${daily.map(r=>`<div class="sc-forecast-row"><b>${e(memberNames(r.members))}</b><span>${e(r.title.replace(memberNames(r.members)+' · ',''))}</span></div>`).join('')}<a class="text-link" href="${e(daily[0].sourceUrl)}" target="_blank" rel="noopener noreferrer">팬 정리 원문 ${icon('external')}</a><small>확인 ${e(formatDate(daily[0].checkedAt.slice(0,10)))} · 자동 갱신 자료 아님</small></section>`:''}</section></div>
 <details class="sc-month"><summary>이달의 일정 모아보기 <span>${monthItems.length}건</span></summary>${monthItems.map(r=>`<div class="sc-month-row"><time>${e(r.date.slice(5))}</time>${scheduleItem(r)}</div>`).join('')||'<p>이달에 등록된 일정이 없습니다.</p>'}</details>
 <section class="sc-news"><header class="section-head"><h2>최근 소식 <small>게시일과 일정일은 다를 수 있어요</small></h2><span>${news.length}건</span></header><div class="sc-news-grid">${news.slice((page-1)*8,page*8).map(scheduleNews).join('')||'<p>조건에 맞는 소식이 없습니다.</p>'}</div>${news.length>8?`<div class="sc-pagination"><button type="button" class="filter-button" data-schedule-page="${page-1}" ${page<=1?'disabled':''}>이전</button><span>${page} / ${Math.ceil(news.length/8)}</span><button type="button" class="filter-button" data-schedule-page="${page+1}" ${page>=Math.ceil(news.length/8)?'disabled':''}>다음</button></div>`:''}</section>
 <details class="sc-sources"><summary>수집 상태와 표시 기준</summary><p>공식 공지·팬 정리·검색 후보를 구분합니다. 날짜가 명시되지 않은 글, 이미지에만 있는 날짜, 서로 충돌하는 일정은 자동 확정하지 않습니다. 본문·댓글·팬의 개인 프로필을 복제하지 않습니다.</p>${scheduleSnapshot.sources.map(s=>`<div><b>${e(s.label)}</b><span>${e(s.detail||'확인 중')}</span></div>`).join('')}<p>카페 원문 자동 크롤링은 사용하지 않습니다. 네이버 공식 검색 API로 발견한 글도 작성자 확인 전에는 공식 공지로 취급하지 않습니다. 새로고침은 사이트에 저장된 수집 결과를 다시 읽습니다.</p></details></div>`;
}
async function scheduleRefresh(force=false){
 if(scheduleLoading||location.protocol==='file:'||(!force&&Date.now()-scheduleLastFetch<300000))return;
 scheduleLoading=true;scheduleLastFetch=Date.now();const control=new AbortController();const timeout=setTimeout(()=>control.abort(),10000);
 try{const response=await fetch('/api/schedule',{credentials:'same-origin',cache:'no-store',signal:control.signal});if(!response.ok)throw new Error('snapshot unavailable');const value=scheduleValidate(await response.json());if(Date.parse(value.generatedAt)>=Date.parse(scheduleSnapshot.generatedAt))scheduleSnapshot=value;scheduleLoadFailed=false;}
 catch{scheduleLoadFailed=true;}
 finally{clearTimeout(timeout);scheduleLoading=false;if(parseRoute(location.hash).parts[0]==='schedule')render({scroll:false});}
}
document.addEventListener('click',event=>{if(event.target.closest('[data-schedule-refresh]'))scheduleRefresh(true);const b=event.target.closest('[data-schedule-page]');if(b)setRouteParam('page',String(Math.max(1,Number(b.dataset.schedulePage))));});
window.addEventListener('hashchange',()=>{if(parseRoute(location.hash).parts[0]==='schedule')scheduleRefresh();});
document.addEventListener('visibilitychange',()=>{if(!document.hidden&&parseRoute(location.hash).parts[0]==='schedule')scheduleRefresh();});
setInterval(()=>{if(!document.hidden&&parseRoute(location.hash).parts[0]==='schedule')scheduleRefresh();},300000);
queueMicrotask(()=>{if(parseRoute(location.hash).parts[0]==='schedule')scheduleRefresh();});
