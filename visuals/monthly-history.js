/* Monthly data augments the curated timeline; malformed responses cannot mutate it. */
const monthlyHistoryBase={events:HISTORY.events.slice(),sources:{...HISTORY.sources},checkedAt:HISTORY.checkedAt};
let monthlyHistoryVersion='',monthlyHistoryPending=false,monthlyHistoryNext=0;
function historyMonthEnd(value){
 const t=Date.parse(value);if(!Number.isFinite(t)||!/(?:Z|[+-]\d{2}:\d{2})$/.test(value))throw Error('Invalid history timestamp');
 const kst=new Date(t+9*3600000);return new Date(Date.UTC(kst.getUTCFullYear(),kst.getUTCMonth(),0)).toISOString().slice(0,10);
}
function validHistoryDay(value){return /^20\d{2}-\d{2}-\d{2}$/.test(value||'')&&Number.isFinite(Date.parse(value))&&new Date(value).toISOString().slice(0,10)===value;}
function historySafeSource(value){
 try{const u=new URL(value);if(u.protocol!=='https:'||u.username||u.password||u.port||u.hash)return false;
  if(u.hostname==='www.youtube.com')return u.pathname==='/watch'&&/^[\w-]{11}$/.test(u.searchParams.get('v')||'')&&[...u.searchParams.keys()].length===1;
  if(u.search)return false;
  if(u.hostname==='parable-asia.com')return true;
  if(u.hostname==='berriz.in')return /^\/ko\/isegyeidol\/notice\/[1-9]\d*\/$/.test(u.pathname);
  return u.hostname==='cafe.naver.com'&&/^\/steamindiegame\/[1-9]\d*$/.test(u.pathname);
 }catch{return false;}
}
function applyMonthlyHistory(feed){
 const start='2026-10-01'; // Stable initial coverage month; curated updates do not invalidate saved history.
 if(!feed||feed.feed!=='monthly-history'||feed.schemaVersion!==1||feed.through!==historyMonthEnd(feed.generatedAt)||feed.windowStart!==start||!Array.isArray(feed.events)||feed.events.length>3000||!feed.sources||Array.isArray(feed.sources)||Object.keys(feed.sources).length>3000)throw Error('Invalid monthly history feed');
 const generated=Date.parse(feed.generatedAt);if(generated>Date.now()+300000)throw Error('Future history generation');
 if(monthlyHistoryVersion&&generated<Date.parse(monthlyHistoryVersion))throw Error('Stale history response');
 const safe=(s,n)=>typeof s==='string'&&s.length>0&&s.length<=n&&!/[<>\x00-\x1f]/.test(s);
 const sources={...monthlyHistoryBase.sources},rows=[],ids=new Set(),sig=r=>r.date+'|'+r.title.normalize('NFKC').toLowerCase().replace(/[^\p{L}\p{N}]/gu,'')+'|'+[...r.members].sort().join(','),names=new Set(monthlyHistoryBase.events.map(sig));
 for(const [key,s] of Object.entries(feed.sources)){
  if(!/^mh-[a-f0-9]{24}$/.test(key)||!s||Object.keys(s).sort().join(',')!=='basis,checkedAt,title,url'||s.basis!=='official'||!safe(s.title,240)||!historySafeSource(s.url)||!Number.isFinite(Date.parse(s.checkedAt))||!/(?:Z|[+-]\d{2}:\d{2})$/.test(s.checkedAt)||Date.parse(s.checkedAt)>generated)throw Error('Invalid history source');
  sources[key]={...s};
 }
 for(const r of feed.events){
  if(!r||!/^monthly-[a-f0-9]{24}$/.test(r.id)||ids.has(r.id)||!Object.hasOwn(HISTORY_TYPES,r.type)||r.type==='all'||!validHistoryDay(r.date)||r.date<start||r.date>feed.through||!safe(r.title,240)||!safe(r.summary,400)||!safe(r.note,400)||!Array.isArray(r.members)||!r.members.length||!r.members.every(id=>LIVE_CHANNELS.some(m=>m.id===id))||new Set(r.members).size!==r.members.length||!Array.isArray(r.sources)||r.sources.length!==1||!Object.hasOwn(feed.sources,r.sources[0])||!['video_published','notice_published'].includes(r.dateBasis))throw Error('Invalid history record');
  const source=feed.sources[r.sources[0]];
  if((r.dateBasis==='video_published')!==(new URL(source.url).hostname==='www.youtube.com')||r.date>new Date(Date.parse(source.checkedAt)+9*3600000).toISOString().slice(0,10)||('announced'in r&&r.announced!==true)||('relatedSong'in r&&!/^daily-[\w-]{11}$/.test(r.relatedSong)))throw Error('Invalid history evidence');
  ids.add(r.id);const key=sig(r);if(names.has(key))continue;names.add(key);
  rows.push({id:r.id,date:r.date,title:r.title,type:r.type,members:[...r.members],sources:[...r.sources],summary:r.summary,note:r.note,dateBasis:r.dateBasis,...(r.announced?{announced:true}:{}),...(r.relatedSong?{relatedSong:r.relatedSong}:{})});
 }
 HISTORY.sources=sources;HISTORY.events=[...monthlyHistoryBase.events,...rows];
 HISTORY.monthly={generatedAt:feed.generatedAt,through:feed.through,partial:feed.coverage?.partial===true};
 monthlyHistoryVersion=feed.generatedAt;return rows.length;
}
function monthlyHistoryRoute(){return /^#\/history(?:\?|$)/.test(location.hash);}
async function refreshMonthlyHistory(){
 if(!monthlyHistoryRoute()||!/^https?:$/.test(location.protocol)||monthlyHistoryPending||Date.now()<monthlyHistoryNext)return;
 monthlyHistoryPending=true;monthlyHistoryNext=Date.now()+60000;
 const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),8000);
 try{
  const response=await fetch('/api/history',{credentials:'same-origin',cache:'no-store',redirect:'error',signal:controller.signal});
  if(!response.ok||!response.headers.get('content-type')?.includes('application/json'))return;
  const raw=await response.text();if(new TextEncoder().encode(raw).length>1500000)throw Error('History feed too large');
  const feed=JSON.parse(raw);if(feed.generatedAt!==monthlyHistoryVersion){applyMonthlyHistory(feed);if(monthlyHistoryRoute())render({focus:false,scroll:false});}
  monthlyHistoryNext=Date.now()+300000;
 }catch{/* Keep the last verified timeline and original source observation dates. */}
 finally{monthlyHistoryPending=false;clearTimeout(timer);}
}
window.addEventListener('hashchange',refreshMonthlyHistory);window.addEventListener('focus',refreshMonthlyHistory);queueMicrotask(refreshMonthlyHistory);
