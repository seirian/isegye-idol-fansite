/* Explicit source-labelled related videos. No network or implicit channel discovery. */
function externalPerformanceLinks(songId, excludeId='') {
  const rows=D.videos.filter(v=>v.category==='external'&&v.relatedSong===songId&&v.id!==excludeId)
    .sort((a,b)=>(a.type==='external_performance'?-1:1)-(b.type==='external_performance'?-1:1)||b.publishedAt.localeCompare(a.publishedAt));
  if(!rows.length)return '';
  const channelNames=[...new Set(rows.map(v=>v.channelName))].join(' · ');
  return `<section class="ai-panel section" aria-label="관련 퍼포먼스 영상"><div class="ai-panel-head"><div><p class="ai-kicker">PERFORMANCE / EXTERNAL CHANNEL</p><h2>관련 퍼포먼스 영상</h2><p class="ai-muted">${esc(channelNames)} · 기존 공식 MV와 별도의 영상입니다.</p></div></div><div class="list">${rows.map(rowCard).join('')}</div><p class="ai-footnote">음악방송 무대·퍼포먼스 본편·티저를 구분합니다. 공개일은 영상 기준이며, 조회수나 재생시간을 음원·공식 MV 통계에 합산하지 않습니다.</p></section>`;
}
