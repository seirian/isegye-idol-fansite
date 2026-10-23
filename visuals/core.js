/** Public image URLs only; never trust a remote title or arbitrary thumbnail URL. */
export function visualLiveThumbnail(record, now=Date.now()) {
 const r=liveEffective(record,now);
 if(!r||r.state!=='live'||r.mediaRestricted||!/^\d{1,12}$/.test(String(r.broadcastId||''))||Number(r.broadcastId)<=0)return '';
 return `https://liveimg.sooplive.com/m/${r.broadcastId}?v=${Math.floor(r.checkedAt/30000)}`;
}
export function visualMusicThumbnail(song) {
 return song&&/^[A-Za-z0-9_-]{11}$/.test(song.videoId||'')?`https://i.ytimg.com/vi/${song.videoId}/hqdefault.jpg`:'';
}
export const HISTORY_TYPES=Object.freeze({all:'전체 기록',audition:'오디션·결성',release:'음악 발매',performance:'공연·행사',content:'콘텐츠·방송',collaboration:'협업·전시',award:'수상'});
export function historyQuery(params) {
 return {year:/^202[1-6]$/.test(params.get('year')||'')?params.get('year'):'all',type:Object.hasOwn(HISTORY_TYPES,params.get('type'))?params.get('type'):'all',member:LIVE_CHANNELS.some(m=>m.id===params.get('member'))?params.get('member'):'all',order:params.get('order')==='new'?'new':'old',q:(params.get('q')||'').trim().slice(0,120)};
}
export function historyFiltered(events,query) {
 const q=query.q.toLocaleLowerCase('ko-KR');
 return events.filter(x=>(query.year==='all'||x.date.startsWith(query.year))&&(query.type==='all'||x.type===query.type)&&(query.member==='all'||x.members.includes(query.member))&&(!q||`${x.title} ${x.summary||''} ${x.venue||''} ${x.members.map(id=>LIVE_CHANNELS.find(m=>m.id===id)?.name||'').join(' ')}`.toLocaleLowerCase('ko-KR').includes(q))).slice().sort((a,b)=>(query.order==='new'?-1:1)*(a.date.localeCompare(b.date)||a.id.localeCompare(b.id)));
}
