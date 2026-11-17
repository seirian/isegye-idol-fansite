import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const source=fs.readFileSync(new URL('../monitoring/monitor.js',import.meta.url),'utf8');
const bootstrap=source.split('  function start() {')[0]+'})();';
function create(stored=null,dark=false,blocked=false){
  const listeners={};const media={matches:dark,addEventListener:(name,fn)=>listeners.media=fn};
  const root={dataset:{}};const storage={getItem:()=>{if(blocked)throw new Error('blocked');return stored;}};
  vm.runInNewContext(bootstrap,{window:{matchMedia:()=>media,addEventListener:(name,fn)=>listeners[name]=fn},document:{documentElement:root,getElementById:()=>null},localStorage:storage});
  return {root,media,listeners};
}
test('monitor default follows the system without storing operational data',()=>assert.equal(create(null,true).root.dataset.theme,'dark'));
test('monitor explicit light overrides dark OS',()=>assert.equal(create('light',true).root.dataset.theme,'light'));
test('monitor explicit dark overrides light OS',()=>assert.equal(create('dark',false).root.dataset.theme,'dark'));
test('monitor corrupt preference falls back safely',()=>assert.equal(create('<script>',false).root.dataset.theme,'light'));
test('monitor blocked preference storage remains usable',()=>assert.equal(create(null,true,true).root.dataset.theme,'dark'));
test('monitor follows live system changes only in system mode',()=>{const c=create();c.media.matches=true;c.listeners.media();assert.equal(c.root.dataset.theme,'dark');const fixed=create('light');fixed.media.matches=true;fixed.listeners.media();assert.equal(fixed.root.dataset.theme,'light');});
test('monitor cross-tab theme changes are validated',()=>{const c=create();c.listeners.storage({key:'isegye:monitor-theme:v1',newValue:'dark'});assert.equal(c.root.dataset.theme,'dark');c.listeners.storage({key:'other',newValue:'light'});assert.equal(c.root.dataset.theme,'dark');c.listeners.storage({key:null,newValue:null});assert.equal(c.root.dataset.theme,'light');});
