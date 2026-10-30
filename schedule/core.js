/* Pure calendar helpers. Dates are KST calendar dates, never post dates. */
export function scheduleValidDate(value) {
 if(!/^\d{4}-\d{2}-\d{2}$/.test(value||''))return false;
 const d=new Date(value+'T00:00:00Z');return Number.isFinite(+d)&&d.toISOString().slice(0,10)===value;
}
export function scheduleSafeUrl(value) {
 try{const u=new URL(value);return u.protocol==='https:'&&!u.username&&!u.password&&!u.port&&(
  u.hostname==='parable-asia.com'||(u.hostname==='cafe.naver.com'&&/^\/steamindiegame\/\d+$/.test(u.pathname))
 )?u.href:null;}catch{return null;}
}
export function scheduleValidate(data) {
 const known=['ine','jingburger','lilpa','jururu','gosegu','viichan'];
 if(data?.schemaVersion!==1||data.timezone!=='Asia/Seoul'||!Number.isFinite(Date.parse(data.generatedAt)))throw new Error('invalid feed');
 const sourceIds=['cafe-members','cafe-agency','fan-roundup','parable-web','naver-search'];
 if(!Array.isArray(data.sources)||data.sources.length!==5||new Set(data.sources.map(x=>x.id)).size!==5||data.sources.some(x=>!sourceIds.includes(x.id)))throw new Error('invalid sources');
 for(const key of ['events','news','forecasts']){
  if(!Array.isArray(data[key])||data[key].length>700)throw new Error('invalid rows');
  const ids=new Set();for(const r of data[key]){
   if(typeof r.id!=='string'||ids.has(r.id)||typeof r.title!=='string'||r.title.length>240||!scheduleSafeUrl(r.sourceUrl)||!Array.isArray(r.members)||r.members.some(x=>!known.includes(x)))throw new Error('invalid item');
   if(!sourceIds.includes(r.sourceId)||!Number.isFinite(Date.parse(r.checkedAt)))throw new Error('invalid source');
   if(key!=='news'&&(!['confirmed','tentative','unknown'].includes(r.certainty)||(r.time&&!/^(?:[01]\d|2[0-3]):[0-5]\d$/.test(r.time))))throw new Error('invalid event');
   ids.add(r.id);if(key!=='news'&&!scheduleValidDate(r.date))throw new Error('invalid date');
   if(['fan-roundup','naver-search'].includes(r.sourceId)&&r.certainty==='confirmed')throw new Error('unverified item');
  }
 }
 return data;
}
export function scheduleStale(item,now=Date.now()) {return !Number.isFinite(Date.parse(item.checkedAt))||now-Date.parse(item.checkedAt)>2*60*60*1000;}
export function scheduleFiltered(rows,{member='all',source='all',kind='all'}={}) {
 return rows.filter(r=>(member==='all'||r.members.includes(member))&&(source==='all'||(source==='official'?!['fan-roundup','naver-search'].includes(r.sourceId):r.sourceId==='fan-roundup'))&&(kind==='all'||r.type===kind));
}
export function scheduleMergeEvents(staticRows,dynamicRows) {
 const out=new Map();for(const r of [...staticRows,...dynamicRows]){
  const key=r.sourceUrl+'|'+r.date+'|'+r.type+'|'+r.members.join(',');out.set(key,r);
 }
 return [...out.values()].sort((a,b)=>a.date.localeCompare(b.date)||(a.time||'99:99').localeCompare(b.time||'99:99')||a.title.localeCompare(b.title));
}
export function scheduleCurrentForecasts(rows,date) {return rows.filter(x=>x.date===date);}
