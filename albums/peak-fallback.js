/* Peak cards use actual Guyso summaries, never relabeled legacy or range ranks. */
export const albumPeakKinds = [
  ['top100','TOP100',100], ['hot100','HOT100 · 100일',100], ['realtime','실시간 차트',100],
  ['hot100_30','HOT100 · 30일',100], ['daily','일간 차트',1000],
  ['new_week','최신발매 · 1주',100], ['new_month','최신발매 · 4주',100]
];
export function albumVerifiedFallback(item, now = Date.now()) {
  const p=item?.melonPeakFallback;
  if (!p || p.schemaVersion!==1 || p.state!=='verified' || p.sourceType!=='guyso_observed_peaks' || p.trackId!==item?.melon?.trackId || p.albumId!==item?.melon?.albumId) return null;
  if (!/^[1-9]\d{0,11}$/.test(p.trackId||'') || p.source!==`https://xn--o39an51b2re.com/song/melon/${p.trackId}`) return null;
  if (p.datePolicy!=='summary_does_not_provide_dates' || !/^[a-f0-9]{64}$/.test(p.responseSha256||'')) return null;
  const at=Date.parse(p.checkedAt);
  if (!Number.isFinite(at) || !/(Z|[+-]\d{2}:\d{2})$/.test(p.checkedAt) || at>now+600000 || !p.records || Object.keys(p.records).length!==7) return null;
  for (const [key,,limit] of albumPeakKinds) {
    const r=p.records[key];if(!r || Object.keys(r).length!==2 || r.date!==null || (r.rank!==null && (!Number.isInteger(r.rank)||r.rank<1||r.rank>limit))) return null;
  }
  return p;
}
const albumPeakDateCharts={top100:'top100',hot100:'hot100-d100',realtime:'realtime',hot100_30:'hot100-d30',daily:'daily',new_week:'newest-w1',new_month:'newest-w4'};
function albumPeakCalendarDate(value) {
  if(typeof value!=='string'||!/^\d{4}-\d{2}-\d{2}$/.test(value))return false;
  const at=Date.parse(value+'T00:00:00Z');
  return Number.isFinite(at)&&new Date(at).toISOString().slice(0,10)===value;
}
function albumPeakDateTime(value) {
  if(typeof value!=='string')return NaN;
  const m=value.match(/^(\d{4}-\d{2}-\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.\d{1,6})?(Z|[+-](\d{2}):(\d{2}))$/);
  if(!m||!albumPeakCalendarDate(m[1])||+m[2]>23||+m[3]>59||+m[4]>59||(m[5]!=='Z'&&(+m[6]>23||+m[7]>59)))return NaN;
  return Date.parse(value);
}
export function albumVerifiedPeakDates(item, now = Date.now()) {
  const reference=albumVerifiedFallback(item,now),p=item?.melonPeakDates;
  if(!reference||!p||p.schemaVersion!==1||p.sourceType!=='guyso_peak_date_evidence'||p.trackId!==reference.trackId||p.albumId!==reference.albumId||!p.records||typeof p.records!=='object'||Array.isArray(p.records))return null;
  if(Object.keys(p.records).some(k=>!Object.hasOwn(albumPeakDateCharts,k)))return null;
  const records={};
  for(const [key] of albumPeakKinds){
    const r=p.records[key];
    if(!r||reference.records[key].rank===null||r.rank!==reference.records[key].rank||r.basis!=='earliest_observed_matching_peak'||r.timeUnit!==(key==='daily'?'DAYS':'HOURS')||!albumPeakCalendarDate(r.date)||!/^[a-f0-9]{64}$/.test(r.responseSha256||''))continue;
    const source=`https://xn--o39an51b2re.com/chart/melon/${albumPeakDateCharts[key]}/trend/ranking/${p.trackId}`;
    if(r.source!==source&&!(typeof r.source==='string'&&r.source.startsWith(source+'?end=')&&albumPeakCalendarDate(r.source.slice((source+'?end=').length))))continue;
    const observed=albumPeakDateTime(r.observedAt),checked=albumPeakDateTime(r.checkedAt),start=albumPeakDateTime(r.rangeStart),end=albumPeakDateTime(r.rangeEnd);
    if(![observed,checked,start,end].every(Number.isFinite)||checked>now+600000||start>observed||observed>end||end>checked+600000)continue;
    const kst=new Date(observed+9*3600000).toISOString();
    if(kst.slice(0,10)!==r.date||(key==='daily'&&kst.slice(11)!=='00:00:00.000Z'))continue;
    records[key]=r;
  }
  return {...p,records};
}
export function albumMergedPeaks(item, now = Date.now()) {
  const reference=albumVerifiedFallback(item,now),dates=albumVerifiedPeakDates(item,now);
  return albumPeakKinds.map(([key,label])=>{
    const row=reference?.records[key],dateEvidence=dates?.records[key]||null;
    return {key,label,rank:row?.rank??null,date:dateEvidence?.date||null,dateEvidence,
      source:reference?.source||'',sourceType:reference?'guyso_observation':'unknown',
      sourceLabel:reference?'가이섬':'기록 미확인',
      checkedAt:reference?.checkedAt||null,fetchState:reference?.fetchState||'unavailable',
      stale:!!reference && (reference.fetchState==='error'||now-Date.parse(reference.checkedAt)>36*3600000)};
  });
}
