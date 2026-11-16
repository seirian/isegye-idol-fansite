/* Compiled with approved quiz sources. Shadow DOM confines the menu's CSS. */
window.PlaygroundUI=(()=>{
  const seed=__SEED__, css=__CSS__, markup=__MARKUP__;
  let host=null, root=null, refresh=null, pending=null;
  let adminReferenceView=null, adminRequest=null, adminFailed=false;
  const adminAllowed=()=>typeof IsegyeOps!=='undefined'&&IsegyeOps.allowed();
  function syncAdminAccess(){
    if(!adminAllowed()){adminReferenceView=null;adminFailed=false;return;}
    if(adminReferenceView||adminRequest||adminFailed)return;
    // Gateway/Visibility checks the live session again on this module request.
    adminRequest=import('/src/playground-admin.js').then(m=>{
      if(adminAllowed())adminReferenceView=m.renderReferenceView;
    }).catch(()=>{adminFailed=true;}).finally(()=>{adminRequest=null;if(host?.isConnected)refresh?.();});
  }
  const styles=document.createElement('link');styles.rel='stylesheet';styles.href='src/playground.css';
  async function mount(target){
    if(!target)return;
    if(host){target.append(host);refresh?.();return;}
    target.innerHTML='<p role="status">놀이터를 준비하고 있어요.</p>';
    pending??=fetchBank(seed);
    const bank=await pending;
    // The visitor may have left the menu while the request was in flight.
    if(!target.isConnected||!location.hash.startsWith('#/playground'))return;
    if(host){target.replaceChildren(host);refresh?.();return;}
    host=window.document.createElement('div');host.className='playground-component';
    root=host.attachShadow({mode:'open'});root.innerHTML=markup;root.prepend(styles.cloneNode(true));
    target.replaceChildren(host);
    const realDocument=window.document;
    const document={querySelector:s=>root.querySelector(s),addEventListener:(...a)=>root.addEventListener(...a),get body(){return root.querySelector('.pg-body');},get activeElement(){return root.activeElement;},set title(t){realDocument.title=t;}};
    const PLAYGROUND_DATA=bank.data;
    __CORE__
    __APP__
    const notice=root.querySelector('#bank-note');notice.textContent=bank.message;notice.hidden=!bank.message;
    new MutationObserver(()=>{if(host?.isConnected)refresh?.();}).observe(realDocument.documentElement,{attributes:true,attributeFilter:['data-theme']});
  }
  __BANK__
  return Object.freeze({mount});
})();
