/** Pure catalog rules. No network, DOM, or implicit classification by title. */
export const CATALOG_TYPES = Object.freeze({all:'전체',original:'오리지널',cover:'커버',remake:'리메이크',official_track:'공식 음원·MV',album_medley:'앨범 메들리',music_clip:'음악 스페셜클립',performance:'공연·편곡'});
export const CATALOG_SCOPES = Object.freeze({all:'모든 구성',solo:'개인',unit:'유닛',group:'단체'});
export const CATALOG_CONTEXTS = Object.freeze({all:'모든 활동',standard:'일반',ost:'OST·테마송',festival:'페스티벌',collab:'외부 협업',audition:'오디션'});
export const catalogIsOfficialTrack=s=>s.type==='official_track'||['official_mv','official_audio'].includes(s.videoSource?.kind);
export function catalogQuery(params) {
  const take=(key,allow,fallback)=>allow.includes(params.get(key))?params.get(key):fallback;
  return {type:take('type',Object.keys(CATALOG_TYPES),'all'),scope:take('scope',Object.keys(CATALOG_SCOPES),'all'),
    context:take('context',Object.keys(CATALOG_CONTEXTS),'all'),member:take('member',['all','ine','jingburger','lilpa','jururu','gosegu','viichan'],'all'),
    year:/^20\d{2}$/.test(params.get('year')||'')?params.get('year'):'all',q:(params.get('q')||'').trim().slice(0,120),
    sort:take('sort',['new','old','title'],'new'),page:Math.min(1000,Math.max(1,parseInt(params.get('page'),10)||1))};
}
export function catalogFilter(items,query,members=[]) {
  const q=catalogQuery(query instanceof URLSearchParams?query:new URLSearchParams(query));
  const words=q.q.normalize('NFKC').toLocaleLowerCase('ko').split(/\s+/).filter(Boolean);
  const names=Object.fromEntries(members.map(m=>[m.id,m.name+' '+m.en]));
  const compact=s=>s.normalize('NFKC').toLocaleLowerCase('ko').replace(/[^\p{L}\p{N}]/gu,'');
  const found=items.filter(s=>(q.type==='all'||s.type===q.type||(q.type==='official_track'&&catalogIsOfficialTrack(s)))&&(q.scope==='all'||s.scope===q.scope)&&
    (q.context==='all'||s.context===q.context)&&(q.member==='all'||s.members.includes(q.member))&&
    (q.year==='all'||s.date.startsWith(q.year))&&words.every(w=>
      (()=>{const hay=[s.title,...(s.aliases||[]),s.title.includes('RE:WIND')||s.title.includes('RE : WIND')?'리와인드':'',s.album||'',s.format,s.scope==='group'?'이세계아이돌 이세돌 ISEGYE IDOL':'',s.videoSource?.channel||'',s.videoSource?.kind==='official_mv'?'공식 MV 뮤직비디오':'',s.members.map(id=>names[id]||id).join(' ')].join(' ').normalize('NFKC').toLocaleLowerCase('ko');return hay.includes(w)||(compact(w)&&compact(hay).includes(compact(w)));})()));
  return found.sort((a,b)=>q.sort==='title'?a.title.localeCompare(b.title,'ko')||a.id.localeCompare(b.id):
    (q.sort==='old'?a.date.localeCompare(b.date):b.date.localeCompare(a.date))||a.title.localeCompare(b.title,'ko'));
}
export function catalogPage(items,requested,size=24) {
  const pages=Math.max(1,Math.ceil(items.length/size));const page=Math.min(pages,Math.max(1,Number(requested)||1));
  return {items:items.slice((page-1)*size,page*size),page,pages,total:items.length};
}
export function catalogNewestVideos(videos,now=Date.now()) {
  const seen=new Set();return [...videos].filter(v=>{
    const valid=/^[A-Za-z0-9_-]{11}$/.test(v.id||'')&&typeof v.title==='string'&&v.title.trim()&&
      Number.isFinite(Date.parse(v.publishedAt))&&Date.parse(v.publishedAt)<=now&&!seen.has(v.id);
    if(valid)seen.add(v.id);return valid;
  }).sort((a,b)=>Date.parse(b.publishedAt)-Date.parse(a.publishedAt)||a.id.localeCompare(b.id)).slice(0,3);
}
export const catalogVideoUrl=id=>/^[A-Za-z0-9_-]{11}$/.test(id||'')?'https://www.youtube.com/watch?v='+id:null;

export function catalogCoverRows(tsv) {
 return tsv.trimEnd().split('\n').filter(s=>s&&!s.startsWith('#')).map(line=>{
  const [videoId,title,members,scope,date,original,context]=line.split('\t');
  if(!catalogVideoUrl(videoId)||!title||!members||!/^20\d{2}-\d{2}-\d{2}$/.test(date))throw new Error('Invalid cover row');
  return {id:'cover-'+videoId,title,type:'cover',scope,members:members.split(','),date,dateKind:'영상 공개일',format:'커버 영상',videoId,url:catalogVideoUrl(videoId),context,sources:['covers'],...(original?{originalReference:'https://namu.wiki/w/'+encodeURI(original)}:{})};
 });
}
