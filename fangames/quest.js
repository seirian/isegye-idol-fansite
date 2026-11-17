/* Original top-down survival encounter. No sprites, recordings or scraped assets. */
(()=>{
const W=800,H=450,DURATION=70;
let chosen=0,support=1,g=null,frame=0,canvas=null,ctx=null,held=new Set(),pointer=null,closed=false;
const upgrades=[['atk','출력 강화','일반 공격 피해 +25%'],['speed','속도 강화','이동 속도 +15%'],['reach','사거리 강화','자동 공격 범위 +18%']];
const rand=(a,b)=>a+Math.random()*(b-a);
function setup(){
 closed=false;g=null;
 const hero=F.MEMBERS[chosen],ally=F.MEMBERS[support];
 F.app.innerHTML='<div class="game-top"><div><span class="eyebrow">02 · CHARACTER ACTION SURVIVAL</span><h2>세돌 원정대</h2><p>멤버를 직접 조작하고, 서로 다른 능력으로 오류 폭풍을 돌파하세요.</p></div>'+F.metrics([['내 최고 격파',F.state.bestQuest],['한 판','70초'],['조작','이동 + 필살기']])+'</div><div class="panel alt" id="quest-setup"><h3>01 · 직접 조작할 멤버</h3><p class="subtle">모든 기술은 팬게임만의 허구 설정입니다. 주인공에 따라 기본 공격과 특수기가 달라져요.</p><div class="member-row">'+F.MEMBERS.map((m,i)=>'<button class="member '+(i===chosen?'selected':'')+'" data-pick="'+i+'">'+F.memberCard(m)+'<span class="label">'+m.name+'</span><small>'+m.power+'</small></button>').join('')+'</div><h3>02 · 함께할 지원 멤버</h3><div class="member-row">'+F.MEMBERS.map((m,i)=>'<button class="member '+(i===support?'selected':'')+'" data-ally="'+i+'">'+F.memberCard(m)+'<span class="label">'+m.name+'</span><small>지원</small></button>').join('')+'</div><div class="member-info">'+F.memberCard(hero)+'<div><strong>'+hero.name+' · '+hero.power+'</strong><p>'+hero.detail+' · 지원: '+ally.name+'</p></div></div><div class="buttons" style="margin-top:18px">'+F.btn('선택한 조합으로 출격 →','start','primary')+'<span class="subtle">소리 없음 · 공격 자동 · 특수기 직접 발동</span></div></div><div id="quest-field"></div><div class="caution">상대는 실존 인물이나 팬이 아닌 가상의 ‘오류 덩어리’입니다. 다른 탭으로 이동하면 자동 일시정지됩니다.</div>';
}
function mount(){
 setup();
 const h=e=>{const el=e.target.closest('[data-action],[data-pick],[data-ally]');if(!el)return;
  if(el.dataset.pick!=null&&!g){chosen=Number(el.dataset.pick);if(chosen===support)support=(support+1)%6;setup();return}
  if(el.dataset.ally!=null&&!g){support=Number(el.dataset.ally);if(support===chosen)chosen=(chosen+1)%6;setup();return}
  const a=el.dataset.action;
  if(a==='start')start();
  if(a==='pause')toggle();
  if(a==='special')special();
  if(a==='quit'&&confirm('원정대를 중단하고 캐릭터를 다시 고를까요?')){stopLoop();setup()}
  if(a?.startsWith('upgrade:'))chooseUpgrade(a.split(':')[1]);
 };
 F.app.addEventListener('click',h);
 const touchOn=e=>{const b=e.target.closest('[data-dir]');if(b){e.preventDefault();held.add(b.dataset.dir);b.setPointerCapture?.(e.pointerId)}};
 const touchOff=e=>{const b=e.target.closest('[data-dir]');if(b){e.preventDefault();held.delete(b.dataset.dir)}};
 F.app.addEventListener('pointerdown',touchOn);F.app.addEventListener('pointerup',touchOff);F.app.addEventListener('pointercancel',touchOff);
 F.onCleanup(()=>{closed=true;stopLoop();F.app.removeEventListener('click',h);F.app.removeEventListener('pointerdown',touchOn);F.app.removeEventListener('pointerup',touchOff);F.app.removeEventListener('pointercancel',touchOff)});
}
function stopLoop(){cancelAnimationFrame(frame);frame=0;held.clear();pointer=null;g=null}
function start(){
 if(g)return;const p=F.MEMBERS[chosen];
 g={t:0,last:performance.now(),x:W/2,y:H/2,hp:100,maxHp:100,atk:1,spd:1,reach:1,bullets:[],enemies:[],effects:[],kills:0,lv:1,xp:0,nextLv:8,auto:0,spawn:0,supportT:0,cd:0,stun:0,shield:0,rapid:0,decoy:0,bossed:false,bossDefeated:false,paused:false,upgrading:false,over:false};
 F.app.querySelector('#quest-setup').remove();
 const f=F.app.querySelector('#quest-field');
 f.innerHTML='<div class="canvas-wrap"><canvas id="quest-canvas" width="'+W+'" height="'+H+'" aria-label="원정대 플레이 화면"></canvas><div class="hud"><span id="q-time">0:00 / 1:10</span><span id="q-life">♥ 100</span><span id="q-kills">격파 0</span><span id="q-level">LV 1</span></div><div id="q-overlay" class="game-overlay" hidden></div></div><div class="touch-pad"><div class="dpad"><button data-dir="up" class="up" aria-label="위로 이동">↑</button><button data-dir="left" class="left" aria-label="왼쪽 이동">←</button><button data-dir="down" class="down" aria-label="아래로 이동">↓</button><button data-dir="right" class="right" aria-label="오른쪽 이동">→</button></div><div class="buttons"><span class="subtle" id="q-special-label">'+F.MEMBERS[chosen].power+'</span>'+F.btn('일시정지','pause','ghost')+F.btn('나가기','quit','ghost')+'<button data-action="special" id="q-special" class="ability-button">✦<small>필살기</small></button></div></div><p class="subtle">PC: WASD·방향키 이동 / Space 필살기 / Esc 일시정지. 모바일: 방향 버튼 또는 화면 드래그 이동.</p>';
 canvas=F.app.querySelector('#quest-canvas');ctx=canvas.getContext('2d');
 const pt=e=>{const r=canvas.getBoundingClientRect();pointer={x:(e.clientX-r.left)/r.width*W,y:(e.clientY-r.top)/r.height*H};};
 const down=e=>{canvas.setPointerCapture(e.pointerId);pt(e)};
 const move=e=>{if(pointer)pt(e)};
 const up=()=>pointer=null;
 canvas.addEventListener('pointerdown',down);canvas.addEventListener('pointermove',move);canvas.addEventListener('pointerup',up);canvas.addEventListener('pointercancel',up);
 tick(performance.now());
}
function pauseUI(title,desc,buttons){
 if(!g)return;const o=F.app.querySelector('#q-overlay');if(!o)return;
 o.hidden=false;o.innerHTML='<h3>'+title+'</h3><p>'+desc+'</p><div class="buttons">'+buttons+'</div>';
}
function hidePause(){const o=F.app.querySelector('#q-overlay');if(o)o.hidden=true}
function toggle(){
 if(!g||g.over||g.upgrading)return;
 g.paused=!g.paused;
 if(g.paused)pauseUI('잠시 쉬어가요','원정은 멈춘 상태예요. 움직일 준비가 되면 계속해 주세요.',F.btn('계속하기','pause','primary')+F.btn('캐릭터 선택','quit'));
 else{hidePause();g.last=performance.now();}
}
function dist(a,b,x,y){return Math.hypot(a-x,b-y)}
function addFx(x,y,r,color,life=.3){g.effects.push({x,y,r,color,t:life,life})}
function damage(e,n){if(!e||e.hp<=0)return;e.hp-=n;addFx(e.x,e.y,e.r+12,'#ffcbda',.2);if(e.hp<=0){g.kills++;g.xp++;if(e.boss)g.bossDefeated=true;addFx(e.x,e.y,e.r+28,'#93e9c3',.6);if(g.xp>=g.nextLv){g.xp=0;g.lv++;g.nextLv=Math.round(g.nextLv*1.32);g.upgrading=true;pauseUI('레벨 '+g.lv+' 달성!','강화 하나를 골라 다음 웨이브에 대비하세요.',upgrades.map(x=>F.btn('<strong>'+x[1]+'</strong><small>'+x[2]+'</small>','upgrade:'+x[0],'secondary')).join(''))}}}
function chooseUpgrade(kind){
 if(!g||!g.upgrading)return;
 if(kind==='atk')g.atk*=1.25;if(kind==='speed')g.spd*=1.15;if(kind==='reach')g.reach*=1.18;
 g.upgrading=false;g.last=performance.now();hidePause();F.toast('강화를 획득했어요!');
}
function nearest(x,y,range,n=1){return g.enemies.filter(e=>e.hp>0&&dist(x,y,e.x,e.y)<range).sort((a,b)=>dist(x,y,a.x,a.y)-dist(x,y,b.x,b.y)).slice(0,n)}
function attack(){
 const target=nearest(g.x,g.y,165*g.reach,1)[0];if(!target)return;
 let dmg=11*g.atk;const hero=F.MEMBERS[chosen].id;
 if(hero==='ine'){dmg=9*g.atk;nearest(target.x,target.y,44,4).forEach(e=>damage(e,dmg*.45));addFx(target.x,target.y,45,'#b7a1fb',.18)}
 if(hero==='jing'){dmg=14*g.atk;g.shield=Math.max(g.shield,.18);addFx(g.x,g.y,70,'#efd68d',.24)}
 if(hero==='lilpa'){dmg=15*g.atk;addFx(target.x,target.y,29,'#91bafa',.3)}
 if(hero==='jururu'){dmg=10*g.atk;target.slow=.9;addFx(target.x,target.y,36,'#ef9cbe',.3)}
 if(hero==='gosegu'){dmg=9*g.atk;nearest(g.x,g.y,175*g.reach,2).forEach(e=>{if(e!==target)damage(e,7*g.atk)});addFx(target.x,target.y,26,'#a2e8e7',.25)}
 if(hero==='viichan'){dmg=17*g.atk;nearest(g.x,g.y,100*g.reach,4).forEach(e=>{if(e!==target)damage(e,6*g.atk)});addFx(g.x,g.y,95,'#a6ebb2',.23)}
 damage(target,dmg);
}
function special(){
 if(!g||g.paused||g.upgrading||g.over||g.cd>0)return;
 g.cd=9;const id=F.MEMBERS[chosen].id;F.toast(F.MEMBERS[chosen].power+'!');
 if(id==='ine'){g.stun=3.3;nearest(g.x,g.y,220,50).forEach(e=>damage(e,9*g.atk));addFx(g.x,g.y,210,'#bdaaff',.8)}
 if(id==='jing'){g.shield=5;g.hp=Math.min(g.maxHp,g.hp+12);addFx(g.x,g.y,96,'#efd68d',.8)}
 if(id==='lilpa'){nearest(g.x,g.y,340,9).forEach(e=>damage(e,34*g.atk));addFx(g.x,g.y,250,'#a4bdff',.8)}
 if(id==='jururu'){g.decoy=6;nearest(g.x,g.y,180,30).forEach(e=>e.slow=3);addFx(g.x+50,g.y,130,'#f6a5d0',.8)}
 if(id==='gosegu'){g.rapid=6;addFx(g.x,g.y,145,'#97e2ec',.8)}
 if(id==='viichan'){nearest(g.x,g.y,180,50).forEach(e=>damage(e,45*g.atk));addFx(g.x,g.y,180,'#b4e7ad',.9)}
}
function supportPulse(){
 const id=F.MEMBERS[support].id;
 if(id==='ine'){g.stun=Math.max(g.stun,1.2);addFx(g.x,g.y,155,'#b7a1fb',.7)}
 else if(id==='jing'){g.hp=Math.min(100,g.hp+13);g.shield=Math.max(g.shield,2);addFx(g.x,g.y,95,'#f4d083',.7)}
 else if(id==='lilpa'){nearest(g.x,g.y,270,5).forEach(e=>damage(e,12));addFx(g.x,g.y,160,'#98b6f6',.7)}
 else if(id==='jururu'){g.decoy=Math.max(g.decoy,3);addFx(g.x+50,g.y,135,'#ef9cbe',.7)}
 else if(id==='gosegu'){g.rapid=Math.max(g.rapid,3);addFx(g.x,g.y,140,'#97dbe6',.7)}
 else if(id==='viichan'){nearest(g.x,g.y,140,7).forEach(e=>damage(e,15));addFx(g.x,g.y,170,'#a7e5ae',.7)}
 F.toast(F.MEMBERS[support].name+'의 지원 도착!');
}
function spawn(boss=false){
 const angle=rand(0,Math.PI*2),r=320,px=Math.max(13,Math.min(W-13,g.x+Math.cos(angle)*r)),py=Math.max(13,Math.min(H-13,g.y+Math.sin(angle)*r));
 const type=boss?3:Math.floor(rand(0,3));
 g.enemies.push({x:px,y:py,type,r:boss?35:type===2?16:12,hp:boss?190:type===2?32:20,speed:boss?25:type===1?60:type===2?33:45,slow:0,boss});
}
function physics(dt){
 g.t+=dt;g.cd=Math.max(0,g.cd-dt);g.shield=Math.max(0,g.shield-dt);g.stun=Math.max(0,g.stun-dt);g.decoy=Math.max(0,g.decoy-dt);g.rapid=Math.max(0,g.rapid-dt);
 let dx=0,dy=0;
 if(held.has('left')||held.has('a')||held.has('ArrowLeft'))dx--;
 if(held.has('right')||held.has('d')||held.has('ArrowRight'))dx++;
 if(held.has('up')||held.has('w')||held.has('ArrowUp'))dy--;
 if(held.has('down')||held.has('s')||held.has('ArrowDown'))dy++;
 if(pointer){const v=Math.hypot(pointer.x-g.x,pointer.y-g.y);if(v>12){dx+=(pointer.x-g.x)/v;dy+=(pointer.y-g.y)/v}}
 const d=Math.hypot(dx,dy);if(d){const speed=180*g.spd*dt/d;g.x=Math.max(20,Math.min(W-20,g.x+dx*speed));g.y=Math.max(20,Math.min(H-20,g.y+dy*speed))}
 g.spawn-=dt;if(g.spawn<=0){g.spawn=.7-Math.min(.3,g.t/200);spawn()}
 if(!g.bossed&&g.t>=42){g.bossed=true;spawn(true);F.toast('⚠ 오류 핵심체 등장!')}
 g.auto-=dt;if(g.auto<=0){attack();g.auto=g.rapid>0?.22:.58}
 g.supportT-=dt;if(g.supportT<=0){g.supportT=15;supportPulse()}
 for(const e of g.enemies){if(e.hp<=0)continue;e.slow=Math.max(0,(e.slow||0)-dt);if(g.stun>0)continue;
  const tx=g.decoy>0?g.x+60:g.x,ty=g.y;const vx=tx-e.x,vy=ty-e.y,v=Math.hypot(vx,vy)||1;
  const rate=e.slow>0?.35:1;e.x+=vx/v*e.speed*dt*rate;e.y+=vy/v*e.speed*dt*rate;
  if(dist(g.x,g.y,e.x,e.y)<e.r+14 && g.shield<=0){
    g.hp-=e.boss?24*dt:11*dt;g.hp=Math.max(0,g.hp);
  }
 }
 g.enemies=g.enemies.filter(e=>e.hp>0).slice(-70);
 g.effects=g.effects.filter(e=>{e.t-=dt;return e.t>0});
 if(g.hp<=0)end(false);
 if(g.t>=DURATION)end(g.bossDefeated);
}
function draw(){
 if(!g||!ctx)return;
 const c=ctx;c.clearRect(0,0,W,H);
 const bg=c.createLinearGradient(0,0,W,H);bg.addColorStop(0,'#111b2b');bg.addColorStop(.6,'#1d1931');bg.addColorStop(1,'#252139');c.fillStyle=bg;c.fillRect(0,0,W,H);
 c.strokeStyle='#ffffff10';c.lineWidth=1;for(let x=0;x<W;x+=40){c.beginPath();c.moveTo(x,0);c.lineTo(x,H);c.stroke()}for(let y=0;y<H;y+=40){c.beginPath();c.moveTo(0,y);c.lineTo(W,y);c.stroke()}
 c.save();c.translate(W/2,H/2);c.strokeStyle='#fff2';c.lineWidth=3;c.strokeRect(-W/2+15,-H/2+15,W-30,H-30);c.restore();
 for(const e of g.effects){c.globalAlpha=Math.max(0,e.t/e.life);c.beginPath();c.arc(e.x,e.y,e.r*(1.3-e.t/e.life*.3),0,Math.PI*2);c.strokeStyle=e.color;c.lineWidth=4;c.stroke();c.globalAlpha=1}
 for(const e of g.enemies){c.save();c.translate(e.x,e.y);c.fillStyle=e.boss?'#d779a5':e.type===1?'#f2c679':e.type===2?'#a67add':'#ee819d';c.strokeStyle='#fff7';c.lineWidth=2;c.beginPath();if(e.type===1){c.rect(-e.r,-e.r,e.r*2,e.r*2)}else{c.arc(0,0,e.r,0,Math.PI*2)}c.fill();c.stroke();c.fillStyle='#211925';c.font='bold '+(e.boss?26:12)+'px system-ui';c.textAlign='center';c.textBaseline='middle';c.fillText(e.boss?'⚠':'×',0,1);c.restore()}
 const m=F.MEMBERS[chosen];c.fillStyle=m.color;c.beginPath();c.arc(g.x,g.y,19,0,Math.PI*2);c.fill();c.strokeStyle=g.shield>0?'#fff29d':'#ffffffa0';c.lineWidth=g.shield>0?6:3;c.stroke();c.fillStyle='#281c30';c.font='bold 14px system-ui';c.textAlign='center';c.textBaseline='middle';c.fillText(m.short,g.x,g.y);
 const a=F.MEMBERS[support];const sx=g.x-30,sy=g.y+30;c.fillStyle=a.color;c.beginPath();c.arc(sx,sy,10,0,Math.PI*2);c.fill();c.fillStyle='#2a212a';c.font='bold 9px system-ui';c.fillText(a.short,sx,sy);
 c.fillStyle='#321a2a';c.fillRect(20,H-23,170,10);c.fillStyle='#e7a0bd';c.fillRect(20,H-23,170*g.hp/100,10);
 c.fillStyle='#d9c8ed';c.font='12px system-ui';c.textAlign='left';c.fillText(m.name+' × '+a.name+' 지원',20,H-34);
}
function ui(){
 const time=F.app.querySelector('#q-time');if(!time)return;
 time.textContent=Math.floor(g.t/60)+':'+String(Math.floor(g.t%60)).padStart(2,'0')+' / 1:10';
 F.app.querySelector('#q-life').textContent='♥ '+Math.ceil(g.hp);
 F.app.querySelector('#q-kills').textContent='격파 '+g.kills;
 F.app.querySelector('#q-level').textContent='LV '+g.lv;
 const sp=F.app.querySelector('#q-special');if(sp){sp.disabled=g.cd>0;sp.innerHTML='✦<small>'+(g.cd>0?'재충전 '+Math.ceil(g.cd)+'초':'필살기')+'</small>'}
}
function tick(now){
 if(!g||closed)return;
 const dt=Math.min(.05,(now-g.last)/1000);g.last=now;
 if(!g.paused&&!g.upgrading&&!g.over)physics(dt);
 draw();ui();
 if(g&&!g.over)frame=requestAnimationFrame(tick);
}
function end(win){
 if(!g||g.over)return;g.over=true;
 if(g.kills>F.state.bestQuest){F.state.bestQuest=g.kills;F.save()}
 const outcome=win?'오류 폭풍 정리 완료!':g.hp<=0?'원정대 후퇴!':'보스를 놓쳤어요!';
 pauseUI(outcome,'격파 '+g.kills+' · 생존 '+Math.floor(g.t)+'초 · 레벨 '+g.lv+' · 나의 최고 격파 '+F.state.bestQuest,F.btn('다시 출격','restart','primary')+F.btn('조합 다시 고르기','quit'));
 const restart=F.app.querySelector('[data-action="restart"]');restart?.addEventListener('click',()=>{stopLoop();setup();start()},{once:true});
}
function key(e){
 if(F.active!=='quest'||!g)return;
 if(['ArrowUp','ArrowDown','ArrowLeft','ArrowRight',' ','Escape'].includes(e.key))e.preventDefault();
 const k=e.key;if(['w','a','s','d'].includes(k.toLowerCase())||k.startsWith('Arrow')){if(e.type==='keydown')held.add(k.toLowerCase().length===1?k.toLowerCase():k)}
 if(k===' ')special();if(k==='Escape')toggle();
}
window.addEventListener('keyup',e=>{held.delete(e.key.toLowerCase().length===1?e.key.toLowerCase():e.key)});
function visibility(){if(g&&!g.paused&&!g.upgrading&&!g.over)toggle()}
F.install('quest',{mount,key,visibility});
})();
