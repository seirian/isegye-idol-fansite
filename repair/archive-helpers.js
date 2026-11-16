
// Finite reviewed archives are independent of the rolling 30-day feed.
export function albumArchiveReference(item, kind) {
  const a=item?.melonHistoryArchive, slug={melon_top100:'top100',melon_hot100:'hot100-d100'}[kind];
  if(!slug || a?.schemaVersion!==1 || a.sourceType!=='guyso_public_historical'
      || !/^[1-9][0-9]{1,11}$/.test(a.trackId||'') || !/^[1-9][0-9]{1,11}$/.test(a.albumId||'')
      || a.trackId!==item?.melon?.trackId || a.albumId!==item?.melon?.albumId
      || !/^[a-f0-9]{64}$/.test(a.datasetSha256||''))return null;
  const start=Date.parse(a.releaseAt), cutoff=Date.parse(a.through), entry=a.charts?.[kind];
  const end=Date.parse(entry?.through),url=`https://xn--o39an51b2re.com/chart/melon/${slug}/trend/ranking/${a.trackId}`;
  if(!Number.isFinite(start)||!Number.isFinite(end)||!Number.isFinite(cutoff)||start>end||end>cutoff
      ||cutoff>Date.now()+600000||entry?.source!==url||!Array.isArray(entry.points)||entry.points.length>50000)return null;
  const times=new Set(),rows=[];let previous=-Infinity;
  for(const p of entry.points) {
    if(!Array.isArray(p)||p.length!==3||!Number.isInteger(p[0])||p[0]<=previous
        ||p[0]*3600000<start||p[0]*3600000>end||![0,1].includes(p[2])
        ||(p[1]!==null&&(!Number.isInteger(p[1])||p[1]<1||p[1]>100)))return null;
    previous=p[0];const t=p[0]*3600000;
    rows.push({at:new Date(t).toISOString(),trackId:a.trackId,rank:p[1],status:p[1]===null?'out':'ranked'});
    if(p[2]===0)times.add(t);
  }
  return {url,times,rows,start,end,cutoff,label:'가이섬 대조·보완',archive:true};
}
export function albumArchiveRows(item, kind, rolling=[]) {
  const reference=albumArchiveReference(item,kind);
  if(!reference)return rolling;
  const map=new Map(reference.rows.map(p=>[Date.parse(p.at),p]));
  for(const p of Array.isArray(rolling)?rolling:[]) {
    const t=Date.parse(p?.at);
    if(!Number.isFinite(t))continue;
    const valid=(p.status==='ranked'&&Number.isInteger(p.rank)&&p.rank>=1&&p.rank<=100)||(p.status==='out'&&p.rank==null);
    if(valid||!map.has(t))map.set(t,p);
  }
  return [...map.values()].sort((a,b)=>Date.parse(a.at)-Date.parse(b.at));
}
export function albumArchiveWindow(item, params, now=Date.now()) {
  const ref=albumArchiveReference(item,'melon_top100')||albumArchiveReference(item,'melon_hot100');
  const result={enabled:false,hours:({ '24h':24,'7d':168,'30d':720 }[params.get('range')]||24),end:now};
  if(!ref)return result;
  const date=t=>new Date(t+9*3600000).toISOString().slice(0,10);
  const minDate=date(ref.start), maxDate=date(Math.min(now,ref.cutoff));
  let selected=params.get('historyEnd');
  if(!/^\d{4}-\d{2}-\d{2}$/.test(selected||'')||!Number.isFinite(Date.parse(selected+'T00:00:00+09:00'))
      ||date(Date.parse(selected+'T00:00:00+09:00'))!==selected||selected<minDate||selected>maxDate) {
    selected=date(Math.min(ref.cutoff,Math.floor((ref.start+9*3600000)/86400000)*86400000-9*3600000+30*86400000-3600000));
  }
  const end=Math.min(now,ref.cutoff,Date.parse(selected+'T23:00:00+09:00'));
  return {...result,minDate,maxDate,date:selected,available:true,...(params.get('range')==='history'?{enabled:true,hours:720,end}: {})};
}
