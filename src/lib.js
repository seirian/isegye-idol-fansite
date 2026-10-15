/** Pure utilities shared by the application, schema checks, and Node tests. */
export function escapeHtml(value=''){return String(value).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
export function safeUrl(value){try{const url=new URL(value);return url.protocol==='https:'&&!url.username&&!url.password?url.href:null;}catch{return null;}}
export function normalize(value=''){return String(value).normalize('NFKC').toLocaleLowerCase('ko').replace(/\s+/g,' ').trim();}
export function initials(value=''){const first='ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ';return [...value].map(c=>{const n=c.charCodeAt(0)-44032;return n>=0&&n<=11171?first[Math.floor(n/588)]:c;}).join('');}
export function searchRecords(records,query,{kind='all',member='all'}={}){
 const terms=normalize(query).split(' ').filter(Boolean);
 return records.filter(r=>r.visibility==='published'&&(kind==='all'||r.kind===kind)&&(member==='all'||r.members.includes(member))).map(record=>{
  const title=normalize(record.title), text=normalize([record.title,record.subtitle,record.summary,...record.tags].join(' '));
  const matches=terms.every(t=>text.includes(t)||(/^[ㄱ-ㅎ]+$/.test(t)&&initials(text).includes(t)));
  return {record,score:terms.reduce((s,t)=>s+(title===t?30:title.startsWith(t)?15:title.includes(t)?8:1),0),matches};
 }).filter(r=>r.matches).sort((a,b)=>b.score-a.score||a.record.title.localeCompare(b.record.title,'ko')).map(r=>r.record);
}
export function kstDate(now=new Date()){const parts=new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Seoul',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(now);const p=Object.fromEntries(parts.map(x=>[x.type,x.value]));return `${p.year}-${p.month}-${p.day}`;}
export function formatDate(date){if(!date)return '날짜 미등록';return date.replaceAll('-','.');}
export function calendarCells(year,month){const first=new Date(Date.UTC(year,month-1,1)).getUTCDay();const total=new Date(Date.UTC(year,month,0)).getUTCDate();return Array.from({length:42},(_,i)=>{const n=i-first+1;return n<1||n>total?null:`${year}-${String(month).padStart(2,'0')}-${String(n).padStart(2,'0')}`;});}
export function shiftMonth(year,month,offset){const d=new Date(Date.UTC(year,month-1+offset,1));return [d.getUTCFullYear(),d.getUTCMonth()+1];}
export function parseRoute(hash){const text=String(hash||'#/home').replace(/^#\/?/,'');const [path,query='']=text.split('?');return {parts:path.split('/').filter(Boolean),params:new URLSearchParams(query)};}
export function getBookmarks(storage,validIds){try{const data=JSON.parse(storage.getItem('isegye:bookmarks:v1')||'[]');return Array.isArray(data)?[...new Set(data.filter(x=>typeof x==='string'&&validIds.has(x)))]:[];}catch{return [];}}
export function validateContent(records,sources,members){
 const errors=[],ids=new Set(),memberIds=new Set(members.map(m=>m.id));
 for(const r of records){
  if(!/^[a-z0-9-]+$/.test(r.id)||ids.has(r.id))errors.push(`Invalid/duplicate id: ${r.id}`);ids.add(r.id);
  if(!['member','music','video','event','entry','guide'].includes(r.kind))errors.push(`Invalid kind: ${r.id}`);
  if(!r.title||!r.summary||!Array.isArray(r.body)||!r.body.length)errors.push(`Missing text: ${r.id}`);
  if(!['verified','editorial'].includes(r.status))errors.push(`Unreviewed status: ${r.id}`);
  if(r.visibility!=='published')errors.push(`Unpublished content must not enter the public bundle: ${r.id}`);
  if(r.status==='verified'&&!r.sourceIds.length)errors.push(`Missing source: ${r.id}`);
  for(const id of r.sourceIds)if(!sources[id])errors.push(`Unknown source: ${r.id}/${id}`);
  for(const id of r.members)if(!memberIds.has(id))errors.push(`Unknown member: ${r.id}/${id}`);
  if(r.date&&(!/^\d{4}-\d{2}-\d{2}$/.test(r.date)||Number.isNaN(Date.parse(r.date))||new Date(r.date).toISOString().slice(0,10)!==r.date))errors.push(`Invalid date: ${r.id}`);
 }
 for(const r of records)for(const id of r.related||[])if(!ids.has(id))errors.push(`Broken relation: ${r.id}/${id}`);
 for(const [id,s] of Object.entries(sources))if(!safeUrl(s.url)||!s.checkedAt||!s.publisher)errors.push(`Invalid source: ${id}`);
 return errors;
}
