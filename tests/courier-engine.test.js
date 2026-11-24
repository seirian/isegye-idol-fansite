import test from 'node:test';
import assert from 'node:assert/strict';
import '../fangames/engine.js';

const Engine = globalThis.CourierEngine;
const frame = 1 / 60;

function advance(state, seconds, input = {}) {
  for (let time = 0; time < seconds - 1e-8; time += frame) {
    Engine.update(state, Math.min(frame, seconds - time), input);
  }
}

function routeTo(state, target, maxSeconds = 10) {
  for (let frames = 0; frames < maxSeconds * 60; frames += 1) {
    const dx = target.x - state.x, dy = target.y - state.y;
    const distance = Math.hypot(dx, dy);
    if (distance < 6 || state.mode !== 'playing') return;
    Engine.update(state, frame, { x: dx / distance, y: dy / distance });
  }
}

test('seeded rounds and replays are deterministic, with safe and reachable entrances', () => {
  const one = Engine.create('jing', 'same-round');
  const two = Engine.create('jing', 'same-round');
  assert.deepEqual(one, two);
  for (const enemy of one.enemies) {
    assert.ok(Math.hypot(enemy.x - one.x, enemy.y - one.y) > 180);
    assert.ok(enemy.spawnTime >= 1.25);
    assert.ok(enemy.x >= one.arena.bounds.left && enemy.x <= one.arena.bounds.right);
    assert.ok(enemy.y >= one.arena.bounds.top && enemy.y <= one.arena.bounds.bottom);
    for (const other of one.enemies) {
      if (other.id !== enemy.id) assert.ok(Math.hypot(other.x - enemy.x, other.y - enemy.y) > 58);
    }
  }
  for (const letter of one.stars) {
    assert.ok(letter.x >= one.arena.bounds.left && letter.x <= one.arena.bounds.right);
    assert.ok(letter.y >= one.arena.bounds.top && letter.y <= one.arena.bounds.bottom);
  }
  for (let index = 0; index < 180; index += 1) {
    const input = { x: Math.sin(index / 40), y: Math.cos(index / 40) };
    Engine.update(one, frame, input);
    Engine.update(two, frame, input);
  }
  assert.deepEqual(one, two);
  assert.notDeepEqual(Engine.create('jing', 11).stars, Engine.create('jing', 12).stars);
});

test('movement normalizes diagonals and bounds delayed or invalid frames', () => {
  const start=Engine.ROUTES[0].start;
  const bounds=Engine.ROUTES[0].arena.bounds;
  const straight = Engine.create('ine', 20);
  const diagonal = Engine.create('ine', 20);
  advance(straight, 0.5, { x: 1, y: 0 });
  advance(diagonal, 0.5, { x: 1, y: 1 });
  assert.ok(Math.abs(Math.hypot(diagonal.x - start.x, diagonal.y - start.y) - (straight.x - start.x)) < 1e-8);
  const saved = structuredClone(straight);
  for (const dt of [NaN, Infinity, -1, 0]) Engine.update(straight, dt, { x: 1 });
  assert.deepEqual(straight, saved);
  Engine.update(straight, 999, { x: 1 });
  assert.ok(Math.abs(straight.timeLeft - (saved.timeLeft - 0.1)) < 1e-8);
  straight.x = bounds.right-60;
  advance(straight, .5, { x: 1, y: 0 });
  assert.equal(straight.x, bounds.right);
  Engine.update(straight, frame, { x: NaN, y: Infinity });
  assert.ok(Number.isFinite(straight.x) && Number.isFinite(straight.y));
  for (const [x, y, dir] of [
    [bounds.left, start.y, { x: -1, y: 0 }],
    [bounds.right, start.y, { x: 1, y: 0 }],
    [start.x, bounds.top, { x: 0, y: -1 }],
    [start.x, bounds.bottom, { x: 0, y: 1 }]
  ]) {
    const edge = Engine.create('gosegu', 24);
    edge.x = x; edge.y = y; edge.dir = dir;
    Engine.dash(edge);
    advance(edge, 0.2, dir);
    assert.equal(edge.x, x);
    assert.equal(edge.y, y);
    edge.enemies[0].x = x; edge.enemies[0].y = y;
    Engine.skill(edge);
    for (const enemy of edge.enemies) {
      assert.ok(enemy.x >= bounds.left && enemy.x <= bounds.right);
      assert.ok(enemy.y >= bounds.top && enemy.y <= bounds.bottom);
    }
  }
});

test('a genuine collection route delivers, pauses for a choice and resumes the next wave', () => {
  const state = Engine.create('ine', 21);
  while (state.cargo < state.required) {
    const next = state.stars.toSorted((a, b) => Math.hypot(a.x - state.x, a.y - state.y) - Math.hypot(b.x - state.x, b.y - state.y))[0];
    routeTo(state, next);
  }
  assert.ok(state.stats.letters >= 8);
  routeTo(state, state.beacon);
  assert.equal(state.mode, 'upgrade');
  assert.equal(state.deliveries, 1);
  assert.equal(state.stage, 0);
  assert.equal(state.required, 8);
  assert.equal(state.cargo, state.required);
  assert.deepEqual(state.beacon,Engine.ROUTES[0].beacon);
  const paused = structuredClone(state);
  advance(state, 15, { x: 1, y: 1 });
  assert.deepEqual(state, paused);
  assert.equal(Engine.dash(state), false);
  assert.equal(Engine.skill(state), false);
  assert.equal(Engine.chooseUpgrade(state, 'invalid'), false);
  assert.equal(state.mode, 'upgrade');
  const draft=[...state.draft];
  assert.equal(new Set(draft).size,3);
  assert.equal(Engine.chooseUpgrade(state,Engine.UPGRADES.find(u=>!draft.includes(u.id)).id),false);
  assert.equal(Engine.chooseUpgrade(state,draft[0]), true);
  assert.equal(state.mode, 'playing');
  assert.equal(state.stage,1);
  assert.equal(state.required,10);
  assert.equal(state.cargo,0);
  assert.deepEqual({x:state.x,y:state.y},Engine.ROUTES[1].start);
  assert.ok(state.enemies.length >= 4);
  assert.ok(state.upgrades.includes(draft[0]));
  assert.deepEqual(state.beacon,Engine.ROUTES[1].beacon);
  assert.equal(state.timeLeft, Engine.ROUTES[1].time);
  assert.equal(Engine.chooseUpgrade(state, 'shield'), false);
});

test('damage drops a recoverable letter, breaks the combo, and grants invulnerability', () => {
  const state = Engine.create('jing', 30);
  state.cargo = 3; state.combo = 3; state.comboTime = 3;
  state.invulnerableTime = 0;
  state.enemies = [{ id: 100, x: state.x+1, y: state.y, kind: 'jelly', hp:90, speed: 0, phase: 0, spawnTime: 0, stunTime: 0, radius: 20 }];
  const beforeLetters = state.stars.length;
  Engine.update(state, frame, {});
  assert.equal(state.hearts, 2);
  assert.equal(state.cargo, 2);
  assert.equal(state.combo, 0);
  assert.equal(state.stars.length, beforeLetters + 1);
  assert.ok(state.stars.at(-1).availableAt > state.elapsed);
  assert.ok(state.invulnerableTime > 1.5);
  state.enemies[0].x = state.x;
  state.enemies[0].y = state.y;
  state.enemies[0].stunTime = 0;
  Engine.update(state, frame, {});
  assert.equal(state.hearts, 2);
  assert.equal(state.stats.hits, 1);
  assert.ok(state.events.some((event) => event.type === 'hit'));
});

test('each stage has an independent seeded field and entrance; only the run build and history travel', () => {
  const starts=new Set(), mailboxes=new Set();
  for (const [index,route] of Engine.ROUTES.entries()) {
    starts.add(JSON.stringify(route.start)); mailboxes.add(JSON.stringify(route.beacon));
    assert.ok(Math.hypot(route.start.x-route.beacon.x,route.start.y-route.beacon.y)>500);
    if (!index) continue;
    const oldRoute=Engine.ROUTES[index-1], previous=Engine.create('jing',648);
    Object.assign(previous,{
      mode:'upgrade', stage:index-1, deliveries:index, beacon:oldRoute.beacon,
      x:oldRoute.beacon.x,y:oldRoute.beacon.y,required:oldRoute.goal,cargo:oldRoute.goal,
      hearts:2,maxHearts:5,score:6578,speedBonus:.14,upgrades:['speed'],draft:['quill'],
      shieldTime:3,hasteTime:1,slowTime:2,magnetTime:3,dashTime:.1,combo:4,comboTime:3,
      dashCooldown:2,skillCooldown:7,nearBeacon:true,_stageShots:3,
      projectiles:[{id:'old'}],hazards:[{id:'old'}],enemies:[{id:'old'}],stars:[{id:'old'}],
      events:[{type:'hit'}],_velocity:{x:720,y:0},_dashDir:{x:1,y:0}
    });
    previous.stats.kills=35; previous.maxCombo=8;
    const snapshot=structuredClone(previous);
    advance(previous,.5,{x:1,y:1});
    assert.deepEqual(previous,snapshot,'draft freezes the completed field');
    // Variation in the previous encounter's RNG consumption or exit position
    // cannot shift the next route's entrances, enemies, hazards, or envelopes.
    const alternative=structuredClone(previous);
    alternative.x-=30; alternative.y+=20; alternative._rng=99999999;
    for(const s of [previous,alternative]) {
      assert.equal(Engine.chooseUpgrade(s,'quill'),true);
      assert.equal(s.stage,index);
      assert.equal(s.deliveries,index);
      assert.deepEqual({x:s.x,y:s.y},route.start);
      assert.ok(Math.hypot(s.x-oldRoute.beacon.x,s.y-oldRoute.beacon.y)>150);
      assert.deepEqual(s.beacon,route.beacon);
      assert.deepEqual(s.arena,route.arena);
      const b=route.arena.bounds;
      for(const point of [s,s.beacon,...s.stars,...s.enemies,...(s.boss?[s.boss]:[])]) {
        assert.ok(point.x>=b.left && point.x<=b.right && point.y>=b.top && point.y<=b.bottom);
      }
      assert.equal(s.required,route.goal);
      assert.equal(s.timeLeft,route.time);
      for(const key of ['stageElapsed','cargo','dashTime','dashCooldown','skillCooldown','shieldTime','hasteTime',
        'slowTime','magnetTime','combo','comboTime','_stageShots']) assert.equal(s[key],0,key);
      assert.equal(s.nearBeacon,false);
      assert.equal(s.invulnerableTime,1.2);
      assert.deepEqual(s._velocity,{x:0,y:0});
      assert.deepEqual(s.projectiles,[]); assert.deepEqual(s.hazards,[]);
      assert.ok(s.enemies.length>0 && !s.enemies.some(e=>e.id==='old'));
      assert.ok(s.stars.length>=route.goal && !s.stars.some(l=>l.id==='old'));
      assert.deepEqual(s.events.map(e=>e.type),route.boss ? ['stage','boss','upgrade'] : ['stage','upgrade']);
      assert.equal(s.events[0].x,route.start.x);
      assert.equal(s.score,6578); assert.equal(s.stats.kills,35);
      assert.equal(s.hearts,2); assert.equal(s.maxHearts,5); assert.equal(s.maxCombo,8);
      assert.deepEqual(s.upgrades,['speed','quill']);
    }
    assert.deepEqual(previous.stars,alternative.stars);
    assert.deepEqual(previous.enemies,alternative.enemies);
  }
  assert.equal(starts.size,10);
  assert.equal(mailboxes.size,10);
});

test('dash is a finite directional burst with cooldown and damage protection', () => {
  const state = Engine.create('gosegu', 31);
  const startX = state.x;
  state.invulnerableTime = 0;
  state.enemies = [{ id: 100, x: state.x+10, y: state.y, kind: 'jelly', hp:90, speed: 0, phase: 0, spawnTime: 0, stunTime: 0, radius: 20 }];
  state.dir = { x: 1, y: 0 };
  assert.equal(Engine.dash(state), true);
  assert.equal(Engine.dash(state), false);
  advance(state, 0.2);
  assert.ok(state.x > startX+130);
  assert.equal(state.hearts, 3);
  assert.equal(state.dashTime, 0);
  assert.ok(state.dashCooldown > 2);
  advance(state, 2.2);
  assert.equal(Engine.dash(state), true);
  assert.equal(state.stats.dashes, 2);
});

test('all six skills have distinct live effects and enforce cooldowns', () => {
  for (const member of Engine.MEMBER_LIST) {
    const state = Engine.create(member.id, 40);
    state.hearts = 2;
    state.enemies[0].x = state.x + 100;
    state.enemies[0].y = state.y;
    assert.equal(Engine.skill(state), true);
    assert.equal(Engine.skill(state), false);
    assert.equal(state.skillCooldown, member.cooldown);
    assert.equal(state.events.find(e=>e.type==='skill').restoredHealth,member.id==='viichan' ? 1 : 0);
    switch (member.id) {
      case 'ine': assert.equal(state.shieldTime, 4); assert.ok(state.enemies[0].x > state.x + 150); break;
      case 'jing': assert.equal(state.slowTime, 5); break;
      case 'lilpa': assert.equal(state.hasteTime, 4); assert.equal(state.shieldTime, 1); break;
      case 'jururu': assert.equal(state.magnetTime, 4); break;
      case 'gosegu': assert.equal(state.enemies[0].stunTime, 3.2); assert.ok(state.enemies[0].x > state.x + 200); break;
      case 'viichan': assert.equal(state.hearts, 3); assert.equal(state.magnetTime, 2); break;
    }
    assert.equal(state.stats.skills, 1);
    assert.ok(state.events.some((event) => event.type === 'skill' && event.member === member.id));
  }
  const healthy = Engine.create('viichan', 41);
  Engine.skill(healthy);
  assert.equal(healthy.hearts, healthy.maxHearts);
  assert.equal(healthy.shieldTime, 3);
  assert.equal(healthy.events.find(e=>e.type==='skill').restoredHealth,0);
});

test('magnet skill collects distant letters and haste increases real travel', () => {
  const magnetic = Engine.create('jururu', 44);
  const ordinary = Engine.create('jururu', 44);
  magnetic.stars = [{ id: 90, x: magnetic.x+130, y: magnetic.y, kind: 'letter', availableAt: 0 }];
  ordinary.stars = structuredClone(magnetic.stars);
  Engine.skill(magnetic);
  advance(magnetic, 0.8);
  advance(ordinary, 0.8);
  assert.equal(magnetic.cargo, 1);
  assert.equal(ordinary.cargo, 0);
  const fast = Engine.create('lilpa', 45);
  const regular = Engine.create('lilpa', 45);
  Engine.skill(fast);
  advance(fast, 0.5, { x: 1 });
  advance(regular, 0.5, { x: 1 });
  assert.ok(fast.x - Engine.ROUTES[0].start.x > (regular.x - Engine.ROUTES[0].start.x) * 1.49);
});

test('timer and final heart have distinct terminal results that freeze the simulation', () => {
  const timed = Engine.create('ine', 50);
  timed.timeLeft = 0.02;
  advance(timed, 0.1);
  assert.equal(timed.mode, 'lost');
  assert.equal(timed.lossReason, 'time');
  assert.equal(timed.timeLeft, 0);
  const saved = structuredClone(timed);
  advance(timed, 10, { x: 1 });
  assert.deepEqual(timed, saved);
  const hurt = Engine.create('ine', 51);
  hurt.hearts = 1; hurt.invulnerableTime = 0;
  hurt.enemies = [{ id: 100, x: hurt.x+1, y: hurt.y, kind: 'jelly', hp:90, speed: 0, phase: 0, spawnTime: 0, stunTime: 0, radius: 20 }];
  Engine.update(hurt, frame);
  assert.equal(hurt.mode, 'lost');
  assert.equal(hurt.lossReason, 'hearts');
  assert.equal(hurt.hearts, 0);
});

// Isolate one stage for mechanical comparisons; the complete-campaign test
// below enters every stage using collection, movement and actual deliveries.
function stageFixture(stage, loadout = [], choice = 'magnet', difficulty = 'easy') {
  const s=Engine.create('ine',817,difficulty);
  s.mode='upgrade'; s.deliveries=stage; s.stage=Math.max(0,stage-1);
  s.upgrades=[...loadout]; s.draft=[choice];
  assert.ok(Engine.chooseUpgrade(s,choice));
  return s;
}

test('default and explicit easy reproduce the original seeded round and random sequence', () => {
  assert.deepEqual(Object.keys(Engine.DIFFICULTIES),['easy','normal','hard']);
  const original=Engine.create('ine',770);
  for (const input of ['easy',null,'__proto__','legendary',{}]) {
    assert.deepEqual(Engine.create('ine',770,input),original);
  }
  assert.equal(original.difficulty,'easy');
  assert.equal(original._rng,3591614899);
  // Frozen gameplay trace from the previous release, including movement,
  // one dash and one skill. No new attack decision may consume easy's RNG.
  for (let i=0;i<300;i++) {
    if (i===42) Engine.dash(original);
    if (i===160) Engine.skill(original);
    Engine.update(original,1/30,{x:Math.cos(i/90),y:Math.sin(i/65)});
  }
  assert.equal(original._rng,2200061165);
  assert.deepEqual([original.hearts,original.score,original.stats.letters,original.stats.shots],[3,170,2,4]);
  assert.deepEqual(original.enemies.slice(0,3).map(e=>[e.kind,Math.round(e.x),Math.round(e.y)]),
    [['jelly',908,998],['jelly',1372,1368],['jelly',1154,1535]]);
});

test('difficulty changes enemy and boss pace while retaining route layout, HP, quotas and reward offers', () => {
  for (const stage of [0,3,6,9]) {
    const easy=stageFixture(stage);
    for (const [level,speed] of [['normal',1.18],['hard',1.36]]) {
      const s=stageFixture(stage,[],'magnet',level);
      assert.equal(s.difficulty,level);
      assert.ok(Engine.DIFFICULTIES[level].name && Engine.DIFFICULTIES[level].description);
      assert.deepEqual(s.stars,easy.stars);
      assert.equal(s.hearts,easy.hearts); assert.equal(s.timeLeft,easy.timeLeft);
      assert.equal(s.required,easy.required); assert.equal(s._rng,easy._rng);
      assert.deepEqual(s.enemies,easy.enemies.map(e=>({...e,speed:e.speed*speed})));
      if (s.boss) assert.deepEqual(s.boss,{...easy.boss,speed:easy.boss.speed*speed});
      if (stage===0) {
        const original=structuredClone(easy);
        for (const runner of [original,s]) {
          runner.x=runner.beacon.x; runner.y=runner.beacon.y; runner.cargo=runner.required;
          Engine.update(runner,frame);
        }
        assert.deepEqual(s.draft,original.draft);
        Engine.chooseUpgrade(s,s.draft[0]);
        assert.equal(s.difficulty,level); assert.equal(s.stage,1);
      }
    }
  }
});

test('jelly springs stay in their warned lane, can be avoided or interrupted, and have a simultaneous cap', () => {
  for (const level of ['easy','normal','hard']) {
    const s=Engine.create('ine',770,level);
    Object.assign(s,{x:1000,y:800,spawnIn:60,attackIn:60,invulnerableTime:0});
    const jelly=s.enemies.find(e=>e.kind==='jelly');
    s.enemies=Array.from({length:3},(_,i)=>({...jelly,id:180+i,x:825,y:800+50*i,spawnTime:0,attackTime:0}));
    Engine.update(s,1/120);
    const lanes=s.hazards.filter(h=>h.pattern==='spring');
    assert.equal(lanes.length,{easy:0,normal:1,hard:2}[level]);
    if (level==='easy') continue;
    const lane=lanes[0];
    assert.ok(lane.charge && lane.delay>.8);
    s.enemies=s.enemies.filter(e=>e.id===lane.source); s.hazards=[lane];
    const hit=structuredClone(s), interrupted=structuredClone(s);
    advance(hit,lane.windup+.45);
    assert.equal(hit.stats.hits,1,'a courier who stands in the lane gets hit');
    advance(s,.6,{y:1});
    assert.equal(s.enemies[0].x,825,'the wind-up holds the spring in place');
    advance(s,.9,{y:1});
    assert.equal(s.stats.hits,0);
    assert.ok(s.enemies[0].x>960,'the jelly travels down the original line');
    interrupted.member='gosegu'; Engine.skill(interrupted); Engine.update(interrupted,frame);
    assert.equal(interrupted.hazards.length,0);
  }
});

test('hard hex locks a visible second stamp ahead of the courier; reversing direction avoids both', () => {
  for (const level of ['normal','hard']) {
    const s=stageFixture(2,[],'magnet',level);
    Object.assign(s,{x:1000,y:800,spawnIn:60,attackIn:60,invulnerableTime:0});
    s.enemies=[{...s.enemies[0],kind:'hex',x:800,y:800,spawnTime:0,attackTime:0}];
    Engine.update(s,1/120,{x:1});
    assert.equal(s.hazards.length,level==='hard' ? 2 : 1);
    if (level==='normal') continue;
    const [first,second]=s.hazards;
    assert.equal(second.pattern,'echo');
    assert.equal(second.x-first.x,104); assert.equal(first.y,second.y);
    assert.ok(second.windup>first.windup && second.delay>1.7);
    const waiting=structuredClone(s);
    waiting.x=second.x; waiting.y=second.y; waiting.enemies=[];
    advance(waiting,1.65); assert.equal(waiting.stats.hits,0);
    advance(waiting,.4); assert.equal(waiting.stats.hits,1);
    advance(s,2.2,{y:1});
    assert.equal(s.stats.hits,0);
  }
});

test('the three bosses telegraph different side attacks, stagger the opposite flank on hard, and keep safe ground', () => {
  for (const [stage,kind] of [[3,'line'],[6,'circle'],[9,'line']]) {
    for (const level of ['easy','normal','hard']) {
      const s=stageFixture(stage,[],'magnet',level);
      const b=s.boss;
      Object.assign(s,{x:b.x-175,y:b.y,spawnIn:60,attackIn:60,invulnerableTime:0,enemies:[]});
      Object.assign(b,{spawnTime:0,attackTime:0});
      Engine.update(s,1/120);
      const marks=s.hazards.filter(h=>h.pattern==='echo');
      assert.equal(marks.length,{easy:0,normal:1,hard:2}[level]);
      assert.ok(marks.every(h=>h.source===b.id && h.kind===kind && h.delay>1.7));
      if (level==='easy') continue;
      assert.ok(marks.every(h=>!h.charge),'only the principal charge moves the Warden');
      if (level==='hard') assert.ok(marks[1].delay-marks[0].delay>.5);
      if (stage===3) assert.equal(Math.round(Math.abs(marks[0].y-b.y)),96);
      if (stage===6) assert.equal(Math.round(Math.abs(marks[0].y-s.y)),83);
      if (stage===9) assert.ok(Math.abs(Math.sin(marks[0].angle))>.3);
      advance(s,.35); assert.equal(s.stats.hits,0);
      advance(s,2.5,{y:stage===6 ? -1 : 1});
      assert.equal(s.stats.hits,0,`${level} stage ${stage+1}: stepping sideways clears the marks`);
    }
  }
});

test('mid-route sealed parcels split into vulnerable motes after an arrival warning, with bounded swarm size', () => {
  for(let stage=0;stage<4;stage++) assert.ok(stageFixture(stage).enemies.every(e=>e.kind!=='parcel'));
  const s=stageFixture(4,['shield'],'speed');
  const parcel=s.enemies.find(e=>e.kind==='parcel');
  assert.ok(parcel);
  Object.assign(parcel,{x:s.x+55,y:s.y,hp:1,spawnTime:0});
  s.enemies=[parcel];
  assert.ok(Engine.dash(s));
  const motes=s.enemies.filter(e=>e.small);
  assert.equal(motes.length,2);
  assert.ok(motes.every(e=>e.kind==='mote' && e.hp===7 && e.spawnTime>1 && e.radius<parcel.radius));
  assert.ok(s.events.some(e=>e.type==='split' && e.count===2));
  assert.equal(s.stats.kills,1);
  const crowded=stageFixture(8,['shield'],'speed');
  const body={...parcel,x:crowded.x+35,y:crowded.y,hp:1,spawnTime:0};
  crowded.enemies=Array.from({length:26},(_,i)=>({...body,id:100+i}));
  Engine.dash(crowded);
  assert.equal(crowded.enemies.filter(e=>e.hp>0).length,28,'many simultaneous splits obey the late-stage hard cap');
});

test('late interceptors predict a diagonal approach then commit to one dodgeable, interruptible lane', () => {
  for(let stage=0;stage<7;stage++) assert.ok(stageFixture(stage).enemies.every(e=>e.kind!=='interceptor'));
  const s=stageFixture(7);
  const enemy=s.enemies.find(e=>e.kind==='interceptor');
  assert.ok(enemy);
  s.x=900; s.y=600; s.shieldTime=0; s.invulnerableTime=0; s.attackIn=60; s.spawnIn=60;
  Object.assign(enemy,{x:720,y:480,spawnTime:0,attackTime:0});
  s.enemies=[enemy];
  Engine.update(s,1/120,{x:1});
  const h=s.hazards.find(h=>h.source===enemy.id);
  assert.equal(h.kind,'line');
  assert.ok(h.charge && h.delay>.9);
  assert.ok(h.angle<Math.atan2(s.y-enemy.y,s.x-enemy.x)-.08,'aim leads the moving player');
  const interrupted=structuredClone(s);
  interrupted.member='gosegu'; Engine.skill(interrupted); Engine.update(interrupted,frame);
  assert.equal(interrupted.hazards.length,0,'stun interrupts the wind-up');
  const hit=structuredClone(s);
  hit.x=h.x+Math.cos(h.angle)*h.length*.5; hit.y=h.y+Math.sin(h.angle)*h.length*.5;
  advance(hit,1.45);
  assert.equal(hit.stats.hits,1,'remaining in the lane costs a heart');
  advance(s,.65,{y:1});
  assert.equal(enemy.x,720,'charger stays still throughout the warning');
  advance(s,.9,{y:1});
  assert.equal(s.stats.hits,0);
  assert.ok(Math.hypot(enemy.x-720,enemy.y-480)>220,'charge actually moves the enemy across the warned lane');
});

test('a full mailbag cannot clear a guarded route until an actual projectile defeats the boss', () => {
  for(const stage of [3,6,9]) {
    const s=stageFixture(stage);
    s.x=s.beacon.x; s.y=s.beacon.y; s.cargo=s.required;
    Engine.update(s,frame);
    assert.equal(s.deliveries,stage);
    assert.equal(s.stage,stage);
    assert.ok(s.boss.hp>0);
    s.boss.hp=1;
    advance(s,3);
    assert.equal(s.deliveries,stage+1);
    assert.equal(s.stats.bosses,1);
    assert.ok(s.events.some(e=>e.type==='impact'));
    assert.ok(s.events.some(e=>e.type==='boss-down'));
  }
});

test('boss attack patterns warn before damage and late routes keep spawning new enemies', () => {
  for(const [stage,kind] of [[3,'line'],[6,'ring'],[9,'line']]) {
    const s=stageFixture(stage);
    s.x=s.boss.x-140; s.y=s.boss.y;
    s.boss.spawnTime=0; s.boss.attackTime=0; s.invulnerableTime=0; s.shieldTime=0;
    const bossId=s.boss.id, hp=s.hearts, ids=new Set(s.enemies.map(e=>e.id));
    Engine.update(s,frame);
    const hazard=s.hazards.find(h=>h.source===bossId);
    assert.equal(hazard.kind,kind);
    assert.ok(hazard.delay>0);
    assert.equal(s.hearts,hp);
    assert.ok(s.events.some(e=>e.type==='warning'));
    advance(s,.45);
    assert.equal(s.hearts,hp,'telegraph is safe');
    advance(s,4);
    assert.ok(s.enemies.some(e=>!ids.has(e.id)),'another wave entered');
    if(stage===9) assert.ok(s.hazards.some(h=>h.kind==='circle'),'the final boss alternates fan shots and tracking blasts');
  }
});

test('complementary perks evolve once, produce their advertised attacks and shorten boss combat', () => {
  const dashBuild=stageFixture(2,['shield'],'speed');
  const target=dashBuild.enemies[0]; target.x=dashBuild.x+35; target.y=dashBuild.y; target.spawnTime=0;
  const health=target.hp;
  Engine.dash(dashBuild);
  assert.ok(target.hp<health && dashBuild.events.some(e=>e.type==='pulse' && e.kind==='express'));
  const refrain=stageFixture(1,['quill'],'ribbon');
  const nearby=refrain.enemies[0]; nearby.x=refrain.x; nearby.y=refrain.y; nearby.spawnTime=0;
  Engine.skill(refrain);
  assert.ok(refrain.events.some(e=>e.type==='pulse' && e.kind==='refrain'));
  assert.ok(refrain.skillCooldown<Engine.MEMBERS.ine.cooldown);
  const orbital=stageFixture(1,['magnet'],'spool');
  orbital.stats.shots=3; orbital._stageShots=3; orbital.attackIn=0;
  Object.assign(orbital.enemies[0],{x:orbital.x+90,y:orbital.y,spawnTime:0});
  Engine.update(orbital,frame);
  assert.ok(orbital.events.some(e=>e.type==='pulse' && e.kind==='orbit'));
  function defeatTime(loadout,choice) {
    const s=stageFixture(9,loadout,choice);
    s.x=s.boss.x-160; s.y=s.boss.y;
    // Hold positioning, incoming threats and survival constant to compare DPS.
    s.enemies=[]; s.spawnIn=1e3; s.invulnerableTime=1e3;
    if(choice==='fan') {
      assert.deepEqual(s.evolutions.map(e=>e.id),['comet']);
      s.mode='upgrade'; s.draft=['fan']; Engine.chooseUpgrade(s,'fan');
      assert.equal(s.evolutions.filter(e=>e.id==='comet').length,1);
      s.x=s.boss.x-160; s.y=s.boss.y; s.enemies=[]; s.spawnIn=1e3;
    }
    while(s.boss && s.elapsed<60) Engine.update(s,.1);
    assert.equal(s.stats.bosses,1);
    return s.elapsed;
  }
  const base=defeatTime([], 'magnet'), evolved=defeatTime(['quill','spool'],'fan');
  assert.ok(base>evolved*1.5, `basic ${base.toFixed(1)}s, offensive ${evolved.toFixed(1)}s`);
});

test('each member and each difficulty can finish all ten mail routes and defeat three bosses through ordinary controls', () => {
  const runs = Engine.MEMBER_LIST.map(member => ({member,difficulty:'easy'}));
  runs.push({member:Engine.MEMBERS.viichan,difficulty:'normal'}, {member:Engine.MEMBERS.viichan,difficulty:'hard'});
  for (const {member,difficulty} of runs) {
    const state = Engine.create(member.id, 770, difficulty);
    const seen=new Set(), patterns=new Set(), drafts=new Set(), taken=[];
    for (let frames = 0; frames < 650 * 30 && !['won', 'lost'].includes(state.mode); frames += 1) {
      if (state.mode === 'upgrade') {
        drafts.add([...state.draft].sort().join('/'));
        const key=state.hearts<=2 && state.draft.includes('shield') ? 'shield' : state.draft.find(id=>['fan','quill','spool'].includes(id)) || state.draft[0];
        taken.push(key);
        Engine.chooseUpgrade(state,key);
        assert.equal(state.difficulty,difficulty);
        continue;
      }
      const target = state.cargo >= state.required ? state.beacon : state.stars.toSorted((a, b) => Math.hypot(a.x - state.x, a.y - state.y) - Math.hypot(b.x - state.x, b.y - state.y))[0];
      const dx = target.x - state.x, dy = target.y - state.y;
      const distance = Math.hypot(dx, dy) || 1;
      let ix = dx / distance, iy = dy / distance, closestEnemy = Infinity, dodge = false;
      if(state.boss) {
        seen.add(state.boss.kind);
        for(const h of state.hazards.filter(h=>h.source===state.boss.id)) patterns.add(state.boss.kind+'/'+h.kind);
        const bx=state.boss.x-state.x,by=state.boss.y-state.y,range=Math.hypot(bx,by)||1;
        if(state.cargo>=state.required || range<255) {
          const radial=Math.max(-1,Math.min(1,(range-185)/65));
          ix=(bx*radial-by*.55)/range; iy=(by*radial+bx*.55)/range;
        }
      }
      // A simple player follows letters, steers around nearby active enemies,
      // and uses the two advertised controls; no simulation state is bypassed.
      for (const enemy of state.enemies) {
        if (enemy.spawnTime > 0 || enemy.stunTime > 0) continue;
        const ex = state.x - enemy.x, ey = state.y - enemy.y;
        const gap = Math.hypot(ex, ey) || 1;
        closestEnemy = Math.min(closestEnemy, gap);
        if (gap < 67) {
          ix += ex / gap * (67 - gap) / 32;
          iy += ey / gap * (67 - gap) / 32;
        }
      }
      for(const h of state.hazards) {
        const ex=state.x-h.x,ey=state.y-h.y,gap=Math.hypot(ex,ey)||1;
        if(h.kind==='circle' && gap<h.radius+38 && h.delay<.7) { ix+=ex/gap*2.2; iy+=ey/gap*2.2; }
        if(h.kind==='ring' && h.delay<.3 && gap>=h.innerRadius-12 && gap<h.radius+65) {
          ix=ex/gap; iy=ey/gap;
          dodge=true;
        }
        if(h.kind==='line') {
          const side=-ex*Math.sin(h.angle)+ey*Math.cos(h.angle),ahead=ex*Math.cos(h.angle)+ey*Math.sin(h.angle);
          if(ahead>0 && ahead<h.length && Math.abs(side)<h.width/2+30) {
            ix-=Math.sin(h.angle)*Math.sign(side||1)*2; iy+=Math.cos(h.angle)*Math.sign(side||1)*2;
          }
        }
      }
      if (state.skillCooldown === 0 && (dodge || closestEnemy < 130 || ['jururu', 'lilpa'].includes(member.id) || state.hearts < 3)) Engine.skill(state);
      Engine.update(state, 1/30, { x: ix, y: iy });
      if (state.dashCooldown === 0 && (dodge || (!state.boss && (closestEnemy < 85 || distance > 150)))) Engine.dash(state);
      for (const entity of [state, ...state.stars, ...state.enemies, ...(state.boss ? [state.boss] : [])]) {
        assert.ok(entity.x >= state.arena.bounds.left && entity.x <= state.arena.bounds.right);
        assert.ok(entity.y >= state.arena.bounds.top && entity.y <= state.arena.bounds.bottom);
      }
    }
    assert.equal(state.mode, 'won', `${member.id} / ${difficulty}: ${state.lossReason}, ${state.deliveries} deliveries`);
    assert.equal(state.deliveries, 10);
    assert.equal(state.stage, 9);
    assert.ok(state.stats.letters >= 172);
    assert.equal(state.stats.bosses,3);
    assert.ok(state.stats.kills>10 && state.stats.shots>10);
    assert.equal(seen.size,3);
    assert.ok(patterns.has('warden/line') && patterns.has('siren/ring'));
    assert.ok(patterns.has('regent/line') || patterns.has('regent/circle'));
    assert.deepEqual(state.upgrades,taken);
    assert.ok(drafts.size>1);
    assert.ok(state.timeLeft > 0);
    assert.ok(state.score > 2000);
    assert.ok(state.events.some((event) => event.type === 'win'));
  }
});
