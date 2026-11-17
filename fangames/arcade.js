/* Six distinct original controls × two rounds. No borrowed mini-game assets. */
(()=>{
let run=null,stage=null,timer=null,nextTimer=null,closed=false;
const names=['방송 장비 구출','마지막 한 획','박쥐단 집합','주폭도 신호','세균단 출동','챠니의 한 칼'];
const desc=[
 '아이네의 EMP가 오기 전에 번쩍이는 장치를 모두 눌러 안전하게 만드세요.',
 '징버거의 그림이 완성되도록 표시된 점들을 번호 순서대로 이어보세요.',
 '릴파의 박쥐단이 다가옵니다. 같은 줄에 서서 모으기를 세 번 성공하세요.',
 '주르르가 보내는 방향 신호를 보고 왼쪽·오른쪽 버튼을 그대로 누르세요.',
 '고세구의 세균단에게 번호대로 자리를 지정하세요. 순서가 중요합니다.',
 '비챤의 타이밍! 움직이는 빛이 중앙 초록 칸에 왔을 때 베기를 누르세요.'
];
function mount(){
 closed=false;run=null;stage=null;
 F.app.innerHTML='<div class="game-top"><div><span class="eyebrow">01 · QUICK-RESPONSE FAN ARCADE</span><h2>우당탕 이세돌</h2><p>여섯 멤버, 여섯 가지 조작. 서로 다른 상황을 6초 안에 해결해 보세요.</p></div>'+F.metrics([['최고 점수',F.state.bestArcade],['게임 유형','6개'],['전체 미션','12개']])+'</div>'+
 '<div class="panel alt"><h3>한 판은 이렇게 진행돼요</h3><p class="subtle">멤버별 장면은 모두 비공식 각색이며 실제 방송·능력이 아닙니다. 각 미션마다 짧은 준비 설명과 6초 도전이 주어집니다.</p><div class="member-row">'+F.MEMBERS.map(m=>'<div class="member">'+F.memberCard(m)+'<span class="label">'+m.name+'</span><small>'+names[F.MEMBERS.indexOf(m)]+'</small></div>').join('')+'</div><div class="buttons">'+F.btn('12개 미션 이어달리기 →','full','primary')+F.btn('6개 미션 연습 →','practice')+'</div></div>'+
 '<div id="arcade-field"></div><div class="caution">조작은 마우스·터치·키보드로 가능합니다. 타이밍 미션은 스페이스키를 사용할 수 있고, 게임 도중 언제든 일시정지할 수 있습니다.</div>';
 const h=e=>{const el=e.target.closest('[data-action],[data-tile],[data-pad]');if(!el)return;
  const a=el.dataset.action;if(a==='full'||a==='practice')begin(a==='full'?12:6);
  if(a==='pause')pauseToggle();
  if(a==='exit'){if(confirm('도전을 종료하고 게임 선택 화면으로 돌아갈까요?')){clear();mount()}}
  if(a==='next'&&run?.ended)advance();
  if(el.dataset.tile!=null)interact(Number(el.dataset.tile));
  if(el.dataset.pad)pad(el.dataset.pad);
 };
 F.app.addEventListener('click',h);F.onCleanup(()=>{closed=true;clear();F.app.removeEventListener('click',h)});
}
function clear(){clearInterval(timer);clearTimeout(nextTimer);timer=null;nextTimer=null}
function begin(total){clear();run={idx:-1,total,score:0,success:0,ended:false,paused:false};advance()}
function advance(){
 clear();if(!run)return;run.ended=false;run.paused=false;run.idx++;
 if(run.idx>=run.total){finish();return}
 const kind=run.idx%6,hard=run.idx>=6;
 stage={kind,hard,seconds:6,deadline:0,done:false,hits:0,moves:0,needed:hard?4:3,lane:1,target:hard?0:2,cursor:0,
  sequence:kind===3?(hard?['L','R','R','L','R']:['R','L','R','L']):[],
  ordered:kind===1?(hard?[10,11,7,3,2]:[12,13,9,5]):kind===4?(hard?[4,8,7,11,15]:[1,5,9,13]):[],
  flashes:(hard?[1,4,6,11]:[2,5,7])};
 draw();
 const start=()=>{if(closed||!run||run.ended)return;stage.deadline=Date.now()+6000;timer=setInterval(tick,60)};
 nextTimer=setTimeout(start,750);
}
function draw(){
 if(!run||!stage)return;
 const m=F.MEMBERS[stage.kind],out=F.app.querySelector('#arcade-field');if(!out)return;
 const n=run.idx+1,rem=stage.deadline?Math.max(0,(stage.deadline-Date.now())/1000):6;
 out.innerHTML='<div class="panel"><div class="levelbar"><span><b style="color:'+m.color+'">'+m.name+'</b> · 미션 '+n+'/'+run.total+(stage.hard?' <span class="tag">LEVEL 2</span>':'')+'</span><div class="buttons"><span class="subtle" id="time-label">'+rem.toFixed(1)+'초</span>'+F.btn(run.paused?'계속하기':'일시정지','pause','ghost')+F.btn('나가기','exit','ghost')+'</div></div><div class="timer-track"><span id="time-progress" style="width:'+(rem/6*100)+'%"></span></div><section class="stage-card" aria-live="polite"><div class="mini-avatar" style="--avatar:'+m.color+';margin:0 auto">'+m.short+'</div><h3>'+names[stage.kind]+'</h3><p>'+desc[stage.kind]+'</p><div id="stage-input">'+stageHTML()+'</div><div class="game-status" id="stage-note">준비! 조작 방법을 확인하세요.</div></section></div>';
}
function stageHTML(){
 const k=stage.kind;
 if(k===0)return '<div class="stage-grid cols4">'+Array.from({length:12},(_,i)=>'<button type="button" class="tile '+(stage.flashes.includes(i)?'bad':'')+'" data-tile="'+i+'" aria-label="장비 '+(i+1)+'">'+(stage.flashes.includes(i)?'⚡':'▣')+'</button>').join('')+'</div><span class="subtle">고장 난 장비 '+stage.flashes.length+'개를 찾아 끄세요.</span>';
 if(k===1)return '<div class="stage-grid cols4">'+Array.from({length:16},(_,i)=>{const t=stage.ordered.indexOf(i);return '<button type="button" class="tile '+(t<stage.hits?'good':t===stage.hits?'target':'')+'" data-tile="'+i+'">'+(t>=0?t+1:'·')+'</button>'}).join('')+'</div><span class="subtle">'+(stage.hits+1)+'번 점을 선택할 차례</span>';
 if(k===2)return '<div class="stage-grid cols3">'+[0,1,2].map(i=>'<div class="tile '+(stage.target===i?'target':'')+'">'+(stage.target===i?'🦇':'·')+(stage.lane===i?'<span>릴파 위치</span>':'')+'</div>').join('')+'</div><div class="action-pads"><button class="pad" data-pad="L">←</button><button class="pad" data-pad="C">모으기</button><button class="pad" data-pad="R">→</button></div><span class="subtle">성공 '+stage.hits+'/3</span>';
 if(k===3)return '<div class="moving-target" style="display:grid;place-items:center;font-size:32px">'+(stage.sequence[stage.hits]==='L'?'← 왼쪽':'오른쪽 →')+'</div><div class="action-pads"><button class="pad" data-pad="L">←</button><button class="pad" data-pad="R">→</button></div><span class="subtle">신호 '+stage.hits+'/'+stage.sequence.length+'</span>';
 if(k===4)return '<div class="stage-grid cols4">'+Array.from({length:16},(_,i)=>{let t=stage.ordered.indexOf(i);return '<button type="button" class="tile '+(t<stage.hits?'good':t===stage.hits?'target':'')+'" data-tile="'+i+'">'+(t>=0?'✦'+(t+1):'◦')+'</button>'}).join('')+'</div><span class="subtle">다음 번호: '+(stage.hits+1)+'</span>';
 return '<div class="moving-target" aria-label="타이밍 게이지"><span class="cursor" id="arcade-cursor"></span></div><div class="action-pads"><button class="pad" data-pad="H">⚔ 베기!</button></div><span class="subtle">명중 '+stage.hits+'/2 · '+(stage.hard?'타이밍이 조금 빨라져요':'초록 구간에서 누르기')+'</span>';
}
function note(t){const e=F.app.querySelector('#stage-note');if(e)e.textContent=t}
function interact(i){
 if(!stage||!run||run.ended||run.paused||!stage.deadline)return;
 if(stage.kind===0){if(stage.flashes.includes(i)){stage.flashes=stage.flashes.filter(x=>x!==i);stage.hits++;if(!stage.flashes.length){resolve(true);return}draw();note('좋아요! '+stage.flashes.length+'개만 더!')}else {stage.deadline-=550;note('멀쩡한 장비였어요! 시간 -0.5초')}}
 if([1,4].includes(stage.kind)){if(stage.ordered[stage.hits]===i){stage.hits++;if(stage.hits>=stage.ordered.length){resolve(true);return}draw();note('정확해요! 다음 번호로!')}else{stage.deadline-=550;note('순서가 달라요. 시간 -0.5초')}}
}
function pad(dir){
 if(!stage||!run||run.ended||run.paused||!stage.deadline)return;
 if(stage.kind===2){
  if(dir==='L')stage.lane=Math.max(0,stage.lane-1);
  if(dir==='R')stage.lane=Math.min(2,stage.lane+1);
  if(dir==='C'){if(stage.lane===stage.target){stage.hits++;if(stage.hits>=3){resolve(true);return}stage.target=(stage.target+2)%3;note('박쥐단 합류 성공!')}else{stage.deadline-=400;note('다른 줄에 있어요!')}}
  const e=F.app.querySelector('#stage-input');if(e)e.innerHTML=stageHTML();
 }else if(stage.kind===3 && ['L','R'].includes(dir)){
  if(dir===stage.sequence[stage.hits]){stage.hits++;if(stage.hits>=stage.sequence.length){resolve(true);return}const e=F.app.querySelector('#stage-input');if(e)e.innerHTML=stageHTML();note('신호 전달!')}else {stage.deadline-=500;note('방향이 반대예요!')}
 }else if(stage.kind===5&&dir==='H'){
  const pos=stage.cursor,range=stage.hard?.08:.11;
  if(Math.abs(pos-.5)<=range){stage.hits++;if(stage.hits>=2){resolve(true);return}note('명중! 한 번 더!');stage.cursor=0}
  else{stage.deadline-=650;note('조금 빗나갔어요! 다시 노려보세요.')}
 }
}
function tick(){
 if(!run||!stage||run.ended||run.paused||!stage.deadline)return;
 const rem=Math.max(0,(stage.deadline-Date.now())/1000),pct=(rem/6*100);
 const time=F.app.querySelector('#time-label');if(time)time.textContent=rem.toFixed(1)+'초';
 const bar=F.app.querySelector('#time-progress');if(bar)bar.style.width=pct+'%';
 if(stage.kind===5){stage.cursor=(Math.sin((6-rem)*(stage.hard?8:6))+1)/2;const cursor=F.app.querySelector('#arcade-cursor');if(cursor)cursor.style.left=(stage.cursor*100)+'%'}
 if(rem<=0)resolve(false);
}
function resolve(win){
 if(!stage||stage.done||!run)return;stage.done=true;run.ended=true;clear();
 const rem=Math.max(0,(stage.deadline-Date.now())/1000);
 if(win){run.success++;run.score+=100+Math.ceil(rem*10)}
 const e=F.app.querySelector('#stage-input');if(e)e.innerHTML='<div class="result" style="padding:16px"><div class="result-star">'+(win?'✦':'○')+'</div><h2>'+(win?'미션 성공!':'시간 종료!')+'</h2><p>'+(win?'다음 멤버의 상황으로 이동합니다.':'다음 도전에서 다시 만나보세요.')+'</p>'+F.btn('다음으로 →','next','primary')+'</div>';
 note(win?'+'+(100+Math.ceil(rem*10))+'점 · 현재 '+run.score+'점':'이번 미션 점수 없음');
 nextTimer=setTimeout(()=>{if(!closed&&run?.ended)advance()},1300);
}
function pauseToggle(){
 if(!run||!stage||run.ended)return;
 if(!run.paused){run.paused=true;stage.remaining=Math.max(0,stage.deadline-Date.now());note('일시정지했어요. 계속하기로 재개하세요.')}
 else{run.paused=false;stage.deadline=Date.now()+stage.remaining;note('다시 시작합니다!')}
 const b=F.app.querySelector('[data-action="pause"]');if(b)b.textContent=run.paused?'계속하기':'일시정지';
}
function finish(){
 if(!run)return;const r=run;if(r.score>F.state.bestArcade){F.state.bestArcade=r.score;F.save()}
 const el=F.app.querySelector('#arcade-field');if(!el)return;
 el.innerHTML='<div class="result"><div class="result-star">✦</div><h2>이세돌 릴레이 완료!</h2><p>이번 판의 기록을 확인해 보세요. 미션은 실제 방송이 아닌 팬게임용 가상 상황입니다.</p><div class="highlights"><div class="highlight"><strong>'+r.success+'/'+r.total+'</strong><span>성공한 미션</span></div><div class="highlight"><strong>'+r.score+'</strong><span>획득 점수</span></div><div class="highlight"><strong>'+F.state.bestArcade+'</strong><span>나의 최고</span></div></div><div class="buttons" style="justify-content:center">'+F.btn('다시 도전','full','primary')+F.btn('연습 모드','practice')+'</div></div>';
 run=null;stage=null;
}
function key(e){
 if(F.active!=='arcade'||!stage||!run||run.ended)return;
 const k=e.key;
 if(['ArrowLeft','ArrowRight',' ','Enter'].includes(k))e.preventDefault();
 if(k==='Escape')pauseToggle();
 if(['ArrowLeft','a','A'].includes(k))pad('L');
 if(['ArrowRight','d','D'].includes(k))pad('R');
 if(k===' '||k==='Enter')pad(stage.kind===2?'C':'H');
}
function visibility(){if(run&&!run.paused&&!run.ended&&stage?.deadline)pauseToggle()}
F.install('arcade',{mount,key,visibility});
})();
