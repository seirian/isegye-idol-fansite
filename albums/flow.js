/* Melon-only chart presentation. Never add observations or alter stored ranks. */
export const albumFlowKinds = Object.freeze({melon_top100:'멜론 TOP100',melon_hot100:'멜론 HOT100 · 100일'});
export function albumFlowKind(requested, item = {}, hours = 24, end = Date.now()) {
  if (Object.hasOwn(albumFlowKinds, requested)) return requested;
  const start=end-([24,168,720].includes(hours)?hours:24)*3600000;
  const choices=Object.keys(albumFlowKinds).map(key=>{
    const rows=(item.charts?.[key] || item.melon?.[key.replace('melon_', '')+'History'] || [])
      .filter(p=>Number.isFinite(Date.parse(p.at)) && Date.parse(p.at)>=start && Date.parse(p.at)<=end)
      .sort((a,b)=>Date.parse(a.at)-Date.parse(b.at));
    const ranked=rows.filter(p=>p.status==='ranked' && Number.isInteger(p.rank) && p.rank>=1 && p.rank<=100);
    return {key,count:ranked.length,active:rows.at(-1)?.status==='ranked'};
  });
  // Prefer a useful measured trend over a newly entered chart with one dot.
  choices.sort((a,b)=>Number(b.active&&b.count>1)-Number(a.active&&a.count>1) || Number(b.active)-Number(a.active) || b.count-a.count);
  return choices[0].key;
}
export function albumCurveSegments(points) {
  if (points.length < 2) return [];
  const h = [], delta = [];
  for (let i=0; i<points.length-1; i++) {
    const dx=points[i+1].x-points[i].x;
    if (!(dx>0) || !Number.isFinite(dx) || !Number.isFinite(points[i].y) || !Number.isFinite(points[i+1].y)) return [];
    h.push(dx); delta.push((points[i+1].y-points[i].y)/dx);
  }
  const slopes=[delta[0]];
  for (let i=1; i<points.length-1; i++) {
    const a=delta[i-1], b=delta[i], w1=2*h[i]+h[i-1], w2=h[i]+2*h[i-1];
    slopes.push(a*b<=0 ? 0 : (w1+w2)/(w1/a+w2/b));
  }
  slopes.push(delta.at(-1));
  // Monotonic Hermite limiter: control points cannot create a false rank peak.
  for (let i=0; i<delta.length; i++) {
    if (!delta[i]) { slopes[i]=0; slopes[i+1]=0; continue; }
    const a=slopes[i]/delta[i], b=slopes[i+1]/delta[i], length=Math.hypot(a,b);
    if (length>3) { slopes[i]=3*a*delta[i]/length; slopes[i+1]=3*b*delta[i]/length; }
  }
  return delta.map((_,i) => ({from:points[i], to:points[i+1],
    c1:{x:points[i].x+h[i]/3,y:points[i].y+h[i]*slopes[i]/3},
    c2:{x:points[i+1].x-h[i]/3,y:points[i+1].y-h[i]*slopes[i+1]/3}}));
}
export function albumSmoothPath(points) {
  if (!points.length) return '';
  const f = n => Number(n.toFixed(3));
  const segments=albumCurveSegments(points);
  if (points.length>1 && !segments.length) return '';
  return `M${f(points[0].x)},${f(points[0].y)}` + segments.map(s=>` C${f(s.c1.x)},${f(s.c1.y)} ${f(s.c2.x)},${f(s.c2.y)} ${f(s.to.x)},${f(s.to.y)}`).join('');
}
export function albumFlowGeometry(rows, start, end, gapMs=90*60000) {
  const ranked=rows.filter(p=>p.rank!==null), values=ranked.map(p=>p.rank);
  if (!values.length) return {points:[],segments:[],gaps:[],ticks:[],start,end};
  let lo=Math.min(...values), hi=Math.max(...values), pad=Math.max(3,Math.ceil((hi-lo)*.15));
  lo=Math.max(1,lo-pad); hi=Math.min(100,hi+pad);
  if (hi-lo<10) {lo=Math.max(1,lo-(10-hi+lo)/2);hi=Math.min(100,lo+10);lo=Math.max(1,hi-10);}
  lo=Math.floor(lo);hi=Math.ceil(hi);
  // The axis shows the actual observed interval, not seven days of empty space.
  let from=rows[0].t, to=rows.at(-1).t;
  if (from===to) {from-=30*60000;to+=30*60000;}
  const g={points:[],segments:[],gaps:[],ticks:[lo,Math.round((lo+hi)/2),hi],start:from,end:to};
  let segment=[], previous=null;
  const flush=()=>{if(segment.length)g.segments.push(segment);segment=[];};
  for (const row of rows) {
    if(row.rank===null) {flush();previous=null;continue;}
    const point={...row,x:24+(row.t-from)/(to-from)*712,y:20+(row.rank-lo)/(hi-lo)*208};
    if(previous && row.t-previous.t>gapMs) {
      flush();
      // A dashed guide is explicitly NOT measured intermediate data; never fill it.
      g.gaps.push([previous,point]);
    }
    segment.push(point);g.points.push(point);previous=point;
  }
  flush();return g;
}
export function albumFreeServiceStatus(provider, item={}, providers={}, now=Date.now()) {
  const old=t=>!Number.isFinite(Date.parse(t)) || now-Date.parse(t)>36*3600000;
  if(provider==='youtube') {
    const y=item.youtube || {}, global=providers.youtube || {};
    if(y.state==='ok' && Number.isFinite(y.viewCount)) return {state:old(y.checkedAt)?'stale':'ok',label:old(y.checkedAt)?'이전 확인값':'연결됨',detail:`무료 공개 통계 · 조회수${Number.isFinite(y.likeCount)?'·좋아요':''}`,checkedAt:y.checkedAt};
    if(y.state==='unavailable') return {state:'unavailable',label:'영상 확인 불가',detail:'삭제·비공개 또는 공개 통계 미제공'};
    if(global.state==='not_configured') return {state:'setup',label:'무료 API 키 설정 필요',detail:'YouTube Data API v3 · 서버 키 등록'};
    if(y.state==='error' || global.state==='error') return {state:'error',label:'일시적 연결 실패',detail:'API 활성화·키 제한·할당량을 확인해 주세요'};
    return {state:'unmatched',label:'공식 영상 매칭 대기',detail:'검증된 영상만 공개 통계와 연결합니다'};
  }
  const m=item.metadata, p=providers.itunes || {};
  if(m?.trackId && m?.title) {
    const stale=old(m.checkedAt) || p.state==='error';
    return {state:stale?'stale':'ok',label:stale?'이전 확인값':'연결됨',detail:'무료 iTunes Search · US 곡 정보',checkedAt:m.checkedAt};
  }
  if(item.match==='not_applicable') return {state:'unavailable',label:'대상 음원 없음',detail:'영상 공개 작품 · 카탈로그 음원과 구분'};
  if(p.state==='error') return {state:'error',label:'일시적 연결 실패',detail:'공개 검색 API 재시도 · 결제나 인증키 불필요'};
  return {state:'unmatched',label:'곡 매칭 대기',detail:'미국 카탈로그의 동일 음원을 확인 중입니다'};
}

// A fixed, song-specific historical source. Never accept arbitrary feed URLs.
export function albumHistoricalReference(item, kind) {
  const h=item?.melonHistoricalBackfill;
  if(!h || h.schemaVersion!==1 || h.sourceType!=='guyso_public_historical'
      || h.trackId!=='603813508' || h.albumId!=='15120216'
      || item?.melon?.trackId!==h.trackId || item?.melon?.albumId!==h.albumId
      || !/^[a-f0-9]{64}$/.test(h.datasetSha256||''))return null;
  const slug={melon_top100:'top100',melon_hot100:'hot100-d100'}[kind];
  if(!slug)return null;
  const url=`https://xn--o39an51b2re.com/chart/melon/${slug}/trend/ranking/603813508`;
  const entry=h.charts?.[kind],from=Date.parse('2026-11-09T18:00:00+09:00'),to=Date.parse('2026-11-16T09:00:00+09:00');
  if(entry?.source!==url || !Array.isArray(entry.at) || entry.at.length>160)return null;
  const times=entry.at.map(Date.parse);
  if(times.some(t=>!Number.isFinite(t)||t<from||t>to||t%3600000))return null;
  return {url,times:new Set(times),label:'가이섬 대조·보완'};
}

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
