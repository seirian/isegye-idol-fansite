/* Pure calendar helpers. Dates are KST calendar dates, never post dates. */
export function scheduleValidDate(value) {
 if(!/^\d{4}-\d{2}-\d{2}$/.test(value||''))return false;
 const d=new Date(value+'T00:00:00Z');return Number.isFinite(+d)&&d.toISOString().slice(0,10)===value;
}
export function scheduleSafeUrl(value) {
 try{const u=new URL(value);return u.protocol==='https:'&&!u.username&&!u.password&&!u.port&&(
  u.hostname==='parable-asia.com'||(u.hostname==='berriz.in'&&!u.search&&!u.hash&&/^\/ko\/isegyeidol\/(?:notice\/[1-9]\d*|calendar)\/?$/.test(u.pathname))||(u.hostname==='cafe.naver.com'&&/^\/steamindiegame\/\d+$/.test(u.pathname))
 )?u.href:null;}catch{return null;}
}
export function scheduleValidate(data) {
 const known=['ine','jingburger','lilpa','jururu','gosegu','viichan'];
 if(data?.schemaVersion!==1||data.timezone!=='Asia/Seoul'||!Number.isFinite(Date.parse(data.generatedAt)))throw new Error('invalid feed');
 const sourceIds=['cafe-members','cafe-agency','fan-roundup','parable-web','naver-search','berriz-notice','berriz-calendar'];
 if(!Array.isArray(data.sources)||data.sources.length<5||data.sources.length>7||new Set(data.sources.map(x=>x.id)).size!==data.sources.length||sourceIds.slice(0,5).some(id=>!data.sources.some(x=>x.id===id))||data.sources.some(x=>!sourceIds.includes(x.id)))throw new Error('invalid sources');
 for(const key of ['events','news','forecasts']){
  if(!Array.isArray(data[key])||data[key].length>700)throw new Error('invalid rows');
  const ids=new Set();for(const r of data[key]){
   if(typeof r.id!=='string'||ids.has(r.id)||typeof r.title!=='string'||r.title.length>240||!scheduleSafeUrl(r.sourceUrl)||!Array.isArray(r.members)||r.members.some(x=>!known.includes(x)))throw new Error('invalid item');
   if(!sourceIds.includes(r.sourceId)||!Number.isFinite(Date.parse(r.checkedAt)))throw new Error('invalid source');
   if(key!=='news'&&(!['confirmed','tentative','unknown'].includes(r.certainty)||(r.time&&!/^(?:[01]\d|2[0-3]):[0-5]\d$/.test(r.time))))throw new Error('invalid event');
   if(r.sourceId.startsWith('berriz-')&&!scheduleBerrizApproved(r))throw new Error('invalid official Berriz item');
   ids.add(r.id);if(key!=='news'&&!scheduleValidDate(r.date))throw new Error('invalid date');
   if(['fan-roundup','naver-search'].includes(r.sourceId)&&r.certainty==='confirmed')throw new Error('unverified item');
  }
 }
 return data;
}
export function scheduleStale(item,now=Date.now()) {return !Number.isFinite(Date.parse(item.checkedAt))||now-Date.parse(item.checkedAt)>2*60*60*1000;}
export function scheduleFiltered(rows,{member='all',source='all',kind='all'}={}) {
 return rows.filter(r=>(member==='all'||r.members.includes(member))&&(source==='all'||(source==='berriz'?['berriz-notice','berriz-calendar'].includes(r.sourceId):source==='official'?!['fan-roundup','naver-search'].includes(r.sourceId):r.sourceId==='fan-roundup'))&&(kind==='all'||r.type===kind));
}
export function scheduleMergeEvents(staticRows,dynamicRows) {
 const out=new Map();for(const r of [...staticRows,...dynamicRows]){
  const key=(r.calendarId||r.sourceUrl)+'|'+r.date+'|'+r.type+'|'+r.members.join(',');out.set(key,r);
 }
 return [...out.values()].sort((a,b)=>a.date.localeCompare(b.date)||schedulePriority(a)-schedulePriority(b)||(a.time||'99:99').localeCompare(b.time||'99:99')||a.title.localeCompare(b.title));
}
export function scheduleCurrentForecasts(rows,date) {return rows.filter(x=>x.date===date);}

// Search matches cannot prove the writer. Deny them even in a stale server snapshot.
export function scheduleApprovedRows(rows, approvedSources) {
 return rows.filter(r=>scheduleBerrizApproved(r)||r.sourceId==='parable-web'&&scheduleSafeUrl(r.sourceUrl)?.startsWith('https://parable-asia.com/')||
  r.sourceId==='fan-roundup'&&r.sourceUrl==='https://cafe.naver.com/steamindiegame/22137397'||
  ['cafe-members','cafe-agency'].includes(r.sourceId)&&approvedSources.get(r.sourceUrl)===r.sourceId);
}
export function schedulePostedDate(publishedAt) {
 const date=new Date(publishedAt);return Number.isFinite(+date)?date.toLocaleDateString('sv-SE',{timeZone:'Asia/Seoul'}):null;
}
export function scheduleNoticeEvent(row) {
 return {...row,id:'notice-'+row.id,date:schedulePostedDate(row.publishedAt),time:null,type:'notice',certainty:'confirmed',status:'published',dateBasis:'publication',detail:'공지 게시일 기준 기록 · 실제 방송·행사일과 다를 수 있습니다.'};
}

// View-only consolidation. The original notice archive and feed stay unchanged.
export function scheduleCalendarItems(rows) {
 const notices=new Map(rows.filter(r=>r.type==='notice').map(r=>[r.sourceUrl,r]));
 const related=new Map();
 for(const r of rows){
  if(r.type==='notice'||r.internal||!notices.has(r.sourceUrl))continue;
  const n=notices.get(r.sourceUrl);
  // A future broadcast/event keeps its own date. Breaks are notice content only.
  if(r.type==='break'||r.date===n.date){
   const list=related.get(r.sourceUrl)||[];
   if(!list.some(x=>x.type===r.type&&x.date===r.date&&x.time===r.time))list.push(r);
   related.set(r.sourceUrl,list);
  }
 }
 const byDay=new Map();
 for(const r of rows){
  if(r.type==='break')continue;
  // Registered records can share a generic source URL; do not collapse them.
  const identity=r.internal||r.calendarId||r.sourceUrl||r.id;
  const key=identity+'|'+r.date;
  const old=byDay.get(key);
  if(!old||r.type==='notice'||old.type!=='notice')byDay.set(key,r);
 }
 return [...byDay.values()].map(r=>r.type==='notice'?{...r,relatedSchedule:related.get(r.sourceUrl)||[]}:r)
  .sort((a,b)=>a.date.localeCompare(b.date)||schedulePriority(a)-schedulePriority(b)||(a.time||'99:99').localeCompare(b.time||'99:99')||a.title.localeCompare(b.title));
}
export function scheduleMemberTone(members=[]) {
 const ids=['ine','jingburger','lilpa','jururu','gosegu','viichan'];
 return members.length===1&&ids.includes(members[0])?members[0]:'group';
}

// Berriz is authoritative only for the two selected official menus, never fan posts.
export function scheduleBerrizApproved(r) {
 const url=scheduleSafeUrl(r.sourceUrl);if(!url||!url.startsWith('https://berriz.in/ko/isegyeidol/'))return false;
 if(r.sourceId==='berriz-notice'){const match=url.match(/\/notice\/([1-9]\d*)\/$/);return !!match&&r.id==='berriz-notice-'+match[1];}
 return r.sourceId==='berriz-calendar'&&url==='https://berriz.in/ko/isegyeidol/calendar/'&&typeof r.calendarId==='string'&&/^[A-Za-z0-9_-]{1,80}$/.test(r.calendarId)&&r.id==='berriz-calendar-'+r.calendarId&&r.dateBasis==='official_calendar';
}
export function schedulePriority(r) {
 const url=scheduleSafeUrl(r.sourceUrl);
 if(url?.startsWith('https://berriz.in/ko/isegyeidol/notice/')&&r.sourceId==='berriz-notice')return 0;
 if(url==='https://berriz.in/ko/isegyeidol/calendar/'&&r.sourceId==='berriz-calendar')return 1;
 return 2;
}
