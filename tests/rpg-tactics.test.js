import test from 'node:test';
import assert from 'node:assert/strict';
import { CHAPTERS, FINALE } from '../rpg/content.js';
import { createGame, dispatch, restore, serialize } from '../rpg/engine.js';
import { createTacticalField, restoreTacticalField, tacticalMoves, tacticalTarget, tacticalFlank, tacticalApproach, tacticalTerrain } from '../rpg/tactics.js';

// Open an encounter through the same dialogue and battle confirmation as the UI.
function enter(boss=false) {
  let s=createGame();
  while (s.mode==='dialogue') s=dispatch(s,{type:'dialogueNext'});
  const chapter=CHAPTERS[0];
  s.met=[chapter.member]; s.room=boss ? 2 : 1;
  if (boss) { s.solved=[chapter.id]; s.defeated=[chapter.encounters[0].id]; s.stats.battles=1; }
  s.position={x:9,y:4};
  s=dispatch(s,{type:'interact',id:boss ? 'boss' : 'guardian'});
  s=dispatch(s,{type:'choose',id:'start'});
  assert.equal(s.mode,'battle');
  return s;
}
const tactic = (s,command,fields) => dispatch(s,{type:'tactic',command,...fields});

test('movement respects occupancy, terrain and a single movement per unit per round', () => {
  let s=enter();
  const f=s.battle.field;
  for(const invalid of [f.leader, f.allies[1], {x:0,y:0}, {x:7,y:7}]) {
    assert.deepEqual(tactic(s,'move',invalid).battle.field,f);
  }
  const dest=tacticalMoves(s).find(p=>tacticalTerrain(s,p.x,p.y)==='+');
  assert.ok(dest);
  s=tactic(s,'move',dest);
  assert.equal(tacticalMoves(s).length,0);
  assert.equal(s.battle.turn,0);
  assert.equal(s.battle.field.allies[0].x,dest.x);
  s=tactic(s,'select',{id:'jingburger'});
  assert.ok(tacticalMoves(s).length>0);
  s=dispatch(s,{type:'support',id:'jingburger'});
  assert.equal(s.battle.field.active,'hero');
  assert.equal(s.battle.turn,0);
  assert.deepEqual(s.battle.field.acted,['jingburger']);
  assert.equal(tactic(s,'select',{id:'jingburger'}).battle.field.active,'hero');
  assert.deepEqual(restore(serialize(s)),s);
  s=dispatch(s,{type:'battle',move:'defend'});
  assert.equal(s.battle.turn,1);
  assert.deepEqual(s.battle.field.moved,[]);
  assert.deepEqual(s.battle.field.acted,[]);
});

test('cover mitigates an enemy strike, flanking increases damage, and exhausted range prevents a hit', () => {
  let s=enter();
  const exposed=structuredClone(s);
  exposed.battle.field.leader={id:'leader',x:3,y:3};
  const sheltered=structuredClone(s);
  sheltered.battle.field.leader={id:'leader',x:4,y:3};
  sheltered.battle.field.allies[0]={id:'hero',x:3,y:3};
  assert.ok(dispatch(sheltered,{type:'battle',move:'cheer'}).player.hp>dispatch(exposed,{type:'battle',move:'cheer'}).player.hp);
  exposed.battle.field.allies[1]={id:'jingburger',x:4,y:3};
  assert.equal(tacticalFlank(exposed),true);
  const after=dispatch(exposed,{type:'battle',move:'attack'});
  assert.ok(after.battle.hp<exposed.battle.hp-exposed.player.attack);
  const far=tacticalMoves(s).find(p=>p.x===2&&p.y===4);
  s=tactic(s,'move',far);
  assert.equal(tacticalApproach(s,1),null);
  const before=s.battle.hp;
  s=dispatch(s,{type:'battle',move:'attack'});
  assert.equal(s.battle.hp,before);
  assert.equal(s.battle.turn,0);
});

test('a separate enemy can be targeted and dispersed without damaging the leader', () => {
  let s=enter(true), leaderHp=s.battle.hp;
  s=tactic(s,'target',{id:'echo'});
  assert.equal(tacticalTarget(s).id,'echo');
  s.player.focus=6; s.battle.field.echo.hp=1;
  s=dispatch(s,{type:'support',id:'jingburger'});
  assert.equal(s.battle.hp,leaderHp);
  assert.equal(s.battle.field.echo.hp,0);
  assert.equal(tacticalTarget(s).id,'leader');
  assert.deepEqual(restore(serialize(s)),s);
});

test('old battle saves deploy the new squad intact and invalid deployments are rejected', () => {
  const s=enter();
  delete s.battle.field;
  s.battle.turn=3; s.battle.hp=45; s.player.hp=65;
  const restored=restore(serialize(s));
  assert.ok(restored);
  assert.equal(restored.battle.hp,45);
  assert.equal(restored.player.hp,65);
  assert.equal(restored.battle.turn,3);
  assert.equal(restored.battle.field.active,'hero');
  const f=restored.battle.field;
  for(const patch of [{active:'stranger'},{acted:['hero']},{moved:['hero','hero']},{target:'echo'}, {leader:{id:'leader',x:f.allies[0].x,y:f.allies[0].y}}]) {
    assert.equal(restoreTacticalField(restored,{...f,...patch}),null);
  }
  for(let c=0;c<=6;c++) {
    const chapter=CHAPTERS[c];
    for(const encounter of chapter?.encounters || [FINALE.encounter]) {
      const setup={chapter:c,battle:encounter,met:CHAPTERS.slice(0,c+1).map(v=>v.member)};
      const field=createTacticalField(setup);
      assert.deepEqual(restoreTacticalField(setup,field),field);
    }
  }
});
