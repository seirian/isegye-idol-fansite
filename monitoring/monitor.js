'use strict';
(() => {
  // Apply before first paint; a blocked storage backend never breaks the dashboard.
  const themeKey = 'isegye:monitor-theme:v1';
  const choices = new Set(['system','light','dark']);
  const systemTheme = window.matchMedia('(prefers-color-scheme: dark)');
  let theme = 'system';
  try { const stored = localStorage.getItem(themeKey); if (choices.has(stored)) theme = stored; } catch {}
  function applyTheme() {
    document.documentElement.dataset.theme = theme === 'system' ? (systemTheme.matches ? 'dark' : 'light') : theme;
    const select = document.getElementById('theme'); if (select) select.value = theme;
  }
  applyTheme();
  systemTheme.addEventListener('change', applyTheme);
  window.addEventListener('storage', event => {
    if (event.key === themeKey || event.key === null) { theme = choices.has(event.newValue) ? event.newValue : 'system'; applyTheme(); }
  });
  function start() {
  const $ = id => document.getElementById(id);
  const labels = {healthy:'정상', attention:'확인 필요', running:'진행 중', paused:'예정·수동 중지', unknown:'확인 불가', missing:'관측 공백', partial:'일부 관측'};
  const execution = {success:['healthy','성공'], failure:['attention','실패'], timed_out:['attention','시간 초과'], cancelled:['unknown','취소'], skipped:['paused','건너뜀'], action_required:['attention','조치 필요'], neutral:['unknown','중립']};
  const active = new Set(['in_progress','queued','pending','waiting','requested']);
  let data = null, filter = 'all', failed = false, loading = false, opener = null, leaving = false;
  const date = value => {
    if (!value || !Number.isFinite(Date.parse(value))) return '확인되지 않음';
    return new Intl.DateTimeFormat('ko-KR',{timeZone:'Asia/Seoul',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).format(new Date(value));
  };
  const seconds = value => Number.isFinite(value) ? (value < 60 ? `${value}초` : `${Math.floor(value/60)}분 ${value%60}초`) : '—';
  function node(tag, text, cls) { const e = document.createElement(tag); if (text !== undefined) e.textContent = String(text); if (cls) e.className = cls; return e; }
  function badge(state, text) { return node('span', text || labels[state] || labels.unknown, 'badge '+(labels[state] ? state : 'unknown')); }
  function isStale() { return !data || failed || Date.now()-Date.parse(data.checkedAt) > data.staleAfterSeconds*1000 || Date.parse(data.checkedAt)>Date.now()+120000; }
  function rowExpired(row) {
    // A fresh snapshot of the previous slot is not evidence for a new slot.
    return isStale() || (!!row.nextDueAt && Date.now() >= Date.parse(row.nextDueAt)+(row.key==='watchdog'?300000:0));
  }
  function freshness(row) {
    if (failed) return ['attention','상태 조회 실패'];
    if (isStale()) return ['attention','최신 점검 지연'];
    if (row.inspectionError) return ['attention',reason(row.inspectionError)];
    if (rowExpired(row)) return ['running','새 회차 확인 대기'];
    if (row.dataState === 'unknown') return ['unknown','게시 증거 미확인'];
    return ['healthy','자료 기준 회차 확인'];
  }
  function reason(code) {
    return ({execution_query_failed:'실행 이력 조회 실패',incomplete_execution_history:'실행 이력 조회 불완전',
      publication_evidence_missing:'게시 증거 없음',publication_evidence_failed:'게시 증거 조회·검증 실패',
      catalog_evidence_failed:'콘텐츠 게시 증거 미확인',main_identity_query_failed:'운영 커밋 조회 실패'})[code] || '점검 실패';
  }
  function resultLabel(row) {
    if (row.dataState === 'healthy') return row.key === 'watchdog' ? '마지막 점검 정상' : row.key === 'capture' ? '현재 회차 관측 검증' : '마지막 반영 완료';
    if(row.key==='capture')return ({attention:'관측 확인 필요',running:'관측 진행 중',paused:'예정·수동 중지',unknown:'관측 증거 미확인'})[row.dataState]||'관측 증거 미확인';
    return ({attention:'반영 확인 필요',running:'반영 확인 진행 중',paused:'예정·수동 중지',unknown:'반영 증거 미확인'})[row.dataState] || '반영 증거 미확인';
  }
  function state(row) { return rowExpired(row) || row.inspectionError ? 'unknown' : row.state; }
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
    const el=$('health'); const quality=data?.collectorHealth;
    const delayed=isStale(), error=quality?.state==='failed', partial=quality?.state==='degraded';
    el.classList.toggle('warn',delayed||error||partial);
    if (!data) { el.textContent=failed?'모니터링 상태 조회 실패 · 배치 장애 여부와 구분해 확인해 주세요.':'모니터링 자료를 확인하고 있습니다.'; return; }
    const age=Math.max(0,Math.floor((Date.now()-Date.parse(data.checkedAt))/60000));
    const title=failed?'모니터링 상태 조회 실패':delayed?'모니터링 갱신 지연':error?'모니터링 점검 실패':partial?'모니터링 일부 점검 미완료':'모니터링 자료 수집 완료';
    el.textContent=(delayed||error||partial?'⚠ ':'● ')+title+' · 마지막 수집 '+date(data.checkedAt)+` · ${age}분 전`+
      (failed?' · 조회 실패, 마지막 검증 결과는 참고용으로 유지합니다.':delayed?' · 배치 전체의 반영 실패를 뜻하지 않습니다. 마지막 검증 결과와 최신 확인 상태를 분리해 표시합니다.':error||partial?' · 확인한 배치 결과와 조회 실패 항목을 구분합니다.':' · 새 회차 대기 여부는 각 항목에서 확인해 주세요.');
    const info=$('inspection-info');
    if (info) info.textContent=(quality?`실행 이력 확인 ${quality.inspected}/${quality.total} · 조회 실패 ${quality.failed} · 반영 증거 미확인 ${quality.unresolved}`:'이전 형식 자료 · 점검 통계 미제공')+' · 마지막 전체 점검 완료 '+date(data.lastCompleteInspectionAt);
  }
  function render() {
    health();
    if (!data) {
      if(failed){$('rows').replaceChildren();const tr=node('tr');const td=node('td','자료 조회에 실패했습니다. 로그인 상태와 접근 권한을 확인한 뒤 다시 읽어 주세요.','empty');td.colSpan=7;tr.append(td);$('rows').append(tr);}
      return;
    }
    $('total').textContent=data.batches.length+'개'; $('summary').replaceChildren();
    for (const key of ['healthy','running','attention','paused','unknown']) {
      const el=node('div',undefined,'metric'); el.dataset.state=key;
      el.append(node('span',labels[key],'label'),node('strong',data.batches.filter(r=>state(r)===key).length),node('small',key==='healthy'?'자료 기준 회차 검증 완료':key==='unknown'?'점검 지연·증거 미확인':'실행·반영을 함께 확인'));
      $('summary').append(el);
    }
    const total=node('div',undefined,'metric'); total.append(node('span','전체 모니터링','label'),node('strong',data.batches.length),node('small','수집 6 · 독립 관측 1 · 배포 1 · 복구 1')); $('summary').append(total);
    const priority={attention:0,unknown:1,running:2,healthy:3,paused:4};
    const rows=[...data.batches].sort((a,b)=>(priority[state(a)]??9)-(priority[state(b)]??9)).filter(r=>filter==='all'||(filter==='attention'?['attention','unknown'].includes(state(r)):state(r)==='running'));
    $('rows').replaceChildren();
    for (const row of rows) {
      const tr=node('tr'); tr.setAttribute('role','row'); const name=node('td'); name.append(node('strong',row.name),node('small',row.schedule));
      const run=node('td'); run.append(runBadge(row.run)); if(rowExpired(row))run.append(node('small','마지막 조회 당시 상태'));
      const pub=node('td');
      const expired=rowExpired(row);
      pub.append(badge(expired?'unknown':row.dataState,resultLabel(row)));
      const [checkState,checkText]=freshness(row);pub.append(node('small',checkText,'freshness '+checkState));
      const last=row.lastVerifiedResult;
      if(last) pub.append(node('small',(last.kind==='inspection'?'정상 점검 확인 ':last.kind==='observation'?'정상 관측 확인 ':'정상 반영 확인 ')+date(last.observedAt),'last-verified'));
      else if(row.dataState==='healthy') pub.append(node('small','검증 확인 '+date(row.checkedAt),'last-verified'));
      else pub.append(node('small','보관된 정상 검증 기록 없음','last-verified'));
      if (row.historicalGapCount) pub.append(node('small',`과거 관측 공백 ${row.historicalGapCount}시간`));
      if (row.lastVerifiedAt) pub.append(node('small',(row.key==='capture'?'관측 확인 ':'재조회 ')+date(row.lastVerifiedAt)));
      if(row.slotSummary){const s=row.slotSummary;pub.append(node('small',`오늘 예정 ${s.expected} · 검증 ${s.verified} · 미확인 ${s.unverified+s.awaiting+s.running}`));}
      const due=node('td',row.dueAt?date(row.dueAt):'이벤트 기준'); due.append(node('small','다음 '+(row.nextDueAt?date(row.nextDueAt):'이벤트 발생 시')));
      const start=node('td',date(row.run?.jobStartedAt||row.run?.startedAt)); if(row.run)start.append(node('small',`#${row.run.id} · ${row.run.attempt}차 시도`));
      const duration=node('td',seconds(row.run?.durationSeconds)); duration.append(node('small','대기 '+seconds(row.run?.queueSeconds)));
      const action=node('td'); const button=node('button','상세 ↗','detail-btn'); button.type='button'; button.setAttribute('aria-label',row.name+' 상세'); button.addEventListener('click',()=>openDetail(row,button)); action.append(button);
      [name,run,pub,due,start,duration,action].forEach((cell,i)=>{cell.dataset.label=['배치 / 예정 주기','실행 상태','데이터 반영','이번 회차 / 다음 예정','확인한 실행 시작','소요 / 대기','상세'][i];cell.setAttribute('role','cell');});
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
    if(rowExpired(row))body.append(node('p','최신 점검이 지연되었거나 새 회차를 기다리고 있습니다. 아래는 마지막 확인 당시의 기록이며 현재 회차 정상 판정이 아닙니다.','detail-note'));
    const [freshState,freshText]=freshness(row);body.append(badge(freshState,freshText));
    const last=row.lastVerifiedResult;
    if(last){body.append(node('h3','마지막으로 검증된 정상 결과','subhead'),node('p','확인 '+date(last.observedAt)+' · 대상 회차 '+date(last.dueAt)+' · 현재 점검 결과와 별도로 보관합니다.','detail-note'));if(last.runId&&last.attempt)body.append(safeLink(`https://github.com/seirian/isegye-idol-fansite/actions/runs/${last.runId}/attempts/${last.attempt}`,'마지막 정상 검증 근거 ↗'));}
    const grid=node('dl',undefined,'detail-grid');
    const fields=[['예정 주기',row.schedule],['자료 기준 회차',date(row.dueAt)],['다음 예정',date(row.nextDueAt)],['마지막 자료 확인',date(row.checkedAt)],['실행 생성',date(row.run?.createdAt)],['실제 작업 시작',date(row.run?.jobStartedAt)],['수집 결과 생성',date(row.evidence?.generatedAt)],['게시 시각',date(row.evidence?.publishedAt)],['서버 재조회',date(row.evidence?.readbackAt)],['명시적 재조회 검증',row.evidence?.verifiedReadback===true?'검증됨':row.evidence?.verifiedReadback===false?'실패':'증거 없음'],['전체 실행 이력 조회',row.listingComplete?'완료':'불완전 · 최신 여부 확정 불가'],['대기 / 실행 소요',seconds(row.run?.queueSeconds)+' / '+seconds(row.run?.durationSeconds)]];
    for(const [key,value] of fields){const div=node('div');div.append(node('dt',key),node('dd',value));grid.append(div);}body.append(grid);
    body.append(safeLink(row.run?.url,'GitHub 실행·원본 로그 열기 ↗'));
    if(row.slotSummary){const s=row.slotSummary;body.append(node('h3','오늘 필수 회차 원장','subhead'),node('p',`예정 ${s.expected}회 · 검증 ${s.verified}회 · 실패 ${s.failed}회 · 취소 ${s.cancelled}회 · 부분 ${s.partial}회 · 복구 ${s.recovered}회 · 미확인 ${s.unverified+s.awaiting+s.running}회`,'muted'),node('p','예정됐으나 증거를 확인하지 못한 회차도 포함합니다. 원장 적용 전 과거 성과를 성공·실패로 추정하지 않습니다.','muted'));}
    if(row.growth){
      const g=row.growth;body.append(node('h3','문제은행 증설 상태','subhead'));
      body.append(node('p',`마지막 신규 추가: ${date(g.lastAdditionAt)} · 오늘 ${g.todayAdded??'—'}문제 · 일일 목표 ${g.dailyTarget??'—'}문제 · 검수 대기 ${g.readyCount??'—'}문제 · 대기분 약 ${g.reserveDays??'—'}일`,'muted'));
      const notices={stalled:'3일 이상 신규 문제 추가 없음',reserve_exhausted:'검수 완료 대기 문제 소진',reserve_low:'검수 완료 대기분이 7일 미만',capacity_reached:'전체 문제은행 상한 도달'};
      for(const code of g.alerts||[])body.append(node('p',notices[code]||'문제 확보 상태 확인 필요','warning'));
      const names={inputRows:'입력 자료',unsupportedChannel:'공식 개인 채널 아님',unsupportedFact:'출제 범위 제외',duplicateInput:'입력 중복',eligibleRows:'공식 출제 후보',alreadyUsed:'기출 자료',unusedOfficial:'미사용 공식 자료',verified:'원본 검증 통과',deferred:'원본 확인 보류',reserveUsedOrDuplicate:'대기열 기출·중복 제외'};
      for(const [key,label] of Object.entries(names)){const value=g.candidateCounts?.[key];if(Number.isInteger(value)&&value>=0)body.append(node('p',`${label}: ${value}건`,'muted'));}
    }
    if(row.publicationLineage?.viaReference){const p=row.publicationLineage;body.append(node('p',`현재 ${p.executionAttempt}차 실행은 ${p.sourcePrepareAttempt}차 준비 후보의 ${p.sourceAttempt}차 운영 배포 증거를 명시적으로 참조합니다. 원본 게시·재조회 시각을 유지합니다.`,'muted'));}
    if(row.evidenceRun && (row.evidenceRun.id!==row.run?.id || row.evidenceRun.attempt!==row.run?.attempt)){body.append(node('p','자료 반영은 아래 실행의 게시 검증 증거를 사용합니다.','muted'),safeLink(row.evidenceRun.url,'게시 검증 근거 실행 ↗'));}
    if(row.sourceTimes){body.append(node('h3','원본 차트 기준 시각','subhead'));for(const [key,value] of Object.entries(row.sourceTimes)){const line=node('div',undefined,'source-row');line.append(node('span',key),node('span',date(value)));body.append(line);}}
    if(row.counts&&Object.keys(row.counts).length){body.append(node('h3','실제 처리·보유 건수','subhead'));const names={questionCount:'문제 수',added:'추가',updated:'수정',collectedCount:'수집',channelCount:'채널 수',videoCount:'영상 수',todayAdded:'오늘 신규 문제',readyCount:'검수 완료 대기 문제',consecutiveZeroDays:'연속 추가 0일 수',chartsComplete:'검증한 차트',requiredCharts:'필수 차트'};for(const [key,value] of Object.entries(row.counts)){const line=node('div',undefined,'source-row');line.append(node('span',names[key]||key),node('span',value+(key==='consecutiveZeroDays'?'일':'건')));body.append(line);}}
    if(row.recoveryStates?.length){body.append(node('h3','복구 제어기 판단','subhead'));const reasons={healthy:'검증 완료',active:'실행·대기 중',cooldown:'재요청 대기 제한',grace:'회차 유예 중',dispatch:'복구 필요',dispatched:'복구 요청됨',retry_budget:'보충 횟수 제한',paused:'수동 중지',night_pause:'새벽 중지',not_due:'예정 전',slot_changed:'회차 변경',inspection_failed:'점검 실패',blocked_permanent:'같은 영구 오류 반복 · 해결 증거 필요',blocked_dependency:'의존 작업 해결 대기',request_unknown:'요청 결과 미확인 · 재요청 금지'};for(const item of row.recoveryStates){const line=node('div',undefined,'source-row');line.append(node('span',data.batches.find(r=>r.key===item.batch)?.name||item.batch),node('span',reasons[item.state]||'확인 불가'));body.append(line);}}
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
  function valid(value){return value?.schemaVersion===1&&value.readOnly===true&&Array.isArray(value.batches)&&value.batches.length===9&&new Set(value.batches.map(r=>r.key)).size===9&&value.batches.every(r=>['albums','music','schedule','catalog','playground','history','production','watchdog','capture'].includes(r.key))&&Number.isFinite(Date.parse(value.checkedAt))&&value.staleAfterSeconds===2700&&value.batches.every(r=>typeof r.key==='string'&&typeof r.name==='string'&&labels[r.state]&&labels[r.dataState]);}
  async function load(){
    if(loading)return;loading=true;$('refresh').disabled=true;
    const controller=new AbortController();const timer=setTimeout(()=>controller.abort(),15000);
    try{const response=await fetch('/ops/batches/data.json',{credentials:'same-origin',cache:'no-store',signal:controller.signal});if([401,403].includes(response.status)){leaving=true;data=null;document.body.replaceChildren(node('p','관리자 계정만 해당 사이트에 접근이 가능합니다.'));window.location.replace('/auth/login?notice=batch-admin');return;}if(!response.ok)throw new Error('unavailable');const value=await response.json();if(!valid(value))throw new Error('invalid');data=value;failed=false;}
    catch{failed=true;}
    finally{clearTimeout(timer);loading=false;if(!leaving){$('refresh').disabled=false;render();}}
  }
  $('theme').value = theme;
  $('theme').addEventListener('change', event => {
    theme = choices.has(event.target.value) ? event.target.value : 'system'; applyTheme();
    try { localStorage.setItem(themeKey, theme); } catch {}
  });
  $('refresh').addEventListener('click',load);$('close').addEventListener('click',()=>$('detail').close());$('detail').addEventListener('close',()=>opener?.focus());
  document.querySelectorAll('[data-filter]').forEach(button=>button.addEventListener('click',()=>{filter=button.dataset.filter;document.querySelectorAll('[data-filter]').forEach(b=>{b.classList.toggle('selected',b===button);b.setAttribute('aria-pressed',String(b===button));});render();}));
  setInterval(()=>{if(!leaving&&!document.hidden){render();if($('auto').checked)load();}},60000);load();
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, {once:true});
  else start();
})();
