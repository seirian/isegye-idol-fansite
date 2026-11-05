// Import compatible operating bookmarks once; never erase or read preview storage.
try {
 if (!localStorage.getItem('isegye:archive:prefs:v1')) {
  const oldTheme=localStorage.getItem('isegye:theme:v1');
  if(['dark','light'].includes(oldTheme))prefs.theme=oldTheme;
  const old=JSON.parse(localStorage.getItem('isegye:bookmarks:v1')||'[]');
  if(Array.isArray(old))for(const id of old.slice(0,3000)){
   if(typeof id!=='string')continue;
   const type=persons.has(id)?'member':songs.has(id)?'song':histories.has(id)?'history':null;
   if(type&&!prefs.favorites.includes(type+':'+id))prefs.favorites.push(type+':'+id);
  }
  localStorage.setItem('isegye:archive:prefs:v1',JSON.stringify(prefs));
 }
}catch{/* Read/write restrictions never block rendering; legacy values stay intact. */}
