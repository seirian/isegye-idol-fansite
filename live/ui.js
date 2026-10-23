/** Shared in-memory live monitor. No cookies, history storage, embeds or credentials. */
const liveMonitor={items:LIVE_CHANNELS.map(m=>liveEmpty(m)),busy:false,lastAttempt:0,lastCompleted:0,auto:true,active:false,filter:'all',query:'',sort:'default',signature:''};
const liveMember=id=>LIVE_CHANNELS.find(m=>m.id===id);
const liveClock=ts=>Number.isFinite(ts)?new Intl.DateTimeFormat('ko-KR',{timeZone:'Asia/Seoul',hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false}).format(new Date(ts)):'아직 확인하지 못했어요';
const liveStateLabel=s=>({live:'방송 중',offline:'방송 종료',unknown:'확인 필요',loading:'확인 중'}[s]||'확인 필요');
const liveBadge=r=>`<span class="live-state" data-state="${r.state}"><i class="live-dot" aria-hidden="true"></i>${liveStateLabel(r.state)}</span>`;
const liveImage=m=>`<img src="./assets/portraits/${m.id}.webp?v=${PORTRAITS[m.id].version}" width="600" height="600" alt="" decoding="async">`;
function liveCurrent(){return liveMonitor.items.map(r=>liveEffective(r));}
function liveHeadline(){const s=liveSummary(liveCurrent());return s.loading===6?'방송 상태를 확인하고 있어요':s.live?`지금 ${s.live}명 방송 중`:s.offline===6?'지금은 모두 방송을 쉬고 있어요':`확인된 방송 ${s.live}명 · ${s.unknown+s.loading}명 확인 필요`;}
function liveUpdateLine(){
 const rows=liveCurrent();const valid=rows.filter(r=>['live','offline'].includes(r.state));
 const t=valid.length?Math.min(...valid.map(r=>r.sourceAt||r.checkedAt)):null;
 if(location.protocol==='file:')return '온라인 사이트에서 방송 상태를 확인할 수 있어요.';
 return `${t?'SOOP 확인 '+liveClock(t)+' KST':'아직 확인된 방송 상태가 없어요'} · ${liveMonitor.auto?'30초마다 갱신':'자동 갱신 일시정지'}`;
}
function liveHomeView(){return `<section class="live-home" aria-label="지금 이세돌 LIVE"><div class="live-topline"><h2><span class="live-onair"><i class="live-dot" aria-hidden="true"></i>LIVE</span><span data-live-headline>${liveHeadline()}</span></h2><div class="live-top-actions"><button class="live-refresh" data-live-action="refresh" data-live-key="home-refresh" aria-label="방송 상태 새로고침">새로고침</button><a class="text-link" href="#/live">LIVE 전체 보기 ${icon('arrow')}</a></div></div><p class="live-home-meta" data-live-update>${liveUpdateLine()}</p><div class="live-home-grid" data-live-mini></div></section>`;}
function liveView(){return `<header class="live-page-heading"><div><span class="live-onair"><i class="live-dot" aria-hidden="true"></i>ISEGYE ON AIR</span><h1>지금, 우리와 함께 LIVE</h1><p>여섯 멤버의 방송을 한곳에서.<br>방송 중인 멤버를 확인하고 SOOP에서 바로 만나요.</p></div><div class="live-count-box"><strong data-live-count>—</strong><span data-live-count-label>방송 상태 확인 중</span></div></header><section class="live-toolbar" aria-label="LIVE 탐색"><div class="live-controls"><div class="live-filters" aria-label="방송 상태 필터"><button data-live-filter="all" data-live-key="all" aria-pressed="${liveMonitor.filter==='all'}">전체 6</button><button data-live-filter="live" data-live-key="live" aria-pressed="${liveMonitor.filter==='live'}">방송 중 <span data-live-filter-count>—</span></button></div><div class="live-tools"><label class="live-search"><span class="sr-only">멤버 이름 또는 방송 제목 검색</span><input type="search" data-live-search placeholder="멤버 이름 · 방송 제목" value="${e(liveMonitor.query)}" autocomplete="off"></label><label><span class="sr-only">방송 목록 정렬</span><select data-live-sort aria-label="방송 목록 정렬"><option value="default">방송 중 우선</option><option value="viewers">시청자 순</option><option value="recent">최근 시작순</option><option value="name">이름순</option></select></label><button class="live-refresh" data-live-action="refresh" data-live-key="page-refresh" aria-label="방송 상태 새로고침">새로고침</button></div></div><div class="live-toolbar-status"><label class="live-toggle"><input type="checkbox" data-live-auto ${liveMonitor.auto?'checked':''}>30초 자동 갱신</label><span class="live-meta" data-live-update></span></div></section><div data-live-notice role="status" aria-live="polite" aria-atomic="true"></div><div class="live-grid" data-live-cards aria-label="멤버별 방송 현황"></div><p class="live-note">SOOP에 공개된 방송 상태를 확인합니다. 실제 시작·종료와 표시 사이에 차이가 있을 수 있어요. 조회가 지연되거나 실패하면 ‘방송 종료’ 대신 ‘확인 필요’로 표시합니다. 시청 버튼은 공식 방송 페이지를 새 탭으로 엽니다.</p>`;}
function liveCard(r){
 const m=liveMember(r.id);const on=r.state==='live';
 const text=on?(r.title||'방송 중이에요. 공식 방송에서 확인해 주세요.'):
  r.state==='offline'?'다음 방송에서 다시 만나요.':r.state==='loading'?'멤버의 방송 상태를 확인하고 있어요.':
  r.reason==='offline'?'인터넷 연결을 확인해 주세요.':r.reason==='file'?'온라인 사이트에서 방송 상태를 확인해 주세요.':'현재 방송 상태를 확인하지 못했어요.';
 const meta=[];
 if(on&&r.viewers!==null)meta.push(`시청자 ${r.viewers.toLocaleString('ko-KR')}명`);
 if(on&&r.startedAt!==null)meta.push(`${liveClock(r.startedAt).slice(0,5)} 시작`);
 if(!meta.length)meta.push(r.state==='unknown'?'방송 여부는 공식 채널에서 확인해 주세요.':r.state==='loading'?'잠시 후 상태가 표시됩니다.':`확인 ${liveClock(r.sourceAt||r.checkedAt)} KST`);
 return `<article class="live-card" data-member="${m.id}" data-state="${r.state}"><div class="live-card-art ${m.tone}">${liveImage(m)}<span class="live-card-label">${liveBadge(r)}</span></div><div class="live-card-body"><div class="live-card-heading"><h2>${m.name}</h2><span class="live-platform">SOOP</span></div><p class="live-card-title">${e(text)}</p><p class="live-meta">${e(meta.join(' · '))}</p><div class="live-card-actions"><a class="button ${on?'':'secondary'}" href="${on?liveWatchUrl(m):liveChannelUrl(m)}" target="_blank" rel="noopener noreferrer" data-live-key="watch-${m.id}">${on?'방송 보러 가기':'공식 채널 보기'} ${icon('external')}</a><a class="text-link" href="#/record/${m.id}">멤버 소개 ${icon('arrow')}</a></div></div></article>`;
}
function liveFiltered(rows){
 let result=liveSorted(rows).filter(r=>(liveMonitor.filter!=='live'||r.state==='live')&&(!liveMonitor.query||`${liveMember(r.id).name} ${liveMember(r.id).channel} ${r.title}`.toLocaleLowerCase().includes(liveMonitor.query.toLocaleLowerCase().trim())));
 const liveFirst=(a,b)=>(a.state==='live'?0:1)-(b.state==='live'?0:1);
 if(liveMonitor.sort==='viewers')result.sort((a,b)=>liveFirst(a,b)||((b.viewers??-1)-(a.viewers??-1)));
 if(liveMonitor.sort==='recent')result.sort((a,b)=>liveFirst(a,b)||((b.startedAt??-1)-(a.startedAt??-1)));
 if(liveMonitor.sort==='name')result.sort((a,b)=>liveMember(a.id).name.localeCompare(liveMember(b.id).name,'ko'));
 return result;
}
function livePaint(){
 if(!liveMonitor.active)return;
 const rows=liveCurrent(),s=liveSummary(rows),key=document.activeElement?.dataset?.liveKey;
 document.querySelectorAll('[data-live-headline]').forEach(x=>x.textContent=liveHeadline());
 document.querySelectorAll('[data-live-update]').forEach(x=>x.textContent=liveUpdateLine());
 const mini=document.querySelector('[data-live-mini]');
 if(mini)mini.innerHTML=rows.map(r=>{const m=liveMember(r.id);return `<a class="live-mini" data-state="${r.state}" data-member="${m.id}" href="${r.state==='live'?liveWatchUrl(m):'#/live'}" ${r.state==='live'?'target="_blank" rel="noopener noreferrer"':''} aria-label="${m.name} ${liveStateLabel(r.state)}${r.state==='live'?', SOOP에서 시청':''}">${liveImage(m)}<span><strong>${m.name}</strong>${liveBadge(r)}</span></a>`;}).join('');
 const count=document.querySelector('[data-live-count]');if(count)count.textContent=s.loading===6?'—':s.live+'명';
 const label=document.querySelector('[data-live-count-label]');if(label)label.textContent=s.loading===6?'방송 상태 확인 중':s.unknown||s.loading?`방송 중 확인 · ${s.unknown+s.loading}명 미확인`:'현재 방송 중';
 document.querySelectorAll('[data-live-filter-count]').forEach(x=>x.textContent=s.loading===6?'—':s.live);
 document.querySelectorAll('[data-live-filter]').forEach(x=>x.setAttribute('aria-pressed',String(x.dataset.liveFilter===liveMonitor.filter)));
 const notice=document.querySelector('[data-live-notice]');if(notice){const message=s.unknown?`${s.unknown}명의 방송 상태를 확인하지 못했습니다. 방송 종료를 뜻하지 않아요.`:s.loading?'방송 상태를 확인하고 있어요.':'';if(notice.textContent!==message)notice.innerHTML=message?`<p class="live-alert">${e(message)}</p>`:'';}
 const cards=document.querySelector('[data-live-cards]');
 if(cards){const filtered=liveFiltered(rows);cards.innerHTML=filtered.length?filtered.map(liveCard).join(''):`<section class="live-empty"><h2>${liveMonitor.query?'검색 결과가 없어요.':s.unknown||s.loading?'확인된 방송이 아직 없어요.':'지금은 방송 중인 멤버가 없어요.'}</h2><p>${s.unknown||s.loading?'일부 상태를 확인하지 못했어요. 전체 목록에서 공식 채널을 확인해 주세요.':'전체 목록에서 멤버의 공식 채널을 만나보세요.'}</p><button class="button secondary" data-live-action="reset" data-live-key="reset">전체 멤버 보기</button></section>`;}
 liveMonitor.signature=rows.map(r=>r.state).join(',');liveControls();
 if(key)document.querySelector(`[data-live-key="${key}"]`)?.focus({preventScroll:true});
}
function liveControls(){
 document.querySelectorAll('[data-live-action=refresh]').forEach(b=>{const seconds=Math.max(0,Math.ceil((LIVE_COOLDOWN_MS-(Date.now()-liveMonitor.lastAttempt))/1000));b.disabled=liveMonitor.busy||seconds>0;b.textContent=liveMonitor.busy?'확인 중…':seconds>0?`${seconds}초 후 새로고침`:'새로고침';});
 document.querySelectorAll('[data-live-mini],[data-live-cards]').forEach(x=>x.setAttribute('aria-busy',String(liveMonitor.busy)));
}
async function liveRefresh(){
 if(liveMonitor.busy||!liveMonitor.active||document.hidden||Date.now()-liveMonitor.lastAttempt<LIVE_COOLDOWN_MS)return;
 liveMonitor.lastAttempt=Date.now();
 if(location.protocol==='file:'||!navigator.onLine){liveMonitor.items=LIVE_CHANNELS.map(m=>liveEmpty(m,location.protocol==='file:'?'file':'offline'));livePaint();return;}
 liveMonitor.busy=true;liveControls();
 const previous=liveMonitor.items;
 const results=await Promise.all(LIVE_CHANNELS.map(async m=>{
  try{return await fetchLiveMember(m);}
  catch(error){return liveEmpty(m,error?.message==='rate-limited'?'rate-limited':'unavailable',previous.find(r=>r.id===m.id));}
 }));
 liveMonitor.items=navigator.onLine?results:LIVE_CHANNELS.map(m=>liveEmpty(m,'offline'));liveMonitor.lastCompleted=Date.now();liveMonitor.busy=false;livePaint();
}
function liveMount(page){
 liveMonitor.active=page==='home'||page==='live';
 if(!liveMonitor.active)return;
 const select=document.querySelector('[data-live-sort]');if(select)select.value=liveMonitor.sort;
 livePaint();
 if(!liveMonitor.lastAttempt||(liveMonitor.auto&&Date.now()-liveMonitor.lastAttempt>=LIVE_POLL_MS))void liveRefresh();
}
function liveTick(){
 if(!liveMonitor.active||document.hidden)return;
 if(liveCurrent().map(r=>r.state).join(',')!==liveMonitor.signature)livePaint();
 liveControls();
 if(liveMonitor.auto&&Date.now()-liveMonitor.lastAttempt>=LIVE_POLL_MS)void liveRefresh();
}
setInterval(liveTick,1000);
document.addEventListener('visibilitychange',liveTick);
window.addEventListener('online',liveTick);
window.addEventListener('offline',()=>{liveMonitor.items=LIVE_CHANNELS.map(m=>liveEmpty(m,'offline'));livePaint();});
document.addEventListener('click',event=>{
 const filter=event.target.closest('[data-live-filter]');if(filter){liveMonitor.filter=filter.dataset.liveFilter;livePaint();}
 const action=event.target.closest('[data-live-action]')?.dataset.liveAction;
 if(action==='refresh')void liveRefresh();
 if(action==='reset'){liveMonitor.filter='all';liveMonitor.query='';const q=document.querySelector('[data-live-search]');if(q)q.value='';livePaint();}
});
document.addEventListener('input',event=>{if(event.target.matches('[data-live-search]')){liveMonitor.query=event.target.value.slice(0,120);livePaint();}});
document.addEventListener('change',event=>{if(event.target.matches('[data-live-auto]')){liveMonitor.auto=event.target.checked;livePaint();liveTick();}if(event.target.matches('[data-live-sort]')){liveMonitor.sort=event.target.value;livePaint();}});
