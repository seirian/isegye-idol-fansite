/* Feature-only enhancement. Compiled after existing app declarations, before render. */
let albumInsights = albumValidSnapshot(ALBUMS_SEED) ? ALBUMS_SEED : {schemaVersion:1,generatedAt:'',tracks:{},providers:{}};
let albumApiState = '검토 스냅샷';
const aiData = id => albumInsights.tracks[id] || {};
const aiNumber = n => Number.isFinite(n) ? new Intl.NumberFormat('ko-KR').format(n) : '미확인';
const aiRelated = a => (a?.songIds || []).map(id => songs.get(id)).filter(Boolean);
const aiMetaCount = rows => rows.filter(s => aiData(s.id).melon?.state==='ok').length;
const aiHours = () => ({'24h':24,'7d':168,'30d':720}[route().params.get('range')] || 168);
const aiStale = () => !Number.isFinite(Date.parse(albumInsights.generatedAt)) || Date.now() - Date.parse(albumInsights.generatedAt) > 36*3600000;
const aiKinds = {melon_top100:'멜론 TOP100',melon_hot100:'멜론 HOT100 · 100일',genie:'지니 TOP200',bugs:'벅스 TOP100',apple:'Apple Music · KR TOP100'};
const aiLimit = kind => kind === 'genie' ? 200 : 100;
function aiArt(a, selected = null) {
  const candidates = selected ? [selected, ...aiRelated(a)] : aiRelated(a);
  const artwork = candidates.map(song => aiData(song.id).artwork).find(v => v && ALBUMS_ART[v.asset]);
  if (artwork) return `<div class="ai-art ai-cover"><img src="${ALBUMS_ART[artwork.asset]}" alt="${esc(a.title)} 앨범 표지" width="400" height="400" loading="lazy" decoding="async"></div>`;
  const n = [...a.id].reduce((v,c) => v+c.charCodeAt(0),0) % 6;
  const letters = (a.title.replace(/[^a-zA-Z가-힣0-9]/g,'').slice(0,2) || '♪').toUpperCase();
  return `<div class="ai-art ai-art-${n}" aria-label="${esc(a.title)} · 국내 발매 표지 미확인"><b>${esc(letters)}</b><span class="ai-label">표지 확인 전</span></div>`;
}

function aiBanner() {
  return `<div class="ai-review" role="note"><strong>앨범 1차 검토 · feature/albums</strong><span>운영 미반영 · 관리자 검토 전용 · <span data-ai-api>${esc(albumApiState)}</span></span></div>`;
}
function aiLink(value, label, cls='') {
  const u = albumSafeUrl(value);
  return u ? `<a class="${cls}" href="${esc(u)}" target="_blank" rel="noopener noreferrer">${esc(label)} ${icon('external')}</a>` : '';
}
function aiHistory(s, kind) {
  const item = aiData(s.id);
  if (item.charts?.[kind]) return item.charts[kind];
  return kind === 'melon_hot100' ? item.melon?.hot100History || [] : kind === 'melon_top100' ? item.melon?.top100History || [] : kind === 'apple' ? item.appleHistory || [] : [];
}
function aiDefaultKind(s) { const item=aiData(s.id); return ['melon_top100','melon_hot100'].find(k=>aiHistory(s,k).at(-1)?.status==='ranked') || 'melon_top100'; }
function aiRankLabel(p, limit=100) { return !p ? '수집 전' : p.status === 'ranked' ? `${p.rank}위` : p.status === 'out' ? `TOP${limit} 밖` : '확인 실패'; }
function aiServiceState(state) { return ({ok:'API 확인',partial:'일부 확인',error:'확인 실패',not_configured:'연동 대기',unavailable:'확인 불가'})[state] || '연동 대기'; }
function aiSourceFooter(s) {
  const item=aiData(s.id), h=albumVerifiedHonor(item,ALBUMS_BADGES),p=albumVerifiedPeaks(item),source=item.metadata;
  return `<details class="ai-detail-toggle"><summary>데이터 기준과 원본 확인</summary><p class="ai-footnote">멜론 → 지니·벅스·유튜브 뮤직·유튜브 → 애플 뮤직 순으로 확인된 정보를 사용합니다. 음원 순위·영상 조회수·앨범 달성 기록은 서로 다른 지표입니다. 미확인은 0으로 바꾸지 않습니다.</p><div class="ai-links">${aiLink(item.melon?.url,'멜론 원본')}${aiLink(item.genie?.url,'지니 원본')}${aiLink(item.bugs?.url,'벅스 원본')}${aiLink(s.videoId?'https://www.youtube.com/watch?v='+s.videoId:null,'유튜브 영상 원본')}${aiLink(source?.url,'애플 뮤직 원본 · US')}${aiLink(item.artwork?.source,'앨범 표지 출처')}${h?aiLink(h.source,'멜론의 전당 공식 기록'):''}${p?aiLink(p.source,'최고 성적 관측 출처'):''}</div>${source?`<p class="ai-footnote">보완 정보: Apple iTunes Search API · 미국 카탈로그 · ${esc(source.artist)} / ${esc(source.title)} / ${esc(source.album)} · ${esc(stamp(source.checkedAt))}</p>`:''}</details>`;
}
function aiHonor(a,s=null) {
  const h=(s?[s,...aiRelated(a)]:aiRelated(a)).map(t=>albumVerifiedHonor(aiData(t.id),ALBUMS_BADGES)).find(Boolean);
  if(!h)return '';
  const label=`멜론의 전당 ${h.label} 달성 · ${a.title} 앨범 발매 첫 24시간 기준`;
  return `<span class="ai-honor" role="img" aria-label="${esc(label)}" title="${esc(label)}"><img src="${ALBUMS_BADGES[h.asset]}" alt="" width="60" height="60"><b aria-hidden="true">${esc(h.label)}</b></span>`;
}
function aiPeaks(s) {
  const item=aiData(s.id),p=albumVerifiedPeaks(item);
  return `<section class="ai-panel ai-peaks" aria-label="멜론 차트 최고 성적"><div class="ai-panel-head"><div><p class="ai-kicker">MELON / BEST RECORD</p><h2>멜론 차트 최고 성적</h2><p class="ai-muted">${esc(s.title)}</p></div><span class="badge neutral">${p?'외부 관측 기록':'기록 확인 전'}</span></div><div class="ai-peaks-grid">${[['top100','TOP100'],['hot100','HOT100 · 100일'],['realtime','실시간']].map(([key,label])=>`<div class="ai-peak" data-peak="${key}"><span>${label}</span><strong>${Number.isInteger(p?.ranks[key])?p.ranks[key]+'<small>위</small>':'—'}</strong><small>${Number.isInteger(p?.ranks[key])?'확인된 최고 성적':p?'확인된 기록 없음':'출처 확인 전'}</small></div>`).join('')}</div><p class="ai-footnote">${p?`이세계차트 공개 관측 기록 · ${esc(stamp(p.checkedAt))} 확인 · ${aiLink(p.source,'기록 출처')}. 멜론 공식 인증 기록이 아니며 수집 범위 밖 기록은 포함되지 않을 수 있습니다.`:'확인된 최고 기록을 연결 중입니다. 현재 순위나 최근 수집 기간의 최고값을 역대 최고 성적으로 대신하지 않습니다.'} 아래 기간별 그래프와는 집계 범위가 다릅니다.</p></section>`;
}

function aiStreaming(s) {
  const data = aiData(s.id), q = encodeURIComponent(memberText(s.members)+' '+s.title), official = s.videoSource?.kind?.startsWith('official_');
  const platforms = [
    ['melon','멜론',data.melon?.url,'https://www.melon.com/search/total/index.htm?q='+q],
    ['genie','지니',data.genie?.url,'https://www.genie.co.kr/search/searchMain?query='+q],
    ['bugs','벅스',data.bugs?.url,'https://music.bugs.co.kr/search/integrated?q='+q],
    ['youtube_music','유튜브 뮤직',data.youtube_music?.url,'https://music.youtube.com/search?q='+q],
    ['youtube','유튜브',s.videoId?'https://www.youtube.com/watch?v='+encodeURIComponent(s.videoId):null,'https://www.youtube.com/results?search_query='+q],
    ['apple','애플 뮤직',data.metadata?.url,'https://music.apple.com/kr/search?term='+q]
  ];
  return `<section class="ai-panel ai-streaming"><p class="ai-kicker">LISTEN & EXPLORE</p><h2>음원 연결</h2><p class="ai-muted">곡 바로가기와 검색을 구분했습니다.</p><div class="ai-platform-links">${platforms.map(([key,label,direct,search])=>{
    const validDirect=albumSafeUrl(direct), target=validDirect||albumSafeUrl(search), badge=validDirect?(key==='youtube'?(official?'공식 영상':'출처 확인'):key==='apple'?'곡 · US':'곡 바로가기'):'검색';
    return target?`<a class="ai-platform-link" href="${esc(target)}" target="_blank" rel="noopener noreferrer" aria-label="${label} · ${badge} · 새 창">${ALBUMS_BRANDS[key]?`<img class="ai-platform-logo" src="${ALBUMS_BRANDS[key]}" alt="" width="24" height="24">`:''}<span>${label}</span><small>${badge}</small></a>`:'';
  }).join('')}</div>${!official&&s.videoId?'<p class="ai-footnote">현재 영상 연결은 공식 MV로 확인된 링크가 아닙니다. 기존 출처 구분을 유지합니다.</p>':''}</section>`;
}

function aiProviders(s) {
  const p=albumInsights.providers, item=aiData(s.id), charts=albumInsights.domesticCharts||{};
  const rows=[
    ['멜론',item.melon?.url?(charts.melon_top100?.state==='ok'?'곡 · 차트 확인':'곡 연결 · 차트 확인 실패'):'음원 매칭 대기'],
    ['지니',item.genie?.url?(charts.genie?.state==='ok'?'곡 · TOP200 확인':'곡 연결 · 차트 확인 실패'):'음원 매칭 대기'],
    ['벅스',item.bugs?.url?(charts.bugs?.state==='ok'?'곡 · TOP100 확인':'곡 연결 · 차트 확인 실패'):'음원 매칭 대기'],
    ['유튜브 뮤직','검색 연결 · 별도 재생수 미제공'],
    ['유튜브 지표',aiServiceState(item.youtube?.state)],
    ['애플 뮤직 메타데이터 · US',item.metadata?'API 확인':'음원 매칭 대기']
  ];
  return `<section class="ai-panel ai-subsection"><p class="ai-kicker">DATA SOURCES</p><h2>서비스 연결 상태</h2>${rows.map(([name,state])=>`<div class="ai-provider-row"><span>${esc(name)}</span><small>${esc(state)}</small></div>`).join('')}<p class="ai-footnote">멜론·지니·벅스는 공개 페이지에서 검증한 정보입니다. Apple·YouTube는 공식 API를 사용합니다. 미연동과 차트 밖은 다릅니다.</p></section>`;
}

function aiSpark(s) {
  const rows = albumRankSeries(aiHistory(s,aiDefaultKind(s)),168), valid = rows.filter(p=>p.rank!==null);
  if(valid.length<2)return `<span class="ai-footnote">${rows.length?'이력 축적 중':'순위 이력 수집 전'}</span>`;
  const g = albumRankGeometry(rows,rows[0].t,rows.at(-1).t,aiDefaultKind(s)==='apple'?36*3600000:90*60000);
  return `<svg class="ai-spark" viewBox="0 0 760 280" role="img" aria-label="최근 7일 순위 추이 · 상세에서 수치 확인">${g.paths.map(p=>`<polyline points="${p.map(v=>v.x+','+v.y).join(' ')}" fill="none" stroke="currentColor" stroke-width="12"/>`).join('')}</svg>`;
}
function aiLengthSpark(rs) {
  const values=rs.map(s=>albumPreferredField(aiData(s.id),'durationMs').value).filter(v=>Number.isFinite(v)&&v>0).slice(0,8);
  if(!values.length)return '<span class="ai-footnote">API 확인 전</span>';
  const max=Math.max(...values),w=100/values.length;
  return `<div><svg class="ai-spark" viewBox="0 0 100 40" role="img" aria-label="확인된 음원 재생시간 비교 · 인기도 그래프 아님">${values.map((v,i)=>`<rect x="${i*w+2}" y="${36-v/max*30}" width="${Math.max(2,w-5)}" height="${v/max*30}" rx="2" fill="currentColor" opacity="${.45+.55*i/Math.max(1,values.length-1)}"/>`).join('')}</svg><small class="ai-mini-label">수록곡 길이</small></div>`;
}
function albumCard(a) {
  const rs = aiRelated(a), lead = rs.find(s=>aiHistory(s,aiDefaultKind(s)).some(p=>p.status==='ranked')) || rs.find(s=>aiData(s.id).metadata) || rs[0];
  const observation = lead ? albumRankSeries(aiHistory(lead,aiDefaultKind(lead)),720).at(-1) : null, count = a.tracks.length || rs.length;
  return `<article class="ai-card"><a class="ai-card-top" href="#/album/${esc(a.id)}">${aiArt(a)}<div><span class="ai-kicker">${esc(a.format||'ALBUM')}</span><div class="ai-title-row"><h3>${esc(a.title)}</h3>${aiHonor(a)}</div><p>${esc(memberText(a.members))}</p><p>${dateText(a.date)} · ${count}곡</p></div></a><div class="ai-card-metric"><div><p>${lead&&observation?esc(aiKinds[aiDefaultKind(lead)]):'멜론 음원 정보'}</p><strong>${lead&&observation?aiRankLabel(observation):`${aiMetaCount(rs)} / ${rs.length}곡 확인`}</strong></div>${lead&&aiHistory(lead,aiDefaultKind(lead)).filter(p=>p.status==='ranked').length>1?aiSpark(lead):aiLengthSpark(rs)}</div><div class="ai-card-footer"><a href="#/album/${esc(a.id)}">수록곡과 기록 보기 →</a>${saveButton(a)}</div></article>`;
}
function musicView(p) {
  if(p.get('tab')!=='albums')return albumsBaseMusicView(p);
  let rows = filtered(D.albums.map(a=>({...a,tags:[...(a.tags||[]),...(a.tracks||[]),...aiRelated(a).flatMap(s=>[s.title,...(s.aliases||[])])]})),p);
  const sort=p.get('sort')||'new';
  rows.sort((a,b)=>sort==='title'?a.title.localeCompare(b.title,'ko') : (sort==='old'?1:-1)*a.date.localeCompare(b.date));
  const pg=paginate(rows,p), allAlbumSongs=[...new Map(D.albums.flatMap(aiRelated).map(s=>[s.id,s])).values()], mode=p.get('view')==='list'?'list':'cards';
  return aiBanner()+`<header class="ai-intro"><div><span class="ai-kicker">MUSIC / ALBUM OBSERVATORY</span><h1>한 곡에서 시작되는 이야기</h1><p>수록곡을 발견하고, 음원의 지금과 변화를 함께 확인하세요.</p></div><div class="ai-total"><div><strong>${D.albums.length}</strong><small>등록 앨범</small></div><div><strong>${allAlbumSongs.length}</strong><small>연결된 곡</small></div><div><strong>${aiMetaCount(allAlbumSongs)}</strong><small>멜론 정보 확인</small></div></div></header>`+tabs([['songs','곡',D.songs.length],['albums','앨범',D.albums.length],['videos','공식 음악 영상']],'albums')+`<section class="panel filters"><form class="search-form" data-query-form><label class="sr-only" for="music-q">앨범·수록곡 검색</label><input id="music-q" type="search" name="q" value="${esc(p.get('q')||'')}" placeholder="앨범·수록곡·멤버 검색" maxlength="180"><button type="submit">검색</button></form>${memberChips(p)}<div class="filter-row">${choose('연도','year',[['all','전체 연도'],...[...new Set(D.albums.map(a=>a.date.slice(0,4)))].sort().reverse().map(y=>[y,y+'년'])],p.get('year')||'all')}${choose('정렬','sort',[['new','최신 발매순'],['old','오래된순'],['title','제목순']],sort)}${choose('멤버 조건','match',[['any','선택 멤버 중 누구나'],['all','선택 멤버 모두']],p.get('match')||'any')}</div></section><div class="result-bar"><p><strong>${rows.length}</strong>개 앨범</p><div class="ai-segments" aria-label="목록 보기 방식"><a href="${esc(patch({view:'cards'}))}" aria-current="${mode==='cards'}">카드</a><a href="${esc(patch({view:'list'}))}" aria-current="${mode==='list'}">리스트</a></div></div>${rows.length?`<div class="ai-grid ${mode==='list'?'ai-list-view':''}">${pg.rows.map(albumCard).join('')}</div>${pg.html}`:empty('조건에 맞는 앨범이 없습니다','검색어와 선택한 조건을 바꿔 보세요.')}<p class="ai-footnote">정보 기준 ${esc(stamp(albumInsights.generatedAt))} · ${aiStale()?'오래된 저장본 · 최신 원본 재확인 필요':'검토 시점 수집 스냅샷'} · 앨범 표지는 멜론 등 국내 음원 사이트에서 확인했으며 상세의 출처에서 원본을 볼 수 있습니다. 미발매 영상은 표지 확인 전으로 구분합니다. 순위는 대표곡 기준이며, 작은 막대는 수록곡 길이 비교입니다. 미국 메타데이터를 한국 순위로 간주하지 않습니다.</p>`;
}
function aiDurationChart(a, activeId='') {
  const rows = aiRelated(a).map(s=>({s,ms:albumPreferredField(aiData(s.id),'durationMs').value,source:albumPreferredField(aiData(s.id),'durationMs').label})).filter(v=>Number.isFinite(v.ms)&&v.ms>0);
  if(!rows.length)return '';
  const max=Math.max(...rows.map(r=>r.ms));
  return `<section class="ai-panel ai-subsection"><div class="ai-panel-head"><div><p class="ai-kicker">ALBUM AT A GLANCE</p><h2>수록곡 재생시간</h2></div><span class="badge neutral">음원 메타데이터 · ${rows.length}곡 확인</span></div>${rows.map(({s,ms,source})=>`<div class="ai-duration-row"><a href="#/song/${esc(s.id)}" ${s.id===activeId?'aria-current="true"':''}><span>${esc(s.title)}</span></a><meter min="0" max="${max}" value="${ms}" aria-label="${esc(s.title)} 재생시간 ${albumDuration(ms)}">${albumDuration(ms)}</meter><span class="ai-duration-meta"><b>${albumDuration(ms)}</b><small>${esc(source)}</small></span></div>`).join('')}<p class="ai-footnote">곡 길이를 비교하는 그래프입니다. 재생 수·인기도를 나타내지 않습니다. 미확인 트랙은 제외했습니다.</p></section>`;
}
function aiVideoChart(a,activeId='') {
  const metric=route().params.get('videoMetric')==='likes'?'likeCount':'viewCount', label=metric==='viewCount'?'조회수':'좋아요';
  const rows=aiRelated(a).map(s=>({s,y:aiData(s.id).youtube})).filter(r=>r.y?.state==='ok'&&Number.isFinite(r.y[metric]));
  if(!rows.length)return '';
  const max=Math.max(1,...rows.map(r=>r.y[metric]));
  return `<section class="ai-panel ai-video-panel"><div class="ai-panel-head"><div><p class="ai-kicker">OFFICIAL VIDEO / YOUTUBE</p><h2>공식 영상의 반응</h2><p class="ai-muted">같은 앨범의 공식 영상 ${rows.length}개 · 공개 API 확인값</p></div><div class="ai-segments" aria-label="영상 통계 선택"><a href="${esc(patch({videoMetric:'views'}))}" aria-current="${metric==='viewCount'}">조회수</a><a href="${esc(patch({videoMetric:'likes'}))}" aria-current="${metric==='likeCount'}">좋아요</a></div></div><div class="ai-video-bars">${rows.map(({s,y})=>`<div class="ai-video-row ${s.id===activeId?'is-selected':''}"><div><a href="#/song/${esc(s.id)}">${esc(s.title)}</a><strong>${aiNumber(y[metric])}<small> ${label==='조회수'?'회':'개'}</small></strong></div><meter min="0" max="${max}" value="${y[metric]}" aria-label="${esc(s.title)} 공식 영상 ${label} ${aiNumber(y[metric])}">${aiNumber(y[metric])}</meter></div>`).join('')}</div><p class="ai-footnote">${esc(stamp(rows[0].y.checkedAt))} 기준 · YouTube Data API. 영상의 공개 시점·유형이 달라 곡의 인기도 순위로 해석하지 않습니다. 미확인 영상은 제외했습니다.</p></section>`;
}
function aiTrackList(a,activeId='') {
  const related=aiRelated(a), titles=a.tracks.length?a.tracks:related.map(s=>s.title);
  return `<section class="ai-panel ai-subsection"><p class="ai-kicker">TRACKS / ${String(titles.length).padStart(2,'0')}</p><h2>같은 앨범, 다른 이야기</h2><div class="ai-track-list">${titles.map((title,i)=>{const s=related.find(s=>normalized(s.title)===normalized(title)), info=s?aiData(s.id):{};return `<div class="ai-track"><span>${String(i+1).padStart(2,'0')}</span><div><h3>${s?`<a href="#/song/${esc(s.id)}" ${s.id===activeId?'aria-current="true"':''}>${esc(title)} ${s.id===activeId?'· 보고 있는 곡':'↗'}</a>`:esc(title)}</h3><small>${s?info.melon?.state==='ok'?'멜론 정보 확인':info.genie?.state==='ok'?'지니 정보 확인':info.bugs?.state==='ok'?'벅스 정보 확인':info.metadata?'애플 뮤직 정보 확인':'음원 정보 확인 전':'트랙명 확인 · 상세 준비 중'}</small></div><div class="ai-track-meta">${albumDuration(albumPreferredField(info,'durationMs').value)}</div></div>`;}).join('')}</div></section>`;
}
function aiChart(s) {
  const p=route().params, hours=aiHours(), kind=Object.hasOwn(aiKinds,p.get('metric'))?p.get('metric'):aiDefaultKind(s);
  const demo=p.get('demo')==='1', limit=aiLimit(kind), end=Date.now(), rows=albumRankSeries(demo?albumDemoSeries(hours,end):aiHistory(s,kind),hours,end,limit), stats=albumRankSummary(rows);
  const g=albumRankGeometry(rows,end-hours*3600000,end,demo?hours*3600000:kind==='apple'?36*3600000:90*60000,limit),last=stats.latest,change=stats.change;
  const timeLabel=t=>new Intl.DateTimeFormat('ko-KR',{timeZone:'Asia/Seoul',month:'numeric',day:'numeric',hour:'2-digit',hour12:false}).format(new Date(t));
  let chart='';
  if(g.points.length)chart=`<svg class="ai-chart" viewBox="0 0 760 280" role="img" aria-label="${demo?'예시 데이터 · 실제 순위 아님. ':''}${esc(aiKinds[kind])} 순위 추이. 1위가 위쪽이며 확인되지 않은 구간은 연결하지 않습니다."><title>${demo?'예시 그래프 (실제 순위 아님)':'확인된 순위 이력'}</title>${(limit===200?[1,50,100,150,200]:[1,25,50,75,100]).map(rank=>{const y=20+(rank-1)/(limit-1)*228;return `<line class="ai-grid-line" x1="44" y1="${y}" x2="740" y2="${y}"/><text x="0" y="${y+4}">${rank}위</text>`;}).join('')}${g.paths.filter(path=>path.length>1).map(path=>`<polyline class="ai-line" points="${path.map(v=>v.x+','+v.y).join(' ')}"/>`).join('')}${g.points.map(v=>`<circle class="ai-dot" cx="${v.x}" cy="${v.y}" r="4" tabindex="0" role="img" aria-label="${esc(stamp(v.at))} ${v.rank}위${demo?' · 예시':''}"><title>${esc(stamp(v.at))} · ${v.rank}위${demo?' (예시)':''}</title></circle>`).join('')}<text x="44" y="275">${esc(timeLabel(end-hours*3600000))}</text><text x="740" y="275" text-anchor="end">${esc(timeLabel(end))} KST</text></svg>`;
  else chart=`<div class="ai-empty">${icon('music')}<strong>${last?.status==='out'?`확인된 시점에는 TOP${limit} 밖입니다`:last?.status==='error'?'차트 응답을 확인하지 못했습니다':'이 구간의 순위 이력이 아직 없습니다'}</strong><p>${last?.status==='out'?'차트 밖은 임의의 순위나 0위로 바꾸어 그리지 않습니다.':last?.status==='error'?'실패한 요청을 차트 밖으로 표시하지 않습니다. 원본 확인 후 다시 수집합니다.':kind==='apple'&&aiData(s.id).appleChartMatch==='unverified_storefront'?'미국 메타데이터와 한국 차트 ID의 연결을 확인 중입니다. 이를 차트 밖으로 표시하지 않습니다.':'첫 수집부터 기록을 쌓습니다. 과거 순위를 임의로 생성하지 않습니다.'}</p></div>`;
  return `<section class="ai-panel" aria-label="음원 순위 추이"><div class="ai-panel-head"><div><p class="ai-kicker">CHART EXPLORER</p><h2>음원의 흐름</h2><p class="ai-muted">서비스와 기간을 선택해 한 그래프에 집중하세요.</p></div><a class="text-link small" href="${esc(patch({demo:demo?null:'1'}))}" aria-pressed="${demo}">${demo?'실제 데이터로 돌아가기':'그래프 예시 보기'}</a></div><div class="ai-controls"><label><span class="sr-only">차트 선택</span><select data-filter="metric">${Object.entries(aiKinds).map(([value,label])=>`<option value="${value}" ${value===kind?'selected':''}>${esc(label)}</option>`).join('')}</select></label><div class="ai-segments" aria-label="조회 기간">${[['24h','24시간',24],['7d','7일',168],['30d','30일',720]].map(([value,label,h])=>`<a href="${esc(patch({range:value}))}" aria-current="${hours===h}">${label}</a>`).join('')}</div></div>${demo?'<div class="ai-demo" role="note"><strong>예시 데이터 · 실제 순위가 아닙니다.</strong> 그래프 동작과 배치 검토 전용입니다.</div>':''}${rows.length?`<div class="ai-metrics"><div class="ai-metric"><span>${demo?'예시 마지막 순위':'선택 기간 마지막 기록'}</span><strong>${aiRankLabel(last,limit)}</strong><small>${last?esc(stamp(last.at)):'기록 없음'}</small></div><div class="ai-metric"><span>${demo?'예시 구간 최고':'선택 기간 관측 최고'}</span><strong>${stats.best===null?'—':stats.best+'위'}</strong><small>역대 최고 순위 아님</small></div><div class="ai-metric"><span>직전 관측 대비</span><strong class="${change>0?'ai-up':''}">${change===null?'—':change===0?'유지':(change>0?'↑ ':'↓ ')+Math.abs(change)}</strong><small>두 시점 모두 차트인일 때</small></div><div class="ai-metric"><span>확인된 시점</span><strong>${stats.observations}<small>개</small></strong><small>${demo?'예시 기록':'수집 실패 포함 · 빈 구간 보간 없음'}</small></div></div>`:''}${chart}<div class="ai-chart-status"><span>${g.points.length===1?'순위 기록 1개 · 추세선을 아직 그리지 않습니다.':'숫자가 작을수록 높은 순위 · 점에 포커스하면 수치를 확인할 수 있습니다.'}</span><span>${demo?'SAMPLE ONLY':aiStale()?'오래된 스냅샷':'수집 시점 기준'}</span></div>${rows.length?`<details class="ai-detail-toggle"><summary>그래프 수치 표로 보기 · ${rows.length}개 시점</summary><div class="ai-table-wrap"><table class="ai-table"><caption>${demo?'예시 데이터 · 실제 기록 아님':esc(aiKinds[kind])+' · 수집된 기록만 표시'}</caption><thead><tr><th>기준 시각 (KST)</th><th>순위 / 상태</th></tr></thead><tbody>${rows.slice().reverse().map(v=>`<tr><td>${esc(stamp(v.at))}</td><td>${aiRankLabel(v,limit)}</td></tr>`).join('')}</tbody></table></div></details>`:''}<p class="ai-footnote">멜론을 우선 표시하고 지니·벅스, 애플 뮤직 순으로 차트를 선택할 수 있습니다. 국내 차트는 공개 페이지, 애플 뮤직은 한국 most-played 공식 피드입니다. 유튜브 뮤직·유튜브의 영상 통계는 음원 순위로 환산하지 않습니다. 차트 기준 시각과 수집 시각은 구분하며, 자동 정기 수집은 아직 활성화하지 않았습니다.</p></section>`;
}
function aiSongFacts(s) {
  const item=aiData(s.id),genre=albumPreferredField(item,'genre'), duration=albumPreferredField(item,'durationMs'),y=item.youtube;
  const facts=[
    {provider:'melon',label:'멜론 좋아요',value:aiNumber(item.melon?.likes),note:Number.isFinite(item.melon?.likes)?stamp(item.melon.checkedAt):'공개 응답 확인 전'},
    {provider:genre.provider,label:'장르 · '+genre.label,value:genre.value||'확인 전',note:'음원 정보 우선순위 적용',text:true},
    {provider:'youtube',label:'공식 영상 조회수 · 유튜브',value:aiNumber(y?.viewCount),note:y?.state==='ok'?stamp(y.checkedAt):'공개 API 확인 전'},
    {provider:duration.provider,label:'재생시간 · '+duration.label,value:albumDuration(duration.value),note:'곡 길이 · 영상 길이와 구분'}
  ];
  const order=p=>albumProviderOrder.includes(p)?albumProviderOrder.indexOf(p):99;
  facts.sort((a,b)=>order(a.provider)-order(b.provider));
  return `<div class="ai-metrics">${facts.map(f=>`<div class="ai-metric"><span>${esc(f.label)}</span><strong class="${f.text?'ai-text-value':''}">${esc(f.value)}</strong><small>${esc(f.note)}</small></div>`).join('')}</div>`;
}

function songView(id) {
  const s=songs.get(id),a=s&&albums.get(s.albumId);
  if(!s||!a)return albumsBaseSongView(id);
  return aiBanner()+`<nav class="ai-hero-nav" aria-label="음악 경로"><a href="#/music?tab=albums">앨범 목록</a><span>/</span><a href="#/album/${esc(a.id)}">${esc(a.title)}</a><span>/ 곡 상세</span></nav><header class="ai-hero">${aiArt(a,s)}<div><span class="ai-kicker">TRACK / ${esc(memberText(s.members))}</span><div class="ai-title-row"><h1>${esc(s.title)}</h1>${aiHonor(a,s)}</div><p>${dateText(s.date)} · ${esc(s.format)} · ${esc(a.title)}</p><div class="button-row">${saveButton(s)}<a class="button" href="#/album/${esc(a.id)}">앨범 전체 보기</a></div></div></header>${aiPeaks(s)}${aiSongFacts(s)}<div class="ai-workspace"><div>${aiChart(s)}${aiVideoChart(a,s.id)}${aiDurationChart(a,s.id)}${aiTrackList(a,s.id)}${aiSourceFooter(s)}</div><aside>${aiStreaming(s)}${aiProviders(s)}</aside></div>`;
}
function albumView(id) {
  const a=albums.get(id);if(!a)return notFound();
  const rs=aiRelated(a),selectedSong=rs.find(s=>s.id===route().params.get('track')) || rs[0];
  return aiBanner()+`<nav class="ai-hero-nav"><a href="#/music?tab=albums">← 앨범 목록으로</a></nav><header class="ai-hero">${aiArt(a)}<div><span class="ai-kicker">ALBUM / ${esc(a.format)}</span><div class="ai-title-row"><h1>${esc(a.title)}</h1>${aiHonor(a)}</div><p>${esc(memberText(a.members))} · ${dateText(a.date)} · ${a.tracks.length||rs.length}곡</p><div class="button-row">${selectedSong?`<a class="button primary" href="#/song/${esc(selectedSong.id)}">선택 곡 자세히 보기 →</a>`:''}${saveButton(a)}</div></div></header>${selectedSong?`<div class="ai-controls"><label>기록을 확인할 수록곡 <select data-filter="track">${rs.map(s=>`<option value="${esc(s.id)}" ${s.id===selectedSong.id?'selected':''}>${esc(s.title)}</option>`).join('')}</select></label><span class="ai-footnote">메타데이터 ${aiMetaCount(rs)} / ${rs.length}곡 확인</span></div>${aiPeaks(selectedSong)}<div class="ai-workspace"><div>${aiChart(selectedSong)}${aiVideoChart(a,selectedSong.id)}${aiDurationChart(a)}${aiTrackList(a)}${aiSourceFooter(selectedSong)}</div><aside>${aiStreaming(selectedSong)}${aiProviders(selectedSong)}</aside></div>`:aiTrackList(a)}`;
}
async function aiLoadSnapshot() {
  if(!location.pathname.startsWith('/review-albums/'))return;
  const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),8000);
  try {
    const response=await fetch('/review-albums/api/insights',{credentials:'same-origin',cache:'no-store',signal:controller.signal});
    if(!response.ok || !(response.headers.get('content-type')||'').includes('application/json'))throw new Error('API unavailable');
    const text=await response.text();if(text.length>2000000)throw new Error('Oversized API response');
    const next=JSON.parse(text);if(!albumValidSnapshot(next))throw new Error('Invalid API schema');
    if(next.generatedAt!==albumInsights.generatedAt)throw new Error('Snapshot version mismatch');
    albumInsights=next;albumApiState='동일 출처 API 확인';
  } catch {albumApiState='API 응답 실패 · 내장 검토본 표시';}
  finally {clearTimeout(timer);document.querySelectorAll('[data-ai-api]').forEach(el=>el.textContent=albumApiState);}
}
queueMicrotask(aiLoadSnapshot);
