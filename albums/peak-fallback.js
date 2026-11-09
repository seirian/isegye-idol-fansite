/* Per-chart provenance: original daily achievements first, approved secondary peaks next. */
import {albumVerifiedPeaks} from './core.js';
export const albumPeakKinds = [
  ['top100','TOP100',100], ['hot100','HOT100 · 100일',100], ['realtime','실시간 차트',100],
  ['hot100_30','HOT100 · 30일',100], ['daily','일간 차트',1000],
  ['new_week','최신발매 · 1주',100], ['new_month','최신발매 · 4주',100]
];
export function albumVerifiedFallback(item, now = Date.now()) {
  const p=item?.melonPeakFallback;
  if (!p || p.schemaVersion!==1 || p.state!=='verified' || p.sourceType!=='isegyechart_observed_peaks' || p.trackId!==item?.melon?.trackId || p.albumId!==item?.melon?.albumId) return null;
  if (!/^https:\/\/isegyechart\.com\/song\/[1-9]\d{0,5}$/.test(p.source||'')) return null;
  const at=Date.parse(p.checkedAt);
  if (!Number.isFinite(at) || !/(Z|[+-]\d{2}:\d{2})$/.test(p.checkedAt) || at>now+600000 || !p.records || Object.keys(p.records).length!==7) return null;
  const day=new Date(at+9*3600000).toISOString().slice(0,10);
  for (const [key,,limit] of albumPeakKinds) {
    const r=p.records[key];if(!r || (r.rank!==null && (!Number.isInteger(r.rank)||r.rank<1||r.rank>limit))) return null;
    if (r.rank===null && r.date!==null) return null;
    if (r.date!==null && (typeof r.date!=='string'||!/^\d{4}-\d{2}-\d{2}$/.test(r.date)||!Number.isFinite(Date.parse(r.date))||new Date(r.date).toISOString().slice(0,10)!==r.date||r.date<'2000-01-01'||r.date>day)) return null;
  }
  return p;
}
export function albumMergedPeaks(item, now = Date.now()) {
  const original=albumVerifiedPeaks(item), secondary=albumVerifiedFallback(item,now);
  return albumPeakKinds.map(([key,label])=>{
    const direct=key==='daily' && Number.isInteger(original?.dailyBestRank);
    const backup=secondary?.records[key];
    const source=direct?original:Number.isInteger(backup?.rank)?secondary:null;
    return {key,label,rank:direct?original.dailyBestRank:source?backup.rank:null,
      date:direct?original.dailyBestDate:source?backup.date:null,
      source:source?.source||'',sourceType:direct?'melon_original':source?'secondary_observation':'unknown',
      sourceLabel:direct?'멜론 원본':source?'이세계차트':'기록 미확인',
      checkedAt:source?.checkedAt||null,fetchState:source?.fetchState||'unavailable',
      stale:!!source && (source.fetchState==='error'||now-Date.parse(source.checkedAt)>36*3600000)};
  });
}
