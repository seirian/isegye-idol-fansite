/** Trusted build-time wording revisions, applied only AFTER bank validation.
 * No remote field can authorize a revision. Answers, IDs, evidence and version
 * remain byte-for-byte equivalent; local play history therefore stays valid.
 */
export function applyEditorial(catalog, manifest) {
  if (!manifest || manifest.schemaVersion!==1 || !Array.isArray(manifest.edits)) throw new Error('Editorial schema');
  const edits=new Map(), allowed=new Set(['stem','hint','explanation']);
  for(const edit of manifest.edits){
    if(edits.has(edit.id)||!edit.before||!edit.after)throw new Error('Editorial identity');
    const keys=Object.keys(edit.after);
    if(!keys.length||keys.length!==Object.keys(edit.before).length||keys.some(k=>!allowed.has(k)||!Object.hasOwn(edit.before,k)))throw new Error('Editorial fields');
    if(keys.some(k=>typeof edit.after[k]!=='string'||edit.after[k].length<1||edit.after[k].length>800||/[<>\x00-\x1f]/.test(edit.after[k])))throw new Error('Editorial text');
    edits.set(edit.id,edit);
  }
  const questions=catalog.questions.map(q=>{
    const edit=edits.get(q.id);if(!edit)return q;
    if(Object.keys(edit.before).some(k=>q[k]!==edit.before[k]))throw new Error('Editorial baseline changed');
    return {...q,...edit.after};
  });
  return {...catalog,questions};
}
