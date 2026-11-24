import { CHAPTERS, MEMBERS, FINALE } from './content.js';
import { enemyIntent } from './engine.js';
import { drawFieldProp } from './field.js';
import { TACTIC_COLS, TACTIC_ROWS, tacticalTerrain, tacticalActive, tacticalTarget, tacticalMoves, tacticalUnits, tacticalRange, tacticalApproach, tacticalFlank, tacticalEchoMax } from './tactics.js';

const tacticsFrame = { width:820, height:432, tileWidth:112, tileHeight:48 };
const tacticsPrevious = new WeakMap();
const tacticsPalettes = [
  {ground:'#8b7756',shine:'#ac9770',rim:'#554638',cover:'#72854e',flora:'lamp',edge:'tent'},
  {ground:'#96ad9d',shine:'#b9cabb',rim:'#536e6c',cover:'#748b72',flora:'pine',edge:'pine'},
  {ground:'#9a8386',shine:'#b89e9b',rim:'#605361',cover:'#807d72',flora:'lamp',edge:'house'},
  {ground:'#7d8295',shine:'#a0a8b6',rim:'#424859',cover:'#677c78',flora:'rock',edge:'lamp'},
  {ground:'#739378',shine:'#9bb297',rim:'#4a6052',cover:'#526f56',flora:'bush',edge:'pine'},
  {ground:'#8ca0a3',shine:'#a7babc',rim:'#536274',cover:'#72878a',flora:'rock',edge:'house'},
  {ground:'#a19875',shine:'#bbb48a',rim:'#62583e',cover:'#71885f',flora:'lamp',edge:'pine'}
];
const tacticsScenery = [
  ['speaker','spotlight','case','flag','booth'],
  ['pine','pine','rock','bush','blossom'],
  ['bookshop','stack','house','lamp','tree'],
  ['speaker','wing','case','flag','spotlight'],
  ['tent','tree','flag','booth','speaker'],
  ['bookshop','poster','house','bush','lamp'],
  ['flag','speaker','lamp','tent','spotlight']
];
const tacticsPoint = (x,y) => ({x:382+(x-y)*56,y:99+(x+y)*24});
const tacticsCoord = (x,y) => `${String.fromCharCode(65+x)}${y+1}`;
const tacticsUnitName = (state, id) => id === 'hero' ? '이파리' : id === 'leader' ? state.battle.name : id === 'echo' ? '수호자의 잔향' : MEMBERS[id].name;
const tacticsIsAlly = id => id !== 'leader' && id !== 'echo';
const tacticsCellName = (state,p) => tacticalTerrain(state,p.x,p.y) === '+' ? '엄폐지' : '평지';

function tacticsUnitButton(state,u,sprite,escape) {
  const ally = tacticsIsAlly(u.id), field = state.battle.field;
  const name = tacticsUnitName(state,u.id), command = ally ? 'select' : 'target';
  const selected = ally ? field.active === u.id : field.target === u.id;
  const spent = field.acted.includes(u.id);
  const art = ally && u.id !== 'hero' ? sprite('member',u.id) : sprite('cast', u.id === 'hero' ? 0 : u.id === 'echo' ? 1 : Math.min(7, state.chapter+1));
  const fill = ally ? state.player.hp / state.player.maxHp : u.id === 'leader' ? state.battle.hp / state.battle.maxHp : field.echo.hp / tacticalEchoMax(state);
  return `<button class="tac-unit ${ally ? 'tac-ally' : 'tac-enemy'} ${selected ? 'is-selected' : ''} ${spent ? 'is-spent' : ''} ${u.id === 'echo' ? 'tac-echo' : ''}" data-action="tactic" data-command="${command}" data-id="${u.id}" data-tac-pos data-x="${u.x}" data-y="${u.y}" aria-pressed="${selected}" aria-label="${escape(name)} · ${tacticsCoord(u.x,u.y)} · ${ally ? '아군 선택' : '공격 대상 지정'}" ${spent || state.mode !== 'battle' ? 'disabled' : ''}><span class="tac-base"></span>${art}<span class="tac-health"><i data-fill="${100*fill}"></i></span><span class="tac-pennant">${ally ? '아군' : '상대'}</span></button>`;
}

export function renderTacticalBattle(state, {sprite,world,escape,supportList,supportOpen}) {
  const b = state.battle, field = b.field, active = tacticalActive(state), target = tacticalTarget(state);
  const moves = tacticalMoves(state), intent = enemyIntent(state), playing = state.mode === 'battle';
  const targeting = tacticsUnitName(state,target.id), targetHp = target.id === 'echo' ? target.hp : b.hp;
  const fieldName = state.chapter === 6 ? FINALE.phases[b.phase] : CHAPTERS[state.chapter].locations[state.room];
  const tiles = moves.map(p => `<button class="tac-destination" data-action="tactic" data-command="move" data-tac-pos data-x="${p.x}" data-y="${p.y}" aria-label="${tacticsCoord(p.x,p.y)} ${tacticsCellName(state,p)}로 ${p.cost}칸 이동"></button>`).join('');
  const reach = tacticalRange(active), attack = tacticalApproach(state,reach);
  const name = tacticsUnitName(state,active.id);
  const buttons = playing ? `<div class="tac-commands" role="group" aria-label="전투 행동">
    <button class="tac-action tac-primary" data-action="battle" data-move="attack" ${attack ? '' : 'disabled'}><b>${attack?.cost ? '접근 공격' : '공격'}</b><small>${attack ? (tacticalFlank(state) ? '협공 +35%' : '사거리 '+reach+'칸') : '사거리 밖'}</small><kbd>1</kbd></button>
    <button class="tac-action" data-action="battle" data-move="defend"><b>방어</b><small>피해 76% 감소</small><kbd>2</kbd></button>
    <button class="tac-action" data-action="battle" data-move="cheer"><b>응원</b><small>체력 +5</small><kbd>3</kbd></button>
    <button class="tac-action" data-action="support-toggle" aria-expanded="${supportOpen}"><b>지원기</b><small>응원 2 소모</small><kbd>4</kbd></button></div>` : '';
  const roll = field.allies.map(u => `<button class="tac-roll-unit" data-action="tactic" data-command="select" data-id="${u.id}" aria-pressed="${u.id === active.id}" ${field.acted.includes(u.id) || !playing ? 'disabled' : ''}>${escape(tacticsUnitName(state,u.id))}${field.acted.includes(u.id) ? ' ✓' : ''}</button>`).join('');
  const moveList = playing ? `<details class="tac-move-list"><summary>이동 칸 목록</summary><div>${moves.length ? moves.map(p => `<button data-action="tactic" data-command="move" data-x="${p.x}" data-y="${p.y}">${tacticsCoord(p.x,p.y)} · ${tacticsCellName(state,p)}</button>`).join('') : '이번 차례의 이동을 마쳤습니다.'}</div></details>` : '';
  return `<section class="tac-panel" aria-label="전술 전장"><header class="tac-heading"><div><span>${escape(fieldName)}</span><h2>${escape(b.name)}</h2></div><div class="tac-turn"><strong>${b.turn+1}턴</strong><span>${playing ? '아군 차례' : '전투 종료'}</span></div></header>
  <div class="tac-field">${world(state.chapter)}<div class="tac-surface"><canvas class="tac-art" width="820" height="432" aria-hidden="true"></canvas><div class="tac-pieces" role="group" aria-label="전장 배치">${playing ? tiles : ''}${tacticalUnits(state).map(u=>tacticsUnitButton(state,u,sprite,escape)).join('')}</div></div></div>
  <div class="tac-legend"><span><i class="tac-legend-move"></i>이동 가능</span><span><i class="tac-legend-cover"></i>엄폐 · 피해 35% 감소</span></div>
  <div class="tac-orders"><div class="tac-command-status"><div class="tac-roll" role="group" aria-label="행동할 아군">${roll}</div><span class="tac-target-status">목표 · <b>${escape(targeting)}</b> ${targetHp} HP</span></div>
  <p>${playing ? `${escape(name)}${active.id === 'hero' ? '의 행동 뒤에는 상대가 움직입니다. 동료가 먼저 행동할 수 있어요.' : '의 행동 뒤에도 이파리가 움직일 수 있습니다.'} ${field.moved.includes(active.id) ? '이동 완료.' : '밝은 칸을 누르면 이동합니다.'}` : '일행이 잠시 물러납니다.'}</p>
  ${buttons}${supportList}${moveList}</div>
  <div class="tac-intent"><b>상대 예고</b><span><strong>${escape(intent.name)}</strong> · ${escape(intent.text)}</span></div></section>
  <div class="battle-log" aria-label="전투 기록">${state.log.slice(0,4).reverse().map(line=>`<p>${escape(line)}</p>`).join('')}</div>`;
}

function tacticsShape(ctx,points,fill,stroke) {
  ctx.beginPath(); ctx.moveTo(...points[0]);
  for (const p of points.slice(1)) ctx.lineTo(...p);
  ctx.closePath(); ctx.fillStyle=fill; ctx.fill();
  if (stroke) { ctx.strokeStyle=stroke; ctx.stroke(); }
}

function paintTacticalField(ctx,state) {
  const pal = tacticsPalettes[state.chapter];
  const moves = new Set(tacticalMoves(state).map(p=>p.y*7+p.x));
  ctx.clearRect(0,0,tacticsFrame.width,tacticsFrame.height);
  const random = seed => { let v=seed+1; return () => {v=(Math.imul(v,1664525)+1013904223)>>>0;return v/4294967296;}; };
  const prop = (kind,p,size,variant) => {
    ctx.save(); drawFieldProp(ctx,kind,p.x,p.y,size,state.chapter,variant); ctx.restore();
  };
  const scenery=tacticsScenery[state.chapter];
  // Two raised verges frame the back of the playable ground. Dress them
  // with the actual venue's equipment, buildings or winter canopy.
  for(let rank=0;rank<8;rank++) {
    const borders=[];
    if(rank<7) borders.push([rank,-.86]);
    if(rank<6) borders.push([-.86,rank]);
    for(const [x,y] of borders) {
      const {x:u,y:v}=tacticsPoint(x,y);
      tacticsShape(ctx,[[u,v-19],[u+51,v],[u,v+21],[u-51,v]],pal.cover,pal.rim);
      tacticsShape(ctx,[[u-51,v],[u,v+21],[u,v+32],[u-51,v+10]],pal.rim);
      const n=rank*3+(x<0 ? 1 : 0), kind=scenery[n%scenery.length];
      prop(kind,{x:u-9,y:v+1},rank===0 ? 53 : 68+(n%3)*9,n%4);
      prop(state.chapter===1 ? 'pine' : state.chapter===2 ? 'stack' : 'bush',{x:u+17,y:v+8},state.chapter===1 ? 57 : 31,(n+1)%4);
    }
  }
  for (let y=0;y<6;y++) for (let x=0;x<7;x++) {
    const {x:px,y:py}=tacticsPoint(x,y), kind=tacticalTerrain(state,x,y);
    const p0=[px,py-24],p1=[px+56,py],p2=[px,py+24],p3=[px-56,py];
    if (x===6) tacticsShape(ctx,[p1,p2,[px,py+37],[px+56,py+13]],pal.rim,'#302f334a');
    if (y===5) tacticsShape(ctx,[p2,p3,[px-56,py+13],[px,py+37]],pal.rim,'#302f334a');
    const fringe=kind==='#' || kind==='+';
    tacticsShape(ctx,[p0,p1,p2,p3],fringe ? pal.cover : pal.ground,'#17272058');
    const rand=random(87+x*1117+y*523+state.chapter*793);
    if (!fringe && ![1,4].includes(state.chapter)) {
      const point=(a,c)=>[px+(a-c)*56,py+(a+c-1)*24];
      const rows=state.chapter===0 ? 4 : 3;
      for(let row=0;row<rows;row++) for(let segment=-1;segment<2;segment++) {
        const off=(row+y*rows)%2*.25;
        const left=Math.max(0,segment*.5+off),right=Math.min(1,(segment+1)*.5+off);
        if(right<=left) continue;
        const near=row/rows,far=(row+1)/rows;
        tacticsShape(ctx,[point(left,near),point(right,near),point(right,far),point(left,far)],
          rand()>.5 ? '#f1e3ae19' : '#281e2714','#3d413043');
      }
    }
    for (let j=0;j<(fringe ? 65 : 24);j++) {
      const a=rand()-.5,c=rand()-.5, u=px+(a-c)*52, v=py+(a+c)*22;
      ctx.fillStyle = j%3 ? '#312b2930' : pal.shine;
      ctx.fillRect(Math.round(u),Math.round(v),2+Math.floor(rand()*5),1+Math.floor(rand()*2));
    }
    if (state.chapter===1 && !fringe && (x+y)%3===0) {
      for(let j=0;j<9;j++) {
        const a=px-20+rand()*32,c=py-7+rand()*11;
        tacticsShape(ctx,[[a-7,c],[a-1,c-2],[a+8,c],[a+2,c+2]],'#e5e9de9c');
      }
    }
    if (moves.has(y*7+x) && state.mode==='battle') {
      ctx.lineWidth=1.8;
      tacticsShape(ctx,[[px,py-21],[px+50,py],[px,py+21],[px-50,py]],'#99e7c12c','#c4f7caaf');
      ctx.lineWidth=1;
    }
    if (kind==='+') {
      // Packed, mossy cover with a low stone breastwork on its far edge.
      for(let i=0;i<5;i++) {
        const u=px-31+i*7,v=py-9-i*2;
        tacticsShape(ctx,[[u-4,v],[u,v-5],[u+5,v-4],[u+6,v],[u+1,v+2]],pal.shine,pal.rim);
      }
    }
  }
  // Dressing is painted back to front after the complete ground plane so
  // adjacent floor faces do not erase the silhouettes of upright props.
  for (let rank=0;rank<12;rank++) for (let y=0;y<TACTIC_ROWS;y++) {
    const x=rank-y;
    if(x<0 || x>=TACTIC_COLS || tacticalTerrain(state,x,y)!=='#') continue;
    const p=tacticsPoint(x,y);
    prop((x===0 || y===0) ? pal.edge : scenery[(x+2*y)%scenery.length],p,(x===0 || y===0) ? 74 : 57,x+y);
  }
}

export function mountTacticalBattle(root,state) {
  const canvas=root.querySelector('.tac-art');
  if (!canvas || !state.battle) return;
  paintTacticalField(canvas.getContext('2d'),state);
  for (const el of root.querySelectorAll('[data-tac-pos]')) {
    const x=Number(el.dataset.x), y=Number(el.dataset.y), p=tacticsPoint(x,y);
    el.style.left=p.x/tacticsFrame.width*100+'%'; el.style.top=p.y/tacticsFrame.height*100+'%';
    if(el.classList.contains('tac-unit')) el.style.zIndex=String(5+x+y);
  }
  const before=tacticsPrevious.get(root);
  tacticsPrevious.set(root,state);
  if (!before || before.battle.id!==state.battle.id || before.battle.phase!==state.battle.phase ||
      state.battle.turn<before.battle.turn || document.documentElement.dataset.reducedMotion==='true' ||
      window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  const field=root.querySelector('.tac-pieces'), bounds=field.getBoundingClientRect();
  const prior=tacticalUnits(before);
  for(const unit of tacticalUnits(state)) {
    const old=prior.find(u=>u.id===unit.id);
    const el=field.querySelector(`[data-id="${unit.id}"]`);
    if (!el || !old || (old.x===unit.x && old.y===unit.y)) continue;
    const a=tacticsPoint(old.x,old.y), z=tacticsPoint(unit.x,unit.y);
    const dx=(a.x-z.x)*bounds.width/tacticsFrame.width, dy=(a.y-z.y)*bounds.height/tacticsFrame.height;
    el.animate([{translate:`${dx}px ${dy}px`},{translate:'0 0'}],
      {duration:230,delay:tacticsIsAlly(unit.id) ? 0 : 130,fill:'backwards',easing:'ease-out'});
  }
  const leaderLoss=before.battle.hp-state.battle.hp, partyLoss=before.player.hp-state.player.hp;
  const echoLoss=(before.battle.field.echo?.hp || 0)-(state.battle.field.echo?.hp || 0);
  const pop=(unit,label,enemy) => {
    const p=tacticsPoint(unit.x,unit.y);
    const notice=document.createElement('span');
    notice.className='tac-pop'; notice.textContent=label; notice.setAttribute('aria-hidden','true');
    notice.style.left=p.x/tacticsFrame.width*100+'%'; notice.style.top=(p.y-70)/tacticsFrame.height*100+'%';
    field.append(notice);
    const animation=notice.animate([{opacity:0,translate:'-50% 5px'},{opacity:1,offset:.15},{opacity:1,offset:.72},{opacity:0,translate:'-50% -12px'}],
      {duration:800,delay:enemy ? 320 : 120,fill:'both'});
    animation.onfinish=()=>notice.remove();
  };
  if(leaderLoss>0) pop(state.battle.field.leader,'−'+leaderLoss,false);
  if(echoLoss>0) pop(state.battle.field.echo,'−'+echoLoss,false);
  if(partyLoss>0) pop(state.battle.field.allies[0],'일행 −'+partyLoss,true);
}
