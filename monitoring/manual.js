'use strict';
(() => {
  const batches = {
    albums:['음반 · 멜론 차트','albums-daily.yml'], music:['음악 영상','music-daily.yml'],
    schedule:['공지 · 일정','schedule-refresh.yml'], catalog:['콘텐츠 목록','video-catalog.yml'],
    playground:['놀이터 문제은행','playground-daily.yml'], history:['활동기록','history-monthly.yml'],
    production:['운영 배포','production.yml'], watchdog:['배치 복구 점검','batch-watchdog.yml']
  };
  const active = new Set(['queued','checking','dispatching','accepted','unknown','running']);
  const states = {queued:'요청 접수 · 실행 대기',checking:'실행 조건 확인 중',dispatching:'GitHub 실행 요청 중',accepted:'GitHub 실행 접수',running:'실행 중',unknown:'실행 접수 여부 미확인',blocked:'실행 요청 차단',expired:'요청 만료 · 실행하지 않음',cancelled:'요청 취소',resolved:'미확인 요청 수동 해제',completed:'실행 종료'};
  const reasons = {awaiting_worker:'실행 처리기가 요청을 확인한 뒤 실행합니다.',paused:'중지 설정이 적용돼 있습니다.',night_pause:'음반 수집은 01:00~06:59에 중지됩니다.',existing_run:'동일 배치가 이미 실행 또는 대기 중입니다.',cooldown:'최근 요청 후 15분 대기 제한입니다.',hourly_limit:'배치별 시간당 수동·복구 요청 2회 제한입니다.',inspection_failed:'실행 조건을 확인하지 못해 안전하게 차단했습니다.',dispatch_unconfirmed:'재전송하지 않았습니다. GitHub에서 실행 여부를 확인해 주세요.',worker_interrupted:'처리기가 중단됐습니다. GitHub에서 실행 여부를 확인해 주세요.',administrator_revoked:'요청자의 관리자 권한이 해제됐습니다.',authorization_or_expiry:'관리자 권한 또는 요청 유효기간을 확인할 수 없습니다.',queue_expired:'접수 후 20분이 지나 실행하지 않았습니다.',request_already_active:'해당 배치에 처리 중인 요청이 있습니다.',id_conflict:'요청 식별자가 일치하지 않습니다.',request_not_cancellable:'이미 실행 처리에 들어간 요청은 취소할 수 없습니다.',manual_control_unavailable:'수동 실행 서비스를 확인할 수 없습니다.',request_authenticity_rejected:'로그인 상태가 변경됐습니다. 화면을 새로고침해 주세요.',queue_capacity:'요청 보관 한도에 도달했습니다.'};
  function start() {
    const $=id=>document.getElementById(id);
    let control=null, busy=false, intent=null, opener=null, fetching=false;
    function node(tag,text,cls){const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;}
    const format=value=>new Intl.DateTimeFormat('ko-KR',{timeZone:'Asia/Seoul',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).format(new Date(value*1000));
    const dialog=node('dialog',undefined,'manual-dialog');dialog.id='manual-dialog';dialog.setAttribute('aria-labelledby','manual-title');
    const head=node('div',undefined,'dialog-head');const title=node('h2','수동 실행 확인');title.id='manual-title';
    const close=node('button','✕');close.type='button';close.setAttribute('aria-label','수동 실행 확인 닫기');head.append(title,close);
    const description=node('p',undefined,'detail-note');const warning=node('p',undefined,'manual-warning');
    const label=node('label',undefined,'manual-consent');const checkbox=node('input');checkbox.type='checkbox';
    const consent=node('span','안내와 실행 범위를 확인했습니다.');label.append(checkbox,consent);
    const status=node('p',undefined,'manual-result');status.setAttribute('role','status');status.setAttribute('aria-live','polite');
    const actions=node('div',undefined,'manual-dialog-actions');const cancel=node('button','돌아가기');cancel.type='button';
    const submit=node('button','실행 요청');submit.type='button';submit.disabled=true;submit.className='manual-primary';actions.append(cancel,submit);
    const github=node('a','GitHub 실행 목록 열기 ↗','external');github.target='_blank';github.rel='noopener noreferrer';
    dialog.append(head,description,warning,label,status,actions,github);document.body.append(dialog);
    function leave(){control=null;dialog.close();for(const id of ['rows','summary','observations','heatmap','detail-body'])$(id)?.replaceChildren();location.replace('/auth/login?notice=batch-admin');}
    async function request(payload){
      const abort=new AbortController();const timer=setTimeout(()=>abort.abort(),12000);
      try {
        const options={credentials:'same-origin',cache:'no-store',signal:abort.signal,headers:{Accept:'application/json'}};
        if(payload){options.method='POST';options.headers['Content-Type']='application/json';options.headers['X-CSRF-Token']=control.csrf;options.body=JSON.stringify(payload);}
        const response=await fetch('/ops/batches/control',options);
        if(response.status===401||response.status===403){leave();throw new Error('로그인이 필요합니다.');}
        const value=await response.json();if(!response.ok)throw new Error(reasons[value.error]||'요청을 처리하지 못했습니다. 다시 확인해 주세요.');return value;
      } finally {clearTimeout(timer);}
    }
    function latest(batch){return control?.requests?.filter(r=>r.batch===batch).sort((a,b)=>b.at-a.at)[0];}
    function show(batch,action='enqueue',record=null,button=null){
      if(!control||busy)return;
      intent={action,batch,id:record?.id||crypto.randomUUID().replaceAll('-',''),confirm:batch};opener=button;
      title.textContent=action==='enqueue'?batches[batch][0]+' 수동 실행':action==='cancel'?'대기 요청 취소':'미확인 요청 해제';
      description.textContent=action==='enqueue'?'main 브랜치의 해당 배치만 실행 요청합니다. 접수와 실행·완료는 서로 다르며, 작업 결과는 기존 검증 절차로 확인합니다.':action==='cancel'?'아직 처리기가 가져가지 않은 대기 요청만 취소할 수 있습니다. 이미 시작된 GitHub 실행은 취소하지 않습니다.':'GitHub에서 기존 실행 여부를 직접 확인한 뒤 해제해 주세요. 해제는 새 실행을 요청하거나 기존 실행을 취소하지 않습니다.';
      warning.textContent=action==='resolve'?'결과를 확인하지 않고 다시 요청하면 작업이 중복될 수 있습니다.':batch==='production'?'주의: 운영 팬사이트 전체를 현재 main으로 다시 배포합니다.':batch==='watchdog'?'주의: 복구 점검 결과에 따라 기존 정책이 허용하는 다른 배치도 실행될 수 있습니다.':batch==='playground'?'일일 추가 한도와 기존 수집·게시 검증을 유지합니다.':'중지 설정, 중복 실행, 새벽 중지 및 요청 제한을 우회하지 않습니다.';
      checkbox.checked=false;submit.disabled=true;status.textContent='';submit.textContent=action==='enqueue'?'실행 요청':action==='cancel'?'대기 요청 취소':'확인 후 해제';
      github.href='https://github.com/seirian/isegye-idol-fansite/actions/workflows/'+batches[batch][1];dialog.showModal();checkbox.focus();
    }
    function decorate(){
      for(const tr of $('rows').querySelectorAll('tr')){
        const batch=Object.keys(batches).find(key=>batches[key][0]===tr.querySelector('td strong')?.textContent);if(!batch)continue;tr.dataset.batch=batch;const cell=tr.lastElementChild;
        cell.querySelector('.manual-controls')?.remove();const box=node('div',undefined,'manual-controls');const record=latest(batch);
        const button=node('button','▶ 수동 실행','manual-button');button.type='button';button.setAttribute('aria-label',batches[batch][0]+' 수동 실행');
        button.disabled=!control||busy||!!(record&&active.has(record.state));button.addEventListener('click',()=>show(batch,'enqueue',null,button));box.append(button);
        if(record){
          const state=node('small',(states[record.state]||'요청 상태 확인 중')+(record.conclusion?' · '+({success:'성공',failure:'실패',cancelled:'취소',timed_out:'시간 초과',skipped:'건너뜀'}[record.conclusion]||record.conclusion):''),'manual-state');state.title=(reasons[record.reason]||'')+' · 접수 '+format(record.at);box.append(state);
          if(record.reason&&reasons[record.reason]&&record.state!=='queued')box.append(node('small',reasons[record.reason],'manual-reason'));
          if(Number.isSafeInteger(record.runId)&&record.runId>0){const a=node('a','실행 #'+record.runId+' ↗','external');a.href='https://github.com/seirian/isegye-idol-fansite/actions/runs/'+record.runId;a.target='_blank';a.rel='noopener noreferrer';box.append(a);}
          if(['queued','unknown'].includes(record.state)){const b=node('button',record.state==='queued'?'요청 취소':'실행 확인 후 해제','manual-secondary');b.type='button';b.disabled=busy;b.addEventListener('click',()=>show(batch,record.state==='queued'?'cancel':'resolve',record,b));box.append(b);}
        }
        cell.append(box);
      }
    }
    async function load(){
      if(fetching)return;fetching=true;
      try{control=await request();const age=control.heartbeat?Math.max(0,Math.floor((control.serverTime-control.heartbeat)/60)):null;
        $('manual-health').textContent='수동 실행은 관리자 확인 후 접수됩니다. 실행 처리기는 5분 간격으로 예약되며 GitHub 지연이 있을 수 있습니다. '+(age===null?'아직 실행 처리기 확인 기록이 없습니다.':`처리기 마지막 확인: ${format(control.heartbeat)} (${age}분 전).`)+(age===null||age>15?' 갱신 지연 시 요청은 대기하며 20분 후 만료됩니다.':'');
      }catch(error){$('manual-health').textContent='수동 실행 상태 조회 실패 · '+error.message;control=null;}
      finally{fetching=false;decorate();}
    }
    const dismiss=()=>{if(!busy){dialog.close();opener?.focus();}};close.addEventListener('click',dismiss);cancel.addEventListener('click',dismiss);
    dialog.addEventListener('cancel',event=>{if(busy)event.preventDefault();});checkbox.addEventListener('change',()=>{submit.disabled=!checkbox.checked||busy;});
    submit.addEventListener('click',async()=>{
      if(!checkbox.checked||busy||!intent||!control)return;busy=true;submit.disabled=true;close.disabled=true;cancel.disabled=true;checkbox.disabled=true;decorate();
      try{const result=await request(intent);status.textContent=result.request?.state==='queued'?'요청을 접수했습니다. 아직 배치가 실행된 것은 아닙니다. 목록에서 진행 상태를 확인해 주세요.':'요청 상태를 변경했습니다.';}
      catch(error){status.textContent=error.message+' 접수 여부가 불확실하면 목록을 먼저 확인해 주세요. 자동으로 다시 요청하지 않습니다.';}
      finally{busy=false;close.disabled=false;cancel.disabled=false;checkbox.disabled=false;checkbox.checked=false;await load();}
    });
    new MutationObserver(decorate).observe($('rows'),{childList:true});$('refresh').addEventListener('click',load);
    decorate();load();setInterval(()=>{if(!document.hidden&&!busy)load();},30000);
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start,{once:true});else start();
})();
