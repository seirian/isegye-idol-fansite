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
export function albumMergedPeaks(item, now = Date.now()) {
  const reference=albumVerifiedFallback(item,now);
  return albumPeakKinds.map(([key,label])=>{
    const row=reference?.records[key];
    return {key,label,rank:row?.rank??null,date:null,
      source:reference?.source||'',sourceType:reference?'guyso_observation':'unknown',
      sourceLabel:reference?'가이섬':'기록 미확인',
      checkedAt:reference?.checkedAt||null,fetchState:reference?.fetchState||'unavailable',
      stale:!!reference && (reference.fetchState==='error'||now-Date.parse(reference.checkedAt)>36*3600000)};
  });
}
