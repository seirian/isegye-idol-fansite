'use strict';
(() => {
  const $ = id => document.getElementById(id);
  const labels = {healthy:'정상', attention:'확인 필요', running:'진행 중', paused:'예정·수동 중지', unknown:'확인 불가', missing:'관측 공백', partial:'일부 관측'};
  const execution = {success:['healthy','성공'], failure:['attention','실패'], timed_out:['attention','시간 초과'], cancelled:['unknown','취소'], skipped:['paused','건너뜀'], action_required:['attention','조치 필요'], neutral:['unknown','중립']};
  const active = new Set(['in_progress','queued','pending','waiting','requested']);
  let data = null, filter = 'all', failed = false, loading = false, opener = null;
  const date = value => {
    if (!value || !Number.isFinite(Date.parse(value))) return '확인되지 않음';
    return new Intl.DateTimeFormat('ko-KR',{timeZone:'Asia/Seoul',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).format(new Date(value));
  };
  const seconds = value => Number.isFinite(value) ? (value < 60 ? `${value}초` : `${Math.floor(value/60)}분 ${value%60}초`) : '—';
  function node(tag, text, cls) { const e = document.createElement(tag); if (text !== undefined) e.textContent = String(text); if (cls) e.className = cls; return e; }
  function badge(state, text) { return node('span', text || labels[state] || labels.unknown, 'badge '+(labels[state] ? state : 'unknown')); }
  function isStale() { return !data || failed || Date.now()-Date.parse(data.checkedAt) > data.staleAfterSeconds*1000 || Date.parse(data.checkedAt)>Date.now()+120000; }
  function state(row) { return isStale() ? 'unknown' : row.state; }
  function runBadge(run) {
    if (!run) return badge('unknown','실행 기록 없음');
    if (active.has(run.status)) return badge('running',run.status==='in_progress'?'실행 중':'대기 중');
    const value = execution[run.conclusion] || ['unknown','확인 불가'];
    return badge(value[0],value[1]);
  }
  function safeLink(url, text) {
    if (!/^https:\/\/github\.com\/seirian\/isegye-idol-fansite\/actions\/runs\/[1-9][0-9]*\/attempts\/[1-9][0-9]*$/.test(url || '')) return node('span','원본 링크 없음','muted');
    const a = node('a',text,'external'); a.href=url; a.target='_blank'; a.rel='noopener noreferrer'; return a;
  }
  function health() {
    const el=$('health'); el.classList.toggle('warn',isStale());
    if (!data) { el.textContent=failed?'상태 조회에 실패했습니다. 정상 여부를 확인할 수 없습니다.':'모니터링 자료를 확인하고 있습니다.'; return; }
    const age=Math.max(0,Math.floor((Date.now()-Date.parse(data.checkedAt))/60000));
    el.textContent=(isStale()?'⚠ 최신 상태 확인 필요 · ':'● 마지막 자료 확인 · ')+date(data.checkedAt)+` · ${age}분 전`+(failed?' · 조회 실패, 이전 자료를 참고용으로 표시합니다.':isStale()?' · 45분 이상 지난 자료이거나 시각이 유효하지 않습니다. 정상으로 판정하지 않습니다.':' · 실행 기록과 게시 증거를 대조했습니다.');
  }
  function render() {
    health(); if (!data) return;
    $('total').textContent=data.batches.length+'개'; $('summary').replaceChildren();
    for (const key of ['healthy','running','attention','paused','unknown']) {
      const el=node('div',undefined,'metric'); el.dataset.state=key;
      el.append(node('span',labels[key],'label'),node('strong',data.batches.filter(r=>state(r)===key).length),node('small',key==='healthy'?'현재 회차 증거 기준':key==='unknown'?'오래된 자료·조회 실패 포함':'실행·반영을 함께 확인'));
      $('summary').append(el);
    }
    const total=node('div',undefined,'metric'); total.append(node('span','전체 모니터링','label'),node('strong',data.batches.length),node('small','수집 6 · 배포 1 · 복구 1')); $('summary').append(total);
    const priority={attention:0,unknown:1,running:2,healthy:3,paused:4};
    const rows=[...data.batches].sort((a,b)=>(priority[state(a)]??9)-(priority[state(b)]??9)).filter(r=>filter==='all'||(filter==='attention'?['attention','unknown'].includes(state(r)):state(r)==='running'));
    $('rows').replaceChildren();
    for (const row of rows) {
      const tr=node('tr'); const name=node('td'); name.append(node('strong',row.name),node('small',row.schedule));
      const run=node('td'); run.append(runBadge(row.run)); if(isStale())run.append(node('small','마지막 조회 당시 상태'));
      const pub=node('td'); pub.append(badge(isStale()?'unknown':row.dataState));
      if (row.historicalGapCount) pub.append(node('small',`과거 관측 공백 ${row.historicalGapCount}시간`));
      if (row.lastVerifiedAt) pub.append(node('small','재조회 '+date(row.lastVerifiedAt)));
      const due=node('td',row.dueAt?date(row.dueAt):'이벤트 기준'); due.append(node('small','다음 '+(row.nextDueAt?date(row.nextDueAt):'이벤트 발생 시')));
      const start=node('td',date(row.run?.jobStartedAt||row.run?.startedAt)); if(row.run)start.append(node('small',`#${row.run.id} · ${row.run.attempt}차 시도`));
      const duration=node('td',seconds(row.run?.durationSeconds)); duration.append(node('small','대기 '+seconds(row.run?.queueSeconds)));
      const action=node('td'); const button=node('button','상세 ↗','detail-btn'); button.type='button'; button.setAttribute('aria-label',row.name+' 상세'); button.addEventListener('click',()=>openDetail(row,button)); action.append(button);
      tr.append(name,run,pub,due,start,duration,action); $('rows').append(tr);
    }
    if(!rows.length){const tr=node('tr');const td=node('td','조건에 맞는 배치가 없습니다.','empty');td.colSpan=7;tr.append(td);$('rows').append(tr);}
    renderHeatmap(); renderObservations();
    $('meta').textContent=`자료 확인 ${date(data.checkedAt)} · main ${(data.mainCommit||'').slice(0,7)} · 인증된 운영자만 조회`;
  }
  function renderHeatmap() {
    const slots=data.batches.find(r=>r.key==='albums')?.chartSlots || [];
    const target=$('heatmap');target.replaceChildren();
    if(!slots.length){target.append(node('p','검증된 원본 관측 이력이 없습니다. 빈칸을 정상으로 추정하지 않습니다.','empty'));return;}
    const map=new Map();
    for(const item of slots){const local=new Date(Date.parse(item.at)+9*3600000);if(!Number.isFinite(local.getTime()))continue;const key=local.toISOString().slice(0,10);if(!map.has(key))map.set(key,new Map());map.get(key).set(local.getUTCHours(),item);}
    const grid=node('div',undefined,'heatmap');grid.append(node('span','KST','hour'));for(let hour=0;hour<24;hour++)grid.append(node('span',String(hour).padStart(2,'0'),'hour'));
    for(const [day,hours] of [...map.entries()].slice(-7)){
      grid.append(node('span',day.slice(5).replace('-','.'),'day'));
      for(let hour=0;hour<24;hour++){
        const item=hours.get(hour);const value=item?.state||'future';const text=`${day} ${String(hour).padStart(2,'0')}:00 · ${item?(labels[value]||'확인 불가'):'관측 범위 밖 또는 미도래'}`;
        const cell=node('button',undefined,'cell '+value);cell.type='button';cell.title=text;cell.setAttribute('aria-label',text);cell.addEventListener('click',()=>{$('heatmap').nextElementSibling.textContent=text+' · 마지막 자료 기준이며 현재 장애와 별도로 해석합니다.';});grid.append(cell);
      }
    }
    target.append(grid);
  }
  function renderObservations(){
    const target=$('observations');target.replaceChildren();const items=[...(data.observations||[])].sort((a,b)=>Date.parse(b.dueAt)-Date.parse(a.dueAt)).slice(0,80);
    if(!items.length){target.append(node('p','보관된 회차별 검증 기록이 없습니다.','empty'));return;}
    for(const item of items){const row=node('div',undefined,'observation');row.append(node('strong',data.batches.find(r=>r.key===item.batch)?.name||item.batch),node('span',date(item.dueAt)),badge(item.state),node('small','확인 '+date(item.checkedAt)));target.append(row);}
  }
  function openDetail(row,button){
    opener=button;$('detail-title').textContent=row.name;const body=$('detail-body');body.replaceChildren();
    body.append(node('p',row.note||'실행 결과와 현재 회차의 반영 증거를 확인합니다.','detail-note'));
    if(isStale())body.append(node('p','오래되었거나 재조회에 실패한 자료입니다. 아래는 마지막 확인 당시의 기록입니다.','detail-note'));
    const grid=node('dl',undefined,'detail-grid');
    const fields=[['예정 주기',row.schedule],['이번 회차',date(row.dueAt)],['다음 예정',date(row.nextDueAt)],['마지막 자료 확인',date(row.checkedAt)],['실행 생성',date(row.run?.createdAt)],['실제 작업 시작',date(row.run?.jobStartedAt)],['수집 결과 생성',date(row.evidence?.generatedAt)],['게시 시각',date(row.evidence?.publishedAt)],['서버 재조회',date(row.evidence?.readbackAt)],['명시적 재조회 검증',row.evidence?.verifiedReadback===true?'검증됨':row.evidence?.verifiedReadback===false?'실패':'증거 없음'],['전체 실행 이력 조회',row.listingComplete?'완료':'불완전 · 최신 여부 확정 불가'],['대기 / 실행 소요',seconds(row.run?.queueSeconds)+' / '+seconds(row.run?.durationSeconds)]];
    for(const [key,value] of fields){const div=node('div');div.append(node('dt',key),node('dd',value));grid.append(div);}body.append(grid);
    body.append(safeLink(row.run?.url,'GitHub 실행·원본 로그 열기 ↗'));
    if(row.evidenceRun && row.evidenceRun.id!==row.run?.id){body.append(node('p','데이터 반영의 근거는 별도 성공 실행입니다.','muted'),safeLink(row.evidenceRun.url,'게시 검증 근거 실행 ↗'));}
    body.append(node('h3','출처별 결과','subhead'));
    if(!row.sources?.length)body.append(node('p','이 배치에서 확인할 수 있는 출처별 보고서가 없습니다.','muted'));
    for(const source of row.sources||[]){const line=node('div',undefined,'source-row');line.append(node('span',source.name),badge(['complete','ok'].includes(source.state)?'healthy':'unknown',source.state),node('span',date(source.lastSuccessAt)));body.append(line);}
    body.append(node('h3','실행 단계','subhead'));
    if(!row.steps?.length)body.append(node('p','단계별 결과를 확인하지 못했습니다. 원본 실행 기록을 확인하세요.','muted'));
    for(const step of row.steps||[]){const line=node('div',undefined,'step');line.append(runBadge(step),node('span',step.name,'step-name'),node('span',date(step.completedAt),'muted'));body.append(line);}
    body.append(node('h3','최근 실행 이력 · 최대 30건','subhead'),node('p','실행 성공 표시만으로 게시 완료를 의미하지 않습니다.','muted'));
    for(const run of row.history||[]){const line=node('div',undefined,'step');line.append(runBadge(run),node('span',date(run.startedAt),'step-name'),safeLink(run.url,`#${run.id} · ${run.attempt}차`));body.append(line);}
    $('detail').showModal();$('close').focus();
  }
  function valid(value){return value?.schemaVersion===1&&value.readOnly===true&&Array.isArray(value.batches)&&value.batches.length===8&&Number.isFinite(Date.parse(value.checkedAt))&&value.staleAfterSeconds===2700&&value.batches.every(r=>typeof r.key==='string'&&typeof r.name==='string'&&labels[r.state]&&labels[r.dataState]);}
  async function load(){
    if(loading)return;loading=true;$('refresh').disabled=true;
    const controller=new AbortController();const timer=setTimeout(()=>controller.abort(),15000);
    try{const response=await fetch('/ops/batches/data.json',{credentials:'same-origin',cache:'no-store',signal:controller.signal});if(!response.ok)throw new Error('unavailable');const value=await response.json();if(!valid(value))throw new Error('invalid');data=value;failed=false;}
    catch{failed=true;}
    finally{clearTimeout(timer);loading=false;$('refresh').disabled=false;render();}
  }
  $('refresh').addEventListener('click',load);$('close').addEventListener('click',()=>$('detail').close());$('detail').addEventListener('close',()=>opener?.focus());
  document.querySelectorAll('[data-filter]').forEach(button=>button.addEventListener('click',()=>{filter=button.dataset.filter;document.querySelectorAll('[data-filter]').forEach(b=>{b.classList.toggle('selected',b===button);b.setAttribute('aria-pressed',String(b===button));});render();}));
  setInterval(()=>{if(!document.hidden){render();if($('auto').checked)load();}},60000);load();
})();
