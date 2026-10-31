/* A simple front door beneath the UNCHANGED liveHomeView. All content comes from existing data. */
function homeShortcutPortrait(m) {
 const profile = HOME_SOOP_PROFILES[m.id];
 return `<div class="portrait ${m.tone} hm-soop-portrait" data-home-soop-profile="${e(m.id)}"><img src="./assets/soop-profiles/${m.id}.webp?v=${profile.version}" width="144" height="144" alt="${e(m.name)} SOOP 프로필 이미지" loading="eager" decoding="async" data-home-soop-image><span class="portrait-fallback" aria-hidden="true">${e(m.name)}</span></div>`;
}
let homeMember = 'all';
let homeMusicType = 'original';
function homeVideoCard(v) {
 return `<article class="hm-video"><a href="${e(catalogVideoUrl(v.id))}" target="_blank" rel="noopener noreferrer" class="hm-video-link" data-home-video="${e(v.id)}" data-published="${e(v.publishedAt)}"><div class="hm-video-image"><span class="hm-image-fallback">YouTube에서 영상 보기 ${icon('external')}</span><img src="https://i.ytimg.com/vi/${v.id}/mqdefault.jpg" alt="" width="320" height="180" loading="lazy" decoding="async" referrerpolicy="no-referrer" data-home-image><span class="hm-play" aria-hidden="true">${icon('play')}</span></div><div class="hm-video-copy"><p class="hm-video-meta"><b>${e(v.memberName)}</b><time datetime="${e(v.publishedAt)}">${catDate(v.publishedAt)}</time></p><h3>${e(v.title)}</h3><span class="hm-channel">${e(v.channelName)} · YouTube ${icon('external')}</span></div></a></article>`;
}
function homeVideoContent() {
 const videos = homeLatestVideos(CATALOG, homeMember);
 const checks = videos.map(v=>v.checkedAt).filter(v=>Number.isFinite(Date.parse(v)));
 const earliest = checks.sort((a,b)=>Date.parse(a)-Date.parse(b))[0];
 return `<div class="hm-video-grid">${videos.length ? videos.map(homeVideoCard).join('') : '<p class="hm-empty">확인된 영상이 아직 없습니다. 멤버 소개에서 공식 채널을 확인해 주세요.</p>'}</div><div class="hm-data-note"><p>${earliest ? `목록 확인 ${e(catStamp(earliest))} · 새 업로드는 반영 전일 수 있어요.` : '확인된 공개 영상만 표시합니다.'}</p>${homeMember !== 'all' ? `<a class="text-link" href="#/record/${homeMember}">${e(catalogProfiles.get(homeMember).name)}의 모든 채널 ${icon('arrow')}</a>` : ''}</div>`;
}
function homeMusicContent() {
 const songs = homeMusicSelection(CATALOG.music.songs, homeMusicType, kstDate());
 return `<div class="catalog-song-grid hm-song-grid">${songs.map(catalogSongCard).join('')}</div><p class="hm-data-note">${homeMusicType === 'cover' ? '영상 공개일 순 · 공식 영상과 팬 백업을 구분해 표시합니다.' : '발매일 순 · 같은 음반은 대표 1곡만 표시합니다.'}</p>`;
}
// Home uses only the two verified Berriz feeds already used by the calendar.
function homeBriefItems(feed, now=new Date()) {
 const today=kstDate(now), ms=+now;
 const notice=feed.news.filter(r=>r.sourceId==='berriz-notice'&&scheduleBerrizApproved(r)&&Date.parse(r.publishedAt)<=ms)
  .sort((a,b)=>Date.parse(b.publishedAt)-Date.parse(a.publishedAt)||b.id.localeCompare(a.id,'en',{numeric:true}))[0];
 const next=feed.events.filter(r=>r.sourceId==='berriz-calendar'&&scheduleBerrizApproved(r)&&r.status==='scheduled'&&r.certainty==='confirmed'&&scheduleValidDate(r.date)&&
  (r.date>today||(r.date===today&&(!r.time||Date.parse(r.date+'T'+r.time+':00+09:00')>=ms))))
  .sort((a,b)=>a.date.localeCompare(b.date)||(a.time||'').localeCompare(b.time||'')||a.id.localeCompare(b.id))[0];
 return {notice,next};
}
function homeBriefContent(){
 const {notice,next}=homeBriefItems(scheduleSnapshot);
 function row(label,item,date,when,href,externalLink){
  const meta=`<span class="hm-brief-label">${label}</span>${date?`<time datetime="${e(date)}">${e(date.replaceAll('-','.'))}${when?' · '+e(when):''}</time>`:''}`;
  if(!item)return `<div class="hm-brief-row"><div class="hm-brief-meta">${meta}</div><p class="hm-brief-empty">${label==='최근 공지'?'아직 확인된 공지가 없습니다.':'아직 확인된 다음 일정이 없습니다.'}</p></div>`;
  return `<a class="hm-brief-row" href="${e(href)}"${externalLink?' target="_blank" rel="noopener noreferrer"':''}><div class="hm-brief-meta">${meta}</div><strong>${e(item.title)} ${icon(externalLink?'external':'arrow')}</strong></a>`;
 }
 const last=scheduleSnapshot.sources.filter(s=>['berriz-notice','berriz-calendar'].includes(s.id)).map(s=>Date.parse(s.lastSuccessAt)).filter(Number.isFinite);
 const saved=scheduleLoadFailed||last.length!==2||Date.now()-Math.min(...last)>86400000;
 return row('최근 공지',notice,notice&&schedulePostedDate(notice.publishedAt),'게시',notice?.sourceUrl,true)+row('다음 일정',next,next?.date,next?.allDay?'종일':next?.time?next.time+' KST':'시간 미정',next&&`#/schedule?month=${next.date.slice(0,7)}&date=${next.date}&source=berriz`,false)+(saved?`<p class="hm-brief-saved">저장된 자료를 표시합니다.${last.length?' 마지막 확인: '+e(kstDate(new Date(Math.min(...last)))):''}</p>`:'');
}
let homeBriefRetry;
async function homeRefreshBrief(){
 clearTimeout(homeBriefRetry);
 if(document.hidden||!document.querySelector('#hm-brief-items')||location.protocol==='file:')return;
 if(scheduleLoading){homeBriefRetry=setTimeout(homeRefreshBrief,1000);return;}
 const target=document.querySelector('#hm-brief-items');
 if(target._briefHtml===undefined)target._briefHtml=homeBriefContent();
 await scheduleRefresh();
 if(!target.isConnected)return;
 const html=homeBriefContent();if(html===target._briefHtml)return;
 const focused=target.contains(document.activeElement)?document.activeElement.getAttribute('href'):null;
 target.innerHTML=html;target._briefHtml=html;
 if(focused)Array.from(target.querySelectorAll('a')).find(a=>a.getAttribute('href')===focused)?.focus({preventScroll:true});
}
document.addEventListener('visibilitychange',homeRefreshBrief);
setInterval(homeRefreshBrief,300000);
function homeSimpleView() {
 queueMicrotask(homeRefreshBrief);
 const upcoming = homeUpcoming(records, kstDate());
 return liveHomeView() + `<div class="hm-page"><h1 class="sr-only">오늘의 이세돌</h1><section class="hm-intro hm-brief" aria-labelledby="hm-brief-title"><div class="hm-intro-copy"><p class="hm-eyebrow">공식 팬클럽 · 베리즈</p><h2 id="hm-brief-title">공식 소식</h2><div id="hm-brief-items">${homeBriefContent()}</div></div><img class="hm-group" src="./assets/isegye-group-hero.webp?v=3ce98e06f795" width="800" height="450" alt="이세계아이돌 여섯 멤버의 단체 일러스트" decoding="async" fetchpriority="high"></section>
 <section class="hm-section" aria-labelledby="hm-video-title"><header class="hm-section-head"><div><h2 id="hm-video-title">최근 영상</h2><p>본채널·음악 채널의 최근 공개 영상</p></div></header><div class="hm-filters" role="group" aria-label="최근 영상 멤버 선택">${[['all','전체'],...MEMBERS.map(m=>[m.id,m.name])].map(([id,name])=>`<button type="button" data-home-member="${id}" aria-pressed="${homeMember===id}" aria-controls="hm-videos">${name}</button>`).join('')}</div><div id="hm-videos">${homeVideoContent()}</div><p class="sr-only" id="hm-video-status" role="status" aria-live="polite"></p><details class="hm-channel-links"><summary>멤버별 채널 보기</summary><nav class="hm-members" aria-label="멤버별 소개 바로가기">${MEMBERS.map(m=>`<a class="hm-member ${m.tone}" href="#/record/${m.id}" data-home-member-link="${m.id}">${homeShortcutPortrait(m)}<span>${e(m.name)}</span>${icon('arrow')}</a>`).join('')}</nav></details></section>
 <section class="hm-section" aria-labelledby="hm-music-title"><header class="hm-section-head"><div><h2 id="hm-music-title">음악</h2><p>노래를 고르고, 영상으로 만나보세요.</p></div><a class="text-link" id="hm-all-music" href="#/music">전체 ${CATALOG.music.songs.length}개 ${icon('arrow')}</a></header><div class="hm-filters" role="group" aria-label="홈 음악 종류 선택">${[['original','오리지널'],['cover','커버'],['remake','리메이크']].map(([id,name])=>`<button type="button" data-home-music="${id}" aria-pressed="${homeMusicType===id}" aria-controls="hm-music">${name}</button>`).join('')}</div><div id="hm-music">${homeMusicContent()}</div><p class="sr-only" id="hm-music-status" role="status" aria-live="polite"></p></section>
 <nav class="hm-more" aria-label="일정과 활동 기록"><a href="#/schedule"><span class="hm-more-icon">${icon('calendar')}</span><div><h2>소식·일정</h2><p>${upcoming.length ? `${formatDate(upcoming[0].date)} · ${e(upcoming[0].title)}` : '날짜별 발매·행사 기록 보기'}</p></div>${icon('arrow')}</a><a href="#/history"><span class="hm-more-icon">${icon('clock')}</span><div><h2>활동 기록</h2><p>2021년 오디션부터 · ${HISTORY.events.length}개 주요 기록</p></div>${icon('arrow')}</a></nav></div>`;
}
document.addEventListener('click', event=>{
 const member = event.target.closest('[data-home-member]');
 if (member) {
  homeMember = member.dataset.homeMember;
  document.querySelectorAll('[data-home-member]').forEach(b=>b.setAttribute('aria-pressed',String(b===member)));
  document.querySelector('#hm-videos').innerHTML=homeVideoContent();
  document.querySelector('#hm-video-status').textContent=`${member.textContent} 영상 ${homeLatestVideos(CATALOG,homeMember).length}개`;
 }
 const music = event.target.closest('[data-home-music]');
 if (music) {
  homeMusicType=music.dataset.homeMusic;
  document.querySelectorAll('[data-home-music]').forEach(b=>b.setAttribute('aria-pressed',String(b===music)));
  document.querySelector('#hm-music').innerHTML=homeMusicContent();
  document.querySelector('#hm-music-status').textContent=`${music.textContent} 음악 표시`;
 }
});
document.addEventListener('error', event=>{
 const img=event.target;
 if(img instanceof HTMLImageElement && img.matches('[data-home-soop-image]')) {img.hidden=true;img.parentElement.dataset.imageError='true';}
 if(img instanceof HTMLImageElement && img.matches('[data-home-image]')) {img.hidden=true;img.parentElement.dataset.imageError='true';}
}, true);
