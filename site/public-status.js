function statusView(){
 const sources=D.sources.filter(source=>source.kind!=='unverified');
 const checked=value=>value&&Number.isFinite(Date.parse(value))?stamp(value):'확인된 날짜가 없습니다';
 return heading('자료 확인 안내','자료의 출처와 마지막 확인 날짜를 안내합니다.','SOURCES & UPDATES')+`
 <div class="notice-box">표시된 날짜는 자료를 마지막으로 확인한 시점입니다. 이후 변경·취소·삭제된 내용은 원문에서 확인해 주세요.</div>
 <div class="grid two"><section class="panel"><h2>소식·일정</h2><p>자료 기준 ${esc(checked(D.snapshotAt))}</p><p>공지 ${D.notices.length.toLocaleString('ko-KR')}건 · 일정 ${D.events.length}건</p></section>
 <section class="panel"><h2>영상</h2><p>자료 기준 ${esc(checked(D.scope.videoCheckedAt))}</p><p>등록 영상 ${D.videos.length.toLocaleString('ko-KR')}개</p><p class="small muted">개별 영상의 확인 날짜는 상세 페이지에서 볼 수 있습니다.</p></section></div>
 <section class="section">${sectionHead('출처별 마지막 확인','공식 원문과 참고 자료를 구분해 안내합니다.')}<div class="status-list">
 ${sources.map(source=>`<article class="panel status-item"><div><h3>${esc(sourceNames[source.id]||source.label||source.id)}</h3><p class="small">마지막 확인 ${esc(checked(source.lastSuccessAt))}</p>${source.kind==='fan'?'<p class="small muted">팬이 정리한 참고 자료이며 공식 안내와 다를 수 있습니다.</p>':''}</div>${external(source.url,'원문 보기','text-link')}</article>`).join('')}
 </div></section><p class="data-note">확인 날짜가 없거나 오래된 자료는 최신 여부를 단정하지 않습니다. 수정이 필요한 내용은 <a href="#/report?type=correction">정보 정정</a>으로 알려 주세요.</p>
 ${IsegyeOps.panel('status')}`;
}
function publicAlbumFreshness(kind){
 const chart=albumInsights.domesticCharts?.[kind],at=chart?.updatedAt;
 const valid=at&&Number.isFinite(Date.parse(at));
 const delayed=!valid||chart?.state!=='ok'||Date.now()-Date.parse(at)>3*3600000;
 return `<div class="ai-hourly-health" role="status"><p>멜론 차트 기준 ${valid?esc(stamp(at)):'확인된 날짜가 없습니다'}</p>${delayed?'<p class="ai-footnote">최신 순위가 확인되지 않아 마지막 확인 기록을 표시합니다. 현재 순위는 멜론 원문에서 확인해 주세요.</p>':''}</div>`;
}
