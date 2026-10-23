/** Pure LIVE state rules. An unavailable/invalid source must never mean offline. */
export const LIVE_POLL_MS = 30000;
export const LIVE_MAX_AGE_MS = 90000;
export const LIVE_TIMEOUT_MS = 9000;
export const LIVE_COOLDOWN_MS = 10000;
export const LIVE_CHANNELS = Object.freeze([
  {id:'ine', name:'아이네', channel:'inehine', tone:'lavender'},
  {id:'jingburger', name:'징버거', channel:'jingburger1', tone:'apricot'},
  {id:'lilpa', name:'릴파', channel:'lilpa0309', tone:'indigo'},
  {id:'jururu', name:'주르르', channel:'cotton1217', tone:'rose'},
  {id:'gosegu', name:'고세구', channel:'gosegu2', tone:'sky'},
  {id:'viichan', name:'비챤', channel:'viichan6', tone:'sage'}
].map(x=>Object.freeze(x)));
export const liveText = value => typeof value === 'string' ? value.replace(/[\u0000-\u001f\u007f]/g,' ').trim().slice(0,300) : '';
export const liveNumber = value => /^(0|[1-9]\d{0,11})$/.test(String(value)) ? Number(value) : null;
export const liveChannelUrl = member => 'https://www.sooplive.com/station/'+member.channel;
export const liveWatchUrl = member => 'https://play.sooplive.com/'+member.channel;
export function liveEmpty(member, reason='pending', last=null) {
  return {id:member.id, state:reason==='pending'?'loading':'unknown', reason, checkedAt:null,
    title:'', viewers:null, startedAt:null, broadcastId:null,
    lastKnown:last && ['live','offline'].includes(last.state) ? {...last} : last?.lastKnown || null};
}
export function liveEffective(record, now=Date.now()) {
  if (!record) return null;
  if (['live','offline'].includes(record.state) && (!Number.isFinite(record.checkedAt) || now-record.checkedAt>LIVE_MAX_AGE_MS || record.checkedAt>now+5000))
    return {...record,state:'unknown',reason:'stale',lastKnown:{...record}};
  return record;
}
export function liveSummary(records, now=Date.now()) {
  const count={live:0,offline:0,unknown:0,loading:0,total:records.length};
  records.map(r=>liveEffective(r,now)).forEach(r=>{if(r && Object.hasOwn(count,r.state))count[r.state]++;else count.unknown++;});
  return count;
}
export function liveSorted(records, now=Date.now()) {
  const rank={live:0,unknown:1,loading:2,offline:3};
  const order=new Map(LIVE_CHANNELS.map((m,i)=>[m.id,i]));
  return records.map(r=>liveEffective(r,now)).sort((a,b)=>(rank[a.state]-rank[b.state])||(order.get(a.id)-order.get(b.id)));
}
export function liveKstTime(value) {
  if(typeof value!=='string' || !/^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d$/.test(value))return null;
  const ts=Date.parse(value.replace(' ','T')+'+09:00');
  if(!Number.isFinite(ts))return null;
  const back=new Date(ts+9*3600000).toISOString().slice(0,19).replace('T',' ');
  return back===value?ts:null;
}
export function normalizeLiveStation(payload,member,now=Date.now()) {
  if(!payload || typeof payload!=='object' || Array.isArray(payload) || !payload.station ||
     payload.station.user_id!==member.channel || !liveText(payload.station.user_nick).includes(member.name) ||
     !Object.hasOwn(payload,'broad'))throw new Error('invalid-channel-response');
  const sourceAt=liveKstTime(payload.current_timestamp);
  if(sourceAt===null || now-sourceAt>LIVE_MAX_AGE_MS || sourceAt>now+60000)throw new Error('stale-source');
  const result={id:member.id,state:'offline',reason:null,checkedAt:now,sourceAt,title:'',viewers:null,startedAt:null,broadcastId:null,lastKnown:null};
  if(payload.broad===null)return result;
  const broad=payload.broad;
  if(!broad || typeof broad!=='object' || Array.isArray(broad))throw new Error('invalid-broadcast');
  const no=liveNumber(broad.broad_no);
  if(!no)throw new Error('invalid-broadcast');
  const started=liveKstTime(broad.broad_start||payload.station.broad_start);
  return {...result,state:'live',broadcastId:String(no),title:liveText(broad.broad_title),
    viewers:liveNumber(broad.current_sum_viewer),
    startedAt:started!==null&&started<=now&&now-started<7*86400000?started:null};
}
export async function fetchLiveMember(member,{fetcher=globalThis.fetch,now=Date.now,timeout=LIVE_TIMEOUT_MS}={}) {
  const controller=new AbortController();const timer=setTimeout(()=>controller.abort(),timeout);
  try {
    const response=await fetcher('https://chapi.sooplive.co.kr/api/'+member.channel+'/station',{
      credentials:'omit',cache:'no-store',referrerPolicy:'no-referrer',signal:controller.signal
    });
    if(!response.ok)throw new Error(response.status===429?'rate-limited':'source-unavailable');
    return normalizeLiveStation(await response.json(),member,now());
  } finally {clearTimeout(timer);}
}
