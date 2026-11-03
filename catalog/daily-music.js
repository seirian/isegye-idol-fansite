/* The reviewed catalog is immutable. URLs are derived from pinned uploader/video IDs, not feed HTML. */
const dailyMusicBase = CATALOG.music.songs.slice(), dailyMusicAdded = new Set();
function applyDailyMusic(payload) {
  if (!payload || payload.feed !== 'daily-music' || payload.schemaVersion !== 1 || !Array.isArray(payload.rows) || payload.rows.length > 2000) throw Error('Invalid music feed');
  const ids=new Set(dailyMusicBase.flatMap(s=>[s.originalVideoId,s.videoId]).filter(Boolean));
  const extras={album_medley:'앨범 하이라이트 메들리',music_clip:'음악 스페셜클립',performance:'공식 공연·편곡 영상'};
  const signature=(s)=>(Object.hasOwn(extras,s.type)?s.type+':':'')+s.title.normalize('NFKC').toLowerCase().replace(/[^\p{L}\p{N}]/gu,'')+'|'+[...s.members].sort().join(',');
  const names=new Set(dailyMusicBase.map(signature)); const added=[],sources={};
  for (const r of payload.rows) {
    const c=Object.hasOwn(DAILY_MUSIC_CHANNELS,r.channelKey)?DAILY_MUSIC_CHANNELS[r.channelKey]:null;
    if(!c || !/^[\w-]{11}$/.test(r.videoId) || !['cover','remake','original','official_track','album_medley','music_clip','performance'].includes(r.type) || !['official_mv','official_audio','official_video'].includes(r.kind) || typeof r.title!=='string' || !r.title.trim() || r.title.length>140 || /[<>\x00-\x1f]/.test(r.title) || !Array.isArray(r.members) || !r.members.length || !r.members.every(id=>catalogProfiles.has(id)) || new Set(r.members).size!==r.members.length) throw Error('Invalid music record');
    if(Object.hasOwn(extras,r.type) && (!['c1','c2'].includes(r.channelKey)||r.kind!=='official_video'||(r.type==='performance'&&r.channelKey!=='c1')))throw Error('Invalid official channel format');
    if(r.context!==undefined&&(!['collab','festival'].includes(r.context)||r.channelKey!=='c1'))throw Error('Invalid context');
    if(r.credits!==undefined&&(typeof r.credits!=='string'||!r.credits||r.credits.length>200||/[<>\x00-\x1f]/.test(r.credits)||r.channelKey!=='c1'))throw Error('Invalid credits');
    const day=/^20\d{2}-\d{2}-\d{2}$/.test(r.publishedAt);if(day!==(r.datePrecision==='day')||(r.datePrecision!==undefined&&r.datePrecision!=='day'))throw Error('Invalid date precision');
    const p=Date.parse(r.publishedAt),t=Date.parse(r.checkedAt);if(!Number.isFinite(p)||!Number.isFinite(t)||p>t) throw Error('Invalid music timestamp');if(day&&new Date(p).toISOString().slice(0,10)!==r.publishedAt)throw Error('Invalid publication date');
    const id='daily-'+r.videoId,src='daily-yt-'+r.videoId, sig=signature(r);if(ids.has(r.videoId)||names.has(sig))continue;
    ids.add(r.videoId);names.add(sig);const url=catalogVideoUrl(r.videoId);sources[src]={id:src,title:'YouTube · '+c.name,url,checkedAt:r.checkedAt};
    added.push({id,title:r.title,members:[...r.members],type:r.type,scope:r.members.length===1?'solo':r.members.length===6?'group':'unit',context:r.context||'standard',date:day?r.publishedAt:new Date(p+9*3600000).toISOString().slice(0,10),dateKind:'영상 공개일',format:extras[r.type]||(r.kind==='official_audio'?'공식 오디오':r.kind==='official_mv'?'공식 MV':'공식 음악 영상'),sources:[src],videoId:r.videoId,url,videoSource:{kind:r.kind,channel:c.name,channelUrl:c.url,checkedAt:r.checkedAt,note:(r.credits?'공동 참여·피처링: '+r.credits+'. ':'')+(day?'YouTube 원문에 표시된 공개 날짜 기준이며 시각·시간대는 추정하지 않습니다. ':'')+'공식 채널의 공개 영상 기준으로 일배치에서 등록했습니다. 영상 공개일과 음반 발매일은 다를 수 있습니다.'}});
  }
  for(const id of dailyMusicAdded){catalogSongs.delete(id);delete CATALOG.music.sources['daily-yt-'+id.slice(6)];}
  dailyMusicAdded.clear();Object.assign(CATALOG.music.sources,sources);CATALOG.music.songs=[...dailyMusicBase,...added];
  for(const s of added){catalogSongs.set(s.id,s);dailyMusicAdded.add(s.id);}return added.length;
}
let dailyMusicPending=false,dailyMusicNext=0,dailyMusicVersion='';
function dailyMusicRoute(){return /^#\/(music(?:\?|$)|song\/)/.test(location.hash);}
async function refreshDailyMusic(){
  if(!dailyMusicRoute() || !/^https?:$/.test(location.protocol) || dailyMusicPending || Date.now()<dailyMusicNext)return;
  dailyMusicPending=true;dailyMusicNext=Date.now()+60000;
  const controller=new AbortController(), timer=setTimeout(()=>controller.abort(),8000);
  try{const response=await fetch('/api/music',{credentials:'same-origin',cache:'no-store',redirect:'error',signal:controller.signal});
    if(!response.ok || !response.headers.get('content-type')?.includes('application/json'))return;
    const feed=await response.json();if(feed.generatedAt!==dailyMusicVersion){const before=dailyMusicAdded.size;const n=applyDailyMusic(feed);dailyMusicVersion=feed.generatedAt;if((n||before)&&dailyMusicRoute())render({focus:false,scroll:false});}
    dailyMusicNext=Date.now()+300000;
  }catch{/* Unavailable feed: keep last good display, never replace the reviewed catalog. */}finally{dailyMusicPending=false;clearTimeout(timer);}
}
window.addEventListener('hashchange',refreshDailyMusic);window.addEventListener('focus',refreshDailyMusic);queueMicrotask(refreshDailyMusic);
