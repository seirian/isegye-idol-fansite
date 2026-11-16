/* Production-only runtime data adapter. Approved album presentation stays unchanged. */
function albumAcceptRuntime(next) {
  if (!albumValidSnapshot(next) || next.feed !== 'daily-albums') return false;
  const at = Date.parse(next.generatedAt), base = Date.parse(albumInsights.generatedAt);
  if (at < base || at > Date.now() + 600000) return false;
  const mappings = {covers: {}, brands: {}, badges: {}};
  for (const [group, target] of Object.entries(mappings)) {
    const rows = next.assets?.[group] || {};
    if (!rows || typeof rows !== 'object' || Array.isArray(rows) || Object.keys(rows).length > 500) return false;
    for (const [key, row] of Object.entries(rows)) {
      const sha = row?.sha256;
      if (!/^[a-f0-9]{64}$/.test(sha || '') || row.path !== `albums/asset-cache/${sha}.webp`) return false;
      if (group !== 'brands' && key !== sha) return false;
      if (group === 'brands' && !['melon','genie','bugs','apple','youtube','youtube_music'].includes(key)) return false;
      target[key] = `/api/albums/assets/${sha}.webp`;
    }
  }
  Object.assign(ALBUMS_ART, mappings.covers);
  Object.assign(ALBUMS_BRANDS, mappings.brands);
  Object.assign(ALBUMS_BADGES, mappings.badges);
  return true;
}

/* Source clock, collection clock and published generation are different facts. */
function albumFreshness(data, kind, at=Date.now()) {
  const offset=9*3600000, local=new Date(at+offset), hour=local.getUTCHours();
  const paused=hour>=1&&hour<7, boundary=Math.floor(at/3600000)*3600000;
  let expected=boundary;
  if(paused)expected-=hour*3600000;
  const chartAt=Date.parse(data?.domesticCharts?.[kind]?.updatedAt);
  const collectedAt=Date.parse(data?.generatedAt), publishedAt=Date.parse(data?.publication?.publishedAt);
  const valid=t=>Number.isFinite(t)&&t<=at+600000;
  const current=valid(chartAt)&&chartAt>=expected&&data?.domesticCharts?.[kind]?.state==='ok';
  const settling=!paused&&at-boundary<10*60000;
  let state=paused?(current?'paused':'paused_stale'):current?'current':settling?'pending':'delayed';
  const gaps=data?.hourlyCoverage?.charts?.[kind]?.missingSlots;
  const missing=Array.isArray(gaps)?gaps.filter(v=>{
    const n=Date.parse(v),h=new Date(n+offset).getUTCHours();
    return valid(n)&&n<expected&&!(h>=1&&h<7);
  }).length:0;
  return {state,paused,chartAt:valid(chartAt)?chartAt:null,collectedAt:valid(collectedAt)?collectedAt:null,
    publishedAt:valid(publishedAt)?publishedAt:null,missing};
}
function albumFlowFreshness(kind) {
  const health=albumFreshness(albumInsights,kind),text={
    current:'현재 시간 차트 반영',pending:'정각 갱신 확인 중',delayed:'시간별 갱신 지연 · 마지막 확인값',
    paused:'새벽 배치 중지 · 07:00 재개',paused_stale:'새벽 배치 중지 · 이전 시간 누락도 있음'};
  const show=n=>n===null?'미기록':esc(stamp(new Date(n).toISOString()));
  return `<div class="ai-hourly-health" role="status" data-album-refresh-state="${health.state}"><p><strong>${text[health.state]}</strong>${health.missing?` · 최근 기록 중 주간 미수집 ${health.missing}시간`:''}</p><p class="ai-footnote">멜론 차트 기준 ${show(health.chartAt)}<br>마지막 수집 ${show(health.collectedAt)} · 게시본 반영 ${show(health.publishedAt)}</p><p class="ai-footnote">${esc(albumApiState)} · 00시 및 07~23시 정각 수집. 01:00~06:59에는 배치를 실행하지 않습니다. 중간 순위는 추정하지 않습니다.</p></div>`;
}
// Keep an open album page current without polling in other menus or hidden tabs.
if(typeof document!=='undefined'&&typeof window!=='undefined') {
  const refresh=()=>{
    if(document.visibilityState==='visible'&&/^#\/(album|song)(?:[/?]|$)|^#\/music(?:\?|$)/.test(location.hash))aiLoadSnapshot();
  };
  window.setInterval(refresh,5*60000);
  document.addEventListener('visibilitychange',refresh);
}
