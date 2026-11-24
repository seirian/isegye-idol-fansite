/*
 * DOM-free game simulation. Positions are world coordinates; dt is in seconds.
 * CourierEngine.create(memberId, seed, difficulty = 'easy') -> mutable state.
 * update(state, dt, {x, y}) accepts keyboard or analogue-stick vectors and limits
 * delayed frames to 100 ms. dash/skill/chooseUpgrade return whether they acted.
 * Renderer consumes state.events.splice(0); no renderer or clock is required.
 * State uses x/y directly, dir:{x,y}, stage:0..9 and mode:
 * playing -> upgrade -> playing -> ... -> won | lost.
 */
(function (global) {
  'use strict';

  const BOUNDS = Object.freeze({ left: 48, right: 2832, top: 64, bottom: 1872 });
  const ARENA = Object.freeze({ width: 2880, height: 1920, padding: 48, bounds: BOUNDS });
  // Each painted court keeps its buildings, water and machinery beyond these play limits.
  const ROUTES = Object.freeze([
    ['소인 광장',8,65,590,625,1250,570,null,[510,525,2370,1560],'문을 여는 첫 우체국으로 소인이 마르기 전에 편지를 옮겨요.'],
    ['바람개비 골목',10,66,1590,1110,2040,555,null,[340,495,2440,1520],'골목을 돌아가는 바람이 흩뜨린 봉투들을 동쪽 창구로 보내요.'],
    ['유리온실 길',12,70,1670,540,2490,770,null,[280,465,2580,1500],'유리온실의 따뜻한 공기 속에 떠 있는 편지를 모아요.'],
    ['닻을 내린 부두',14,90,2190,700,1880,1390,'warden',[550,615,2380,1560],'물길을 막은 먹물 닻지기의 돌진을 옆으로 피해 부두를 열어요.'],
    ['반딧불 수로',16,75,480,1360,1180,980,null,[315,345,2540,1535],'반딧불을 따라 수로 건너편 배달함까지 가요.'],
    ['달빛 인쇄소',18,78,1510,1340,730,1210,null,[650,520,2170,1425],'막 찍힌 초대장을 챙겨 밤샘 인쇄소로 향해요.'],
    ['종탑 우체국',20,98,1780,780,920,1400,'siren',[570,410,2320,1510],'종소리가 퍼질 때 울림의 틈으로 빠져나가요.'],
    ['유성 철교',22,82,1190,890,1740,1420,null,[120,390,2760,1510],'철교 위를 가로지르는 유성을 따라 기다리는 관객을 찾아요.'],
    ['새벽 활주로',24,85,1660,1020,2430,1310,null,[300,515,2570,1410],'새벽 항공편에 마지막 초대장을 실어 보내요.'],
    ['마지막 환승역',28,108,1520,1140,2310,640,'regent',[330,515,2485,1510],'반송왕이 봉인한 종착역을 열고 오늘의 마지막 우편을 전해요.']
  ].map(([name,goal,time,sx,sy,x,y,boss,[left,top,right,bottom],brief]) => Object.freeze({
    arena:Object.freeze({...ARENA,bounds:Object.freeze({left,top,right,bottom})}),
    name,goal,time,boss,brief,start:Object.freeze({x:sx,y:sy}),beacon:Object.freeze({x,y,radius:60})
  })));
  const BEACON = ROUTES[0].beacon;
  const REQUIREMENTS = Object.freeze(ROUTES.map(route=>route.goal));
  const DIFFICULTIES = Object.freeze({
    easy: Object.freeze({name:'쉬움', description:'기존 적 속도로 편지를 모으고 보스의 공격을 익혀요.', speed:1}),
    normal: Object.freeze({name:'보통', description:'적이 18% 빨라져요. 젤리의 도약과 보스의 후속 공격을 피하세요.', speed:1.18}),
    hard: Object.freeze({name:'어려움', description:'적이 36% 빨라져요. 예측 소인과 양쪽에서 오는 후속 공격에 대비하세요.', speed:1.36})
  });
  const BOSSES = {
    warden: {name:'먹물 닻지기',hp:165,radius:36,speed:45},
    siren: {name:'유리종 소프라노',hp:275,radius:34,speed:42},
    regent: {name:'반송왕 제로',hp:440,radius:44,speed:52}
  };
  const MEMBERS = Object.freeze({
    ine: Object.freeze({ id: 'ine', name: '아이네', color: '#b397ff', skill: '별빛 보호막', skillDescription: '4초 동안 피해를 막고 가까운 젤리를 밀어내요.', cooldown: 10 }),
    jing: Object.freeze({ id: 'jing', name: '징버거', color: '#ffcc69', skill: '젤리 슬로 타임', skillDescription: '5초 동안 모든 젤리가 느리게 움직여요.', cooldown: 11 }),
    lilpa: Object.freeze({ id: 'lilpa', name: '릴파', color: '#8cafff', skill: '밤하늘 비행', skillDescription: '4초 동안 빨라지고 출발할 때 피해를 막아요.', cooldown: 11 }),
    jururu: Object.freeze({ id: 'jururu', name: '주르르', color: '#ff9bc6', skill: '하트 자석', skillDescription: '4초 동안 멀리 있는 별 편지를 끌어당겨요.', cooldown: 10 }),
    gosegu: Object.freeze({ id: 'gosegu', name: '고세구', color: '#7be4f0', skill: '구름 팡!', skillDescription: '주변 젤리를 밀어내고 3초 동안 멈춰요.', cooldown: 10 }),
    viichan: Object.freeze({ id: 'viichan', name: '비챤', color: '#afe58e', skill: '숲의 응원', skillDescription: '하트를 하나 회복해요. 하트가 가득 차면 보호막!', cooldown: 13 })
  });
  const UPGRADES = Object.freeze([
    Object.freeze({ id: 'speed', key: 'speed', name: '가벼운 운동화', description: '이동 속도 +14%', icon: 'speed' }),
    Object.freeze({ id: 'shield', key: 'shield', name: '든든한 우편 가방', description: '최대 하트 +1 · 하트 1 회복', icon: 'shield' }),
    Object.freeze({ id: 'magnet', key: 'magnet', name: '반짝이는 나침반', description: '편지를 끌어오는 거리 +34', icon: 'magnet' }),
    Object.freeze({ id:'quill', key:'quill', name:'유성 펜촉', description:'자동 별탄의 피해 +5', icon:'quill' }),
    Object.freeze({ id:'spool', key:'spool', name:'속기 태엽', description:'자동 별탄의 발사 간격 15% 단축', icon:'spool' }),
    Object.freeze({ id:'fan', key:'fan', name:'분류 날개', description:'다른 적에게 추가 별탄 1발. 적이 하나면 집중 사격', icon:'fan' }),
    Object.freeze({ id:'ribbon', key:'ribbon', name:'앙코르 리본', description:'멤버 특기 재사용 시간 18% 단축', icon:'ribbon' })
  ]);
  const EVOLUTIONS = Object.freeze([
    {id:'comet',name:'혜성 만년필',requires:['quill','fan'],description:'별탄이 첫 적을 관통해 뒤쪽 적까지 맞혀요.'},
    {id:'orbit',name:'공전 우표',requires:['spool','magnet'],description:'네 번째 사격마다 주변 적 모두에게 별빛 파동을 보내요.'},
    {id:'express',name:'은하 급행',requires:['shield','speed'],description:'대시를 시작할 때 가까운 적에게 충격파를 보내요.'},
    {id:'refrain',name:'메아리 리본',requires:['ribbon','quill'],description:'특기를 쓰면 주변 적에게 펜촉 피해의 두 배를 입혀요.'}
  ]);
  const STEP = 1 / 120;
  const clamp = (value, min, max) => Math.max(min, Math.min(max, value));
  const distance = (a, b) => Math.hypot(a.x - b.x, a.y - b.y);

  function seedNumber(seed) {
    if (typeof seed === 'number' && Number.isFinite(seed)) return seed >>> 0;
    let hash = 2166136261;
    for (const ch of String(seed ?? 1)) hash = Math.imul(hash ^ ch.charCodeAt(0), 16777619);
    return hash >>> 0;
  }

  function random(s) {
    s._rng = (s._rng + 0x6D2B79F5) >>> 0;
    let value = s._rng;
    value = Math.imul(value ^ (value >>> 15), value | 1);
    value ^= value + Math.imul(value ^ (value >>> 7), value | 61);
    return ((value ^ (value >>> 14)) >>> 0) / 4294967296;
  }

  function emit(s, type, detail = {}) {
    s.events.push({ type, x: s.x, y: s.y, ...detail });
    if (s.events.length > 256) s.events.splice(0, s.events.length - 256);
  }

  function star(s, x, y, delay = 0) {
    return {
      id: ++s._id, x: clamp(x, s.arena.bounds.left + 14, s.arena.bounds.right - 14),
      y: clamp(y, s.arena.bounds.top + 14, s.arena.bounds.bottom - 14),
      kind: 'letter', variant: Math.floor(random(s) * 3),
      phase: random(s) * Math.PI * 2, availableAt: s.elapsed + delay
    };
  }

  function spawnStars(s) {
    const count = s.required + Math.ceil(s.required / 7);
    const dx = s.beacon.x - s.x, dy = s.beacon.y - s.y;
    const span = Math.hypot(dx, dy) || 1, nx = -dy / span, ny = dx / span;
    const phase = random(s) * Math.PI * 2;
    s.stars = [];
    // Mail bags spill in little clusters along a winding outbound route.
    for (let i = 0; i < count; i += 1) {
      const t = .13 + .84 * (i + random(s)) / count;
      const spanAcross = 300 + s.stage * 79;
      const winding = Math.sin(t * 13.5 + phase) * spanAcross;
      const offset = winding + (random(s) - .5) * (260 + s.stage * 60);
      const along = t + (random(s)-.5)*(.35+s.stage*.18);
      // Reflect the route back into the streets at the city limits. Clamping a
      // wide switchback would put a pile of parcels in one spot along the edge.
      const reflect = (v,low,high) => {
        const span=high-low, distance=((v-low)%(span*2)+span*2)%(span*2);
        return low+Math.min(distance,span*2-distance);
      };
      const x = reflect(s.x+dx*along+nx*offset,s.arena.bounds.left+40,s.arena.bounds.right-40);
      const y = reflect(s.y+dy*along+ny*offset,s.arena.bounds.top+40,s.arena.bounds.bottom-40);
      const letter=star(s,x,y);
      letter.stamp=i%9===7 ? 'ward' : i%7===5 ? 'signal' : i%5===4 ? 'express' : 'plain';
      s.stars.push(letter);
    }
  }

  const MOB_TYPES = {
    jelly: {hp:13,speed:55,radius:18}, mote: {hp:8,speed:83,radius:14},
    brute: {hp:27,speed:45,radius:25}, hex: {hp:17,speed:59,radius:18},
    parcel: {hp:32,speed:52,radius:22}, interceptor: {hp:24,speed:77,radius:17}
  };
  function makeMob(s,kind,x,y) {
    const type = MOB_TYPES[kind];
    const hp = type.hp + s.stage*1.8;
    return {
      id: ++s._id, x, y, kind, hp, maxHp:hp,
      speed: (type.speed + s.stage * 3 + random(s) * 8) * DIFFICULTIES[s.difficulty].speed,
      phase: random(s) * Math.PI * 2, spawnTime: 1.25,
      attackTime: (kind==='interceptor' ? .75 : 2) + random(s)*2,
      stunTime: 0, radius: type.radius
    };
  }

  function spawnEnemy(s, angle, featured) {
    let x, y;
    for (let attempt = 0; attempt < 32; attempt += 1) {
      const direction = angle + attempt * .73, radius = 270 + random(s) * 170;
      x = clamp(s.x + Math.cos(direction) * radius, s.arena.bounds.left, s.arena.bounds.right);
      y = clamp(s.y + Math.sin(direction) * radius, s.arena.bounds.top, s.arena.bounds.bottom);
      if (Math.hypot(x - s.x, y - s.y) > 190 && s.enemies.every(enemy => Math.hypot(enemy.x - x, enemy.y - y) > 60)) break;
    }
    const kinds = ['jelly','mote','jelly', ...(s.stage > 0 ? ['brute'] : []), ...(s.stage > 1 ? ['hex'] : [])];
    if (s.stage>=4) kinds.push('parcel');
    if (s.stage>=7) kinds.push('interceptor');
    const kind = featured || kinds[Math.floor(random(s)*kinds.length)];
    return makeMob(s,kind,x,y);
  }

  function spawnStage(s) {
    const route = ROUTES[s.stage];
    s.arena = route.arena;
    s._rng = s.stage === 0 ? s.seed : seedNumber(`${s.seed}/${s.stage}`);
    s._accumulator = 0;
    s._stageShots = 0;
    s.x = route.start.x;
    s.y = route.start.y;
    const length = distance(route.start,route.beacon);
    s.dir = {x:(route.beacon.x-s.x)/length, y:(route.beacon.y-s.y)/length};
    s._dashDir = {...s.dir};
    s._velocity = {x:0,y:0};
    s.dashTime = 0; s.dashCooldown = 0; s.skillCooldown = 0;
    s.shieldTime = 0; s.slowTime = 0; s.hasteTime = 0; s.magnetTime = 0;
    s.invulnerableTime = 1.2;
    s.combo = 0; s.comboTime = 0;
    s.cargo = 0; s.required = route.goal;
    s.beacon = route.beacon;
    s.timeLeft = route.time;
    s.stageElapsed = 0;
    s.nearBeacon = false;
    s.projectiles = []; s.hazards = [];
    spawnStars(s);
    const count = 4 + Math.floor(s.stage*.75);
    s.enemies = [];
    const featured = s.stage>=7 ? 'interceptor' : s.stage>=4 ? 'parcel' : null;
    for (let index = 0; index < count; index++) {
      s.enemies.push(spawnEnemy(s,index/count*Math.PI*2,index===0 ? featured : null));
    }
    s.spawnIn = 2.8; s.attackIn = .45;
    s.boss = null; s.bossDefeated = false;
    emit(s, 'stage', { stage: s.stage, required: s.required });
    if (route.boss) {
      const boss = BOSSES[route.boss];
      s.boss = {...boss, speed:boss.speed*DIFFICULTIES[s.difficulty].speed, id:++s._id, kind:route.boss, maxHp:boss.hp,
        x:s.beacon.x-48, y:s.beacon.y-60, phase:0, spawnTime:1.4, stunTime:0, attackTime:1.3, pattern:0};
      emit(s,'boss',{kind:route.boss,name:boss.name,x:s.boss.x,y:s.boss.y});
    }
  }

  function create(member = 'ine', seed = 1, difficulty = 'easy') {
    const memberId = typeof member === 'string' ? member : member?.id;
    const resolved = Object.hasOwn(MEMBERS, memberId) ? memberId : 'ine';
    const normalizedSeed = seedNumber(seed);
    const s = {
      version: 2, seed: normalizedSeed, member: resolved, mode: 'playing',
      difficulty: typeof difficulty==='string' && Object.hasOwn(DIFFICULTIES,difficulty) ? difficulty : 'easy',
      arena: ARENA, elapsed: 0, stage: 0, deliveries: 0,
      hearts: 3, maxHearts: 3, score: 0, maxCombo: 0,
      baseSpeed: 210, speedBonus: 0, magnetBonus: 0,
      events: [], upgrades: [], draft:[], evolutions:[],
      stats: { letters: 0, hits: 0, dashes: 0, skills: 0, kills:0, bosses:0, shots:0 },
      lossReason: null, _id: 0
    };
    spawnStage(s);
    return s;
  }

  function dash(s) {
    if (s.mode !== 'playing' || s.dashCooldown > 0 || s.dashTime > 0) return false;
    s.dashTime = 0.19;
    s.dashCooldown = 2.3;
    s._dashDir = { ...s.dir };
    s.stats.dashes += 1;
    if (hasEvolution(s,'express')) pulse(s,145,24,'express');
    emit(s, 'dash', { dir: { ...s.dir } });
    return true;
  }

  function repel(s, radius, force, stunTime) {
    for (const enemy of s.enemies) {
      const dx = enemy.x - s.x, dy = enemy.y - s.y;
      const dist = Math.hypot(dx, dy);
      if (dist > radius) continue;
      const angle = dist > 0.01 ? Math.atan2(dy, dx) : enemy.phase;
      enemy.x = clamp(enemy.x + Math.cos(angle) * force, s.arena.bounds.left, s.arena.bounds.right);
      enemy.y = clamp(enemy.y + Math.sin(angle) * force, s.arena.bounds.top, s.arena.bounds.bottom);
      enemy.stunTime = Math.max(enemy.stunTime, stunTime);
    }
  }

  function skill(s) {
    if (s.mode !== 'playing' || s.skillCooldown > 0) return false;
    const previousHearts = s.hearts;
    s.skillCooldown = MEMBERS[s.member].cooldown * Math.pow(.82,rank(s,'ribbon'));
    s.stats.skills += 1;
    switch (s.member) {
      case 'ine': s.shieldTime = 4; repel(s, 210, 85, 0.7); break;
      case 'jing': s.slowTime = 5; break;
      case 'lilpa': s.hasteTime = 4; s.shieldTime = Math.max(s.shieldTime, 1); break;
      case 'jururu': s.magnetTime = 4; break;
      case 'gosegu': repel(s, 280, 115, 3.2); break;
      case 'viichan':
        if (s.hearts < s.maxHearts) s.hearts += 1;
        else s.shieldTime = Math.max(s.shieldTime, 3);
        s.magnetTime = 2;
        break;
    }
    if (hasEvolution(s,'refrain')) pulse(s,270,2*shotPower(s),'refrain');
    emit(s, 'skill', { member: s.member, name: MEMBERS[s.member].skill, restoredHealth: s.hearts - previousHearts });
    return true;
  }

  function chooseUpgrade(s, key) {
    if (s.mode !== 'upgrade' || !s.draft.includes(key)) return false;
    s.events.length=0;
    s.stage=s.deliveries;
    spawnStage(s);
    if (key === 'speed') s.speedBonus += 0.14;
    if (key === 'shield') { s.maxHearts += 1; s.hearts = Math.min(s.maxHearts, s.hearts + 1); }
    if (key === 'magnet') s.magnetBonus += 34;
    s.upgrades.push(key);
    s.draft = [];
    for (const evo of EVOLUTIONS) {
      if (!hasEvolution(s,evo.id) && evo.requires.every(part=>s.upgrades.includes(part))) {
        s.evolutions.push(evo);
        emit(s,'evolve',{id:evo.id,name:evo.name});
      }
    }
    s.mode = 'playing';
    emit(s, 'upgrade', { key });
    return true;
  }

  function rank(s,key) { return s.upgrades.filter(id=>id===key).length; }
  function hasEvolution(s,key) { return s.evolutions.some(e=>e.id===key); }
  function shotPower(s) { return 13 + 5*rank(s,'quill'); }

  function drawDraft(s) {
    const candidates = UPGRADES.filter(u=>rank(s,u.id)<3).map(u=>u.id);
    // Every draft offers at least one weapon. Other slots can reinforce a build
    // or complete a recipe, with the remaining pool shuffled from this run's seed.
    const shuffled = [...candidates];
    for(let i=shuffled.length-1; i>0; i--) {
      const j=Math.floor(random(s)*(i+1));
      [shuffled[i],shuffled[j]]=[shuffled[j],shuffled[i]];
    }
    const weapon = shuffled.find(key=>['quill','spool','fan'].includes(key));
    return weapon ? [weapon,...shuffled.filter(key=>key!==weapon).slice(0,2)] : shuffled.slice(0,3);
  }

  function finish(s, won, reason) {
    s.mode = won ? 'won' : 'lost';
    s.lossReason = reason || null;
    s._accumulator = 0;
    if (won) s.score += Math.ceil(s.timeLeft) * 15 + s.hearts * 100;
    emit(s, won ? 'win' : 'lose', { score: s.score, reason: s.lossReason });
  }

  function deliver(s) {
    const stage = s.stage;
    const points = 300 + stage * 150 + s.combo * 20;
    s.score += points;
    s.deliveries += 1;
    emit(s, 'delivery', { stage, deliveries: s.deliveries, points });
    if (s.deliveries === REQUIREMENTS.length) { finish(s, true); return; }
    s.hearts=Math.min(s.maxHearts,s.hearts+1);
    s.draft = drawDraft(s);
    s.mode = 'upgrade';
    s._accumulator = 0;
    emit(s, 'checkpoint', { stage: s.stage, nextStage: s.deliveries });
  }

  function hurt(s, enemy) {
    s.hearts -= 1;
    s.stats.hits += 1;
    s.combo = 0;
    s.comboTime = 0;
    s.invulnerableTime = 1.6;
    if (s.cargo > 0) {
      s.cargo -= 1;
      const away = Math.atan2(s.y - enemy.y, s.x - enemy.x);
      s.stars.push(star(s, s.x + Math.cos(away) * 52, s.y + Math.sin(away) * 52, 0.65));
    }
    repel(s, 115, 55, 0.9);
    emit(s, 'hit', { hearts: s.hearts });
    if (s.hearts <= 0) finish(s, false, 'hearts');
  }

  function vulnerable(s) { return s.invulnerableTime<=0 && s.shieldTime<=0 && s.dashTime<=0; }

  function damage(s,enemy,amount) {
    if (enemy.hp<=0) return;
    enemy.hp = Math.max(0,enemy.hp-amount);
    emit(s,'impact',{x:enemy.x,y:enemy.y,damage:amount,target:enemy.id,kind:enemy.kind});
    if (enemy.hp>0) return;
    const boss = enemy === s.boss;
    s.stats.kills++; s.score += boss ? 450 : 20;
    emit(s,'kill',{x:enemy.x,y:enemy.y,kind:enemy.kind,boss});
    if (enemy.kind==='parcel') {
      // Reserve up to two extra slots beyond the ordinary wave cap. Chain
      // kills cannot produce an unbounded crowd, and these small motes never split.
      const living=s.enemies.filter(e=>e.hp>0).length;
      const count=Math.min(2,Math.max(0,12+s.stage*2-living));
      const angle=Math.atan2(enemy.y-s.y,enemy.x-s.x)+Math.PI/2;
      for (let i=0;i<count;i++) {
        const side=i===0 ? -1 : 1;
        const x=clamp(enemy.x+side*Math.cos(angle)*33,s.arena.bounds.left,s.arena.bounds.right);
        const y=clamp(enemy.y+side*Math.sin(angle)*33,s.arena.bounds.top,s.arena.bounds.bottom);
        const mote=makeMob(s,'mote',x,y);
        mote.small=true; mote.hp=7; mote.maxHp=7; mote.radius=11; mote.spawnTime=1.1;
        s.enemies.push(mote);
      }
      emit(s,'split',{x:enemy.x,y:enemy.y,count});
    }
    if (enemy.kind==='interceptor') s.hazards=s.hazards.filter(h=>h.source!==enemy.id);
    if (boss) {
      s.boss=null; s.bossDefeated=true; s.stats.bosses++;
      s.hazards=s.hazards.filter(h=>h.source!==enemy.id);
      emit(s,'boss-down',{kind:enemy.kind,name:enemy.name,x:enemy.x,y:enemy.y});
    }
  }

  function pulse(s,radius,power,kind) {
    for (const enemy of s.boss ? [...s.enemies,s.boss] : s.enemies) {
      if (enemy.spawnTime<=0 && distance(enemy,s)<=radius+enemy.radius) damage(s,enemy,power);
    }
    emit(s,'pulse',{kind,radius});
  }

  function fire(s) {
    const targets=(s.boss ? [...s.enemies,s.boss] : [...s.enemies])
      .filter(e=>e.hp>0 && e.spawnTime<=0 && distance(s,e)<360)
      .sort((a,b)=>distance(s,a)-distance(s,b));
    if (!targets.length) { s.attackIn=.12; return; }
    // A nearby boss takes the first shot even when small enemies crowd its feet.
    if (s.boss && targets.includes(s.boss)) {
      targets.splice(targets.indexOf(s.boss),1); targets.unshift(s.boss);
    }
    const count=1+rank(s,'fan'), power=shotPower(s), piercing=hasEvolution(s,'comet');
    for(let i=0;i<count;i++) {
      const target=targets[i%targets.length];
      const angle=Math.atan2(target.y-s.y,target.x-s.x);
      const side=(i-(count-1)/2)*6;
      s.projectiles.push({id:++s._id,kind:piercing ? 'nova' : 'bolt', target:target.id,
        x:s.x-Math.sin(angle)*side,y:s.y+Math.cos(angle)*side,
        vx:Math.cos(angle)*520,vy:Math.sin(angle)*520,damage:i ? Math.ceil(power*.67) : power,
        radius:6,hits:[],pierce:piercing ? 2 : 1,life:1.05});
    }
    s.stats.shots++; s._stageShots++; emit(s,'shot',{target:targets[0].id,count});
    if (hasEvolution(s,'orbit') && s._stageShots%4===0) pulse(s,185,power,'orbit');
    s.attackIn=.83*Math.pow(.85,rank(s,'spool'));
  }

  function moveShots(s,dt) {
    s.attackIn-=dt;
    if(s.attackIn<=0) fire(s);
    const enemies=s.boss ? [...s.enemies,s.boss] : s.enemies;
    for(const shot of s.projectiles) {
      shot.life-=dt;
      shot.x+=shot.vx*dt; shot.y+=shot.vy*dt;
      for(const target of enemies) {
        if (target.hp<=0 || target.spawnTime>0 || shot.hits.includes(target.id) || distance(shot,target)>shot.radius+target.radius) continue;
        damage(s,target,shot.damage); shot.hits.push(target.id);
        if(shot.hits.length>=shot.pierce) { shot.life=0; break; }
      }
    }
    s.projectiles=s.projectiles.filter(p=>p.life>0);
    s.enemies=s.enemies.filter(e=>e.hp>0);
  }

  function warn(s,enemy,kind,x,y,options={}) {
    const windup=options.windup ?? 1.1;
    const h={id:++s._id,source:enemy.id,kind,x,y,radius:65,innerRadius:0,width:38,length:310,angle:0,
      windup,delay:windup,life:.36,hit:false,...options};
    h.duration=h.life;
    s.hazards.push(h);
    emit(s,'warning',{x,y,source:enemy.id,kind});
  }

  function hazardTouches(h,s) {
    if(h.kind==='line') {
      const dx=s.x-h.x,dy=s.y-h.y,c=Math.cos(h.angle),a=Math.sin(h.angle);
      const along=dx*c+dy*a, across=Math.abs(-dx*a+dy*c);
      return along>=-8 && along<=h.length+8 && across<=h.width/2+8;
    }
    const dist=distance(h,s);
    return dist<=h.radius+8 && (h.kind!=='ring' || dist>=h.innerRadius-8);
  }

  function moveHazards(s,dt) {
    for(const h of s.hazards) {
      const charger = h.charge ? (s.boss?.id===h.source ? s.boss : s.enemies.find(e=>e.id===h.source)) : null;
      if (h.charge && (!charger || charger.stunTime>0)) { h.life=0; continue; }
      if(h.delay>0) { h.delay=Math.max(0,h.delay-dt); continue; }
      h.life-=dt;
      if(h.kind==='ring') { h.radius+=155*dt; h.innerRadius=h.radius-31; }
      if(charger) {
        const progress=clamp(1-h.life/h.duration,0,1);
        charger.x=clamp(h.x+Math.cos(h.angle)*h.length*progress,s.arena.bounds.left,s.arena.bounds.right);
        charger.y=clamp(h.y+Math.sin(h.angle)*h.length*progress,s.arena.bounds.top,s.arena.bounds.bottom);
      }
      const touching=charger ? distance(charger,s)<=h.width/2+10 : hazardTouches(h,s);
      if(!h.hit && vulnerable(s) && touching) {
        h.hit=true; hurt(s,h);
        if(s.mode!=='playing') return;
      }
    }
    s.hazards=s.hazards.filter(h=>h.life>0);
  }

  function warnBossFollowup(s,b,angle,gap) {
    const side=b.pattern%2===0 ? 1 : -1;
    const bounds=s.arena.bounds;
    // Each mark is fixed when drawn and strikes after the main pattern. On
    // hard, the opposite flank follows later, leaving time to cross its lane.
    const count=s.difficulty==='hard' ? 2 : 1;
    for (let i=0;i<count;i++) {
      const flank=i===0 ? side : -side;
      const nx=-Math.sin(angle)*flank, ny=Math.cos(angle)*flank;
      const windup=1.8+i*.55;
      if (b.kind==='warden') {
        const x=clamp(b.x+nx*96,bounds.left,bounds.right), y=clamp(b.y+ny*96,bounds.top,bounds.bottom);
        warn(s,b,'line',x,y,{
          angle,length:Math.min(320,gap+60),width:32,windup,life:.24,pattern:'echo'
        });
      } else if (b.kind==='siren') {
        const x=clamp(s.x+nx*83,bounds.left,bounds.right), y=clamp(s.y+ny*83,bounds.top,bounds.bottom);
        warn(s,b,'circle',x,y,{radius:49,windup,life:.26,pattern:'echo'});
      } else {
        // Two oblique return beams meet at the courier's former position.
        const x=clamp(b.x+nx*120,bounds.left,bounds.right), y=clamp(b.y+ny*120,bounds.top,bounds.bottom);
        warn(s,b,'line',x,y,{angle:Math.atan2(s.y-y,s.x-x),
          length:Math.min(450,Math.hypot(s.x-x,s.y-y)+55),width:29,windup,life:.24,pattern:'echo'});
      }
    }
  }

  function moveBoss(s,dt) {
    const b=s.boss;
    if(!b) return;
    b.spawnTime=Math.max(0,b.spawnTime-dt);
    const gap=distance(b,s);
    if(b.spawnTime>0 || gap>540) return;
    const angle=Math.atan2(s.y-b.y,s.x-b.x);
    b.phase=b.hp<b.maxHp*.5 ? 1 : 0;
    b.attackTime-=dt*(s.slowTime>0 ? .65 : 1);
    if(b.attackTime<=0) {
      if(b.kind==='warden') {
        warn(s,b,'line',b.x,b.y,{angle,length:Math.min(320,gap+60),width:54,windup:1.15,charge:true});
      } else if(b.kind==='siren') {
        warn(s,b,'ring',b.x,b.y,{radius:70,innerRadius:39,windup:1.2,life:1.65});
        if(b.phase) warn(s,b,'ring',b.x,b.y,{radius:70,innerRadius:39,windup:2.05,life:1.15});
      } else if(b.pattern%2===0) {
        for(const spread of [-.48,0,.48]) warn(s,b,'line',b.x,b.y,{angle:angle+spread,length:400,width:42,windup:1.2});
      } else {
        for(let i=0;i<2+b.phase;i++) {
          const x=clamp(s.x+s.dir.x*i*105,s.arena.bounds.left,s.arena.bounds.right), y=clamp(s.y+s.dir.y*i*105,s.arena.bounds.top,s.arena.bounds.bottom);
          warn(s,b,'circle',x,y,{radius:73,windup:.9+i*.36});
        }
      }
      if (s.difficulty!=='easy') warnBossFollowup(s,b,angle,gap);
      b.pattern++; b.attackTime=b.phase ? 3.1 : 4;
    }
    if(gap>115 && !s.hazards.some(h=>h.charge && h.source===b.id)) {
      const step=b.speed*dt*(s.slowTime>0 ? .45 : 1);
      b.x+=Math.cos(angle)*step; b.y+=Math.sin(angle)*step;
    }
    if(vulnerable(s) && gap<b.radius+13) hurt(s,b);
  }

  function moveEnemies(s, dt) {
    s.spawnIn-=dt;
    if(s.spawnIn<=0) {
      const cap=10+s.stage*2;
      s.enemies=s.enemies.filter(e=>distance(e,s)<820);
      for(let i=0;i<(s.stage>=5 ? 2 : 1) && s.enemies.length<cap;i++) s.enemies.push(spawnEnemy(s,random(s)*Math.PI*2));
      s.spawnIn=Math.max(1.05,2.5-s.stage*.16);
    }
    for (let index = 0; index < s.enemies.length; index += 1) {
      const enemy = s.enemies[index];
      if (enemy.spawnTime > 0) { enemy.spawnTime = Math.max(0, enemy.spawnTime - dt); continue; }
      if (enemy.stunTime > 0) { enemy.stunTime = Math.max(0, enemy.stunTime - dt); continue; }
      const dx = s.x - enemy.x, dy = s.y - enemy.y;
      const dist = Math.hypot(dx, dy) || 1;
      enemy.attackTime-=dt;
      if (s.difficulty!=='easy' && enemy.kind==='jelly') {
        if (s.hazards.some(h=>h.source===enemy.id && h.charge)) continue;
        if (enemy.attackTime<=0 && dist>80 && dist<255 &&
            s.hazards.filter(h=>h.pattern==='spring').length < (s.difficulty==='hard' ? 2 : 1)) {
          warn(s,enemy,'line',enemy.x,enemy.y,{angle:Math.atan2(dy,dx),length:Math.min(245,dist+25),
            width:30,windup:s.difficulty==='hard' ? .85 : 1.05,life:.36,charge:true,pattern:'spring'});
          enemy.attackTime=5.5;
          continue;
        }
      }
      if (enemy.kind==='interceptor') {
        if (s.hazards.some(h=>h.source===enemy.id && h.charge)) continue;
        const tx=clamp(s.x+clamp(s._velocity.x,-240,240)*.5,s.arena.bounds.left,s.arena.bounds.right);
        const ty=clamp(s.y+clamp(s._velocity.y,-240,240)*.5,s.arena.bounds.top,s.arena.bounds.bottom);
        const ax=tx-enemy.x, ay=ty-enemy.y, length=Math.hypot(ax,ay);
        if(enemy.attackTime<=0 && length<350 && Math.abs(ax)>35 && Math.abs(ay)>35) {
          warn(s,enemy,'line',enemy.x,enemy.y,{angle:Math.atan2(ay,ax),length:length+55,width:34,
            windup:.95,life:.42,charge:true});
          enemy.attackTime=4.6;
        } else {
          // Set up on a flank even when the player is stationary. Once the
          // warning appears the lane is locked, so changing direction beats it.
          const gx=clamp(tx+(ax<0 ? 165 : -165),s.arena.bounds.left,s.arena.bounds.right);
          const gy=clamp(ty+(ay<0 ? 140 : -140),s.arena.bounds.top,s.arena.bounds.bottom);
          const gap=Math.hypot(gx-enemy.x,gy-enemy.y)||1;
          const step=Math.min(gap,enemy.speed*dt*(s.slowTime>0 ? .3 : 1));
          enemy.x+=(gx-enemy.x)/gap*step; enemy.y+=(gy-enemy.y)/gap*step;
        }
        continue;
      }
      const mote=enemy.kind==='mote', hex=enemy.kind==='hex';
      const sway=Math.sin(s.stageElapsed*(mote ? 3.5 : 1.4)+enemy.phase)*(mote ? .8 : .16);
      const burst=mote && Math.sin(s.stageElapsed*2.2+enemy.phase)>.77 ? 1.65 : 1;
      const speed=enemy.speed*burst*(s.slowTime>0 ? .3 : 1);
      const approach=hex && dist<215 ? (dist<145 ? -.6 : 0) : 1;
      enemy.x+=(dx/dist*approach-dy/dist*sway)*speed*dt;
      enemy.y+=(dy/dist*approach+dx/dist*sway)*speed*dt;
      if(enemy.attackTime<=0 && hex && dist<320) {
        warn(s,enemy,'circle',s.x,s.y,{radius:45,windup:1.25}); enemy.attackTime=4.8;
        if (s.difficulty==='hard') {
          // The second stamp lands one step ahead of the courier's heading.
          // Reversing direction after either warning clears the marked ground.
          const x=clamp(s.x+s.dir.x*104,s.arena.bounds.left,s.arena.bounds.right);
          const y=clamp(s.y+s.dir.y*104,s.arena.bounds.top,s.arena.bounds.bottom);
          warn(s,enemy,'circle',x,y,{radius:42,windup:1.8,life:.24,pattern:'echo'});
        }
      } else if(enemy.attackTime<=0 && enemy.kind==='brute' && dist<95) {
        warn(s,enemy,'circle',enemy.x,enemy.y,{radius:90,windup:.85}); enemy.attackTime=4; enemy.stunTime=.9;
      }
      // A little separation keeps enemies legible instead of forming one stack.
      for (let otherIndex = 0; otherIndex < index; otherIndex += 1) {
        const other = s.enemies[otherIndex];
        const ox = enemy.x - other.x, oy = enemy.y - other.y;
        const gap = Math.hypot(ox, oy);
        if (gap > 0.01 && gap < 39) {
          enemy.x += ox / gap * (39 - gap) * dt * 2;
          enemy.y += oy / gap * (39 - gap) * dt * 2;
        }
      }
      enemy.x = clamp(enemy.x, s.arena.bounds.left, s.arena.bounds.right);
      enemy.y = clamp(enemy.y, s.arena.bounds.top, s.arena.bounds.bottom);
      if (vulnerable(s) && distance(enemy, s) < enemy.radius + 14) {
        hurt(s, enemy);
        if (s.mode !== 'playing') return;
      }
    }
  }

  function moveStars(s, dt) {
    if (s.cargo >= s.required) return;
    const magnetRadius = 44 + s.magnetBonus + (s.magnetTime > 0 ? (s.member === 'jururu' ? 105 : 50) : 0);
    for (let index = s.stars.length - 1; index >= 0; index -= 1) {
      const item = s.stars[index];
      if (item.availableAt > s.elapsed) continue;
      const dist = distance(item, s);
      if (dist < magnetRadius && dist > 23) {
        const move = Math.min(dist - 20, (180 + (magnetRadius - dist) * 3) * dt);
        item.x += (s.x - item.x) / dist * move;
        item.y += (s.y - item.y) / dist * move;
      }
      if (distance(item, s) <= 25) {
        s.stars.splice(index, 1);
        s.cargo += 1;
        s.stats.letters += 1;
        s.combo = s.comboTime > 0 ? Math.min(8, s.combo + 1) : 1;
        s.comboTime = 4;
        s.maxCombo = Math.max(s.maxCombo, s.combo);
        if(item.stamp==='ward') s.shieldTime=Math.max(s.shieldTime,1.6);
        if(item.stamp==='signal') s.skillCooldown=Math.max(0,s.skillCooldown-1.5);
        const points = 40 + (s.combo - 1) * 10 + (item.stamp==='express' ? 55 : 0);
        s.score += points;
        emit(s, 'pickup', { x: item.x, y: item.y, points, cargo: s.cargo, combo: s.combo, stamp:item.stamp || 'plain' });
        if (s.cargo >= s.required) { emit(s, 'cargo-full'); break; }
      }
    }
  }

  function tick(s, dt, input) {
    s.elapsed += dt;
    s.stageElapsed += dt;
    s.timeLeft = Math.max(0, s.timeLeft - dt);
    for (const key of ['dashCooldown', 'skillCooldown', 'shieldTime', 'slowTime', 'hasteTime', 'magnetTime', 'invulnerableTime', 'comboTime']) {
      s[key] = Math.max(0, s[key] - dt);
    }
    if (s.comboTime === 0) s.combo = 0;
    const ix = Number.isFinite(input?.x) ? input.x : 0;
    const iy = Number.isFinite(input?.y) ? input.y : 0;
    const magnitude = Math.hypot(ix, iy);
    const dx = magnitude > 1 ? ix / magnitude : ix;
    const dy = magnitude > 1 ? iy / magnitude : iy;
    if (magnitude > 0.08 && s.dashTime <= 0) s.dir = { x: ix / magnitude, y: iy / magnitude };
    const dashing = s.dashTime > 0;
    const speed = s.baseSpeed * (1 + s.speedBonus) * (s.hasteTime > 0 ? 1.5 : 1);
    const startX=s.x, startY=s.y;
    s.x = clamp(s.x + (dashing ? s._dashDir.x * 720 : dx * speed) * dt, s.arena.bounds.left, s.arena.bounds.right);
    s.y = clamp(s.y + (dashing ? s._dashDir.y * 720 : dy * speed) * dt, s.arena.bounds.top, s.arena.bounds.bottom);
    s._velocity.x=(s.x-startX)/dt; s._velocity.y=(s.y-startY)/dt;
    s.nearBeacon = distance(s, s.beacon) <= s.beacon.radius;
    moveStars(s, dt);
    moveShots(s,dt);
    if (s.nearBeacon && s.cargo >= s.required && !s.boss) { deliver(s); return; }
    moveEnemies(s, dt);
    if(s.mode==='playing') moveBoss(s,dt);
    if(s.mode==='playing') moveHazards(s,dt);
    s.dashTime = Math.max(0, s.dashTime - dt);
    if (s.mode === 'playing' && s.timeLeft <= 0) finish(s, false, 'time');
  }

  function update(s, dt, input = {}) {
    if (s.mode !== 'playing' || !Number.isFinite(dt) || dt <= 0) return s;
    s._accumulator += Math.min(0.1, dt);
    while (s._accumulator + 1e-10 >= STEP && s.mode === 'playing') {
      s._accumulator = Math.max(0, s._accumulator - STEP);
      tick(s, STEP, input);
    }
    return s;
  }

  global.CourierEngine = Object.freeze({ create, update, dash, skill, chooseUpgrade, DIFFICULTIES, MEMBERS, MEMBER_LIST: Object.values(MEMBERS), UPGRADES, EVOLUTIONS, ROUTES, BOSSES, ARENA, BEACON, REQUIREMENTS });
})(globalThis);
