/* Three original, offline, unaffiliated fan-game previews. No external media or network calls. */
'use strict';
const F=(()=>{
 const K='isegye:review:fangames:v1';
 const MEMBERS=[
  {id:'ine',name:'아이네',short:'아',color:'#b7a1fb',mark:'✦',power:'EMP 펄스',detail:'주변의 오류를 잠시 멈추는 역할'},
  {id:'jing',name:'징버거',short:'징',color:'#f4d083',mark:'✎',power:'그림 방벽',detail:'틈을 잇고 아군을 보호하는 역할'},
  {id:'lilpa',name:'릴파',short:'릴',color:'#98b6f6',mark:'✧',power:'박쥐 편대',detail:'빠르게 적을 추적하는 역할'},
  {id:'jururu',name:'주르르',short:'주',color:'#ef9cbe',mark:'❀',power:'여우 유인',detail:'적을 모으고 흐름을 바꾸는 역할'},
  {id:'gosegu',name:'고세구',short:'세',color:'#97dbe6',mark:'◇',power:'세균단 분신',detail:'팀을 불려 여러 방향을 견제'},
  {id:'viichan',name:'비챤',short:'챤',color:'#a7e5ae',mark:'⚔',power:'집중 참격',detail:'타이밍에 맞춰 전방을 돌파'}
 ];
 let state={bestArcade:0,bestQuest:0,escapeUnlocked:1,escapeBest:{},volume:false};
 try{const x=JSON.parse(localStorage.getItem(K)||'null');if(x&&typeof x==='object'&&!Array.isArray(x))state={...state,...x}}catch{}
 let active='home',cleanup=[],messageTimer=null;
 const app=document.getElementById('app'),toastEl=document.getElementById('toast');
 function save(){try{localStorage.setItem(K,JSON.stringify(state))}catch{}}
 function esc(t){return String(t??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
 function toast(t){toastEl.textContent=t;toastEl.hidden=false;clearTimeout(messageTimer);messageTimer=setTimeout(()=>toastEl.hidden=true,3000)}
 function btn(text,action,style='secondary',props=''){return '<button type="button" class="'+style+'" data-action="'+esc(action)+'" '+props+'>'+text+'</button>'}
 function memberCard(m,sel=false){return '<div class="mini-avatar" style="--avatar:'+m.color+'">'+m.short+'</div>'}
 function metrics(items){return '<div class="metric-row">'+items.map(([label,v])=>'<div class="metric"><span class="value">'+esc(v)+'</span><small>'+esc(label)+'</small></div>').join('')+'</div>'}
 function getRoute(){const h=location.hash;return h.startsWith('#/')?h.slice(2).split('?')[0]:'home'}
 function navigate(path){const t='#/'+path;if(location.hash===t)render();else location.hash=t}
 function onCleanup(fn){cleanup.push(fn)}
 function stop(){cleanup.forEach(f=>{try{f()}catch{}});cleanup=[]}
 function home(){return '<section class="intro"><div><span class="overline">FAN GAME · THREE EXPERIENCES</span><h2>이세돌이라서 가능한<br>세 개의 작은 게임.</h2><p>멤버별 상황에 맞춰 반응하고, 다른 능력을 조합해 돌파하고, 함께 탈출해 보세요. 게임 속 설정은 모두 비공식 창작입니다.</p></div><div class="round-badge" aria-hidden="true">6 ✦</div></section>'+
 '<div class="section-head"><div><h2>어떤 게임부터 해볼까요?</h2><p>별도 설치 없이, PC와 모바일에서 바로 플레이합니다.</p></div></div>'+
 '<div class="game-list">'+[
 ['arcade','우당탕 이세돌','상황극 릴레이 · 12개 미션','멤버 여섯 명에게 각기 다른 조작 미션이 주어집니다. 6초 안에 미션을 완수하고 다음 상황으로!', '✺','arcade'],
 ['quest','세돌 원정대','캐릭터 액션 · 짧은 생존전','여섯 멤버 중 주인공과 동료를 선택하세요. 선택한 멤버에 따라 공격과 필살기가 달라집니다.','⚔','quest'],
 ['escape','이세돌 합방 탈출','협동 두뇌 퍼즐 · 8개 스테이지','아이네·징버거·릴파의 서로 다른 능력을 순서대로 활용해야 문을 열고 모두 탈출합니다.','▦','escape']
 ].map(([id,title,label,desc,art,cl])=>'<article class="game-card"><div class="game-art '+cl+'"><div class="art-dots"></div><div class="big" aria-hidden="true">'+art+'</div></div><div class="body"><span class="tag">'+label+'</span><h3>'+title+'</h3><p>'+desc+'</p><div class="card-foot"><small>'+({arcade:'반응 · 타이밍',quest:'움직임 · 조합',escape:'전략 · 협동'}[id])+'</small><a class="primary" href="#/'+id+'">플레이하기 →</a></div></div></article>').join('')+'</div>'+
 '<div class="caution">검토 원칙: 기존 팬게임의 이미지·코드·게임 데이터는 사용하지 않았습니다. 멤버명과 팬문화 소재에서 착안한 오리지널 규칙·도형·문장만 사용합니다.</div>';
 }
 function render(){
  stop();active=getRoute();if(!['home','arcade','quest','escape'].includes(active))active='home';
  document.querySelectorAll('[data-nav]').forEach(e=>{const y=e.getAttribute('data-nav')===active;e.classList.toggle('active',y);if(y)e.setAttribute('aria-current','page');else e.removeAttribute('aria-current')});
  if(active==='home')app.innerHTML=home();
  else if(active==='arcade')arcade.mount();
  else if(active==='quest')quest.mount();
  else escape.mount();
 }
 function key(e){if(e.target&&/input|textarea|select/i.test(e.target.tagName))return;const mod=active==='arcade'?arcade:active==='quest'?quest:active==='escape'?escape:null;if(mod?.key)mod.key(e)}
 let arcade={},quest={},escape={};
 function install(name,obj){if(name==='arcade')arcade=obj;if(name==='quest')quest=obj;if(name==='escape')escape=obj}
 window.addEventListener('hashchange',render);
 window.addEventListener('keydown',key);
 document.addEventListener('visibilitychange',()=>{if(document.hidden){if(arcade.visibility)arcade.visibility();if(quest.visibility)quest.visibility()}});
 document.querySelectorAll('.nav a').forEach(a=>a.addEventListener('click',()=>{if(location.hash===a.hash)render()}));
 return {MEMBERS,state,save,esc,toast,btn,memberCard,metrics,app,render,navigate,onCleanup,stop,install,get active(){return active}};
})();
