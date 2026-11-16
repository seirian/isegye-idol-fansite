/* Fail closed until the current server session authorizes the separate module. */
const IsegyeOps=(()=>{
 let views=null,authorized=false,checking=false,epoch=0,controller=null;
 const active=()=>authorized&&views!==null;
 function repaint(){
  if(typeof render!=='function'||!document.getElementById('app'))return;
  const y=scrollY,focused=document.activeElement,id=focused?.id;
  render();scrollTo(0,y);
  if(id)document.getElementById(id)?.focus({preventScroll:true});
 }
 function revoke(){
  const changed=active();authorized=false;views=null;epoch++;
  document.querySelectorAll('[data-admin-only]').forEach(el=>el.remove());
  if(changed)repaint();
 }
 async function refresh(){
  if(checking||document.hidden||!/^https?:$/.test(location.protocol))return;
  checking=true;const version=epoch;controller=new AbortController();
  const timer=setTimeout(()=>controller?.abort(),5000);
  try{
   const response=await fetch('/auth/status',{credentials:'same-origin',cache:'no-store',redirect:'error',signal:controller.signal});
   if(!response.ok||!response.headers.get('content-type')?.includes('application/json'))throw Error('Role unavailable');
   const state=await response.json();
   if(version!==epoch||document.hidden)return;
   if(state.authenticated!==true||state.administrator!==true||state.allowed!==true){revoke();return;}
   if(active())return;
   // The server checks administrator authority again on this request.
   const module=await import('/src/admin-operations.js');
   if(version!==epoch||document.hidden)return;
   views=module.createViews(Object.freeze({D,esc,stamp,badge,sourceNames,FeedValidators,patch,
    aiData,albumFreeServiceStatus,albumFreshness,
    get albumInsights(){return albumInsights;},get albumApiState(){return albumApiState;}}));
   authorized=true;repaint();
  }catch{if(version===epoch)revoke();}
  finally{clearTimeout(timer);controller=null;checking=false;}
 }
 function panel(name,...args){
  if(!active()||typeof views[name]!=='function')return '';
  return `<div data-admin-only="${name}" class="admin-only-panel">${views[name](...args)}</div>`;
 }
 window.addEventListener('pagehide',()=>{controller?.abort();revoke();});
 window.addEventListener('pageshow',()=>void refresh());
 window.addEventListener('focus',()=>void refresh());
 document.addEventListener('visibilitychange',()=>{if(document.hidden){controller?.abort();revoke();}else void refresh();});
 setInterval(()=>void refresh(),15000);queueMicrotask(()=>void refresh());
 return Object.freeze({allowed:active,panel});
})();
