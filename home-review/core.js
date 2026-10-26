/* Home-only selectors. Reuse verified source snapshots; never invent live/news data. */
export function homeLatestVideos(catalog, member = 'all', now = Date.now(), limit = 3) {
 const eligible = new Map();
 for (const person of catalog.members || []) {
  if (member !== 'all' && person.id !== member) continue;
  for (const channel of person.channels || []) {
   if (['본채널', '음악'].includes(channel.kind)) eligible.set(channel.key, {person, channel});
  }
 }
 const seen = new Set(), result = [];
 for (const feed of catalog.videos?.channels || []) {
  const owner = eligible.get(feed.key);
  if (!owner || feed.channelId !== owner.channel.channelId) continue;
  for (const video of feed.videos || []) {
   const published = Date.parse(video.publishedAt);
   if (!/^[A-Za-z0-9_-]{11}$/.test(video.id || '') || !Number.isFinite(published) || published > now) continue;
   result.push({...video, member: owner.person.id, memberName: owner.person.name,
    channelName: owner.channel.name, checkedAt: feed.checkedAt, stale: feed.status !== 'ok' ||
    !Number.isFinite(Date.parse(feed.checkedAt)) || now - Date.parse(feed.checkedAt) > 36 * 3600000});
  }
 }
 return result.sort((a,b) => Date.parse(b.publishedAt) - Date.parse(a.publishedAt) || a.id.localeCompare(b.id))
  .filter(video => {if (seen.has(video.id)) return false; seen.add(video.id); return true;}).slice(0,limit);
}
export function homeMusicSelection(songs, type = 'original', today = '', limit = 3) {
 const kind = ['original','cover','remake'].includes(type) ? type : 'original';
 const rank = {official_mv:0,official_video:1,official_audio:2,fan_backup:3,karaoke_tj:4,karaoke_ky:4};
 const sorted = songs.filter(s => s.type === kind && /^\d{4}-\d{2}-\d{2}$/.test(s.date || '') && (!today || s.date <= today))
  .slice().sort((a,b) => b.date.localeCompare(a.date) ||
   (rank[a.videoSource?.kind] ?? 9) - (rank[b.videoSource?.kind] ?? 9) || a.id.localeCompare(b.id));
 const albums = new Set();
 return sorted.filter(s => {
  const key = kind === 'cover' ? s.id : `${s.album || s.id}|${[...s.members].sort().join(',')}`;
  if (albums.has(key)) return false; albums.add(key); return true;
 }).slice(0,limit);
}
export function homeUpcoming(records, today) {
 return records.filter(r => ['event','music'].includes(r.kind) && /^\d{4}-\d{2}-\d{2}$/.test(r.date || '') && r.date >= today)
  .slice().sort((a,b)=>a.date.localeCompare(b.date)).slice(0,1);
}
