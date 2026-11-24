/* The map and its hit areas share this projection and the engine's collision grid. */
const FIELD_W = 760, FIELD_H = 440;
const fieldPoint = (x, y) => ({ x: 259 + x * 32 - y * 27, y: 63 + x * 13 + y * 16 });
const fieldCenter = (x, y) => fieldPoint(x + 0.5, y + 0.5);
const fieldArtCache = new Map();
let fieldTerrainCache;
let fieldScenery;
const fieldEscape = value => String(value).replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char]));

const fieldThemes = [
  { path:'#b19377', light:'#e0c39b', dark:'#846e61', verge:'#5c7355', side:'#594b45', roof:'#a65440', wall:'#e9c798', trim:'#495e57', lamp:'#ffda83' },
  { path:'#b6b4a5', light:'#eff1d6', dark:'#92a3a1', verge:'#649389', side:'#556d76', roof:'#76979e', wall:'#dcd9c5', trim:'#47736d', lamp:'#ffe0b0' },
  { path:'#c6aa9c', light:'#e9cdad', dark:'#a68b87', verge:'#708478', side:'#675665', roof:'#93677b', wall:'#eed2b1', trim:'#526f71', lamp:'#ffe19b' },
  { path:'#91a0a5', light:'#c4ced0', dark:'#6f838b', verge:'#506971', side:'#3c4a59', roof:'#597988', wall:'#bdc7c2', trim:'#3d535e', lamp:'#f4d291' },
  { path:'#abac79', light:'#d9cf9c', dark:'#95916b', verge:'#607f51', side:'#505944', roof:'#658d76', wall:'#e5c495', trim:'#486450', lamp:'#f5cc7b' },
  { path:'#91a6ac', light:'#c7cbd0', dark:'#687f90', verge:'#526e78', side:'#3f505f', roof:'#596e8e', wall:'#b7c7c9', trim:'#465367', lamp:'#ffdc8d' },
  { path:'#c6a574', light:'#edd2a3', dark:'#a28a68', verge:'#797858', side:'#625745', roof:'#927355', wall:'#ead9b7', trim:'#585b55', lamp:'#ffdd83' }
];

function fieldNoise(seed) {
  let n = seed >>> 0;
  return () => { n = (Math.imul(n, 1664525) + 1013904223) >>> 0; return n / 4294967296; };
}
function fieldPoly(ctx, color, points) {
  ctx.fillStyle = color;
  ctx.beginPath();
  ctx.moveTo(points[0], points[1]);
  for (let i = 2; i < points.length; i += 2) ctx.lineTo(points[i], points[i + 1]);
  ctx.closePath();
  ctx.fill();
}
function fieldLine(ctx, color, points, width = 1) {
  ctx.strokeStyle = color;
  ctx.lineWidth = width;
  ctx.beginPath();
  ctx.moveTo(points[0], points[1]);
  for (let i = 2; i < points.length; i += 2) ctx.lineTo(points[i], points[i + 1]);
  ctx.stroke();
}
function fieldOval(ctx, color, x, y, w, h) {
  ctx.fillStyle = color; ctx.beginPath(); ctx.ellipse(x, y, w, h, 0, 0, Math.PI * 2); ctx.fill();
}
function fieldCanvas(w, h) {
  const c = document.createElement('canvas'); c.width = w; c.height = h; return c;
}

export async function loadFieldArt(url) {
  const image = new Image(); image.src = url;
  await image.decode();
  const atlas = fieldCanvas(image.naturalWidth,image.naturalHeight), g = atlas.getContext('2d');
  g.drawImage(image,0,0);
  const pixels=g.getImageData(0,0,atlas.width,atlas.height).data;
  const cells=[];
  for(let i=0;i<12;i++) {
    const x0=Math.round(i%4*atlas.width/4), x1=Math.round((i%4+1)*atlas.width/4);
    const y0=Math.round(Math.floor(i/4)*atlas.height/3), y1=Math.round((Math.floor(i/4)+1)*atlas.height/3);
    let left=x1,top=y1,right=x0,bottom=y0;
    for(let y=y0;y<y1;y++) for(let x=x0;x<x1;x++) {
      if(pixels[(y*atlas.width+x)*4+3]<24) continue;
      left=Math.min(left,x);right=Math.max(right,x);top=Math.min(top,y);bottom=Math.max(bottom,y);
    }
    cells.push(right>left && bottom>top ? [left,top,right-left+1,bottom-top+1] : null);
  }
  fieldScenery={image,cells};
  fieldArtCache.clear();
  fieldTerrainCache=null;
}

function fieldSceneryIndex(kind,chapter,variant) {
  if(kind==='pine') return chapter===1 && variant%3!==2 ? 2 : 0;
  const indices={ tree:1,blossom:3,house:4,tent:5,booth:5,marquee:6,bookshop:7,rock:8,case:9,bush:10,lamp:11 };
  return indices[kind];
}

// A 64px miniature is painted at its own resolution and enlarged with nearest-neighbour sampling.
function fieldMiniature(kind, chapter, variant) {
  const key = [kind,chapter,variant].join('/');
  if (fieldArtCache.has(key)) return fieldArtCache.get(key);
  const pic = fieldCanvas(72, 94), g = pic.getContext('2d');
  g.translate(36, 88);
  const t = fieldThemes[chapter] || fieldThemes[0], random = fieldNoise(8911 + variant * 433 + chapter * 87);
  const poly = (color, ...pts) => fieldPoly(g, color, pts);
  const line = (color, ...pts) => fieldLine(g, color, pts);
  const rect = (color, x, y, w, h) => { g.fillStyle = color; g.fillRect(x, y, w, h); };
  const oval = (color, x, y, w, h) => fieldOval(g, color, x, y, w, h);
  const outline = '#394542', wood = '#8d6849', honey = '#e0bd82', iron = '#495d61', metal = '#adc3bb';
  function box(x, y, a, b, h, top, left, right) {
    poly(left, x-a,y-b, x,y, x,y-h, x-a,y-h-b);
    poly(right, x,y, x+a,y-b, x+a,y-h-b, x,y-h);
    poly(top, x-a,y-h-b, x,y-h-b*2, x+a,y-h-b, x,y-h);
  }
  function pane(x, y, w, h) {
    rect(outline,x-1,y-1,w+2,h+2); rect(t.lamp,x,y,w,h);
    rect('#e99e65',x,y+h-2,w,2); rect(wood,x+Math.floor(w/2),y,1,h);
  }
  function pages(x, y, scale = 1) {
    g.save(); g.translate(x,y); g.scale(scale,scale);
    poly('#825d48',-16,-8,-3,-11,12,-6,15,-2,0,3,-16,-2);
    poly('#f4e5bc',-15,-9,-3,-13,0,-9,-1,0,-15,-4);
    poly('#dfd2a6',0,-9,10,-11,16,-6,2,-1,-1,0);
    line('#b99c78',-12,-8,-4,-10); line('#c3a886',-10,-6,-4,-8);
    line('#a98e73',3,-6,10,-8); rect('#a76851',1,-4,2,8);
    g.restore();
  }
  function leaves(x,y,scale, colors) {
    for (let i=0;i<100;i++) {
      const a=random()*Math.PI*2, r=Math.sqrt(random()), xx=Math.cos(a)*r, yy=Math.sin(a)*r;
      const shade = (xx*.5+yy*.7+random()*.7+.7)/2;
      g.fillStyle=colors[Math.min(colors.length-1, Math.max(0, Math.floor(shade*colors.length)))];
      g.fillRect(Math.round(x+xx*scale),Math.round(y+yy*scale*.8),2+Math.floor(random()*4),2+Math.floor(random()*3));
    }
  }
  function base() { box(0,0,16,6,3,'#aeb8a5','#6b7568','#58665c'); }
  function timber(x,y,h) { rect('#6d5140',x,y-h,4,h); rect('#b78a5d',x,y-h,1,h); }
  function lamp(x,y) {
    rect(iron,x-1,y-18,3,18);
    poly(outline,x-5,y-22,x,y-25,x+5,y-22,x+3,y-13,x-3,y-13);
    rect('#ffdb82',x-3,y-21,6,6); rect('#ffefba',x-2,y-21,2,5);
    rect('#86694c',x,y-22,1,8); rect(iron,x-5,y-23,10,2);
  }
  function sign(textKind) {
    timber(-2,-3,27);
    poly(wood,-16,-25,9,-29,17,-26,12,-20,-15,-17);
    line(honey,-15,-24,9,-28,15,-26); line('#694e3c',-12,-20,7,-23);
    if (textKind === 'sun') { oval('#ffdb74',0,-24,3,3); }
    if (textKind === 'down') { line('#f6e4bd',2,-27,2,-21,-2,-22); }
  }
  if (kind==='case' && fieldScenery) {
    drawFieldProp(g,'case',0,0,56,chapter,variant);
  } else if (kind==='snowman') {
    oval('#a5b9ae',0,-5,15,5);oval('#dce3d0',0,-12,13,12);
    oval('#edf1dc',-2,-28,10,10);oval('#f7f2de',-4,-29,6,7);
    rect('#867596',-11,-22,19,4);rect('#a08baf',3,-21,4,11);
    rect('#48545a',-7,-30,2,2);rect('#48545a',-1,-31,2,2);
    poly('#cc885d',-4,-28,-12,-26,-4,-26);
    line(wood,9,-15,17,-22,17,-26);line(wood,-11,-15,-18,-20);
  } else if (kind==='boat') {
    oval('#8db7ae',0,-3,19,6);
    poly('#efe3bf',-21,-15,0,-10,6,-24,11,-14,20,-18,7,-4,-8,-5);
    poly('#d1bfa2',-21,-15,-1,-10,7,-4,-8,-5);
    line('#fff2cc',-20,-15,-1,-10,19,-17);
  } else if (kind==='wand') {
    box(0,-1,10,4,3,honey,wood,iron);
    poly(iron,-3,-4,-6,-5,1,-21,4,-19);
    poly('#7f9f58',0,-20,0,-25,8,-40,12,-38,10,-31,4,-20);
    line('#f2ff9b',3,-23,10,-37);line('#b1df78',1,-23,8,-38);
  } else if(kind==='tracks' || kind==='stairs') {
    for(let i=0;i<3;i++) {
      box(i*6-6,-2-i*3,12,4,3,'#cabda0','#a09179','#877e6e');
      if(kind==='tracks') {
        oval(wood,i*6-7,-7-i*3,2.2,1.8);
        for(let j=0;j<3;j++)oval(wood,i*6-9+j*2,-9-i*3,0.7,0.7);
      } else rect(t.roof,i*6-8,-7-i*3,3,2);
    }
  } else if (kind === 'pine') {
    rect(wood,-3,-17,7,17); rect('#bb9464',-3,-12,2,11);
    const snow = chapter === 1 && variant % 3 !== 2;
    const colors = snow ? ['#526e73','#779696','#a7bfba','#d7ded0','#edf0db'] : ['#304e49','#406c59','#538664','#80a16e','#9cb584'];
    for (let tier=0;tier<4;tier++) {
      const w=22-tier*4, y=-7-tier*11;
      poly(colors[0],-w,y-3,-w+5,y-11,-w+9,y-13,0,y-29,w-7,y-12,w-2,y-10,w,y-4,8,y,3,y-2,-6,y+1);
      poly(colors[1],-w+2,y-4,-w+8,y-12,0,y-26,3,y-12,1,y-3,-6,y-1);
      for(let k=0;k<w*3;k++) {
        const level=random(), xx=(random()*2-1)*w*level, yy=y-25+level*22;
        rect(colors[Math.min(4,Math.floor(random()*3)+(xx<0?2:0))], Math.floor(xx),Math.floor(yy),2,2);
      }
    }
  } else if (kind === 'tree' || kind === 'blossom' || kind === 'bush') {
    const low = kind === 'bush';
    if (!low) { timber(-3,-2,39); line(wood,1,-20,-9,-33); line(wood,1,-24,10,-34); }
    const colors = kind === 'blossom' ? ['#ffe6d8','#eebfbb','#d99da5','#b98293','#927582'] : ['#a5b87f','#8fa36c','#748c62','#526f59','#456452'];
    const high = low ? -10 : -40;
    for (const [ox,oy,sz] of [[0,-7,15],[-10,1,13],[11,3,12],[-1,7,13]]) {
      oval(colors[3],ox,high+oy,sz,sz*.8); leaves(ox-1,high+oy-1,sz,colors);
    }
    if (low && variant % 3 === 0) for(let i=0;i<12;i++) rect(t.lamp,random()*26-14,random()*11-20,2,2);
  } else if (kind === 'rock') {
    poly('#687b78',-20,-2,-25,-9,-14,-23,-4,-27,12,-22,23,-7,16,-1,2,1);
    poly('#b7bba2',-25,-9,-14,-23,-4,-27,4,-21,-3,-10,-13,-5);
    poly('#929e90',-3,-10,4,-21,12,-22,20,-9,4,-4);
    line('#cdd1b7',-22,-10,-12,-22,-6,-23);
    for(let i=0;i<14;i++)rect('#a2ac96',random()*24-12,random()*8-12,2,1);
  } else if (kind === 'marquee') {
    // A little illuminated proscenium above the ticket lane.
    box(1,-1,29,10,25,t.wall,'#967b67','#b99772');
    poly('#3d4c50',1,-28,26,-36,26,-12,1,-3);
    for(const [x,y] of [[1,-4],[24,-12]]) { timber(x,y,32); rect(honey,x,y-30,2,27); }
    poly('#a45a51',-1,-33,28,-42,26,-33,22,-27,18,-31,13,-25,8,-27,4,-20,0,-22);
    box(0,-29,33,11,5,'#c99071','#996258','#ad6b54');
    for(let i=0;i<12;i++)rect(i%3===0?'#fff0c0':'#eeb578',-30+i*5,-40+Math.min(i,12-i)*1.7,2,2);
    poly('#b87a5f',-26,-46,-10,-59,15,-51,27,-47,0,-36);
    poly('#874f48',0,-36,15,-51,27,-47,25,-44,0,-33);
    poly('#e8c78d',-18,-45,-9,-56,12,-49,17,-46,1,-39);
    oval('#6a6f64',-3,-48,5,5);oval('#ffdc9b',-3,-48,4,4);
    line('#88573c',-3,-51,-3,-48,0,-48);
  } else if (kind === 'house' || kind === 'bookshop') {
    const roofTint=[t.roof,t.roof,t.trim,'#7f7569'][variant%4];
    box(0,-1,26,10,35,t.wall,'#bdab8e',t.wall);
    for(let i=0;i<4;i++)line('#897d6a',-25,-10-i*7,-1,-1-i*7);
    for(let i=0;i<3;i++)line('#b3a78c',1,-2-i*10,25,-11-i*10);
    poly('#665d51',-31,-49,-14,-71,14,-61,31,-46,0,-32);
    poly(roofTint,-31,-49,-13,-71,15,-61,-2,-39);
    poly(t.trim,-2,-39,15,-61,31,-46,0,-33);
    line('#e2ab82',-29,-49,-13,-69,15,-60); line('#ceb190',-30,-47,-1,-36,29,-46);
    for(let i=0;i<4;i++)line('#ffffff35',-26+i*3,-52-i*4,0+i*3,-42-i*4);
    rect(wood,-24,-37,3,29); rect(wood,-3,-29,3,26); rect(wood,22,-38,2,26);
    pane(-18,-32,8,10); pane(11,-33,7,8);
    poly(t.trim,2,-3,9,-6,9,-22,2,-19);
    rect(honey,7,-12,1,2);
    if (kind === 'bookshop' || variant % 2 === 0) {
      poly(t.roof,0,-26,24,-35,30,-29,5,-19);
      for(let i=0;i<3;i++)poly('#e8d8b5',4+i*7,-27-i*2.6,7+i*7,-28-i*2.6,13+i*7,-22-i*2.6,10+i*7,-21-i*2.6);
    } else {
      poly('#ccbea2',-17,-58,-9,-60,-9,-76,-17,-74);
      poly('#8e8374',-9,-60,-5,-62,-5,-77,-9,-76);
      poly('#765f58',-19,-74,-10,-77,-3,-76,-10,-73);
    }
    box(16,-3,7,2,4,'#839269','#8d7152','#6f604b');
    for(let i=0;i<9;i++)rect(i%2?t.lamp:'#71926a',8+random()*14,-7-random()*5,2,3);
  } else if (kind === 'tent' || kind === 'booth') {
    timber(-20,-7,24); timber(18,-7,27); timber(0,-1,27);
    poly(t.trim,-28,-35,-7,-54,20,-44,29,-36,1,-23);
    poly(t.roof,-28,-35,-7,-54,0,-26);
    for(let i=0;i<3;i++) poly('#eee0b7',-5+i*6,-52+i*2,0+i*6,-50+i*2,8+i*6,-27-i*2,3+i*6,-25-i*2);
    box(1,-2,20,6,10,honey,wood,'#a97e56');
    for(let i=0;i<3;i++)pane(-11+i*7,-18-i%2*2,4,4);
  } else if (kind === 'fence' || kind === 'flowers') {
    box(0,-1,19,7,4,'#839273','#8e7e63','#766a56');
    if(kind==='fence') {
      for(let i=0;i<2;i++) {
        line(wood,-17,-10-i*6,14,-18-i*6);
        line(honey,-17,-11-i*6,14,-19-i*6);
      }
      for(let i=0;i<4;i++)timber(-16+i*10,-4-i*2.6,17);
    } else {
      for(let i=0;i<18;i++) {
        const xx=Math.round(random()*30-15), yy=Math.round(random()*5-10-Math.abs(xx)*.18);
        rect('#608266',xx,yy-5,1,6);
        rect(['#f0cfa8','#dfac9c','#b8bd98'][i%3],xx-1,yy-7,3,2);
      }
    }
  } else if (kind === 'lamp') {
    base(); timber(-1,-7,34); line(iron,1,-38,6,-45,12,-46,14,-42);
    poly(iron,8,-40,12,-43,17,-40,16,-33,10,-32);
    rect('#ffe5a1',10,-39,5,5);rect('#fff4ca',10,-39,2,4);
  } else if (kind === 'gate' || kind === 'sealed') {
    base(); box(0,1,23,7,2,'#c4b79b','#837c6d','#706c62');
    for(const [x,y] of [[-16,-5],[15,-12]]) {
      box(x,y,5,2,40,'#ead8ac',wood,'#6c574b'); box(x,y-39,6,3,3,honey,wood,'#6c574b');
    }
    poly(t.roof,-23,-47,11,-56,23,-51,-12,-40);
    poly(t.trim,-12,-40,23,-51,23,-47,-12,-36);
    line(honey,-22,-47,11,-55,21,-51);
    if(kind === 'sealed') {
      line('#b4754e',-13,-24,14,-21); line('#d8ae78',-13,-23,14,-20);
      poly('#be9763',-3,-23,4,-25,4,-17,-3,-15); rect(outline,0,-21,1,3);
    } else {
      for(let i=0;i<6;i++) { oval(i%2?t.lamp:'#eabc82',-13+i*5,-37-i*1.5,1.5,2); }
    }
  } else if (kind === 'bench') {
    for(const [x,y] of [[-18,-3],[12,-8],[0,-1]])timber(x,y,9);
    box(0,-7,20,6,3,honey,wood,'#675543');
    poly(wood,-21,-13,12,-23,12,-29,-21,-19);
    line(honey,-21,-18,12,-28); line('#ad8860',-20,-15,12,-25);
    lamp(19,-5);
  } else if (kind === 'lectern' || kind === 'press') {
    box(0,0,12,5,3,wood,'#715744','#584b40'); timber(-1,-4,18);
    box(0,-17,17,7,3,honey,wood,'#715744'); pages(0,-23);
    if (kind==='press') { timber(-16,-18,21); timber(13,-23,22); rect(iron,-16,-44,33,3); rect(iron,0,-45,3,15); }
  } else if (kind === 'notice' || kind === 'poster') {
    timber(-12,-1,27); timber(10,-5,27);
    poly(wood,-18,-38,15,-46,16,-18,-18,-10);
    poly('#f2e0b3',-14,-35,12,-41,12,-21,-14,-15);
    for(let i=0;i<3;i++)line('#a58561',-10,-28+i*4,7,-32+i*4);
    poly(t.roof,-21,-38,-15,-44,14,-50,20,-44); rect('#bc6951',6,-26,3,4);
  } else if (kind === 'case' || kind === 'reel' || kind === 'stack') {
    box(0,-2,18,7,13,honey,wood,'#745e4c');
    if(kind === 'stack') {
      for(let i=0;i<4;i++)box((i%2)*2,-14-i*4,13,5,3,i%2?t.roof:t.trim,'#d9c7a0','#aa9c7e');
    } else if (kind === 'reel') {
      for (const x of [-7,6]) {
        oval(metal,x,-22,7,7); oval(iron,x,-22,2,2);
        for(let i=0;i<4;i++)oval(iron,x+Math.cos(i*1.57)*4,-22+Math.sin(i*1.57)*4,1.2,1.2);
      }
    } else { for (const x of [-9,9])rect('#c5ab77',x,-18,3,11); rect(honey,-1,-13,3,4); }
  } else if (kind === 'spotlight' || kind === 'relay') {
    base(); timber(-2,-5,18);
    if(kind === 'relay') {
      rect(iron,-3,-44,4,26);
      for(let i=0;i<3;i++){line(metal,-12+i*2,-36-i*5,9-i*2,-42-i*4);}
      box(0,-5,12,5,16,metal,iron,'#5b7777'); pane(2,-19,6,4);
    } else {
      line(iron,-12,-28,-12,-16,8,-19,8,-30);
      poly(iron,-13,-38,2,-42,14,-34,10,-24,-4,-21,-15,-28);
      oval('#ccb982',-9,-29,8,8); oval(variant%2?'#ffdaa1':'#eee0b5',-10,-30,6,6);
      line(metal,2,-41,12,-35);
    }
  } else if (kind === 'bridge') {
    for(let i=0;i<6;i++)box(-15+i*6,-4-Math.sin(i*.63)*4,7,3,3,'#d2e1de','#76939a','#92aeb1');
    for(let i=0;i<3;i++)timber(-15+i*14,-5,9);
    line('#b9cfcf',-14,-14,-1,-18,14,-14);
  } else if (kind === 'seed') {
    box(0,-1,16,7,9,'#846d53','#a67456','#94644d');
    line('#59764c',0,-11,-2,-29); oval('#83a066',-5,-22,7,3); oval('#abc288',3,-29,6,3);
    oval('#f7d7ac',-1,-34,4,6); oval('#e6a799',2,-34,3,4);
  } else if (kind === 'wheel') {
    timber(-10,-3,14); timber(9,-6,16);
    oval(wood,0,-21,14,17); oval('#c6a775',0,-21,11,14); oval('#6a7f79',0,-21,9,12);
    for(let i=0;i<8;i++)line(honey,0,-21,Math.cos(i*Math.PI/4)*12,-21+Math.sin(i*Math.PI/4)*15);
    oval(iron,0,-21,3,4);
  } else if (kind === 'lever' || kind === 'wing') {
    box(0,-1,15,6,7,metal,iron,'#60726f');
    line(iron,1,-11,9,-30); oval(t.roof,9,-30,4,4);
    if(kind==='wing') {
      for(let i=0;i<3;i++)poly(i%2?'#afaec5':'#d3d4d6',0,-15,-6-i*3,-23-i*4,-20-i,-37+i*3,-12-i,-20+i*2);
    }
  } else if (['cassette','headphones','musicbox','pass','collar','stamp'].includes(kind)) {
    box(0,-1,18,7,9,honey,wood,'#775e4b');
    if (kind==='cassette') {
      poly('#394f57',-13,-27,8,-32,13,-16,-8,-12);
      poly('#f0dcb3',-10,-25,6,-29,8,-23,-8,-19);
      for(const x of [-5,4])oval('#8caaab',x,-20-x*.2,2,2);
    } else if(kind==='headphones' || kind==='collar') {
      g.lineWidth=3;g.strokeStyle=kind==='collar'?'#bc7159':iron;g.beginPath();
      g.ellipse(0,-24,11,9,-.35,kind==='collar'?0:Math.PI*.8,kind==='collar'?Math.PI*2:Math.PI*2.2);
      g.stroke();
      if(kind==='headphones') { oval(iron,-10,-20,4,6); oval('#718586',11,-22,4,6); }
      else { oval('#ebbf70',3,-15,3,4); rect('#9c693e',3,-15,1,3); }
    } else if(kind==='stamp') {
      box(2,-16,6,3,3,iron,wood,'#695240');timber(0,-19,6);oval(t.roof,2,-26,6,4);
      poly('#f4dfae',-12,-15,-5,-18,1,-13,-6,-11);
    } else if(kind==='pass') {
      timber(0,-15,22);line('#bb7358',-8,-33,1,-24,8,-36);
      poly('#f6d598',-6,-26,6,-29,9,-17,-3,-14);
      line(t.roof,-4,-23,5,-25);rect(iron,1,-21,3,4);
    } else {
      box(0,-13,11,5,5,'#bca377','#865f53','#77504a');
      poly('#ad8070',-10,-22,9,-27,7,-38,-12,-33);
      poly('#f3d9aa',-8,-24,7,-28,6,-35,-9,-31);
      oval('#ddebd5',1,-29,3,4);oval('#d8b1ad',-1,-24,4,2);
    }
  } else if(kind==='jukebox') {
    box(0,-1,15,7,23,wood,'#a66b56','#86604f');
    oval('#d8bd86',0,-31,13,12);oval('#638b8b',0,-30,9,9);
    for(let i=0;i<3;i++)rect('#e3d4aa',-10+i*6,-16,3,10);
    rect('#eee0af',-7,-25,14,3);
  } else if (kind === 'speaker') {
    box(0,0,14,6,33,'#858e82','#475451','#62716c');
    oval('#273e3c',5,-14,6,8); oval('#819289',5,-14,3,4); oval('#314744',5,-27,3,4);
  } else if (kind === 'flag') {
    timber(-2,-2,48); poly(t.roof,2,-48,17,-45,23,-46,19,-36,4,-36);
    poly('#f1d69f',2,-47,6,-46,6,-36,2,-37); base();
  } else { sign(kind); }
  // Trim the transparent headroom from hit testing without shifting the base anchor.
  const rgba=g.getImageData(0,0,pic.width,pic.height).data;
  let top=pic.height, left=pic.width, right=0, bottom=0;
  for(let y=0;y<pic.height;y++) for(let x=0;x<pic.width;x++) {
    if(rgba[(y*pic.width+x)*4+3]<16) continue;
    top=Math.min(top,y);left=Math.min(left,x);right=Math.max(right,x);bottom=Math.max(bottom,y);
  }
  pic.fieldClip=`inset(${top/pic.height*100}% ${(pic.width-1-right)/pic.width*100}% ${(pic.height-1-bottom)/pic.height*100}% ${left/pic.width*100}%)`;
  fieldArtCache.set(key,pic);
  return pic;
}

export function drawFieldProp(ctx, kind, x, y, size, chapter=0, variant=0) {
  const cell=fieldScenery?.cells[fieldSceneryIndex(kind,chapter,variant)];
  if(cell) {
    const [, , width,height]=cell;
    const small=['rock','case','bush'].includes(kind);
    const scale=Math.min(size*(small ? .72 : .9)/width, size*(small ? .55 : 1.12)/height);
    ctx.save(); ctx.imageSmoothingEnabled=true;ctx.imageSmoothingQuality='high';
    ctx.drawImage(fieldScenery.image,...cell,x-width*scale/2,y-height*scale,width*scale,height*scale);
    ctx.restore();
    return;
  }
  const pic = fieldMiniature(kind, chapter, variant);
  ctx.save(); ctx.imageSmoothingEnabled = false;
  ctx.drawImage(pic,x-size/2,y-size*88/72,size,size*94/72); ctx.restore();
}

function fieldWallKind(ch, room, x, y, noise, border, front) {
  if (ch === 1) {
    if (front) return noise < .53 ? 'bush' : 'rock';
    return x < 7 ? 'pine' : (noise < .76 ? 'blossom' : 'tree');
  }
  if (front) return noise < .45 ? 'bush' : noise < .72 ? 'flowers' : noise < .88 ? 'fence' : 'flag';
  if (ch===0 && ((x===5 && y===0) || (x===0 && y===3))) return 'marquee';
  if (border) {
    const skyline = [
      ['house','tent','tree','lamp'], ['pine','blossom','tree','rock'],
      ['bookshop','house','tree','lamp'], ['booth','speaker','flag','lamp'],
      ['tent','tree','booth','flag'], ['house','bookshop','flag','lamp'], ['booth','flag','lamp','tree']
    ][ch];
    return skyline[Math.floor(noise*skyline.length)];
  }
  const furnishings = [
    room === 1 ? ['speaker','case','spotlight','bush','fence','lamp','case','flowers']
      : ['booth','bush','fence','flowers','tree','bush','case','fence'],
    ['pine','blossom','rock'], ['stack','fence','tree','bush','bookshop','flowers','lamp','fence'],
    ['speaker','case','bush','fence','lamp','wing','flag','bush'],
    ['flag','bush','speaker','flowers','fence','tent','tree','bush'],
    ['stack','bush','poster','fence','flowers','lamp','case','tree'],
    ['lamp','flag','speaker','bench','fence','flowers','bush','speaker']
  ][ch];
  return furnishings[Math.floor(noise*furnishings.length)];
}

function fieldSurface(g, ch, x, y, tile, room) {
  const t = fieldThemes[ch], rand = fieldNoise(98731 + x*1371+y*3391+room*19+ch*6361);
  const p = (sx,sy) => fieldPoint(x+sx, y+sy);
  function diamond(col, x1,y1,x2,y2) {
    const corners = [p(x1,y1),p(x2,y1),p(x2,y2),p(x1,y2)];
    fieldPoly(g,col,corners.flatMap(pt => [pt.x,pt.y]));
  }
  const wall = tile === '#';
  const lush = ch === 4 && (y < 3 || y > 5);
  const garden = ch === 1;
  const surface = wall ? (garden && x < 7 ? '#98b4ab' : t.verge)
    : garden ? (x < 7 ? '#c6cdc0' : '#bcae88') : t.path;
  diamond(surface,0,0,1.015,1.015);
  if (wall || lush) {
    if (lush && !wall) diamond('#a1a577',0,0,1,1);
    for(let i=0;i<40;i++) {
      const pt=p(rand(),rand());
      if(ch===1 && x<7 && wall) { g.fillStyle=rand()<.5?'#d6dfcd':'#b8cabc'; g.fillRect(pt.x|0,pt.y|0,4,2); }
      else { g.fillStyle=rand()<.5?'#aec18b77':'#304e4959'; g.fillRect(pt.x|0,pt.y|0,2,1); }
    }
  } else if (garden || ch === 4) {
    // Sparse flecks and flat stepping stones read as soil and snow from a distance.
    for(let i=0;i<37;i++) {
      const pt=p(rand(),rand());
      g.fillStyle=rand()<.6 ? '#f6eac147' : '#6e725c33';
      g.fillRect(pt.x|0,pt.y|0,2+Math.floor(rand()*3),1);
    }
    for(let i=0;i<3;i++) {
      const pt=p(.19+rand()*.6,.18+rand()*.62), s=2+rand()*2;
      fieldPoly(g,'#838b7770',[pt.x-s,pt.y,pt.x-1,pt.y-2,pt.x+s,pt.y-1,pt.x+s+1,pt.y,pt.x,pt.y+2]);
      fieldLine(g,'#e3dfc3bb',[pt.x-s,pt.y,pt.x-1,pt.y-1.5,pt.x+s,pt.y-1]);
    }
  } else {
    // Stagger each course across tile boundaries. The grid reads as continuous paving.
    for(let row=0;row<3;row++) {
      const shift = (row + y * 3)%2 ? .25 : 0;
      for(let j=-1;j<2;j++) {
        const sx=Math.max(0,j/2+shift), ex=Math.min(1,(j+1)/2+shift);
        if(ex<=sx) continue;
        diamond(rand()<.48 ? '#ffffff10':'#292a3110',sx,row/3,ex,(row+1)/3);
        const a=p(sx,row/3), b=p(ex,row/3), c=p(sx,(row+1)/3);
        fieldLine(g,t.dark+'77',[b.x,b.y,a.x,a.y,c.x,c.y],.8);
        fieldLine(g,t.light+'79',[a.x+1,a.y+1,b.x,b.y+1],.8);
      }
    }
    // The main aisle is inlaid in brass at chapter venues, pale stone in the garden.
    if (y===4) {
      for(const off of [.03,.97]) {
        const a=p(0,off),b=p(1,off);
        fieldLine(g,t.light,[a.x,a.y,b.x,b.y],1.4);
      }
    }
  }
}
function fieldTerrain(scene, state) {
  const cacheKey = scene.id + '/' + state.chapter;
  if (fieldTerrainCache?.key === cacheKey) return fieldTerrainCache.canvas;
  const base=fieldCanvas(FIELD_W*2,FIELD_H*2), g=base.getContext('2d');
  g.scale(2,2);
  const t=fieldThemes[state.chapter];
  const corners=[[0,0],[15,0],[15,9],[0,9]].map(([x,y])=>fieldPoint(x,y));
  // Exposed stone and earth on the two front faces of the diorama.
  for(const [a,b] of [[corners[3],corners[2]],[corners[2],corners[1]]]) {
    fieldPoly(g,t.side,[a.x,a.y,b.x,b.y,b.x,b.y+13,a.x,a.y+13]);
    for(let d=0;d<1;d+=.025) {
      const x=a.x+(b.x-a.x)*d,y=a.y+(b.y-a.y)*d;
      fieldLine(g,'#252a3244',[x,y+2,x-1,y+11],1.5);
    }
    fieldLine(g,'#d2b98766',[a.x,a.y+3,b.x,b.y+3]);
  }
  const walls = [];
  scene.tiles.forEach((row,y)=>[...row].forEach((tile,x)=>{
    fieldSurface(g,state.chapter,x,y,tile,state.room);
    if(tile==='#') walls.push({...fieldCenter(x,y),gx:x,gy:y});
  }));
  walls.sort((a,b)=>a.y-b.y);
  for (const w of walls) {
    const {gx,gy,x,y}=w;
    const border=gx===0 || gy===0 || gx===14 || gy===8, front=gx===14 || gy===8;
    const rand=fieldNoise(8979 +gx*1867+gy*3221+state.chapter*347);
    const n=rand(), kind=fieldWallKind(state.chapter,state.room,gx,gy,n,border,front);
    // Front borders form a low embankment so that they never hide the accessible squares behind.
    const garden=state.chapter===1;
    const size=kind==='marquee' ? 94 : front ? 24+n*10 : border ? 59+n*17 : garden ? 41+n*22 : 42+n*13;
    fieldOval(g,'#213d394f',x+4,y+2,size*.29,size*.09);
    drawFieldProp(g,kind,x,y+4,size,state.chapter,(gx+gy)%4);
    if(garden && !front && n < .64) {
      drawFieldProp(g,gx<7?'pine':'blossom',x-11+rand()*4,y+8,25+rand()*13,state.chapter,(gy+1)%4);
    } else if(border && !front && n<.42) {
      drawFieldProp(g,'bush',x-14,y+5,23,state.chapter,gy%3);
    }
  }
  fieldTerrainCache={key:cacheKey,canvas:base};
  return base;
}

const fieldControls = [
  ['spotlight','spotlight','spotlight'], ['bridge','seed','wheel'], ['lever','stack','press'],
  ['wing','wing','wing'], ['relay','relay','relay'], ['sun','sign','down']
];
const fieldRelics = [
  ['notice','cassette'],['musicbox','lectern'],['lectern','jukebox'],
  ['stamp','pass'],['headphones','lectern'],['collar','stamp']
];
const fieldMemories = [
  ['lectern','case'], ['snowman','pass'], ['notice','boat'],
  ['stairs','notice'], ['pass','wand'], ['tracks','poster']
];
function fieldObjectKind(obj,state) {
  switch (obj.type) {
    case 'member': case 'battle': case 'ensemble': return '';
    case 'record': return fieldRelics[state.chapter][Number(obj.id.slice(-1))];
    case 'memory': return fieldMemories[state.chapter][state.room===1 ? 1 : 0];
    case 'clue': return 'notice';
    case 'rest': return 'bench';
    case 'portal': case 'exit': return obj.locked ? 'sealed' : 'gate';
    case 'puzzle': return fieldControls[state.chapter][obj.control];
    default: return 'sign';
  }
}
function fieldObjective(scene,state) {
  const active = type => scene.objects.find(o=>o.type===type && !o.done);
  if (state.chapter===6) return (!state.finalMet && active('ensemble')) || active('battle');
  return active('member') || (state.room===1 && active('puzzle') && scene.objects.find(o=>o.type==='clue'))
    || active('battle') || scene.objects.find(o=>(o.id==='forward' || o.type==='exit') && !o.locked);
}
function fieldControlLit(obj,state,scene) {
  if (obj.type !== 'puzzle') return obj.done;
  const p=state.puzzle[scene.chapter.id], i=obj.control;
  if (obj.done) return true;
  if(state.chapter===3) return p.wings[i];
  if(state.chapter===0) return p.sequence.includes(i);
  return Boolean(p.values[i]);
}

export function renderField(scene, state, sprite) {
  const target=fieldObjective(scene,state);
  const tiles=scene.tiles.flatMap((row,y)=>[...row].map((v,x)=>v==='#' ? '' :
    `<button type="button" class="field-tile" data-action="walk" data-x="${x}" data-y="${y}" tabindex="-1" aria-label="이동 ${x}, ${y}"></button>`)).join('');
  const objects=scene.objects.map(obj=>{
    const kind=fieldObjectKind(obj,state);
    const active=fieldControlLit(obj,state,scene);
    const status=obj.locked?'조건 필요':obj.done?'완료':active?'작동 중':'';
    let art;
    if (kind) art=`<canvas class="field-prop" data-prop="${kind}" data-variant="${obj.control ?? 0}" width="72" height="94" aria-hidden="true"></canvas>`;
    else if(obj.type==='ensemble') art=`<span class="field-ensemble">${state.met.map(id=>sprite('member',id)).join('')}</span>`;
    else art=obj.type==='member' ? sprite('member',obj.member) : sprite('cast',state.chapter===6 ? 7 : state.chapter+1);
    const cls=['field-object', obj.near && 'field-near',obj.locked && 'field-locked',obj.done && 'field-done',active && 'field-lit',obj.id===target?.id && 'field-goal'].filter(Boolean).join(' ');
    const name=fieldEscape(obj.name), title=[name,status].filter(Boolean).join(' · ');
    const action=`data-action="object" data-id="${fieldEscape(obj.id)}" data-x="${obj.x}" data-y="${obj.y}"`;
    // Paint overlapping scenery in depth order; its tile keeps a frontmost click target.
    return `<div class="${cls}" ${action} title="${title}" aria-hidden="true"><span class="field-base"></span>${art}<span class="field-label">${name}${obj.locked?' · 잠김':''}</span></div><button type="button" class="map-object field-target" ${action} title="${title}" aria-label="${title}" ${state.mode==='explore'?'':'disabled'}></button>`;
  }).join('');
  return `<div class="map-board field-board field-ch-${state.chapter}" role="group" tabindex="0" aria-label="${fieldEscape(scene.title)} 탐험 지도. 밝은 길을 누르거나 방향키로 이동하고 E로 조사합니다."><div class="field-horizon world-art world-${Math.min(state.chapter,5)}" aria-hidden="true"></div><canvas class="field-ground" width="${FIELD_W*2}" height="${FIELD_H*2}" aria-hidden="true"></canvas><canvas class="field-route" width="${FIELD_W}" height="${FIELD_H}" aria-hidden="true"></canvas><div class="field-tiles" aria-hidden="true" ${state.mode==='explore'?'':'inert'}>${tiles}</div>${objects}<div class="map-player field-player" data-x="${state.position.x}" data-y="${state.position.y}">${sprite('cast',0)}</div></div>`;
}

export function fieldRoute(scene,start,goal) {
  const queue=[start], parents=new Map([[start,null]]), seen=new Set([start.y*15+start.x]);
  for(let i=0;i<queue.length;i++) {
    const at=queue[i], d=Math.abs(at.x-goal.x)+Math.abs(at.y-goal.y);
    if(d <= (goal.adjacent?1:0)) {
      const path=[];
      for(let pt=at;parents.get(pt);pt=parents.get(pt)) path.push(pt);
      return path.reverse();
    }
    for(const [dx,dy] of [[1,0],[-1,0],[0,1],[0,-1]]) {
      const x=at.x+dx,y=at.y+dy,idx=y*15+x;
      if(scene.tiles[y]?.[x]!=='.' || seen.has(idx))continue;
      const next={x,y};queue.push(next);seen.add(idx);parents.set(next,at);
    }
  }
  return null;
}
export function paintField(root, scene, state, destination=null) {
  const board=root.querySelector('.field-board');
  if(!board) return;
  board.querySelector('.field-ground').getContext('2d').drawImage(fieldTerrain(scene,state),0,0);
  for(const node of board.querySelectorAll('[data-x][data-y]')) {
    const p=fieldCenter(Number(node.dataset.x),Number(node.dataset.y));
    node.style.left=p.x/FIELD_W*100+'%'; node.style.top=p.y/FIELD_H*100+'%';
    if(!node.classList.contains('field-tile')) node.style.zIndex=String(Math.round(p.y)+(node.classList.contains('field-target') ? 1000 : 1));
  }
  for(const c of board.querySelectorAll('canvas[data-prop]')) {
    const art=fieldMiniature(c.dataset.prop,state.chapter,Number(c.dataset.variant));
    c.getContext('2d').drawImage(art,0,0);
    c.style.clipPath=art.fieldClip;
  }
  const route=board.querySelector('.field-route').getContext('2d');
  function trace(goal) {
    route.clearRect(0,0,FIELD_W,FIELD_H);
    if(!goal) return;
    const path=fieldRoute(scene,state.position,goal) || [];
    for(const [i,at] of path.entries()) {
      const p=fieldCenter(at.x,at.y);
      fieldOval(route,'#62513cbb',p.x,p.y+1,4.4,2.5);
      fieldOval(route,'#fff1a6',p.x,p.y,3.8,1.8);
      if(i===path.length-1) {
        route.strokeStyle='#ffedac'; route.lineWidth=2;route.beginPath();
        route.ellipse(p.x,p.y,10,4,0,0,2*Math.PI);route.stroke();
      }
    }
  }
  if(state.mode!=='explore')return;
  trace(destination);
  function preview(event) {
    const target=event.target.closest('[data-action][data-x][data-y]');
    trace(destination || (target && {x:Number(target.dataset.x),y:Number(target.dataset.y),adjacent:target.dataset.action==='object'}));
  }
  board.addEventListener('pointerover',preview); board.addEventListener('focusin',preview);
  board.addEventListener('pointerleave',()=>trace(destination));
  board.addEventListener('focusout',()=>trace(destination));
}
