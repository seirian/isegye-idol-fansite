/* In-app legal navigation retains the existing shell, palette and browser history. */
const LegalDocuments=(()=>{
 function mount(){
  const r=route(),kind=r.parts[0],section=r.params.get('section');
  if(!['terms','privacy'].includes(kind)||!section)return;
  if(section!=='document-top'&&!new RegExp('^'+kind+'-\\d{2}$').test(section))return;
  requestAnimationFrame(()=>requestAnimationFrame(()=>{const target=document.getElementById(section);if(!target?.closest('.legal-in-site'))return;
   target.setAttribute('tabindex','-1');target.focus({preventScroll:true});target.scrollIntoView({block:'start',behavior:'instant'});
  }));
 }
 document.addEventListener('click',event=>{
  if(event.defaultPrevented||event.button!==0||event.ctrlKey||event.metaKey||event.shiftKey||event.altKey)return;
  const a=event.target.closest('a[href]');if(!a||a.target==='_blank'||a.hasAttribute('download'))return;
  let u;try{u=new URL(a.href,location.href);}catch{return;}
  if(![location.origin,'https://isegye-idol.kr'].includes(u.origin)||u.search)return;
  const match=/^\/(?:auth|account)\/(terms|privacy)$/.exec(u.pathname);if(!match)return;
  const kind=match[1],s=u.hash.slice(1),section=s==='document-top'||new RegExp('^'+kind+'-\\d{2}$').test(s)?s:'';
  event.preventDefault();const next='#/'+kind+(section?'?section='+encodeURIComponent(section):'');
  if(location.hash===next)mount();else location.hash=next;
 });
 return {mount};
})();
