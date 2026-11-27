/* A source outage changes playback availability, never the song's history. */
function sourceAvailabilityBlocked(row){
 const state=row?.videoSource?.availability;
 return !!state&&state!=='available';
}
function sourceAvailabilityNotice(row){
 if(!sourceAvailabilityBlocked(row))return '';
 const checked=row.videoSource?.availabilityCheckedAt;
 return `<div class="notice-box music-source-unavailable" data-video-availability="unavailable"><strong>영상 확인 불가</strong><p>현재 연결된 영상을 확인할 수 없어 재생 링크를 제공하지 않습니다. 곡과 발매 기록은 그대로 보존합니다.</p>${checked?`<p class="small muted">마지막 확인 ${esc(stamp(checked))}</p>`:''}</div>`;
}
function sourceAvailabilityAction(row,label){
 if(sourceAvailabilityBlocked(row))return '<button class="button primary" disabled aria-disabled="true">영상 확인 불가</button>';
 return external(row.url||(row.videoId?'https://www.youtube.com/watch?v='+row.videoId:''),label,'button primary');
}
