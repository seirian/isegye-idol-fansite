/* Turn-based original cooperation puzzle: three specialists must unlock each other's routes. */
(()=>{
const ROLES=[F.MEMBERS[0],F.MEMBERS[1],F.MEMBERS[2]];
const configs=[
 ['첫 합방의 문','D!~',[4,4,4],[1,3,5]],
 ['뒤바뀐 통로','~D!',[4,4,4],[3,5,1]],
 ['천문대의 전원','!~D',[4,4,4],[5,1,3]],
 ['스위치의 순서','D~!',[4,4,4],[1,5,3]],
 ['세 가지 갈림길','!D~',[4,4,4],[5,3,1]],
 ['반대편에서 만나','~!D',[4,4,4],[3,1,5]],
 ['조금 더 먼 다리','!~D',[5,4,3],[5,1,3]],
 ['마지막 합방','D!~',[3,5,4],[3,5,1]]
];
let level=0,board=null,history=[],selected=0,ended=false;
const labels={D:'⛔', '!':'⚡', '~':'◯', E:'✦', '#':'', '.':''};
const skillLabels=['⚡ EMP 사용','✎ 다리 그리기','✧ 원격 스위치'];
function createLevel(n){
 const [title,barriers,cols,starts]=configs[n];
 const cells=Array.from({length:7},(_,y)=>Array.from({length:9},(_,x)=>{
   if(y===0||y===6||x===0||x===8)return '#';
   if((y===2||y===4)&&x>=4)return '#';
   if([1,3,5].includes(y)&&x===7)return 'E';
   return '.';
 }));
 [1,3,5].forEach((y,i)=>{cells[y][cols[i]]=barriers[i]});
 const positions=starts.map(y=>({x:1,y}));
 return {title,cells,positions,flags:{D:false,'!':false,'~':false},moves:0,complete:false};
}
function mount(){
 level=0;board=createLevel(0);history=[];selected=0;ended=false;
 F.app.innerHTML='<div class="game-top"><div><span class="eyebrow">03 · THREE-PERSON CO-OP LOGIC</span><h2>이세돌 합방 탈출</h2><p>혼자서 세 명을 번갈아 조작하세요. 한 명의 능력이 다른 멤버의 출구를 엽니다.</p></div>'+F.metrics([['스테이지','8개'],['최대 진행',F.state.escapeUnlocked+'/8'],['조작','턴제']])+'</div>'+
 '<div class="panel"><div class="levelbar"><h3 style="margin-bottom:0">스테이지 선택</h3><div class="level-pills" id="escape-levels"></div></div><div class="game-layout"><div class="main-play"><div class="levelbar" style="margin-top:14px"><h3 id="escape-title"></h3><span class="subtle" id="escape-moves"></span></div><div id="escape-board" class="puzzle-board" role="grid" aria-label="합방 탈출 판"></div><div class="puzzle-tools"><button class="pad" data-move="up" aria-label="위로 이동">↑</button><button class="pad" data-move="left" aria-label="왼쪽으로 이동">←</button><button class="pad" data-move="down" aria-label="아래로 이동">↓</button><button class="pad" data-move="right" aria-label="오른쪽으로 이동">→</button></div><div class="buttons" style="justify-content:center;margin-top:15px">'+F.btn('선택한 멤버 능력 사용','skill','primary')+F.btn('되돌리기','undo')+F.btn('다시 시작','reset','ghost')+F.btn('힌트','hint','ghost')+'</div><div class="game-status" id="escape-note">세 명을 골라 움직이며 다른 멤버의 길을 열어 주세요.</div><div id="escape-result"></div></div><aside class="sidebar"><h3>조작할 멤버</h3><div id="escape-members"></div><h3 style="margin-top:22px">합방 규칙</h3><ol class="help-list"><li>멤버를 선택하고 방향키나 화살표 버튼으로 움직이세요.</li><li><b>아이네</b>는 ⚡ 옆에서 EMP, <b>징버거</b>는 ◯ 옆에서 다리, <b>릴파</b>는 ⛔ 옆에서 문을 엽니다.</li><li>세 능력은 모두 다른 멤버에게도 영향을 줍니다.</li><li>세 명 모두 각기 다른 ✦ 출구에 도착하면 성공!</li><li>1·2·3: 멤버 선택, X: 능력, Z: 되돌리기, R: 초기화</li></ol><p class="subtle">색과 기호를 함께 표시합니다. 실제 멤버의 공식 초능력 설정이 아닙니다.</p></aside></div></div>';
 render();
 const h=e=>{
  const el=e.target.closest('[data-action],[data-level],[data-select],[data-move],[data-cell]');if(!el)return;
  if(el.dataset.level!=null){load(Number(el.dataset.level));return}
  if(el.dataset.select!=null){selected=Number(el.dataset.select);render();return}
  if(el.dataset.move){move(el.dataset.move);return}
  if(el.dataset.cell!=null){tapCell(Number(el.dataset.cell));return}
  const a=el.dataset.action;
  if(a==='skill')skill();
  if(a==='undo')undo();
  if(a==='reset'){if(confirm('현재 스테이지를 처음부터 다시 풀까요?'))load(level)}
  if(a==='hint')hint();
  if(a==='next')load(Math.min(configs.length-1,level+1));
 };
 F.app.addEventListener('click',h);F.onCleanup(()=>F.app.removeEventListener('click',h));
}
function note(t){const e=F.app.querySelector('#escape-note');if(e)e.textContent=t}
function load(n){level=n;board=createLevel(level);history=[];selected=0;ended=false;render();note('스테이지 '+(level+1)+' 시작! 능력은 가까이에서 사용합니다.')}
function snapshot(){return JSON.parse(JSON.stringify({positions:board.positions,flags:board.flags,moves:board.moves,complete:board.complete}))}
function keep(){history.push(snapshot());if(history.length>150)history.shift()}
function undo(){if(!history.length){F.toast('되돌릴 동작이 없어요.');return}const p=history.pop();Object.assign(board,p);ended=false;render();note('한 수 되돌렸어요.')}
function render(){
 if(!board)return;
 const levels=F.app.querySelector('#escape-levels'),cells=F.app.querySelector('#escape-board'),members=F.app.querySelector('#escape-members');if(!cells)return;
 levels.innerHTML=configs.map((c,i)=>'<button type="button" data-level="'+i+'" aria-current="'+(i===level)+'">'+(i+1)+(F.state.escapeBest[i]!=null?' ✓':'')+'</button>').join('');
 F.app.querySelector('#escape-title').textContent=(level+1)+'. '+board.title;
 F.app.querySelector('#escape-moves').textContent='이동·능력 '+board.moves+'수';
 cells.innerHTML=board.cells.map((row,y)=>row.map((v,x)=>{
  const p=board.positions.findIndex(q=>q.x===x&&q.y===y);
  const cleared=board.flags[v],display=cleared?'.':v;
  const cls=v==='#'?'wall':v==='E'?'exit':v==='D'&&!cleared?'gate':v==='!'&&!cleared?'hazard':v==='~'&&!cleared?'pit':'';
  let mark=labels[display]||'',token=p>=0?'<span class="piece '+(p===selected?'selected':'')+'" style="--avatar:'+ROLES[p].color+'">'+ROLES[p].short+'</span>':'';
  return '<button type="button" data-cell="'+(y*9+x)+'" class="puzzle-cell '+cls+'" aria-label="'+(v==='#'?'벽':v==='E'?'출구':v==='!'?'전기':v==='~'?'틈':v==='D'?'문':'통로')+(p>=0?' '+ROLES[p].name:'')+'" '+(v==='#'?'disabled':'')+'>'+mark+token+'</button>';
 }).join('')).join('');
 members.innerHTML=ROLES.map((m,i)=>'<button type="button" data-select="'+i+'" class="member-info" style="width:100%;border:1px solid '+(selected===i?'#f4bad3':'#4d3e5e')+';color:inherit;text-align:left;margin-bottom:8px;cursor:pointer">'+F.memberCard(m)+'<div><strong>'+m.name+(selected===i?' · 선택됨':'')+'</strong><p>'+skillLabels[i]+' '+(board.flags[['!','~','D'][i]]?'✓ 사용됨':'· 사용 전')+'</p></div></button>').join('');
 const res=F.app.querySelector('#escape-result');
 res.innerHTML=board.complete?'<div class="result" style="margin-top:16px"><div class="result-star">✦</div><h2>세 명 모두 탈출 성공!</h2><p>서로 다른 능력으로 통로를 열었습니다. '+board.moves+'수로 클리어!</p><div class="buttons" style="justify-content:center">'+F.btn(level===7?'마지막 스테이지 다시 풀기':'다음 스테이지 →',level===7?'reset':'next','primary')+'</div></div>':'';
}
function validMove(x,y){if(x<0||x>=9||y<0||y>=7)return false;let v=board.cells[y][x];if(v==='#')return false;if(['D','!','~'].includes(v)&&!board.flags[v])return false;return !board.positions.some((p,i)=>i!==selected&&p.x===x&&p.y===y)}
function move(dir){
 if(!board||board.complete)return;const d={up:[0,-1],down:[0,1],left:[-1,0],right:[1,0]}[dir];if(!d)return;
 const p=board.positions[selected],x=p.x+d[0],y=p.y+d[1];if(!validMove(x,y)){note('이쪽은 막혀 있어요. 다른 멤버의 능력이 필요할지도 몰라요.');return}
 keep();p.x=x;p.y=y;board.moves++;check();render();if(!board.complete)note(ROLES[selected].name+' 이동 완료');
}
function tapCell(n){
 const x=n%9,y=Math.floor(n/9),p=board.positions.findIndex(v=>v.x===x&&v.y===y);
 if(p>=0){selected=p;render();return}
 const cur=board.positions[selected];const dx=x-cur.x,dy=y-cur.y;
 if(Math.abs(dx)+Math.abs(dy)!==1){note('선택한 멤버의 옆 칸을 눌러 이동해 보세요.');return}
 move(dx===1?'right':dx===-1?'left':dy===1?'down':'up');
}
function skill(){
 if(board.complete)return;const symbol=['!','~','D'][selected];
 if(board.flags[symbol]){note('이 멤버의 능력은 이미 사용했어요.');return}
 const p=board.positions[selected];let found=null;
 for(let y=0;y<7;y++)for(let x=0;x<9;x++){if(board.cells[y][x]===symbol&&Math.abs(p.x-x)+Math.abs(p.y-y)<=1)found={x,y}}
 if(!found){note(ROLES[selected].name+'을 해당 장애물 바로 옆으로 이동한 뒤 사용하세요.');return}
 keep();board.flags[symbol]=true;board.moves++;check();render();note(ROLES[selected].name+'의 '+ROLES[selected].power+'! 동료의 길까지 열렸어요.');
}
function check(){
 const onExit=board.positions.every((p)=>board.cells[p.y][p.x]==='E');
 if(onExit){board.complete=true;ended=true;const best=F.state.escapeBest[level];if(best==null||board.moves<best){F.state.escapeBest[level]=board.moves;F.state.escapeUnlocked=Math.max(F.state.escapeUnlocked,level+2>8?8:level+2);F.save()}}
}
function hint(){
 const missing=[['!','아이네는 전기가 있는 줄 옆으로 가 EMP를 사용'],['~','징버거는 틈 옆에 가 다리를 그리기'],['D','릴파는 잠긴 문 옆에서 원격 스위치를 사용']].filter(([s])=>!board.flags[s]);
 if(missing.length)note('힌트: '+missing[0][1]+'하세요. 다른 멤버의 길도 열립니다.');
 else note('힌트: 세 명을 모두 오른쪽 초록색 출구에 각각 한 명씩 이동시키세요.');
}
function key(e){
 if(F.active!=='escape')return;const k=e.key;
 if(['ArrowUp','ArrowDown','ArrowLeft','ArrowRight','1','2','3','x','X','z','Z','r','R'].includes(k))e.preventDefault();
 if(k==='1'||k==='2'||k==='3'){selected=Number(k)-1;render()}
 const keys={ArrowUp:'up',ArrowDown:'down',ArrowLeft:'left',ArrowRight:'right'};if(keys[k])move(keys[k]);
 if(k==='x'||k==='X')skill();if(k==='z'||k==='Z')undo();if(k==='r'||k==='R')load(level);
}
F.install('escape',{mount,key});
})();
