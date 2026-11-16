/** Pure, bounded helpers. No operating storage, network calls or account access. */
export const STORAGE_KEY = 'isegye:fanmade:review:v1';
export const KINDS = {art:'팬아트',video:'팬영상',craft:'만들기'};
export const MEMBERS = {group:'단체',ine:'아이네',jingburger:'징버거',lilpa:'릴파',jururu:'주르르',gosegu:'고세구',viichan:'비챤'};
export function escapeHtml(value='') { return String(value).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
export function normalize(value='') { return String(value).normalize('NFKC').toLocaleLowerCase('ko').replace(/\s+/g,' ').trim(); }
export function safeUrl(value) { try {const u=new URL(value);return u.protocol==='https:'&&!u.username&&!u.password?u.href:null;} catch {return null;} }
export function canPublish(w) { return w?.sample===false && w?.permission?.status==='granted' && w?.permission?.allowPreview===true && !!safeUrl(w.originalUrl); }
export function filters(params) {return {kind:Object.hasOwn(KINDS,params.get('kind'))?params.get('kind'):'all',member:Object.hasOwn(MEMBERS,params.get('member'))?params.get('member'):'all',q:(params.get('q')||'').slice(0,80),sort:params.get('sort')==='title'?'title':'curated'};}
export function searchWorks(works,creators,f) {
 const terms=normalize(f.q).split(' ').filter(Boolean),names=new Map(creators.map(c=>[c.id,c.name]));
 const selected=works.filter(w=>(f.kind==='all'||w.kind===f.kind)&&(f.member==='all'||w.members.includes(f.member))&&terms.every(t=>normalize([w.title,names.get(w.creatorId),w.medium,...w.tags,...w.members.map(m=>MEMBERS[m])].join(' ')).includes(t)));
 return f.sort==='title'?[...selected].sort((a,b)=>a.title.localeCompare(b.title,'ko')):selected;
}
export function sanitizeSaved(value,valid) {return Array.isArray(value)?[...new Set(value.filter(id=>typeof id==='string'&&valid.has(id)))].slice(0,200):[];}
export function loadSaved(storage,valid) {try {const raw=storage.getItem(STORAGE_KEY);if(raw&&raw.length>20000)throw Error('oversized');return {ids:sanitizeSaved(JSON.parse(raw||'[]'),valid),available:true};}catch{return {ids:[],available:false};}}
export function saveSaved(storage,ids) {try {storage.setItem(STORAGE_KEY,JSON.stringify(ids));return true;}catch{return false;}}
export function relatedWorks(works,current,by='theme') {return works.filter(w=>w.id!==current.id&&(by==='creator'?w.creatorId===current.creatorId:current.exhibitions.some(id=>w.exhibitions.includes(id)))).slice(0,4);}
export function route(hash) {const text=String(hash||'#/fanmade').replace(/^#\/?/,'');const i=text.indexOf('?');const path=i<0?text:text.slice(0,i),query=i<0?'':text.slice(i+1);return {parts:path.split('/').filter(Boolean),params:new URLSearchParams(query)};}
