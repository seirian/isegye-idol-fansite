/** Pure rules. No network, operating-site storage or account access. */
export const STORAGE_KEY = 'isegye:playground:review:v1';
export const HISTORY_LIMIT = 20;
export function esc(value) { return String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
export function kstDate(now = new Date()) {
  if (!Number.isFinite(now.getTime())) throw new Error('Invalid date');
  return new Date(now.getTime()+9*3600000).toISOString().slice(0,10);
}
export function seeded(text) {
  let n=2166136261; for(const c of String(text)) n=Math.imul(n^c.charCodeAt(0),16777619)>>>0;
  return () => { n=(n+0x6D2B79F5)>>>0; let t=n; t=Math.imul(t^(t>>>15),t|1); t^=t+Math.imul(t^(t>>>7),t|61); return ((t^(t>>>14))>>>0)/4294967296; };
}
export function shuffle(values, random = Math.random) {
  const result=[...values]; for(let i=result.length-1;i>0;i--){const j=Math.floor(random()*(i+1)); [result[i],result[j]]=[result[j],result[i]];} return result;
}
export function safeLink(url) {
  if(typeof url!=='string')return '';
  if(/^\/#\/(?:song|member)\/[a-z0-9-]+$/.test(url)||/^\/#\/(?:history|content|members|music)$/.test(url))return url;
  try { const u=new URL(url); return u.protocol==='https:'&&!u.username&&!u.password ? u.href : ''; } catch {return '';}
}
export function questionPool(data, category='all') {
  return data.questions.filter(q => category==='all'||q.category===category);
}
export function chooseQuestions(data,{mode='quiz',category='all',count=5,seed='',ids=null}={}) {
  const random=seeded(seed); const pool=ids?data.questions.filter(q=>ids.includes(q.id)):questionPool(data,category);
  if(mode==='daily'){
    // Round-robin categories keeps the small daily set from becoming all dates.
    const groups=shuffle(Object.keys(data.categories),random).map(c=>shuffle(pool.filter(q=>q.category===c),random));
    const chosen=[];
    while(chosen.length<Math.min(count,pool.length)) for(const group of groups){if(group.length&&chosen.length<count)chosen.push(group.pop());}
    return chosen.map(q=>q.id);
  }
  return shuffle(pool,random).slice(0,count).map(q=>q.id);
}
export function orderPairs(tracks,seed,count=5) {
  const random=seeded(seed), pairs=[];
  for(let i=0;i<tracks.length;i++)for(let j=i+1;j<tracks.length;j++)if(tracks[i].date!==tracks[j].date)pairs.push([tracks[i].id,tracks[j].id]);
  return shuffle(pairs,random).slice(0,count).map(p=>shuffle(p,random));
}
export function score(session) {
  const answers=session.answers||[];
  return {total:session.mode==='order'?session.pairs.length:session.ids.length,correct:answers.filter(a=>a.correct).length,skipped:answers.filter(a=>a.choice===null).length,answered:answers.length,hints:answers.filter(a=>a.hint).length};
}
export function freshState(version) { return {schema:1,version,session:null,history:[],wrong:[],dark:false}; }
export function cleanSession(s,data) {
  if(!s||typeof s!=='object'||s.version!==data.version||!['daily','quiz','order','retry'].includes(s.mode)||typeof s.id!=='string'||!/^r[\w-]{1,90}$/.test(s.id)||typeof s.seed!=='string'||s.seed.length>150||!/^\d{4}-\d{2}-\d{2}$/.test(s.day)||typeof s.title!=='string'||s.title.length>100)return null;
  const byId=new Map(data.questions.map(q=>[q.id,q])),trackMap=new Map(data.tracks.map(t=>[t.id,t]));
  const ids=s.ids,pairs=s.pairs;
  if(!Array.isArray(ids)||!Array.isArray(pairs))return null;
  if(s.mode==='order'){
    if(ids.length||pairs.length<1||pairs.length>10||pairs.some(p=>!Array.isArray(p)||p.length!==2||p[0]===p[1]||!p.every(id=>trackMap.has(id))||trackMap.get(p[0]).date===trackMap.get(p[1]).date)||new Set(pairs.map(p=>[...p].sort().join(':'))).size!==pairs.length)return null;
  }else if(pairs.length||ids.length<1||ids.length>data.questions.length||ids.some(id=>!byId.has(id))||new Set(ids).size!==ids.length)return null;
  const total=s.mode==='order'?pairs.length:ids.length;
  if(!Number.isInteger(s.index)||s.index<0||s.index>=total||!Array.isArray(s.answers)||s.answers.length>total||typeof s.complete!=='boolean')return null;
  if(s.complete?(s.index!==total-1||s.answers.length!==total):![s.index,s.index+1].includes(s.answers.length))return null;
  const answers=[];
  for(let i=0;i<s.answers.length;i++){
    const a=s.answers[i]; if(!a||!(a.choice===null||Number.isInteger(a.choice))||typeof a.hint!=='boolean')return null;
    if(a.choice!==null&&(a.choice<0||a.choice>=(s.mode==='order'?2:byId.get(ids[i]).choices.length)))return null;
    const correctIndex=s.mode==='order'?(trackMap.get(pairs[i][0]).date<trackMap.get(pairs[i][1]).date?0:1):byId.get(ids[i]).answer;
    answers.push({choice:a.choice,correct:a.choice!==null&&a.choice===correctIndex,hint:a.hint});
  }
  return {id:s.id,version:s.version,seed:s.seed,day:s.day,title:s.title,mode:s.mode,ids:[...ids],pairs:pairs.map(p=>[...p]),index:s.index,answers,hint:!!s.hint,complete:s.complete};
}
export function cleanState(raw,data) {
  if(!raw||typeof raw!=='object'||raw.schema!==1||raw.version!==data.version) return freshState(data.version);
  const valid=new Set(data.questions.map(q=>q.id));
  return {schema:1,version:data.version,dark:raw.dark===true,session:cleanSession(raw.session,data),wrong:[...new Set(Array.isArray(raw.wrong)?raw.wrong.filter(id=>valid.has(id)):[])],history:(Array.isArray(raw.history)?raw.history:[]).map(s=>cleanSession(s,data)).filter(s=>s?.complete).slice(0,HISTORY_LIMIT)};
}
export function readState(storage,data) {
  try { const text=storage.getItem(STORAGE_KEY); if(!text)return {state:freshState(data.version),warning:''};
    const raw=JSON.parse(text); if(raw.schema!==1||raw.version!==data.version)return {state:freshState(data.version),warning:'문항 구성이 바뀌어 검토본 기록을 새로 시작합니다.'};
    const state=cleanState(raw,data);return {state,warning:raw.session&&!state.session?'중단된 풀이 기록을 읽지 못해 초기화했습니다.':''};
  }catch{return {state:freshState(data.version),warning:'저장 기록을 읽을 수 없습니다. 이 탭에서만 이용할 수 있어요.'};}
}
export function saveState(storage,state) { try{storage.setItem(STORAGE_KEY,JSON.stringify(state));return true;}catch{return false;} }
export function createSession(data,{mode='quiz',category='all',count=5,seed,day=kstDate(),ids=null}={}) {
  seed=seed||`${day}-${Math.random().toString(36).slice(2)}`;
  const selected=mode==='order'?[]:chooseQuestions(data,{mode,category,count,seed,ids});
  const pairs=mode==='order'?orderPairs(data.tracks,seed,count):[];
  if(!selected.length&&!pairs.length)throw new Error('No questions');
  const names={daily:'오늘의 5문제',order:'먼저일까, 나중일까?',retry:'다시 풀어보기',quiz:category==='all'?'골고루 퀴즈':(data.categories[category]||'퀴즈')};
  return {id:'r'+Date.now().toString(36)+'-'+Math.random().toString(36).slice(2,9),version:data.version,seed,day,title:names[mode],mode,ids:selected,pairs,index:0,answers:[],hint:false,complete:false};
}
export function recordAnswer(session,choice,data) {
  if(session.complete||session.answers.length!==session.index)return session;
  let answer,limit;
  if(session.mode==='order'){const p=session.pairs[session.index].map(id=>data.tracks.find(t=>t.id===id));answer=p[0].date<p[1].date?0:1;limit=2;}
  else {const q=data.questions.find(q=>q.id===session.ids[session.index]);answer=q.answer;limit=q.choices.length;}
  if(choice!==null&&(!Number.isInteger(choice)||choice<0||choice>=limit))return session;
  return {...session,answers:[...session.answers,{choice,correct:choice!==null&&choice===answer,hint:session.hint}]};
}
export function nextQuestion(session) {
  const total=session.mode==='order'?session.pairs.length:session.ids.length;
  if(session.complete||session.answers.length!==session.index+1)return session;
  return session.index===total-1?{...session,complete:true}:{...session,index:session.index+1,hint:false};
}
export function commitResult(state,session) {
  if(!session.complete)return state;
  const wrong=new Set(state.wrong);
  if(session.mode!=='order')session.ids.forEach((id,i)=>session.answers[i].correct?wrong.delete(id):wrong.add(id));
  return {...state,session,wrong:[...wrong],history:[session,...state.history.filter(s=>s.id!==session.id)].slice(0,HISTORY_LIMIT)};
}
