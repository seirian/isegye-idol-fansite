/* Served only after the existing server-side administrator check. No credentials. */
const adminTitle=title=>`<p class="ai-kicker">ADMIN ONLY</p><h2>${title}</h2>`;
function status(){
 return `<section class="section panel">${adminTitle('출처 수집 진단')}<p class="data-note">관리자 전용 · 자료에 기록된 상태이며 현재 배치 실행 성공을 보장하지 않습니다.</p>
 <div class="status-list">${D.sources.map(source=>`<article class="status-item"><div><h3>${esc(sourceNames[source.id]||source.label||source.id)}</h3><p class="small">마지막 원본 확인 ${stamp(source.lastSuccessAt)}<br>마지막 시도 ${stamp(source.lastAttemptAt)}</p><p class="small muted">${esc(source.detail||'')}</p></div><div>${badge(source.state==='ok'?'저장 시점 확인 성공':source.state==='snapshot'?'기존 확인 자료':source.state==='restricted'?'공개 등록 제외':'확인 필요',source.state==='ok'?'good':'warning')}</div></article>`).join('')}</div>
 <h3>운영 연동 시 구분할 항목</h3><div class="scope-table-wrap"><table class="scope-table"><thead><tr><th>확인 항목</th><th>확인 기준</th></tr></thead><tbody>
 <tr><td>서버 게시 결과</td><td>배포 실행 결과와 게시 후 검증 보고서에서 확인합니다. 원본 확인 성공과 구분합니다.</td></tr>
 <tr><td>출처 수집 완료</td><td>출처별 마지막 시도·성공 시각과 누락 여부를 대조합니다.</td></tr>
 <tr><td>영상 수집 범위</td><td>${Number(D.scope.videoCoverageComplete)||0}/${Number(D.scope.videoChannelCount)||0}개 채널의 과거 수집 완료 기록입니다.</td></tr>
 <tr><td>신규·수정·삭제</td><td>확인된 이력만 사용하며 측정하지 않은 건수는 표시하지 않습니다.</td></tr></tbody></table></div>
 <p><a href="/build-info.json" target="_blank" rel="noopener noreferrer">배포 빌드 정보</a></p></section>`;
}
function coverage(){return `<p class="data-note">관리자 · 전체 과거 영상 수집 ${Number(D.scope.videoCoverageComplete)||0}/${Number(D.scope.videoChannelCount)||0}개 채널 완료</p>`;}
function notice(){return `<details class="panel section"><summary>관리자 · 공지 변경 이력 수집</summary><p>공지 수정 전·후 본문 이력은 현재 이 화면에 연결되지 않았습니다. 원문 확인과 변경 이력 수집을 구분합니다.</p></details>`;}
function schedule(){return `<details class="panel section"><summary>관리자 · 일정 수집 상태</summary><p>${esc(FeedValidators.scheduleCollectionMessage({sources:D.sources,collectionHealth:D.scope.collectionHealth})||'현재 자료에 별도 수집 경고가 없습니다. 배포 성공을 뜻하지는 않습니다.')}</p><a href="#/status">출처별 수집 진단</a></details>`;}
function history(){return `<details class="panel section"><summary>관리자 · 활동 기록 갱신</summary><p>기록 데이터 기준 ${esc(stamp(D.scope.historyCheckedAt))}. 월간 수집 결과와 화면에 반영된 날짜를 별도로 확인하세요.</p></details>`;}
function demoLink(demo,kind){return `<a class="text-link small" href="${esc(patch({demo:demo?null:'1',metric:kind}))}" aria-pressed="${demo}">${demo?'실제 데이터로 돌아가기':'그래프 예시 보기'}</a>`;}
// The build adds the already-tested provider and chart-diagnostic renderers below.
