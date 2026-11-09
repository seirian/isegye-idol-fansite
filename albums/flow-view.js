/* View helpers for the isolated album preview; only aiChart/aiProviders use these. */
function albumFlowView(s) {
  const p=route().params, hours=aiHours(), kind=albumFlowKind(p.get('metric'),aiData(s.id));
  const demo=p.get('demo')==='1', end=Date.now();
  const rows=albumRankSeries(demo?albumDemoSeries(hours,end):aiHistory(s,kind),hours,end,100);
  const summary=albumRankSummary(rows), latest=summary.latest;
  const g=albumFlowGeometry(rows,end-hours*3600000,end,demo?hours*3600000:90*60000);
  const time=t=>new Intl.DateTimeFormat('ko-KR',{timeZone:'Asia/Seoul',month:'numeric',day:'numeric',hour:'2-digit',minute:'2-digit',hour12:false}).format(new Date(t));
  const gradient='melon-flow-'+String(s.id).replace(/[^a-z0-9-]/gi,'')+'-'+kind;
  const source=albumSafeUrl(albumInsights.domesticCharts?.[kind]?.source);
  let graphic='';
  if(g.points.length) {
    const areas=g.segments.filter(segment=>segment.length>1).map(segment=>{
      const d=albumSmoothPath(segment);
      return `<path class="ai-flow-area" d="${d} L${segment.at(-1).x},248 L${segment[0].x},248 Z" fill="url(#${gradient})"/><path class="ai-flow-line" d="${d}"/>`;
    }).join('');
    const dots=g.points.map((point,i)=>`<circle class="ai-dot ai-flow-dot ${i===g.points.length-1?'is-last':''}" cx="${point.x}" cy="${point.y}" r="${i===g.points.length-1?4:3}" tabindex="0" role="img" data-flow-value="${esc(stamp(point.at))} · ${point.rank}위${demo?' · 예시':''}" aria-label="${esc(stamp(point.at))} ${point.rank}위${demo?' · 예시':''}"><title>${esc(stamp(point.at))} · ${point.rank}위</title></circle>`).join('');
    graphic=`<div class="ai-flow-canvas"><div class="ai-flow-axis" aria-hidden="true">${g.ticks.map(t=>`<span>${t}위</span>`).join('')}</div><svg class="ai-chart ai-flow-svg ${g.gaps.length?'is-sparse':''}" viewBox="0 0 760 268" preserveAspectRatio="none" role="img" aria-label="${demo?'예시 · 실제 기록 아님. ':''}${esc(albumFlowKinds[kind])} 관측 순위. 위쪽일수록 높은 순위. 축 ${g.ticks[0]}위부터 ${g.ticks[2]}위. 점선은 중간 기록이 없는 간격입니다."><title>${demo?'예시 데이터':'멜론 원본 관측값'} · 곡선은 관측 지점 연결용</title><defs><linearGradient id="${gradient}" x1="0" y1="20" x2="0" y2="248" gradientUnits="userSpaceOnUse"><stop offset="0%" stop-color="currentColor" stop-opacity=".48"/><stop offset="100%" stop-color="currentColor" stop-opacity="0"/></linearGradient></defs>${[20,124,228].map(y=>`<line class="ai-flow-grid" x1="24" x2="736" y1="${y}" y2="${y}"/>`).join('')}${g.gaps.map(points=>`<path class="ai-flow-gap" d="${albumSmoothPath(points)}"><title>관측 사이 미수집 간격 · 중간 순위는 확인되지 않았습니다</title></path>`).join('')}${areas}${dots}</svg></div><div class="ai-flow-times"><span>${esc(time(g.start))}</span><span>${g.points.length===1?'단일 관측':'관측 구간 · KST'}</span><span>${esc(time(g.end))}</span></div><p class="ai-flow-readout" data-flow-readout aria-live="polite">${g.points.length===1?'순위 기록 1개 · 추세선은 아직 표시하지 않습니다.':'점에 마우스를 올리거나 키보드로 선택하면 정확한 수치를 확인할 수 있습니다.'}</p>`;
  } else {
    const message=latest?.status==='out'?'이 구간의 확인된 기록은 차트 밖입니다':latest?.status==='error'?'멜론 차트 응답을 확인하지 못했습니다':'선택한 기간의 멜론 순위 기록이 아직 없습니다';
    graphic=`<div class="ai-empty ai-flow-empty">${icon('music')}<strong>${message}</strong><p>미확인·차트 밖을 임의의 순위로 그리지 않습니다. 기록이 확인되면 이 영역에 표시합니다.</p></div>`;
  }
  const delta=summary.change;
  return `<section class="ai-panel ai-flow-panel" aria-label="음원 순위 추이"><div class="ai-panel-head"><div><p class="ai-kicker">MELON / RANK TREND</p><h2>음원의 흐름</h2><p class="ai-muted">멜론 차트의 변화를 한눈에.</p></div><a class="text-link small" href="${esc(patch({demo:demo?null:'1',metric:kind}))}" aria-pressed="${demo}">${demo?'실제 데이터로 돌아가기':'그래프 예시 보기'}</a></div><div class="ai-controls"><label><span class="sr-only">멜론 차트 선택</span><select data-filter="metric">${Object.entries(albumFlowKinds).map(([key,label])=>`<option value="${key}" ${key===kind?'selected':''}>${esc(label)}</option>`).join('')}</select></label><div class="ai-segments" aria-label="조회 기간">${[['24h','24시간',24],['7d','7일',168],['30d','30일',720]].map(([key,label,h])=>`<a href="${esc(patch({range:key,metric:kind}))}" aria-current="${hours===h}">${label}</a>`).join('')}</div></div>${demo?'<div class="ai-demo" role="note"><strong>예시 데이터 · 실제 순위가 아닙니다.</strong> 선·영역의 표현을 확인하는 검토용 예시입니다.</div>':''}<div class="ai-flow-surface"><div class="ai-flow-heading"><div><span class="ai-flow-name">${esc(albumFlowKinds[kind])}</span><strong class="ai-flow-rank">${aiRankLabel(latest)}</strong><small>${latest?esc(stamp(latest.at)):'관측 기록 대기'}</small></div><span class="ai-flow-period">최근 ${hours===24?'24시간':hours===168?'7일':'30일'}${demo?' · 예시':''}</span></div>${graphic}<div class="ai-flow-summary"><span>기간 관측 최고 <b>${summary.best===null?'—':summary.best+'위'}</b></span><span>직전 대비 <b>${delta===null?'—':delta===0?'유지':(delta>0?'↑ ':'↓ ')+Math.abs(delta)}</b></span><span>관측 <b>${rows.length}회</b></span></div></div><p class="ai-footnote ai-flow-note">멜론 원본 수집값 · 1위가 위쪽입니다. 곡선은 관측 지점을 부드럽게 연결한 표현이며, 중간 시각의 실측값을 뜻하지 않습니다.${g.gaps.length?' <strong>점선은 90분을 넘긴 미수집 간격</strong>이며 영역을 채우지 않습니다.':''} 차트 밖·수집 실패 전후는 연결하지 않습니다. 축은 확인된 순위와 시간 범위에 맞췄습니다.</p>${rows.length?`<details class="ai-detail-toggle"><summary>그래프 수치 표로 보기 · ${rows.length}개 시점</summary><div class="ai-table-wrap"><table class="ai-table"><caption>${demo?'예시 데이터 · 실제 기록 아님':esc(albumFlowKinds[kind])+' · 관측 원본'}</caption><thead><tr><th>기준 시각 (KST)</th><th>순위 / 상태</th></tr></thead><tbody>${rows.slice().reverse().map(row=>`<tr><td>${esc(stamp(row.at))}</td><td>${aiRankLabel(row)}</td></tr>`).join('')}</tbody></table></div></details>`:''}<p class="ai-footnote">${source?`<a href="${esc(source)}" target="_blank" rel="noopener noreferrer">멜론 차트 원본</a> · `:''}${aiStale()?'이전 스냅샷':'수집 시점 기준'} · 기간 관측 최고는 역대 최고가 아닙니다. 정기 수집은 검토 단계에서 활성화하지 않았습니다.</p></section>`;
}
function albumProviderPanel(s) {
  const item=aiData(s.id), providers=albumInsights.providers, charts=albumInsights.domesticCharts||{};
  const domestic=(key,name)=>({name,state:item[key]?.state==='ok'?'ok':'unmatched',label:item[key]?.state==='ok'?'연결됨':'곡 매칭 대기',detail:item[key]?.state!=='ok'?'동일 음원의 ID를 확인 중입니다':key==='melon'?(charts.melon_top100?.state==='ok'?'곡 정보·멜론 차트 확인':'곡 정보 확인 · 차트 재확인 필요'):'곡 정보·바로가기 확인',checkedAt:item[key]?.checkedAt});
  const rows=[domestic('melon','멜론'),domestic('genie','지니'),domestic('bugs','벅스'),{name:'유튜브 뮤직',state:'link',label:'검색 연결',detail:'별도 재생수·차트 수집 대상 아님'}, {name:'유튜브',...albumFreeServiceStatus('youtube',item,providers)}, {name:'애플 뮤직 · US',...albumFreeServiceStatus('apple',item,providers)}];
  return `<section class="ai-panel ai-subsection ai-provider-panel"><p class="ai-kicker">DATA SOURCES</p><h2>서비스 연결 상태</h2>${rows.map(row=>`<div class="ai-provider-entry" data-provider-state="${row.state}"><div class="ai-provider-top"><span>${esc(row.name)}</span><span class="ai-status-badge is-${row.state}">${esc(row.label)}</span></div><p>${esc(row.detail)}</p>${row.checkedAt?`<small>${esc(stamp(row.checkedAt))}</small>`:''}</div>`).join('')}<p class="ai-footnote">유튜브 공개 통계와 Apple iTunes Search 곡 정보는 무료 범위만 사용합니다. 유료 Apple Music API·MusicKit 연동은 사용하지 않습니다. 순위 흐름은 멜론만 표시합니다.</p></section>`;
}
function albumFlowReadout(event) {
  const dot=event.target.closest?.('[data-flow-value]');
  if(!dot)return;
  const output=dot.closest('.ai-flow-panel')?.querySelector('[data-flow-readout]');
  if(output)output.textContent=dot.dataset.flowValue;
}
document.addEventListener('pointerover',albumFlowReadout);
document.addEventListener('focusin',albumFlowReadout);
