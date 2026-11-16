/** Append-only public question-bank validation. Never evaluate remote code. */
export const MAX_BANK_BYTES = 5000000;
export function canonical(value) { return JSON.stringify(value, (_,v)=>v&&typeof v==='object'&&!Array.isArray(v)?Object.fromEntries(Object.keys(v).sort().map(k=>[k,v[k]])):v); }
export function checkedBank(feed, seed) {
  if(!feed||feed.schemaVersion!==1||feed.feed!=='playground'||feed.baseVersion!==seed.version||!/^\d{4}-\d{2}-\d{2}T/.test(feed.generatedAt||'')||!Number.isFinite(Date.parse(feed.generatedAt))||Date.parse(feed.generatedAt)>Date.now()+120000)throw new Error('Bank envelope');
  const d=feed.catalog, text=s=>typeof s==='string'&&s.length>0&&s.length<=800&&!/[<>\x00-\x08]/.test(s);
  if(!d||d.schemaVersion!==1||d.version!==seed.version||canonical(d.categories)!==canonical(seed.categories)||!Array.isArray(d.questions)||d.questions.length<seed.questions.length||d.questions.length>1000||!Array.isArray(d.tracks)||d.tracks.length>100||!d.sources||Object.keys(d.sources).length>1500)throw new Error('Bank schema');
  const ids=new Set();
  for(const [id,s] of Object.entries(d.sources)){
    if(!/^[A-Za-z0-9_-]{1,90}$/.test(id)||!text(s.title)||!['primary','catalog','archive','community','context'].includes(s.kind)||!/^\d{4}-\d{2}-\d{2}$/.test(s.checkedAt))throw new Error('Source');
    const u=new URL(s.url);if(u.protocol!=='https:'||u.username||u.password||!u.hostname)throw new Error('Source URL');
  }
  for(const q of d.questions){
    if(!/^[a-z0-9-]{1,60}$/.test(q.id)||ids.has(q.id)||!Object.hasOwn(d.categories,q.category)||!['reviewed','community'].includes(q.status)||![q.stem,q.hint,q.explanation,q.level].every(text)||!Array.isArray(q.choices)||q.choices.length!==4||new Set(q.choices).size!==4||!q.choices.every(text)||!Number.isInteger(q.answer)||q.answer<0||q.answer>3)throw new Error('Question');
    ids.add(q.id);
    if(!Array.isArray(q.sources)||!q.sources.length||q.sources.some(s=>!Object.hasOwn(d.sources,s)||d.sources[s].kind==='context'))throw new Error('Answer evidence');
    if(!Array.isArray(q.inspiration)||q.inspiration.some(r=>!Object.hasOwn(d.sources,r.source)||!Array.isArray(r.items)||!r.items.every(n=>Number.isInteger(n)&&n>0&&n<=1000)))throw new Error('Inspiration');
    if(q.related&&!/^\/#\/(?:song\/[a-z0-9-]+|member\/[a-z0-9-]+|history|content|members|music)$/.test(q.related))throw new Error('Related link');
    if(q.eligibleFrom&&!/^\d{4}-\d{2}-\d{2}$/.test(q.eligibleFrom))throw new Error('Eligibility');
  }
  // Existing facts/answers are immutable in an automatic daily refresh.
  for(const q of seed.questions)if(canonical(q)!==canonical(d.questions.find(v=>v.id===q.id)))throw new Error('Seed changed');
  for(const [id,s] of Object.entries(seed.sources))if(canonical(s)!==canonical(d.sources[id]))throw new Error('Seed source changed');
  if(canonical(d.tracks)!==canonical(seed.tracks))throw new Error('Release dates changed');
  return d;
}
export async function fetchBank(seed, fetcher=fetch) {
  const controller=new AbortController(), timer=setTimeout(()=>controller.abort(),5000);
  try {
    const r=await fetcher('/api/playground',{credentials:'same-origin',cache:'no-store',signal:controller.signal});
    if(!r.ok)throw new Error('Unavailable');const raw=await r.text();if(raw.length>MAX_BANK_BYTES)throw new Error('Oversized');
    const f=JSON.parse(raw);return {data:checkedBank(f,seed),message:f.fallback?'현재 기본 문제은행으로 이용할 수 있습니다.':'',checkedAt:f.generatedAt};
  } catch { return {data:seed,message:'문제은행의 새 정보를 확인하지 못해 기본 문제로 시작합니다.',checkedAt:null}; }
  finally {clearTimeout(timer);}
}
