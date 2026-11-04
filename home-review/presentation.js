/* Header input submits once, including Korean IME; URL remains the search state. */
let headerSearchComposing=false;
let disposeHomeGallery=()=>{};
document.addEventListener('compositionstart',event=>{if(event.target.id==='header-search-input')headerSearchComposing=true;});
document.addEventListener('compositionend',event=>{if(event.target.id==='header-search-input')headerSearchComposing=false;});
document.addEventListener('keydown',event=>{
 if(event.target.id==='header-search-input'&&event.key==='Enter'&&(event.isComposing||headerSearchComposing||event.keyCode===229))event.preventDefault();
});
document.addEventListener('submit',event=>{
 if(event.target.id!=='header-search')return;
 event.preventDefault();
 if(headerSearchComposing)return;
 const input=document.getElementById('header-search-input');
 const query=input.value.trim().slice(0,160);
 if(!query){input.focus();return;}
 const target='#/search?'+new URLSearchParams({q:query}).toString();
 if(location.hash===target){document.getElementById('main')?.focus();return;}
 location.hash=target;
});

// Include the current song catalog in global search without losing member/initial filters.
function headerCatalogMatches(query,options,existing){
 if(!['all','music'].includes(options.kind))return [];
 const key=r=>[r.title.normalize('NFKC').toLocaleLowerCase('ko').replace(/[^\p{L}\p{N}]/gu,''),[...r.members].sort().join(','),r.date].join('|');
 const seen=new Set(existing.filter(r=>r.kind==='music').map(key));
 const index=CATALOG.music.songs.map(song=>({
  id:song.id,kind:'music',visibility:'published',title:song.title,date:song.date,members:song.members,
  subtitle:catMemberNames(song),summary:song.album||song.format,
  tags:[...(song.aliases||[]),...(song.albumTracks||[]),song.album||'',song.format,
   CATALOG_TYPES[song.type]||'',song.scope==='group'?'이세계아이돌 이세돌 ISEGYE IDOL':'',
   /re\s*:?\s*wind/i.test(song.title)?'리와인드':'',
   song.members.map(id=>catalogProfiles.get(id)?.en||'').join(' ')]
 }));
 return searchRecords(index,query,{kind:'music',member:options.member}).filter(row=>!seen.has(key(row)));
}
function headerMusicResult(row){
 return `<article class="result-row" data-search-song="${e(row.id)}"><span class="list-symbol">${icon('music')}</span><a class="list-content" href="#/song/${encodeURIComponent(row.id)}"><span class="badge editorial">음악</span><h3>${e(row.title)}</h3><p>${e(row.summary)}</p><p>${formatDate(row.date)} · ${e(row.subtitle)}</p></a>${icon('arrow')}</article>`;
}

function homeGalleryView(){
 const first=HOME_GROUP_GALLERY[0];
 return `<figure class="hm-gallery" aria-label="이세계아이돌 단체 사진" aria-roledescription="슬라이드 쇼" aria-live="off"><div class="hm-gallery-stage"><img class="hm-group" src="${e(first.src)}" width="800" height="450" alt="${e(first.alt)}" decoding="async" fetchpriority="high"></div></figure>`;
}

function homePresentationMount(){
 const input=document.getElementById('header-search-input');
 const route=parseRoute(location.hash);
 if(input&&route.parts[0]==='search')input.value=(route.params.get('q')||'').slice(0,160);
 disposeHomeGallery();
 const root=document.querySelector('.hm-gallery');
 if(!root)return;
 const image=root.querySelector('.hm-group');
 const motion=matchMedia('(prefers-reduced-motion: reduce)');
 let current=0,timer=0,fade=0,generation=0,disposed=false;
 const failed=new Set(),loaded=new Map();
 const blocked=()=>disposed||document.hidden;
 function schedule(){
  clearTimeout(timer);
  root.dataset.autoplay=blocked()?'paused':'playing';
  if(!blocked()){
   // Preload the next photo; only a ready image replaces the current one.
   load((current+1)%HOME_GROUP_GALLERY.length);
   timer=setTimeout(()=>show(current+1),10000);
  }
 }
 function load(index){
  if(!loaded.has(index))loaded.set(index,new Promise(resolve=>{
   const next=new Image();
   next.onload=()=>resolve(next.naturalWidth>0);
   next.onerror=()=>resolve(false);
   next.src=HOME_GROUP_GALLERY[index].src;
  }));
  return loaded.get(index);
 }
 async function show(requested){
  clearTimeout(timer);clearTimeout(fade);
  image.classList.remove('is-changing');
  const token=++generation;
  let index=requested%HOME_GROUP_GALLERY.length;
  for(let attempts=0;attempts<HOME_GROUP_GALLERY.length;attempts++){
   if(blocked()||token!==generation)return;
   if(!failed.has(index)&&await load(index)){
    if(blocked()||token!==generation||!root.isConnected)return;
    const apply=()=>{
     if(blocked()||token!==generation||!root.isConnected)return;
     const item=HOME_GROUP_GALLERY[index];
     current=index;image.src=item.src;image.alt=item.alt;
     root.dataset.index=String(index);
     image.classList.remove('is-changing');schedule();
    };
    // Reduced-motion users get an instant replacement, without a fade.
    if(motion.matches)apply();else{image.classList.add('is-changing');fade=setTimeout(apply,180);}
    return;
   }
   failed.add(index);index=(index+1)%HOME_GROUP_GALLERY.length;
  }
  // Retain the last successfully rendered image when every source is unavailable.
  schedule();
 }
 root.dataset.index='0';
 // No click/hover controls: the visible gallery rotates without user interaction.
 const visibility=()=>{generation++;clearTimeout(fade);image.classList.remove('is-changing');schedule();};
 document.addEventListener('visibilitychange',visibility);
 disposeHomeGallery=()=>{
  disposed=true;generation++;clearTimeout(timer);clearTimeout(fade);
  document.removeEventListener('visibilitychange',visibility);
 };
 schedule();
}
