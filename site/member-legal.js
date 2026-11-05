/* Authenticated disclosures only: shared chrome/theme, no application data or API calls. */
(()=>{
 'use strict';
 const key='isegye:archive:prefs:v1';
 let theme='dark';
 try{const prefs=JSON.parse(localStorage.getItem(key)||'null');const value=prefs?.theme||localStorage.getItem('isegye:theme:v1');if(['dark','light'].includes(value))theme=value;}catch{}
 const paths={sun:'M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1 1M18 18l1 1M5 19l1-1M18 6l1-1M16 12a4 4 0 1 1-8 0 4 4 0 0 1 8 0',moon:'M20 15a9 9 0 0 1-11-11A9 9 0 1 0 20 15'};
 function apply(){document.documentElement.dataset.theme=theme;const b=document.querySelector('[data-action="theme"] path');if(b)b.setAttribute('d',paths[theme==='dark'?'sun':'moon']);}
 apply();
 document.addEventListener('DOMContentLoaded',()=>{
  apply();
  try{const p=JSON.parse(localStorage.getItem(key)||'null');const badge=document.querySelector('[data-save-count]');if(badge&&Array.isArray(p?.favorites)){badge.textContent=String(p.favorites.filter(x=>typeof x==='string').length);badge.hidden=false;}}catch{}
 });
 document.addEventListener('click',e=>{
  const b=e.target.closest('[data-action]');if(!b)return;
  if(b.dataset.action==='theme'){
   theme=theme==='dark'?'light':'dark';apply();
   try{const p=JSON.parse(localStorage.getItem(key)||'{}');if(!p||typeof p!=='object'||Array.isArray(p))throw Error('Invalid preferences');p.theme=theme;localStorage.setItem(key,JSON.stringify(p));}
   catch{document.getElementById('legal-status').textContent='브라우저 저장을 사용할 수 없어 이 페이지에서만 테마를 유지합니다.';}
  }
  if(b.dataset.action==='more'){
   const menu=document.getElementById('more-menu');const open=menu.classList.toggle('open');b.setAttribute('aria-expanded',String(open));
  }
 });
 let composing=false;
 document.addEventListener('compositionstart',()=>{composing=true;});document.addEventListener('compositionend',()=>{composing=false;});
 document.addEventListener('keydown',e=>{
  if(e.key==='Enter'&&(composing||e.isComposing||e.keyCode===229)&&e.target.matches('input'))e.preventDefault();
  if(e.key==='Escape'){document.getElementById('more-menu')?.classList.remove('open');document.querySelector('[data-action=more]')?.setAttribute('aria-expanded','false');}
 });
 document.addEventListener('submit',e=>{
  if(e.target.id!=='header-search')return;e.preventDefault();if(composing)return;
  const q=String(new FormData(e.target).get('q')||'').trim().slice(0,180);
  if(q)location.assign('/#/search?'+new URLSearchParams({q}));else e.target.querySelector('input').focus();
 });
 addEventListener('storage',e=>{if(e.key!==key)return;try{const p=JSON.parse(e.newValue||'null');if(['dark','light'].includes(p?.theme)){theme=p.theme;apply();}}catch{}});
})();
