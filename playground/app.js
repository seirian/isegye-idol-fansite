/* Preview UI. All state belongs to this browser and this preview only. */
(() => {
  'use strict';
  const data=PLAYGROUND_DATA, main=document.querySelector('#main');
  const questions=new Map(data.questions.map(q=>[q.id,q])), tracks=new Map(data.tracks.map(t=>[t.id,t]));
  let storage,loaded;
  try { storage=window.localStorage;loaded=readState(storage,data); }
  catch { storage=null; }
  // A blocked storage getter must never stop gameplay.
  if(!storage)loaded={state:freshState(data.version),warning:'브라우저 저장을 사용할 수 없습니다. 이 탭에서만 이용할 수 있어요.'};
  let state=loaded.state, setupCategory='all',setupCount=5, lastOpener=null;
  const kindNames={primary:'공개 원본 확인',catalog:'기존 카탈로그 대조',archive:'나무위키 기반 보존 자료',community:'커뮤니티 공개 답안',context:'참고 범위 안내'};
  function warn(message){const n=document.querySelector('#storage-note');n.textContent=message;n.hidden=!message;}
  warn(loaded.warning);
  function persist(){if(!saveState(storage,state))warn('브라우저에 저장하지 못했습니다. 현재 탭에서는 계속 풀 수 있어요.');}
  function announce(text){document.querySelector('#status').textContent=text;clearTimeout(announce.timer);announce.timer=setTimeout(()=>document.querySelector('#status').textContent='',3500);}
  function applyTheme(){document.body.classList.toggle('dark',state.dark);const b=document.querySelector('#theme');b.setAttribute('aria-label',state.dark?'밝은 화면으로 전환':'어두운 화면으로 전환');b.setAttribute('aria-pressed',String(state.dark));}
  applyTheme();document.querySelector('#theme').addEventListener('click',()=>{state.dark=!state.dark;persist();applyTheme();});
  function path(){return (location.hash.slice(1)||'/playground').split('?')[0];}
  function go(to){if(location.hash==='#'+to)render();else location.hash=to;}
  function heading(title,description,tag='PLAYGROUND'){return `<div class="page-heading"><div><div class="eyebrow">${esc(tag)}</div><h1>${esc(title)}</h1><p>${esc(description)}</p></div><span class="badge">시간제한 없이, 가볍게</span></div>`;}
  function sourceHTML(ids){return ids.map(id=>{const s=data.sources[id];return `<div class="source-item"><a href="${esc(safeLink(s.url))}" target="_blank" rel="noopener noreferrer">${esc(s.title)} ↗</a><p>${esc(kindNames[s.kind])} · 확인 자료 기준 ${esc(s.checkedAt)}${s.note?' · '+esc(s.note):''}</p></div>`;}).join('');}
  function evidence(q){return `<details><summary>문항 근거와 참고 글 보기</summary>${sourceHTML(q.sources)}${q.inspiration?.length?`<p class="note">소재 참고: ${q.inspiration.map(r=>esc(data.sources[r.source].title)+' '+r.items.join('·')+'번').join(' / ')}. 문항과 보기는 새로 구성했습니다.</p>`:''}</details>`;}
  function home(){
    const active=state.session&&!state.session.complete?state.session:null;
    const today=state.history.find(s=>s.mode==='daily'&&s.day===kstDate());
    return heading('놀이터','알고 있던 이세돌도, 처음 만나는 이세돌도.')+
      (active?`<div class="banner"><div><strong>풀던 문제가 있어요</strong><p>${esc(active.title)} · ${active.index+1}번째 문제에서 이어서 시작하세요.</p></div><a class="button" href="#/play">이어서 풀기 →</a></div>`:'')+
      `<section class="hero" aria-labelledby="daily-title"><div><span class="badge">${kstDate().replaceAll('-','.')} · 오늘의 퀴즈</span><h2 id="daily-title">오늘의 다섯 문제</h2><p>멤버 이야기부터 좋아하던 노래까지.<br>정답을 몰라도 괜찮아요. 해설에서 함께 알아가요.</p><div class="actions"><button class="primary" data-start="daily">${today?'오늘 문제 다시 풀기':'다섯 문제 시작하기'} →</button>${today?`<span class="muted">오늘의 최근 기록 ${score(today).correct}/5</span>`:'<span class="muted">힌트 · 건너뛰기 가능</span>'}</div><div class="dot-row" aria-hidden="true"><i></i><i></i><i></i><i></i><i></i></div></div><div class="hero-art" aria-hidden="true"><div class="tile a"><strong>?</strong><span>QUIZ</span></div><div class="tile b"><strong>✦</strong><span>DISCOVER</span></div><div class="tile c"><strong>♪</strong><span>PLAY</span></div></div></section>
<!--PREVIEW-QUIZ-OPTIONS-->`;
  }
  function setup(){const count=questionPool(data,setupCategory).length;return `<div class="game-wrap">${heading('좋아하는 주제부터','보기 중 하나를 고르면 정답과 이야기를 바로 확인할 수 있어요.')}<section class="panel"><h2>퀴즈 고르기</h2><span class="setup-label">주제</span><div class="chips">${[['all','골고루'],...Object.entries(data.categories)].map(([id,name])=>`<button class="chip" data-category="${id}" aria-pressed="${id===setupCategory}">${name}</button>`).join('')}</div><span class="setup-label">문제 수</span><div class="chips">${[5,10].map(n=>`<button class="chip num-choice" data-count="${n}" aria-pressed="${n===setupCount}" ${n>count?'disabled':''}>${n}문제</button>`).join('')}</div><p class="note">선택한 주제에는 ${count}개 문항이 있습니다. 힌트를 써도 점수는 줄지 않아요.</p><div class="actions spacer"><button class="primary" data-start="quiz">퀴즈 시작하기 →</button><a class="button" href="#/playground">돌아가기</a></div></section></div>`;}
  function start(mode){
    if(mode==='retry'&&!state.wrong.length)return;
    const launch=()=>{
      const day=kstDate();
      state.session=createSession(data,{mode,day,category:setupCategory,count:mode==='quiz'?setupCount:mode==='retry'?Math.min(10,state.wrong.length):5,seed:mode==='daily'?data.version+':'+day:undefined,ids:mode==='retry'?state.wrong:null});
      persist();go('/play');
    };
    if(state.session&&!state.session.complete)confirmAction('새 문제를 시작할까요?','지금 풀던 진행 상태는 바뀝니다. 완료한 기록은 남아 있어요.',launch);else launch();
  }
  function current(){const s=state.session;return s?.mode==='order'?null:questions.get(s?.ids[s.index]);}
  function play(){
    const s=state.session;if(!s)return empty('아직 시작한 문제가 없어요','놀이터에서 하고 싶은 퀴즈를 골라주세요.');if(s.complete)return result(s);
    const total=s.mode==='order'?s.pairs.length:s.ids.length,a=s.answers[s.index],q=current();
    const isOrder=s.mode==='order';
    let options,answer,stem,cat,hint;
    if(isOrder){const ts=s.pairs[s.index].map(id=>tracks.get(id));answer=ts[0].date<ts[1].date?0:1;stem='먼저 발매된 곡은 무엇일까요?';cat='발매 순서';hint='두 곡의 발매 연도는 '+ts.map(t=>t.date.slice(0,4)+'년').join('과 ')+'입니다.';
      options=ts.map((t,i)=>({label:t.title,index:i,date:t.date}));
    }else{answer=q.answer;stem=q.stem;cat=data.categories[q.category];hint=q.hint;options=shuffle(q.choices.map((label,index)=>({label,index})),seeded(s.seed+':'+q.id));}
    const feedback=a?(isOrder?orderFeedback(s,a,answer):questionFeedback(q,a)):'';
    return `<div class="game-wrap"><div class="game-top"><a href="#/playground">← 놀이터</a><span>${esc(s.title)}</span><a class="small-link" href="#/playground">나중에 이어풀기</a></div><div class="progress" aria-label="${s.index+1}/${total} 문제">${Array.from({length:total},(_,i)=>`<span class="${i<s.index?'done':i===s.index?'current':''}"></span>`).join('')}</div><section class="question-panel"><div class="question-tags"><span class="badge">${s.index+1} / ${total}</span><span class="badge">${esc(cat)}</span>${q?`<span class="badge">${esc(q.level)}</span>${q.status==='community'?'<span class="badge">커뮤니티 답안 기준</span>':''}`:''}</div><h1>${esc(stem)}</h1>${isOrder?'<p class="question-note">최초 국내 음원 발매일 기준 · MV 공개일과는 달라요.</p>':''}<div class="options ${isOrder?'order-options':''}" role="group" aria-label="답 고르기">${options.map((o,displayIndex)=>`<button class="option ${isOrder?'order-option ':''}${a?(o.index===answer?'correct':o.index===a.choice?'wrong':''):''}" data-answer="${o.index}" data-key="${displayIndex+1}" ${a?'disabled':''}>${isOrder?'<span class="disc" aria-hidden="true">◉</span>':`<span class="key" aria-hidden="true">${displayIndex+1}</span>`}<span class="option-label">${esc(o.label)}</span>${a?`<span class="state">${o.index===answer?'✓ 정답':o.index===a.choice?'내 선택':''}</span>`:''}${isOrder&&a?`<time datetime="${o.date}">${o.date.replaceAll('-','.')}</time>`:''}</button>`).join('')}</div>${s.hint&&!a?`<div class="hint"><strong>힌트</strong> · ${esc(hint)}</div>`:''}${!a?`<div class="actions between"><button class="ghost" data-action="hint" ${s.hint?'disabled':''}>${s.hint?'힌트를 확인했어요':'힌트 보기'}</button><button class="ghost" data-action="skip">모르겠어요 · 건너뛰기</button></div>`:feedback}</section><div class="under-game"><span class="muted">${a?'충분히 읽고 다음 문제로 이동하세요.':'시간제한은 없어요. 천천히 생각해 보세요.'}</span>${a?`<button class="primary" data-action="next">${s.index===total-1?'결과 보기':'다음 문제'} →</button>`:''}</div></div>`;
  }
  function verdict(a){return a.choice===null?'새로운 이야기를 알아가요':a.correct?'정답이에요!':'이렇게 기억해 보세요';}
  function questionFeedback(q,a){return `<div class="feedback ${a.correct?'':'miss'}" role="status" aria-live="polite"><h2>${verdict(a)}</h2><p><strong>정답 · ${esc(q.choices[q.answer])}</strong></p><p>${esc(q.explanation)}</p>${q.status==='community'?'<p class="note">커뮤니티 공개 답안을 기준으로 구성한 문항입니다.</p>':''}</div>${q.related?`<a class="related" href="${esc(safeLink(q.related))}" target="_blank" rel="noopener">아카이브에서 더 보기 ↗</a>`:''}${evidence(q)}`;}
  function orderFeedback(s,a,answer){const ts=s.pairs[s.index].map(id=>tracks.get(id));return `<div class="feedback ${a.correct?'':'miss'}" role="status"><h2>${verdict(a)}</h2><p><strong>${esc(ts[answer].title)}</strong>가 먼저 발매됐어요.</p>${[...ts].sort((x,y)=>x.date.localeCompare(y.date)).map(t=>`<div class="date-line"><strong>${esc(t.title)}</strong><time datetime="${t.date}">${t.date.replaceAll('-','.')} · 국내 음원 발매</time></div>`).join('')}</div><details><summary>발매일 출처 보기</summary>${sourceHTML([...new Set(ts.flatMap(t=>t.sources))])}</details>`;}
  function empty(title,desc){return `<div class="empty"><h1>${esc(title)}</h1><p>${esc(desc)}</p><a class="button primary" href="#/playground">놀이터로 돌아가기</a></div>`;}
  function result(s){
    const sc=score(s),isOrder=s.mode==='order',missed=isOrder?[]:s.ids.filter((_,i)=>!s.answers[i].correct);
    return `<div class="game-wrap">${heading('오늘도 한 뼘 더 알아갔어요',s.title+' · '+s.day)}<section class="result-hero"><span class="badge">플레이 완료</span><div class="score">${sc.correct} <small>/ ${sc.total}</small></div><h2>${sc.correct===sc.total?'모두 맞혔어요!':'새롭게 알게 된 이야기가 있나요?'}</h2><p>팬심에는 점수가 없어요. 몰랐던 기록을 발견했다면 충분해요.</p><div class="actions"><button class="primary" data-action="new">다른 문제 풀기</button><button data-share-result="${esc(s.id)}">결과 공유</button></div></section><div class="stats"><div class="stat"><strong>${sc.correct}</strong><span>정답</span></div><div class="stat"><strong>${sc.total-sc.correct-sc.skipped}</strong><span>다시 알아보기</span></div><div class="stat"><strong>${sc.skipped}</strong><span>건너뛴 문제</span></div></div>${missed.length?`<div class="banner"><div><strong>기억하고 싶은 ${missed.length}문제</strong><p>틀리거나 건너뛴 문제만 한 번 더 풀어보세요.</p></div><button data-retry-result="${esc(s.id)}">이 문제 다시 풀기</button></div>`:''}<div class="section-head"><h2>문제와 해설 다시 보기</h2><span class="muted">힌트 사용 ${sc.hints}회</span></div>${(isOrder?s.pairs:s.ids).map((item,i)=>reviewRow(s,item,i)).join('')}<div class="actions spacer"><a class="button" href="#/playground">놀이터로</a><a class="button" href="#/records">내 기록 보기</a></div></div>`;
  }
  function reviewRow(s,item,i){const a=s.answers[i];if(s.mode==='order'){const ts=item.map(id=>tracks.get(id)),first=[...ts].sort((x,y)=>x.date.localeCompare(y.date))[0];return `<details class="review-question"><summary><span class="verdict ${a.correct?'':'miss'}">${a.correct?'✓ 정답':a.choice===null?'— 건너뜀':'↻ 다시 보기'}</span><span>${i+1}. ${ts.map(t=>esc(t.title)).join(' / ')}</span></summary><p>먼저 발매된 곡은 <strong>${esc(first.title)}</strong>입니다.</p>${ts.map(t=>`<p>${esc(t.title)} · ${t.date}</p>`).join('')}${sourceHTML([...new Set(ts.flatMap(t=>t.sources))])}</details>`;}
    const q=questions.get(item);return `<details class="review-question"><summary><span class="verdict ${a.correct?'':'miss'}">${a.correct?'✓ 정답':a.choice===null?'— 건너뜀':'↻ 다시 보기'}</span><span>${i+1}. ${esc(q.stem)}</span></summary><p>내 선택: ${a.choice===null?'건너뛰기':esc(q.choices[a.choice])}<br><strong>정답: ${esc(q.choices[q.answer])}</strong></p><p>${esc(q.explanation)}</p>${q.related?`<a class="related" target="_blank" rel="noopener" href="${esc(safeLink(q.related))}">관련 아카이브 ↗</a>`:''}${evidence(q)}</details>`;
  }
  function records(){return heading('내 플레이 기록','이 브라우저에서 완료한 최근 20회만 보관합니다.')+`<div class="actions"><button data-start="retry" ${!state.wrong.length?'disabled':''}>틀리거나 건너뛴 ${state.wrong.length}문제 다시 풀기</button><button class="ghost" data-action="reset">검토본 기록 지우기</button></div><p class="note">발매 순서 게임은 회차별 해설에서 다시 볼 수 있어요. 다른 기기나 계정에는 기록이 전송되지 않습니다.</p><div class="records-list spacer">${state.history.length?state.history.map(s=>`<div class="record-row"><div><strong>${esc(s.title)}</strong><p>${s.day} · ${score(s).correct}/${score(s).total} 정답</p></div><a class="button" href="#/result/${esc(s.id)}">해설 보기</a></div>`).join(''):empty('아직 완료한 기록이 없어요','첫 문제를 풀어보면 이곳에 기록이 남아요.')}</div>`;}
  function sources(){return heading('문항과 참고 자료','문제는 새로 구성하고, 사실의 근거와 아이디어를 얻은 경로는 구분했습니다.','ABOUT THIS PLAYGROUND')+`<div class="panel"><h2>어떤 자료를 참고했나요?</h2><p>왁물원 문제집의 본문·답안·정정 댓글을 확인했습니다. 기존 나무위키 기반 멤버·커버 카탈로그도 참고하되, 이번에 원문 전체를 다시 읽었다고 표시하지 않았습니다.</p><p>원문 퀴즈를 통째로 복제하지 않았습니다. 개인 취향 질문, 가사 재현, 이미지 식별, 정답이 충돌하거나 시점이 모호한 문항은 제외했습니다.</p><p>행사 답안을 이용한 문항에는 해당 기준을 표시합니다. 음악의 발매일과 영상의 공개일은 섞지 않습니다. 최근 수치나 최신 순위는 출제하지 않았어요.</p><p class="note">문제은행 ${data.questions.length}개 · 순서 게임 ${data.tracks.length}곡 / ${orderPairs(data.tracks,'all',100).length}개 조합 · 버전 ${esc(data.version)}. 날짜가 바뀌어도 같은 문항이 다시 나올 수 있습니다.</p></div><div class="section-head"><h2>참고한 출처</h2></div><div class="source-grid">${Object.values(data.sources).map(s=>`<section class="panel"><span class="badge">${esc(kindNames[s.kind])}</span><h3 class="spacer">${esc(s.title)}</h3><p>${esc(s.note||'문항의 사실과 발매 정보를 확인하는 출처입니다.')}</p><p>자료 확인 기준 ${esc(s.checkedAt)}</p><a href="${esc(safeLink(s.url))}" target="_blank" rel="noopener noreferrer">원문 열기 ↗</a></section>`).join('')}</div>`;}
  function render(focus=true){const p=path();
    if(p==='/playground'||p==='/')main.innerHTML=home();
    else if(p==='/quiz')main.innerHTML=setup();
    else if(p==='/play')main.innerHTML=play();
    else if(p==='/records')main.innerHTML=records();
    else if(p==='/sources')main.innerHTML=sources();
    else if(p.startsWith('/result/')){const s=state.history.find(s=>s.id===p.split('/')[2]);main.innerHTML=s?result(s):empty('이 기록을 찾을 수 없어요','이 브라우저에 남아 있는 완료 기록만 열 수 있습니다.');}
    else main.innerHTML=empty('찾을 수 없는 페이지예요','놀이터 첫 화면에서 다시 시작해 주세요.');
    document.title=(main.querySelector('h1')?.textContent||'놀이터')+' · ISEGYE! 놀이터';
    if(focus){main.focus({preventScroll:true});window.scrollTo({top:0,behavior:'instant'});}
  }
  function confirmAction(title,text,callback){const d=document.querySelector('#confirm');document.querySelector('#confirm-title').textContent=title;document.querySelector('#confirm-text').textContent=text;const opener=document.activeElement;d.returnValue='';d.addEventListener('close',()=>{if(d.returnValue==='ok')callback();else if(opener?.isConnected)opener.focus();},{once:true});d.showModal();}
  function getResult(id){return state.history.find(s=>s.id===id)|| (state.session?.id===id?state.session:null);}
  document.addEventListener('click',e=>{
    const b=e.target.closest('button');if(!b||b.disabled)return;
    if(b.dataset.start){start(b.dataset.start);return;}
    if(b.dataset.category){setupCategory=b.dataset.category;if(questionPool(data,setupCategory).length<setupCount)setupCount=5;render(false);main.querySelector(`[data-category="${setupCategory}"]`)?.focus();return;}
    if(b.dataset.count){setupCount=Number(b.dataset.count);render(false);main.querySelector(`[data-count="${setupCount}"]`)?.focus();return;}
    if(b.dataset.answer!==undefined){state.session=recordAnswer(state.session,Number(b.dataset.answer),data);persist();render(false);main.querySelector('[data-action=next]')?.focus({preventScroll:true});return;}
    if(b.dataset.retryResult){const s=getResult(b.dataset.retryResult);const ids=s.ids.filter((_,i)=>!s.answers[i].correct);state.session=createSession(data,{mode:'retry',ids,count:ids.length});persist();go('/play');return;}
    if(b.dataset.shareResult){const s=getResult(b.dataset.shareResult),sc=score(s);lastOpener=b;document.querySelector('#share-text').value=`이세돌 놀이터 · ${s.title}\n${sc.total}문제 중 ${sc.correct}문제 정답!\n시간제한 없이 가볍게 즐겨보세요.\nhttps://isegye-idol.kr/review-playground/\n(검토본 · 기존 관리자 로그인 필요)`;document.querySelector('#share').showModal();return;}
    const action=b.dataset.action;
    if(action==='hint'){state.session.hint=true;persist();render(false);main.querySelector('.hint')?.scrollIntoView({block:'nearest'});}
    else if(action==='skip'){state.session=recordAnswer(state.session,null,data);persist();render(false);main.querySelector('[data-action=next]')?.focus({preventScroll:true});}
    else if(action==='next'){state.session=nextQuestion(state.session);if(state.session.complete)state=commitResult(state,state.session);persist();render();}
    else if(action==='new'){go('/quiz');}
    else if(action==='reset'){confirmAction('검토본 기록을 지울까요?','진행 중인 풀이, 완료 기록과 다시 풀 문제를 지웁니다. 운영 저장함은 변경하지 않습니다.',()=>{const dark=state.dark;state=freshState(data.version);state.dark=dark;persist();render();announce('검토본 기록을 지웠습니다.');});}
    else if(action==='close-share')document.querySelector('#share').close();
    else if(action==='copy'){const t=document.querySelector('#share-text');if(navigator.clipboard?.writeText)navigator.clipboard.writeText(t.value).then(()=>announce('결과 텍스트를 복사했습니다.')).catch(()=>{t.select();announce('복사 권한이 없어 텍스트를 선택했습니다. 직접 복사해 주세요.');});else{t.select();announce('선택된 텍스트를 직접 복사해 주세요.');}}
  });
  document.querySelector('#share').addEventListener('close',()=>lastOpener?.isConnected&&lastOpener.focus());
  document.addEventListener('keydown',e=>{if(e.ctrlKey||e.altKey||e.metaKey||document.querySelector('dialog[open]')||e.target.closest('input,textarea,select')||path()!=='/play')return;const key=Number(e.key);if(key>=1&&key<=4)main.querySelector(`[data-key="${key}"]:not(:disabled)`)?.click();});
  window.addEventListener('hashchange',()=>render());
  render(false);
})();
