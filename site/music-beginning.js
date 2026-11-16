/* Only the introductory series uses direct official YouTube links. */
function musicBeginningView(){
 const series=D.series.find(s=>s.id==='music-beginning');
 if(!series||series.entryMode!=='youtube_original')return notFound();
 const cards=series.officialVideos.map((entry,index)=>{
  const v=videos.get(entry.videoId),original=safeExternal(entry.url);
  if(!v||original!=='https://www.youtube.com/watch?v='+entry.videoId)return '';
  const label=entry.kind==='official_special_clip'?'Official Special Clip':'Official MV';
  const duration=Math.floor(entry.durationSeconds/60)+':'+String(entry.durationSeconds%60).padStart(2,'0');
  const direct='href="'+esc(original)+'" target="_blank" rel="noopener noreferrer"';
  return `<article class="content-card" data-item-key="${esc(v.key)}" data-music-beginning-video="${esc(entry.videoId)}">
   <a ${direct} aria-label="${esc(entry.title+' · '+label+' · YouTube 새 탭에서 보기')}">${thumb(v)}</a>
   <div class="card-body"><div class="badges">${badge(String(index+1).padStart(2,'0'),'neutral')}${badge(label)}</div>
   <a ${direct}><h3>${esc(entry.title)}</h3></a><p>${esc(entry.channelName)}</p>
   <p class="small muted">${dateText(kstDay(entry.publishedAt))} · 영상 공개 · ${duration}</p>
   <div class="card-bottom">${external(original,'YouTube에서 보기')}<span class="content-card-actions">${saveButton(v)}</span></div>
   <a class="text-link" href="#/video/${esc(entry.videoId)}" aria-label="${esc(entry.title+' 영상 상세')}">영상 상세 ${icon('arrow')}</a></div></article>`;
 }).join('');
 return `<a class="text-link" href="#/content?tab=series">${icon('back')}시리즈·합방</a>
  ${heading(series.title,series.description,series.subtitle)}
  <div class="notice-box">${badge('공식 원본 연결')} 카드를 누르면 YouTube 원본 영상이 새 탭에서 열립니다. 운영자가 선정한 감상 순서이며 공식 추천·인기순·전체 발매 목록은 아닙니다.</div>
  <section aria-label="처음부터 만나는 공식 음악 영상"><div class="grid music-beginning-grid">${cards}</div></section>
  <p class="data-note">Smile For You는 공식 채널의 원본 명칭인 Special Clip으로 표시합니다. 날짜는 영상 공개일이며 앨범 발매일과 다를 수 있습니다.</p>`;
}
