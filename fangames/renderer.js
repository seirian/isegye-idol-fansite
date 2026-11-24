/* A camera onto the same world used for movement, targeting and hit tests. */
(function (global) {
  'use strict';

  const E = global.CourierEngine;
  const TAU = Math.PI * 2;
  const clamp = (n, low, high) => Math.max(low, Math.min(high, n));
  const portraits = ['ine','jing','lilpa','jururu','gosegu','viichan'];
  const accents = [
    '#ffd79c', '#f2e9a6', '#a7efd0', '#ffc68c', '#89f3cc',
    '#dbb7fc', '#c3caff', '#f8c68e', '#95def4', '#ffe3b4'
  ];
  const bodyFont = '"Gowun Dodum","Malgun Gothic",sans-serif';
  const displayFont = '"Jua","Gowun Dodum",sans-serif';

  function getCamera(state, aspect, compact = false) {
    const arena = state.arena || E.ARENA;
    // Preserve square world units even on ultrawide or portrait viewports.
    const height = Math.min(compact ? 485 : 620, arena.height, arena.width / aspect);
    const width = height * aspect;
    return {
      width, height,
      x:clamp(state.x-width/2,0,arena.width-width),
      y:clamp(state.y-height*.54,0,arena.height-height)
    };
  }
  function oval(g,x,y,rx,ry,fill) {
    g.beginPath();g.ellipse(x,y,rx,ry,0,0,TAU);g.fillStyle=fill;g.fill();
  }
  function stroke(g,color,thickness,points) {
    g.beginPath();g.moveTo(points[0],points[1]);
    for(let i=2;i<points.length;i+=2)g.lineTo(points[i],points[i+1]);
    g.strokeStyle=color;g.lineWidth=thickness;g.stroke();
  }
  function polygon(g,color,points) {
    g.beginPath();g.moveTo(points[0],points[1]);
    for(let i=2;i<points.length;i+=2)g.lineTo(points[i],points[i+1]);
    g.closePath();g.fillStyle=color;g.fill();
  }
  function star(g,x,y,r,color,points=4) {
    const corners=[];
    for(let i=0;i<points*2;i++) {
      const a=i*Math.PI/points-Math.PI/2, dist=i%2?r*.38:r;
      corners.push(x+Math.cos(a)*dist,y+Math.sin(a)*dist);
    }
    polygon(g,color,corners);
  }
  function glow(g,x,y,r,color) {
    const fill=g.createRadialGradient(x,y,0,x,y,r);
    fill.addColorStop(0,color);fill.addColorStop(1,color.slice(0,7)+'00');
    g.fillStyle=fill;g.fillRect(x-r,y-r,r*2,r*2);
  }
  function roundBox(g,x,y,w,h,r,fill) {
    g.beginPath();g.roundRect(x,y,w,h,r);g.fillStyle=fill;g.fill();
  }
  function text(g,value,x,y,size,color='#fdf8df',align='center',weight=700,font=bodyFont) {
    g.font=weight+' '+size+'px '+font;
    g.textAlign=align;g.textBaseline='middle';g.fillStyle=color;g.fillText(value,x,y);
  }
  function sprite(g, art, index, x, y, width, height=width, flip=false, cols=3, rows=2) {
    if(!art)return;
    const sw=art.naturalWidth/cols, sh=art.naturalHeight/rows;
    g.save();g.translate(x,y);if(flip)g.scale(-1,1);
    g.drawImage(art,(index%cols)*sw,Math.floor(index/cols)*sh,sw,sh,-width/2,-height/2,width,height);
    g.restore();
  }
  function inView(camera,p,padding=130) {
    return p.x>=camera.x-padding && p.x<=camera.x+camera.width+padding &&
      p.y>=camera.y-padding && p.y<=camera.y+camera.height+padding;
  }
  function drawField(g, image, arena, cam) {
    // Sample the same painting in the field and the overview. Every image edge
    // maps to its corresponding world edge and no neighbouring scene is loaded.
    const sx=image.naturalWidth/arena.width, sy=image.naturalHeight/arena.height;
    g.imageSmoothingEnabled=true;
    g.drawImage(image,cam.x*sx,cam.y*sy,cam.width*sx,cam.height*sy,
      cam.x,cam.y,cam.width,cam.height);

    // A quiet brass inlay shows where the playable ground actually ends.
    const b=arena.bounds;
    if(!b || (cam.x>b.left && cam.y>b.top &&
       cam.x+cam.width<b.right && cam.y+cam.height<b.bottom)) return;
    g.save();
    g.beginPath();g.rect(cam.x,cam.y,cam.width,cam.height);
    g.rect(b.left,b.top,b.right-b.left,b.bottom-b.top);
    g.fillStyle='#18172824';g.fill('evenodd');
    g.strokeStyle='#3e354a80';g.lineWidth=3;
    g.strokeRect(b.left,b.top,b.right-b.left,b.bottom-b.top);
    g.strokeStyle='#ffe3a8a6';g.lineWidth=1.2;
    g.setLineDash([14,8]);g.strokeRect(b.left,b.top,b.right-b.left,b.bottom-b.top);
    g.restore();
  }

  function drawStop(g,s) {
    const p=s.beacon;
    const full=s.cargo>=s.required && !s.boss;
    const tint=full?'#a6ffd5':accents[s.stage];
    glow(g,p.x,p.y,full?90:65,tint+(full?'56':'30'));
    // The delivery ring matches the simulation's interaction radius.
    g.save();g.strokeStyle=tint+'d9';g.lineWidth=2.3;
    if(!full)g.setLineDash([4,6]);
    g.beginPath();g.arc(p.x,p.y,p.radius,0,TAU);g.stroke();g.restore();
    if(full) {
      for(let i=0;i<8;i++) {
        const angle=i*TAU/8;
        star(g,p.x+Math.cos(angle)*p.radius,p.y+Math.sin(angle)*p.radius,3.6,tint);
      }
    }
  }

  function mailbox(g,art,s) {
    const p=s.beacon, tint=accents[s.stage];
    oval(g,p.x,p.y+4,26,8,'#18213c69');
    sprite(g,art.items,5,p.x,p.y-32,83);
    if(s.cargo>=s.required && !s.boss)star(g,p.x+24,p.y-61,7,'#fff7bb');
    const label=E.ROUTES[s.stage].name;
    g.font='14px '+displayFont;
    const width=g.measureText(label).width+24, top=p.y-100;
    roundBox(g,p.x-width/2,top,width,21,6,'#1a3049ed');
    text(g,label,p.x,top+10,14,'#fff3d7','center',400,displayFont);
    polygon(g,tint,[p.x-4,top+21,p.x+4,top+21,p.x,top+26]);
  }

  function drawHazard(g,h) {
    const waiting=h.delay>0, progress=clamp(1-h.delay/h.windup,0,1);
    const edge=waiting?'#ffd581':'#ff616b', inside=waiting?'#eb9a463d':'#ef40585e';
    g.save();g.translate(h.x,h.y);g.strokeStyle=edge;g.fillStyle=inside;g.lineWidth=waiting?2.2:3.5;
    g.setLineDash(waiting?[8,5]:[]);
    g.beginPath();
    if(h.kind==='line') {
      g.rotate(h.angle);g.rect(0,-h.width/2,h.length,h.width);
    } else {
      g.arc(0,0,h.radius,0,TAU);
      if(h.kind==='ring' && h.innerRadius>0){g.moveTo(h.innerRadius,0);g.arc(0,0,h.innerRadius,0,TAU,true);}
    }
    g.fill('evenodd');g.stroke();g.setLineDash([]);
    if(h.kind==='line') {
      // The stripe fills towards the end of the dash while the enemy winds up.
      g.fillStyle=waiting?'#ffcd764d':'#ff72773f';g.fillRect(0,-h.width/2+3,h.length*progress,h.width-6);
      for(let x=18;x<h.length-8;x+=42)stroke(g,edge,2,[x,-5,x+7,0,x,5]);
      if(h.pattern==='spring')stroke(g,'#fff2c3',2,[9,6,13,-6,17,6,21,-6,25,6]);
      if(h.pattern==='echo')stroke(g,edge,1.4,[3,-h.width/2+5,h.length-3,-h.width/2+5]);
    } else {
      if(waiting) {
        g.beginPath();g.arc(0,0,h.radius-4,-Math.PI/2,-Math.PI/2+TAU*progress);
        g.strokeStyle='#ffe6a2';g.lineWidth=3;g.stroke();
      }
      const markerY=h.kind==='ring'?-(h.radius-12):0;
      if(h.pattern==='echo') {
        g.beginPath();g.arc(0,0,h.radius-6,0,TAU);g.strokeStyle=edge;g.lineWidth=1;g.stroke();
      }
      g.beginPath();g.roundRect(-7,markerY-10,14,18,4);g.fillStyle='#473342';g.fill();
      text(g,'!',0,markerY,14,edge);
    }
    g.restore();
  }
  function hpBar(g,x,y,w,hp,max,tint) {
    roundBox(g,x-w/2,y,w,5,2,'#152037e6');
    const amount=(w-2)*clamp(hp/max,0,1);
    if(amount>.5)roundBox(g,x-w/2+1,y+1,amount,3,1,tint);
  }
  function parcel(g,e,bob) {
    // Two little stowaways peek out as the wax seal gives way.
    g.save();g.scale(e.radius/22,e.radius/22);g.translate(0,bob);
    const split=clamp(1-e.hp/e.maxHp,0,1),lift=Math.max(0,(split-.20)*9);
    const paper=g.createLinearGradient(-17,-24,13,1);
    paper.addColorStop(0,'#efcb88');paper.addColorStop(1,'#b17a54');
    polygon(g,'#43354b',[-23,-27,0,-37,22,-29,22,-2,1,7,-22,-1]);
    polygon(g,paper,[-20,-25,1,-18,1,4,-20,-3]);
    polygon(g,'#98704e',[2,-18,19,-26,19,-4,2,3]);
    polygon(g,'#38293e',[-21,-28,0,-36,20,-29,1,-19]);
    if(lift>1) {
      oval(g,-5,-26,5,4,'#70558b');oval(g,5,-27,5,4,'#72558b');
      oval(g,-6,-25,1.9,1.1,'#ffce77');oval(g,5,-26,1.9,1.1,'#ffce77');
    }
    g.save();g.translate(0,-lift);
    polygon(g,'#65485a',[-24,-29,-1,-39,23,-31,21,-25,0,-17,-23,-24]);
    polygon(g,'#f1d19a',[-22,-29,-1,-37,20,-30,0,-22]);
    polygon(g,'#d19c66',[-22,-28,0,-21,0,-19,-21,-25]);
    polygon(g,'#b8865b',[1,-21,20,-29,20,-26,1,-19]);
    polygon(g,'#9a4856',[-15,-32,-10,-34,13,-26,8,-24]);
    polygon(g,'#bf6261',[-12,-23,8,-34,13,-33,-6,-21]);
    stroke(g,'#f1a28b',1.5,[-10,-32,-2,-29,10,-26]);
    // Hand-tied cord, with asymmetric loops and trailing ends.
    g.beginPath();g.moveTo(0,-29);g.bezierCurveTo(-18,-43,-16,-19,-1,-28);
    g.bezierCurveTo(11,-46,18,-29,1,-28);
    g.lineWidth=2.8;g.strokeStyle='#83523f';g.stroke();g.lineWidth=1.1;g.strokeStyle='#f6c986';g.stroke();
    stroke(g,'#936546',2,[-1,-28,-4,-25,-10,-21]);stroke(g,'#f5cb86',1.5,[0,-29,5,-22,9,-22]);
    g.restore();
    polygon(g,'#a94e53',[-12,-22,-6,-20,-6,1,-12,-1]);
    polygon(g,'#a25951',[8,-20,12,-22,12,-2,8,0]);
    polygon(g,'#fff0c0',[6,-16,15,-19,16,-13,7,-10]);
    stroke(g,'#765153',1,[8,-14,13,-16]);
    oval(g,-6,-10,6.8,6,'#8d3547');oval(g,-6,-11,5.7,5.3,'#d6635c');
    star(g,-6,-11,3.5,'#ffce8a',5);
    if(split>.48)stroke(g,'#552e40',1.5,[-4,-16,-7,-12,-4,-10,-8,-5]);
    g.restore();
  }
  function interceptor(g,s,e,warning,bob) {
    const a=warning ? warning.angle : Math.atan2(s.y-e.y,s.x-e.x);
    const charging=warning && warning.delay>0;
    g.save();g.scale(e.radius/17,e.radius/17);
    g.translate(0,-9+bob*.5);g.rotate(a);
    if(warning) {
      const tail=charging?8+14*(1-warning.delay/warning.windup):31;
      polygon(g,charging?'#ffc36bb8':'#9ceeecc2',[-10,-4,-tail-14,0,-10,4]);
      stroke(g,'#fff2b0',1.7,[-12,0,-tail-5,0]);
    }
    // Folded air-mail wings, red/teal postage stripes and a sharply pointed nose.
    polygon(g,'#27384e',[-17,-4,-21,-19,7,-9,23,-1,24,2,7,7,-19,19,-14,5,-21,4]);
    polygon(g,'#e1efdd',[-17,-16,7,-7,20,0,-9,-2]);
    polygon(g,'#99cbc9',[-17,15,-9,2,20,1,6,6]);
    polygon(g,'#478891',[-14,-15,-9,-14,1,-5,-3,-6]);
    polygon(g,'#ea8b80',[-9,-13,-6,-12,4,-4,1,-4]);
    polygon(g,'#44838d',[-12,12,-7,10,0,4,-4,5]);
    polygon(g,'#cd746f',[-7,10,-3,8,4,3,1,4]);
    polygon(g,'#f9edc6',[-17,-3,10,-4,22,1,6,3,-14,3]);
    polygon(g,'#88ada9',[-16,3,20,1,6,5,-10,6]);
    polygon(g,'#df8a75',[14,-2,21,1,13,1]);
    oval(g,5,-1.8,1.8,1.2,'#344a60');
    star(g,-8,-8,3,'#e6aa63',5);
    if(charging)star(g,22,0,3.5,'#fff4bd');
    g.restore();
  }
  function drawEnemy(g,art,s,e,time,isBoss,reduced,cast) {
    const bossIndex=['warden','siren','regent'].indexOf(e.kind);
    const isBat=e.kind==='mote' || e.kind==='hex';
    const color=isBoss?['#ff997e','#9fe8ff','#d4abff'][bossIndex]:({brute:'#ffbc82',hex:'#edaae8',mote:'#aab6ff',jelly:'#e5add7',parcel:'#e5ae73',interceptor:'#a1dedb'}[e.kind]||'#eac2db');
    const size=isBoss?e.radius*3.5:e.radius*(isBat?3.6:3.15);
    const bob=reduced?0:Math.sin(time*(isBat?5:3)+(e.id||0))*2;
    g.save();g.translate(e.x,e.y);
    if(e.spawnTime>0) {
      g.strokeStyle=color;g.lineWidth=1.8;g.setLineDash([5,6]);g.beginPath();g.arc(0,0,e.radius+7,0,TAU);g.stroke();g.setLineDash([]);
      g.globalAlpha=.52;
    }
    oval(g,0,2,e.radius,Math.max(4,e.radius*.35),'#0d173b75');
    const warning=s.hazards.find(h=>h.source===e.id && h.charge);
    if(isBoss || warning || Math.hypot(s.x-e.x,s.y-e.y)<100) {
      // Attacks and body contact use a circular ground footprint. Wings and
      // raised heads can extend beyond it without increasing the damage area.
      g.strokeStyle=color+'ac';g.lineWidth=1.35;g.beginPath();g.arc(0,0,e.radius,0,TAU);g.stroke();
    }
    if(e.kind==='hex') {
      g.save();g.translate(0,-size*.34);g.rotate(time*.24);
      for(let i=0;i<4;i++){
        polygon(g,color,[-3,-size*.56,0,-size*.65,3,-size*.56,0,-size*.49]);g.rotate(Math.PI/2);
      }
      g.restore();
    }
    if(isBoss && art.bosses) {
      // Each boss cell is square on a horizontal triptych. Keep its source aspect.
      const ratio=(art.bosses.naturalWidth/3)/art.bosses.naturalHeight;
      const h=size*1.13, w=h*ratio;
      sprite(g,art.bosses,bossIndex,0,-h*.41+bob,w,h,false,3,1);
    } else if(e.kind==='parcel') {
      parcel(g,e,bob);
    } else if(e.kind==='interceptor') {
      interceptor(g,s,e,warning,bob);
    } else {
      sprite(g,art.items,isBat?2:1,0,-size*.31+bob,size);
      if(e.kind==='brute') {
        for (const side of [-1,1]) {
          g.save();g.scale(side,1);
          polygon(g,'#714659',[size*.12,-size*.62,size*.3,-size*.74,size*.29,-size*.54,size*.19,-size*.51]);
          polygon(g,'#f1ba78',[size*.14,-size*.62,size*.27,-size*.7,size*.23,-size*.59]);g.restore();
        }
      }
    }
    if(e.stunTime>0 && cast?.member==='gosegu' && Math.hypot(e.x-cast.x,e.y-cast.y)<=408) {
      cloud(g,0,-size*.81,7);
      star(g,11,-size*.83-3,3,'#fff1b2');
    } else if(e.stunTime>0) {
      for(let i=0;i<3;i++){const a=time*3+i*TAU/3;star(g,Math.cos(a)*13,-size*.83+Math.sin(a)*3,3,'#ffec9f');}
    }
    if(!isBoss && e.hp<e.maxHp)hpBar(g,0,-size*.82-3,size*.56,e.hp,e.maxHp,color);
    if(s.slowTime>0) {
      g.strokeStyle='#ffdc99';g.lineWidth=1.3;g.beginPath();g.ellipse(0,2,e.radius*.94,e.radius*.42,0,0,TAU);g.stroke();
      stroke(g,'#ffe6ac',1.3,[-3,-1,0,2,e.radius*.55,2]);
    }
    if(isBoss) {
      hpBar(g,0,-size*1.05,Math.max(68,size*.68),e.hp,e.maxHp,color);
      if(e.phase>0){g.strokeStyle=color;g.lineWidth=2;g.beginPath();g.ellipse(0,3,e.radius*1.1,e.radius*.41,0,0,TAU);g.stroke();}
    }
    g.restore();
  }
  // Keep presentation state separate from the deterministic simulation. A new run
  // owns its own stride, and a stage entrance never counts as travelled distance.
  const courierPoses = new WeakMap();
  function courierPose(s,opt) {
    let pose=courierPoses.get(s);
    const now=s.stageElapsed;
    if(!pose || pose.stage!==s.stage || now<pose.time) {
      pose={stage:s.stage,time:now,x:s.x,y:s.y,left:s.dir.x<0,frame:1,travel:0,moving:false,
        dash:false,echoes:[],lastEchoX:s.x,lastEchoY:s.y};
      courierPoses.set(s,pose);
      return pose;
    }
    if(opt.paused || now===pose.time)return pose;
    const dx=s.x-pose.x, dy=s.y-pose.y, distance=Math.hypot(dx,dy);
    const moving=distance>.01;
    pose.moving=moving;
    if(Math.abs(dx)>.01)pose.left=dx<0;
    pose.dash=moving && s.dashTime>0;
    if(moving) {
      pose.travel=(pose.travel+distance)%80;
      pose.frame=Math.floor(pose.travel/20);
      // Contact and passing poses alternate while walking. A dash emphasizes
      // the two extended strides as the courier moves across the ground.
      if(pose.dash)pose.frame=pose.travel<40 ? 0 : 2;
    } else {
      pose.travel=0;
      pose.frame=1;
    }
    pose.echoes=pose.echoes.filter(mark=>now-mark.time<.17 && !opt.reducedMotion);
    if(pose.dash && !opt.reducedMotion && Math.hypot(s.x-pose.lastEchoX,s.y-pose.lastEchoY)>19) {
      pose.echoes.push({x:s.x,y:s.y,left:pose.left,frame:pose.frame,time:now,dash:true,moving:true});
      pose.lastEchoX=s.x;pose.lastEchoY=s.y;
    }
    if(!pose.dash){pose.lastEchoX=s.x;pose.lastEchoY=s.y;}
    pose.time=now;pose.x=s.x;pose.y=s.y;
    return pose;
  }

  function courierSprite(g,art,row,pose,x,y) {
    if(!pose.moving && art.standing) {
      sprite(g,art.standing,row,x,y-34,79,79,pose.left);
      return;
    }
    if(!art.walk) {
      sprite(g,art.characters,row,x,y-27,82,82,pose.left);
      return;
    }
    // All 24 cells share a ground baseline. Lean from the feet without lifting
    // them, so the character lands on the same pixel regardless of her stride.
    g.save();g.translate(x,y);
    if(pose.left)g.scale(-1,1);
    if(pose.dash)g.transform(1,0,-.095,.97,0,0);
    sprite(g,art.walk,row*4+pose.frame,0,-34,79,79,false,4,6);
    g.restore();
  }

  function drawDashTrail(g,s,art,pose) {
    const row=portraits.indexOf(s.member);
    g.save();
    for(const mark of pose.echoes) {
      g.globalAlpha=.25*clamp(1-(s.stageElapsed-mark.time)/.17,0,1);
      courierSprite(g,art,row,mark,mark.x,mark.y);
    }
    g.restore();
  }

  function drawPlayer(g,s,art,opt,pose,cast,time) {
    oval(g,s.x,s.y+3,17,5,'#091b3270');
    if(s.shieldTime>0 && cast?.member!=='ine' && cast?.member!=='viichan' && cast?.member!=='lilpa') {
      g.strokeStyle='#a3edff';g.lineWidth=1.8;
      g.beginPath();g.ellipse(s.x,s.y-26,34,39,0,0,TAU);
      g.fillStyle='#92d4ff18';g.fill();g.stroke();
    }
    g.save();
    if(s.invulnerableTime>0 && !opt.reducedMotion)g.globalAlpha=.74+Math.abs(Math.sin(time*10))*.26;
    courierSprite(g,art,portraits.indexOf(s.member),pose,s.x,s.y);g.restore();
    if(s.cargo) {
      roundBox(g,s.x+14,s.y-53,20,15,6,'#23493dec');text(g,String(s.cargo),s.x+24,s.y-45,10,'#bcffe1');
    }
  }

  function drawOccludedCourier(g,s,art,pose) {
    const boss=s.boss;
    if(!boss || boss.y<=s.y || !art.bosses)return;
    const height=boss.radius*3.5*1.13;
    const width=height*(art.bosses.naturalWidth/3)/art.bosses.naturalHeight;
    const left=boss.x-width/2, top=boss.y-height*.91;
    if(Math.abs(s.x-boss.x)>width*.43+12 || s.y<top+3 || s.y-45>top+height)return;
    // Match the foreground stride exactly when revealing a courier behind a boss.
    g.save();g.beginPath();g.rect(left,top,width,height);g.clip();
    g.globalAlpha=.81;g.shadowColor='#bcffeb';g.shadowBlur=3;
    courierSprite(g,art,portraits.indexOf(s.member),pose,s.x,s.y);
    g.restore();
    g.save();g.beginPath();g.arc(s.x,s.y,12,0,TAU);
    g.lineWidth=3.8;g.strokeStyle='#153947';g.stroke();
    g.lineWidth=1.65;g.strokeStyle='#c1ffe5';g.stroke();
    const x=s.x,y=s.y-74;
    polygon(g,'#183342',[x-8,y-5,x+8,y-5,x,y+6]);
    polygon(g,'#c1ffe5',[x-5,y-3,x+5,y-3,x,y+3]);g.restore();
  }

  function curve(g,color,width,draw) {
    g.beginPath();draw();g.strokeStyle=color;g.lineWidth=width;g.stroke();
  }
  function arc(g,x,y,r,from,to,color,width) {
    curve(g,color,width,()=>g.arc(x,y,r,from,to));
  }
  function litArc(g,x,y,r,from,to,color,outline,width) {
    arc(g,x,y,r,from,to,outline,width+2.8);
    arc(g,x,y,r,from,to,color,width);
  }
  function crystal(g,x,y,size) {
    polygon(g,'#58436f',[x,y-size*1.4,x+size*.72,y,x,y+size*1.4,x-size*.72,y]);
    polygon(g,'#ac99ed',[x,y-size,x+size*.51,y,x,y+size,x-size*.51,y]);
    polygon(g,'#fff4ff',[x,y-size,x,y+size*.35,x-size*.5,y]);
  }
  function heart(g,x,y,size,color='#fb94bf',edge='#733852') {
    g.save();g.translate(x,y);g.scale(size,size);g.beginPath();g.moveTo(0,1);
    g.bezierCurveTo(-1.9,-.18,-.8,-1.45,0,-.56);
    g.bezierCurveTo(.82,-1.47,1.9,-.18,0,1);
    g.fillStyle=color;g.fill();g.strokeStyle=edge;g.lineWidth=.21;g.stroke();
    oval(g,-.44,-.48,.19,.1,'#fff0e4');g.restore();
  }
  function leaf(g,x,y,r,angle) {
    g.save();g.translate(x,y);g.rotate(angle);g.scale(r,r);g.beginPath();
    g.moveTo(-1,0);g.quadraticCurveTo(-.25,-1.12,1,-.22);
    g.quadraticCurveTo(.7,.78,-1,0);g.closePath();g.fillStyle='#a6d997';g.fill();
    g.strokeStyle='#496e62';g.lineWidth=.16;g.stroke();
    stroke(g,'#f8f4b6',.15,[-.72,.02,.62,-.15]);g.restore();
  }
  function pocketWatch(g,x,y,r,turn) {
    g.save();g.translate(x,y);
    roundBox(g,-r*.18,-r*1.3,r*.36,r*.45,r*.1,'#f6ca78');
    oval(g,0,0,r,r,'#705267');oval(g,0,0,r*.89,r*.89,'#f7c777');
    oval(g,0,0,r*.73,r*.73,'#fff2c4');
    for(let i=0;i<8;i++){
      const a=i*TAU/8;
      stroke(g,'#b57f62',Math.max(.8,r*.08),[Math.cos(a)*r*.59,Math.sin(a)*r*.59,Math.cos(a)*r*.68,Math.sin(a)*r*.68]);
    }
    stroke(g,'#754b59',Math.max(1.1,r*.13),[Math.cos(turn)*r*.54,Math.sin(turn)*r*.54,0,0,-r*.24,-r*.3]);
    oval(g,0,0,r*.09,r*.09,'#7c4f60');g.restore();
  }
  function cloud(g,x,y,r) {
    g.save();g.translate(x,y);g.scale(r,r);g.beginPath();g.moveTo(-1,.26);
    g.bezierCurveTo(-1.4,-.16,-1.01,-.64,-.65,-.53);
    g.bezierCurveTo(-.51,-1.12,.33,-1.16,.48,-.54);
    g.bezierCurveTo(1.24,-.76,1.55,.13,.9,.36);
    g.bezierCurveTo(.33,.6,-.64,.64,-1,.26);g.fillStyle='#d6f8ff';g.fill();
    g.strokeStyle='#6399bc';g.lineWidth=.13;g.stroke();
    curve(g,'#ffffff',.11,()=>{g.moveTo(-.56,-.54);g.quadraticCurveTo(-.22,-1.02,.17,-.74);});g.restore();
  }

  function starlightShield(g,s,cast,age,t,reduced) {
    const pulse=clamp(age/.68,0,1);
    if(age<.68) {
      const radius=reduced?125:24+(210-24)*(1-(1-pulse)**2);
      g.save();g.globalAlpha=Math.min(1,(1-pulse)*1.65);
      for(let i=0;i<8;i++){
        const a=i*TAU/8;
        litArc(g,cast.x,cast.y,radius,a+.07,a+.47,'#dfc9ff','#655381',2.9);
        crystal(g,cast.x+Math.cos(a)*radius,cast.y+Math.sin(a)*radius,6.5);
      }
      g.restore();
    }
    const x=s.x,y=s.y-33;
    // A cut-glass shield, open at its centre so the courier remains visible.
    const poly=[x,y-44,x+24,y-30,x+38,y-8,x+31,y+22,x,y+41,x-31,y+22,x-38,y-8,x-24,y-30];
    const glass=g.createLinearGradient(x-38,y-33,x+38,y+34);
    glass.addColorStop(0,'#e1c4ff54');glass.addColorStop(.49,'#c9e7ff10');glass.addColorStop(1,'#99deff4a');
    polygon(g,glass,poly);stroke(g,'#584572',4.7,[...poly,poly[0],poly[1]]);
    stroke(g,'#dfdcff',2.5,[...poly,poly[0],poly[1]]);
    stroke(g,'#c9e5ffb0',1.3,[x-31,y+22,x-26,y-6,x-24,y-30,x,y-44,x+24,y-30,x+27,y-7,x+31,y+22]);
    star(g,x,y-44,5.8,'#fff6d2');
    for(let i=0;i<3;i++){
      const a=t*.75+i*TAU/3;
      crystal(g,x+Math.cos(a)*37,y+Math.sin(a)*36,4.8);
    }
  }

  function slowClock(g,s,cast,age,t,reduced) {
    const pulse=clamp(age/.85,0,1),x=s.x,y=s.y+1;
    if(age<.85) {
      g.save();g.globalAlpha=(1-pulse)*.8;
      const r=reduced?67:33+101*pulse;
      for(let i=0;i<12;i++) {
        const a=i*TAU/12;
        stroke(g,'#ffe6a5',i%3?2:4,[cast.x+Math.cos(a)*(r-6),cast.y+Math.sin(a)*(r-6),cast.x+Math.cos(a)*r,cast.y+Math.sin(a)*r]);
      }
      arc(g,cast.x,cast.y,r-7,-Math.PI*.95,Math.PI*.65,'#ffcd79',2.4);g.restore();
    }
    // The rotating face is projected on the floor. Slowed enemies carry the same gold dial.
    g.save();g.translate(x,y);g.scale(1,.48);
    oval(g,0,0,48,48,'#77543935');
    arc(g,0,0,47,0,TAU,'#7c5661',4);arc(g,0,0,47,0,TAU,'#ffe09b',2);
    for(let i=0;i<12;i++){
      const a=i*TAU/12;
      stroke(g,i%3?'#ffd68c':'#fff4ba',i%3?1.8:3,[Math.cos(a)*39,Math.sin(a)*39,Math.cos(a)*45,Math.sin(a)*45]);
    }
    const a=-Math.PI/2+t*.85;stroke(g,'#ffe1a3',2.3,[Math.cos(a)*32,Math.sin(a)*32,0,0,8,-18]);
    g.restore();pocketWatch(g,x-31,y-56,13,-Math.PI/2+t*.8);
  }

  function nightFlight(g,s,cast,age,t,reduced) {
    const beat=reduced?0:Math.sin(t*7)*3;
    g.save();g.translate(s.x,s.y-33);
    for(const side of [-1,1]) {
      g.save();g.scale(side*1.12,1.08);g.beginPath();g.moveTo(9,9);
      g.bezierCurveTo(19,-4,41,-9,53,-27+beat);
      g.quadraticCurveTo(64,-10+beat,52,3);g.quadraticCurveTo(49,-5,41,1);
      g.quadraticCurveTo(44,9,35,15);g.quadraticCurveTo(30,10,22,18);
      g.lineTo(9,9);g.fillStyle='#635aad';g.fill();g.lineWidth=4.4;g.strokeStyle='#403960';g.stroke();
      g.lineWidth=2.1;g.strokeStyle='#bedaff';g.stroke();
      curve(g,'#e0dfff',1.8,()=>{g.moveTo(12,10);g.quadraticCurveTo(37,-4,53,-23+beat);});
      if(s.shieldTime>0)star(g,53,-23+beat,5,'#fff1b1');
      g.restore();
    }
    g.restore();
    const dx=s.dir.x,dy=s.dir.y;
    for(let i=0;i<3;i++) {
      const phase=(t*.7+i/3)%1, trail=reduced?31+i*12:24+phase*48;
      star(g,s.x-dx*trail-dy*(i-1)*11,s.y-24-dy*trail+dx*(i-1)*11,4-phase*2,'#cfdaff');
    }
    if(age<.63) {
      const p=age/.63,distance=reduced?45:24+65*p;
      g.save();g.globalAlpha=Math.min(1,(1-p)*1.6);
      for(const side of [-1,1]) {
        const swoosh=()=>{
          g.moveTo(cast.x+side*13,cast.y+4);
          g.quadraticCurveTo(cast.x+side*(distance+12),cast.y-18,cast.x+side*distance,cast.y-62);
        };
        curve(g,'#484575',6,swoosh);curve(g,'#bedeff',3,swoosh);
      }
      g.restore();
    }
  }

  function heartMagnet(g,s,cast,age,t,reduced) {
    const reach=44+s.magnetBonus+105;
    if(age<.8) {
      const p=age/.8,r=reduced?reach*.8:16+(reach-16)*(1-p);
      g.save();g.globalAlpha=Math.min(1,(1-p)*1.65);
      for(let i=0;i<5;i++) {
        const a=i*TAU/5+(reduced?0:p*.65);
        const hx=cast.x+Math.cos(a)*r,hy=cast.y+Math.sin(a)*r;
        const trail=()=>{
          g.moveTo(cast.x+Math.cos(a-.44)*(r+12),cast.y+Math.sin(a-.44)*(r+12));
          g.quadraticCurveTo(cast.x+Math.cos(a-.17)*(r+22),cast.y+Math.sin(a-.17)*(r+22),hx,hy);
        };
        curve(g,'#913e68',5.1,trail);curve(g,'#ffb5db',2.8,trail);
        heart(g,hx,hy,8+p*2);
      }
      g.restore();
    }
    if(s.cargo<s.required)for(const mail of s.stars) {
      if(mail.availableAt>s.elapsed || Math.hypot(mail.x-s.x,mail.y-s.y)>reach)continue;
      const midX=(mail.x+s.x)/2,midY=(mail.y+s.y)/2-22;
      curve(g,'#ffb4d7a8',1.8,()=>{g.moveTo(mail.x,mail.y-5);g.quadraticCurveTo(midX,midY,s.x,s.y-5);});
    }
    for(let i=0;i<3;i++) {
      const a=t*1.25+i*TAU/3;
      heart(g,s.x+Math.cos(a)*41,s.y-26+Math.sin(a)*23,8);
    }
  }

  function cloudBurst(g,s,cast,age,t,reduced) {
    const p=clamp(age/.88,0,1);
    if(age<.88) {
      const r=reduced?125:26+254*(1-(1-p)**2);
      g.save();g.globalAlpha=Math.min(1,(1-p)*1.5);
      for(let i=0;i<7;i++) {
        const a=i*TAU/7;
        litArc(g,cast.x,cast.y,r,a+.08,a+.54,'#b5f4ff','#55839d',3.3);
        cloud(g,cast.x+Math.cos(a)*r,cast.y+Math.sin(a)*r,14+4*p);
      }
      g.restore();
    }
    // Wisps linger where the knockback landed. Stunned targets show a matching cloud.
    g.save();g.globalAlpha=clamp((3.2-age)/.7,0,1)*.9;
    for(let i=0;i<3;i++){
      const a=i*TAU/3-.8;
      cloud(g,cast.x+Math.cos(a)*(39+i*4),cast.y-23+Math.sin(a)*17+Math.sin(t*2+i)*2,7+i);
    }
    g.restore();
  }

  function forestCheer(g,s,cast,age,t,reduced) {
    if(age<1.15) {
      const p=age/1.15,h=reduced?82:76+p*19;
      g.save();g.globalAlpha=clamp((1-p)*2,0,1);
      const x=s.x,y=s.y-h;
      for(let i=0;i<6;i++){
        const a=i*TAU/6, r=24+(reduced?10:p*24);
        leaf(g,cast.x+Math.cos(a)*r,cast.y-17+Math.sin(a)*r*.5,8,a);
      }
      // Distinguish a restored heart from the ward granted at full health.
      // Keep both badges above the sprite, including while the courier walks.
      if(cast.restoredHealth>0) {
        heart(g,x,y,15,'#60c192','#335c51');
        stroke(g,'#fffce0',3.4,[x-5,y,x+5,y]);stroke(g,'#fffce0',3.4,[x,y-5,x,y+5]);
      } else {
        const crest=[x-14,y-8,x,y-13,x+14,y-8,x+11,y+5,x,y+14,x-11,y+5];
        polygon(g,'#639e82',crest);stroke(g,'#385a54',3,[...crest,crest[0],crest[1]]);
        stroke(g,'#ebefbb',1.5,[...crest,crest[0],crest[1]]);
        leaf(g,x,y,8,-1);
      }
      g.restore();
    }
    const protectedNow=cast.restoredHealth===0 && s.shieldTime>0;
    for(const side of [-1,1]){
      g.save();g.translate(s.x,s.y+2);g.scale(side,1);
      const high=protectedNow?67:37, sway=reduced?0:Math.sin(t*2)*2;
      curve(g,'#698e73',3,()=>{g.moveTo(8,0);g.bezierCurveTo(32,-5,45+sway,-high*.48,28+sway,-high);});
      for(let i=0;i<4;i++){
        const f=(i+.5)/4,xx=15+Math.sin(f*Math.PI*.83)*20+sway*f;
        leaf(g,xx+(i%2?5:-3),-high*f,6.5,i%2?-.72:-2.45);
      }
      star(g,28+sway,-high,4.2,'#fff4b6');g.restore();
    }
  }

  const skillArt = {
    ine:{duration:4,draw:starlightShield}, jing:{duration:5,draw:slowClock},
    lilpa:{duration:4,draw:nightFlight}, jururu:{duration:4,draw:heartMagnet},
    gosegu:{duration:3.2,draw:cloudBurst}, viichan:{duration:3,draw:forestCheer}
  };
  function drawSkill(g,s,opt) {
    const cast=opt.skillCast;
    if(!cast || cast.member!==s.member || !skillArt[cast.member])return null;
    const age=s.stageElapsed-cast.startedAt, skill=skillArt[cast.member];
    const duration=cast.member==='viichan' && cast.restoredHealth>0 ? 2 : skill.duration;
    if(age<0 || age>=duration)return null;
    g.save();g.lineCap='round';g.lineJoin='round';
    g.globalAlpha=clamp((duration-age)/.22,0,1);
    skill.draw(g,s,cast,age,opt.reducedMotion?0:age,!!opt.reducedMotion);
    g.restore();return cast;
  }

  function drawShot(g,shot) {
    const nova=shot.kind==='nova',angle=Math.atan2(shot.vy,shot.vx);
    g.save();g.translate(shot.x,shot.y-8);g.rotate(angle);
    const length=nova?30:22, color=nova?'#b3d2ff':'#ffdb81';
    const gradient=g.createLinearGradient(-length,0,3,0);
    gradient.addColorStop(0,nova?'#9caff600':'#ffc08100');gradient.addColorStop(1,color);
    polygon(g,gradient,[-length,-2,-2,-4,6,0,-2,4,-length,2]);
    polygon(g,'#fff9db',[-5,0,0,-3,6,0,0,3]);
    if(nova)stroke(g,'#c4edff',1.4,[-18,-5,-7,-6,0,-3]);
    g.restore();
  }
  function drawLetter(g,art,item,bob,marked) {
    const ink={express:'#ffd184',ward:'#8ee3ff',signal:'#dda8ff'}[item.stamp];
    oval(g,item.x,item.y+7,13,4,'#1924456e');
    glow(g,item.x,item.y,24,(ink||'#ffcf68')+'60');
    if(marked) {
      g.beginPath();g.ellipse(item.x,item.y+6,16,5,0,0,TAU);
      g.lineWidth=1.4;g.strokeStyle='#fae5ada6';g.stroke();
    }
    sprite(g,art.items,0,item.x,item.y-3+bob,40);
    if(!ink)return;
    const x=item.x+13,y=item.y-13+bob;
    oval(g,x,y,7,7,'#2b3550');oval(g,x,y,5.8,5.8,ink);
    if(item.stamp==='ward')polygon(g,'#356480',[x-3,y-3,x+3,y-3,x+3,y,x,y+4,x-3,y]);
    else if(item.stamp==='signal')star(g,x,y,4,'#644f88');
    else {
      stroke(g,'#855826',1.6,[x-3,y-2,x-1,y,x-3,y+2]);
      stroke(g,'#855826',1.6,[x,y-2,x+2,y,x,y+2]);
    }
  }
  function drawEffects(g,opt) {
    g.save();
    for(const p of opt.particles || []) {
      g.globalAlpha=clamp(p.life*2,0,1);g.fillStyle=p.color;g.fillRect(p.x,p.y,p.size,p.size);
    }
    for(const r of opt.rings || []) {
      g.globalAlpha=clamp(r.life,0,1);g.strokeStyle=r.color;g.lineWidth=2.7;
      g.beginPath();g.arc(r.x,r.y,r.radius,0,TAU);g.stroke();
    }
    g.textAlign='center';g.textBaseline='middle';g.font='15px '+displayFont;
    for(const f of opt.floaters || []) {
      g.globalAlpha=clamp(f.life*2,0,1);g.strokeStyle='#18233be6';g.lineWidth=3;g.strokeText(f.text,f.x,f.y);
      g.fillStyle=f.color;g.fillText(f.text,f.x,f.y);
    }
    g.restore();
  }

  function goalFor(s) {
    if(s.cargo>=s.required) return s.boss ?
      {point:s.boss,label:s.boss.name,color:'#ffb9bc'} : {point:s.beacon,label:'배달함',color:'#baffe0'};
    let closest=null, shortest=Infinity;
    for(const item of s.stars) {
      if(item.availableAt>s.elapsed)continue;
      const dx=item.x-s.x,dy=item.y-s.y,d=dx*dx+dy*dy;
      if(d<shortest){shortest=d;closest=item;}
    }
    return {point:closest||s.beacon,label:closest?'편지':'배달함',color:closest?'#ffdea0':'#baffe0'};
  }
  function miniMap(g,s,cam,arena,image,canvasWidth,compact,target) {
    const width=compact?91:142, height=width*arena.height/arena.width;
    const padding=3, x=canvasWidth-width-padding*2-10, y=10;
    const sx=width/arena.width, sy=height/arena.height;
    g.save();g.translate(x,y);
    roundBox(g,0,0,width+padding*2,height+padding*2,7,'#19223cf0');
    g.strokeStyle='#f0dbb49c';g.lineWidth=1;g.stroke();
    g.translate(padding,padding);
    g.beginPath();g.roundRect(0,0,width,height,4);g.clip();
    g.drawImage(image,0,0,width,height);
    g.fillStyle='#18223c96';g.fillRect(0,0,width,height);

    const b=arena.bounds;
    g.beginPath();g.rect(0,0,width,height);
    g.rect(b.left*sx,b.top*sy,(b.right-b.left)*sx,(b.bottom-b.top)*sy);
    g.fillStyle='#181a326e';g.fill('evenodd');
    g.strokeStyle='#efd7a775';g.lineWidth=.7;
    g.strokeRect(b.left*sx,b.top*sy,(b.right-b.left)*sx,(b.bottom-b.top)*sy);
    const view=[cam.x*sx,cam.y*sy,cam.width*sx,cam.height*sy];
    g.fillStyle='#e5ffed20';g.fillRect(...view);
    g.strokeStyle='#e3ffefad';g.lineWidth=1;g.strokeRect(...view);
    if(s.cargo<s.required) {
      for(const letter of s.stars) {
        if(letter.availableAt>s.elapsed)continue;
        const px=letter.x*sx, py=letter.y*sy;
        oval(g,px,py,2,2,'#42374a');
        oval(g,px,py,1.3,1.3,'#ffdf93');
      }
      if(target.point!==s.beacon) {
        g.beginPath();g.arc(target.point.x*sx,target.point.y*sy,3.1,0,TAU);
        g.lineWidth=1;g.strokeStyle='#ffeaad';g.stroke();
      }
    }
    // Mark the box even when a nearby letter or boss is the current objective.
    const mx=s.beacon.x*sx, my=s.beacon.y*sy;
    roundBox(g,mx-4.5,my-3.4,9,6.8,1.5,'#212e43');
    roundBox(g,mx-3.5,my-2.4,7,4.8,1,'#ffe1a2');
    stroke(g,'#72563f',.85,[mx-3,my-1.8,mx,my+.3,mx+3,my-1.8]);
    if(s.boss) {
      const bx=s.boss.x*sx, by=s.boss.y*sy;
      polygon(g,'#3c243a',[bx,by-5,bx+4.5,by,bx,by+5,bx-4.5,by]);
      polygon(g,'#ff8c99',[bx,by-3.5,bx+3,by,bx,by+3.5,bx-3,by]);
    }
    g.save();g.translate(s.x*sx,s.y*sy);g.rotate(Math.atan2(s.dir.y,s.dir.x));
    polygon(g,'#173943',[6.1,0,-4.6,-4.5,-3.3,0,-4.6,4.5]);
    polygon(g,'#baffea',[4.4,0,-3,-2.6,-2,0,-3,2.6]);g.restore();
    g.restore();
    return {x,y,w:width+padding*2,h:height+padding*2};
  }
  function direction(g,s,target,cam,scale,w,h,map,compact) {
    const goal=target.point, tx=(goal.x-cam.x)*scale,ty=(goal.y-cam.y)*scale;
    if(tx>=13 && tx<w-13 && ty>=18 && ty<h-20)return;
    const px=(s.x-cam.x)*scale,py=(s.y-cam.y)*scale,dx=tx-px,dy=ty-py;
    const margin=compact?18:24,bot=h-(compact?31:36);
    const fx=dx>0?(w-margin-px)/dx:dx<0?(margin-px)/dx:Infinity;
    const fy=dy>0?(bot-py)/dy:dy<0?(margin-py)/dy:Infinity;
    const f=Math.max(0,Math.min(fx,fy));
    const x=clamp(px+dx*f,margin,w-margin), raw=clamp(py+dy*f,margin,bot);
    const y=(x>map.x-16 && raw<map.y+map.h+17)?map.y+map.h+17:raw;
    g.save();g.translate(x,y);g.rotate(Math.atan2(dy,dx));
    oval(g,0,0,12,12,'#203049e6');polygon(g,target.color,[-5,-6,8,0,-5,6,-1,0]);g.restore();
    const label=target.label;g.font='700 11px '+bodyFont;
    const lw=g.measureText(label).width+12;
    const lx=clamp(x+(x<w*.5?19+lw/2:-19-lw/2),lw/2+3,w-lw/2-3);
    roundBox(g,lx-lw/2,y-9,lw,18,5,'#1c3046df');text(g,label,lx,y,11,target.color);
  }
  function draw(ctx,art,s,opt={}) {
    if(!s || !art.characters || !art.items)return;
    const image=s.stage===0 ? art.plaza : art['stage'+String(s.stage+1).padStart(2,'0')];
    if(!image)return;
    const arena=s.arena || E.ARENA;
    const canvas=ctx.canvas, rect=canvas.getBoundingClientRect();
    if(!rect.width || !rect.height)return;
    const w=rect.width,h=rect.height,dpr=Math.min(2,global.devicePixelRatio||1);
    const pw=Math.round(w*dpr),ph=Math.round(h*dpr);
    if(canvas.width!==pw || canvas.height!==ph){canvas.width=pw;canvas.height=ph;}
    const cam=getCamera(s,w/h,opt.compact),scale=w/cam.width;
    const t=opt.reducedMotion?0:(opt.elapsed ?? s.elapsed);
    const pose=courierPose(s,opt);
    ctx.save();
    ctx.setTransform(pw/w*scale,0,0,ph/h*scale,-cam.x*pw/w*scale,-cam.y*ph/h*scale);
    drawField(ctx,image,arena,cam);
    const entities=[];
    if(inView(cam,s.beacon,125)) {
      drawStop(ctx,s);
      entities.push({type:'box',y:s.beacon.y});
    }
    // The floor effects sit beneath warnings. Keep hostile targeting geometry
    // on top of friendly bursts even in the boss's closest attack range.
    const cast=drawSkill(ctx,s,opt);
    drawDashTrail(ctx,s,art,pose);
    for(const haz of s.hazards||[])drawHazard(ctx,haz);
    const target=goalFor(s),showLetters=s.cargo<s.required;
    if(showLetters)for(const item of s.stars) {
      if(item.availableAt>s.elapsed || !inView(cam,item,35))continue;
      const bob=opt.reducedMotion?0:Math.sin(t*3+item.phase)*2.6;
      drawLetter(ctx,art,item,bob,item===target.point);
    }
    for(const e of s.enemies)if(inView(cam,e))entities.push({type:'enemy',p:e,y:e.y});
    if(s.boss && inView(cam,s.boss,200))entities.push({type:'boss',p:s.boss,y:s.boss.y});
    entities.push({type:'player',y:s.y});
    entities.sort((a,b)=>a.y-b.y);
    for(const unit of entities){
      if(unit.type==='box')mailbox(ctx,art,s);
      else if(unit.type==='player')drawPlayer(ctx,s,art,opt,pose,cast,t);
      else drawEnemy(ctx,art,s,unit.p,t,unit.type==='boss',opt.reducedMotion,cast);
    }
    for(const shot of s.projectiles||[])if(inView(cam,shot,35))drawShot(ctx,shot);
    drawEffects(ctx,opt);
    drawOccludedCourier(ctx,s,art,pose);
    ctx.setTransform(pw/w,0,0,ph/h,0,0);
    const map=miniMap(ctx,s,cam,arena,image,w,opt.compact,target);
    direction(ctx,s,target,cam,scale,w,h,map,opt.compact);
    if(opt.countdown>0) {
      ctx.fillStyle='#17244168';ctx.fillRect(0,0,w,h);
      const x=w/2,y=h*.46;
      text(ctx,opt.countdown>1.25?'READY':'GO!',x,y,opt.compact?48:69,'#fff0bf','center',400,displayFont);
    }
    ctx.restore();
  }

  global.CourierRenderer=Object.freeze({draw,getCamera});
})(globalThis);
