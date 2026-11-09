/* Melon-only chart presentation. Never add observations or alter stored ranks. */
export const albumFlowKinds = Object.freeze({melon_top100:'멜론 TOP100',melon_hot100:'멜론 HOT100 · 100일'});
export function albumFlowKind(requested, item = {}) {
  if (Object.hasOwn(albumFlowKinds, requested)) return requested;
  return Object.keys(albumFlowKinds).find(k => (item.charts?.[k] || item.melon?.[k.replace('melon_', '')+'History'] || []).at(-1)?.status === 'ranked') || 'melon_top100';
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
