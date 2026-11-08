/* Pure, dependency-free helpers shared by the isolated album review and tests. */
export function albumDuration(ms) {
  if (!Number.isFinite(ms) || ms <= 0 || ms >= 3600000) return '미확인';
  const seconds = Math.round(ms / 1000);
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`;
}
export function albumSafeUrl(value) {
  try {
    const u = new URL(value);
    return u.protocol === 'https:' && ['music.apple.com', 'itunes.apple.com', 'www.melon.com', 'www.genie.co.kr', 'music.bugs.co.kr', 'www.music-flo.com', 'open.spotify.com', 'www.youtube.com', 'music.youtube.com'].includes(u.hostname) && !u.username && !u.password ? u.href : '';
  } catch { return ''; }
}
export function albumValidSnapshot(value) {
  if (!value || value.schemaVersion !== 1 || !Number.isFinite(Date.parse(value.generatedAt)) || !value.providers || !value.tracks || typeof value.tracks !== 'object' || Array.isArray(value.tracks)) return false;
  return Object.values(value.tracks).every(t => t && typeof t === 'object' && (!t.metadata || (typeof t.metadata.title === 'string' && typeof t.metadata.artist === 'string' && (t.metadata.durationMs === null || Number.isFinite(t.metadata.durationMs)))) && (!t.appleHistory || Array.isArray(t.appleHistory)));
}
export function albumRankSeries(rows, hours = 168, end = Date.now(), maxRank = 100) {
  const limit = [24, 168, 720].includes(hours) ? hours : 168, keyed = new Map();
  for (const p of Array.isArray(rows) ? rows : []) {
    if (!p || !Number.isFinite(Date.parse(p.at))) continue;
    const t = Date.parse(p.at);
    if (t > end || t < end - limit * 3600000) continue;
    if (!['ranked', 'out', 'error'].includes(p.status)) continue;
    if (p.status === 'ranked' && (!Number.isInteger(p.rank) || p.rank < 1 || p.rank > maxRank)) continue;
    if (p.status !== 'ranked' && p.rank != null) continue;
    keyed.set(t, {at: p.at, t, rank: p.status === 'ranked' ? p.rank : null, status: p.status});
  }
  return [...keyed.values()].sort((a, b) => a.t - b.t);
}
export function albumRankSummary(rows) {
  const valid = rows.filter(p => p.status === 'ranked' && Number.isInteger(p.rank));
  const latest = rows.at(-1), previous = rows.at(-2);
  return {latest, best: valid.length ? Math.min(...valid.map(p => p.rank)) : null,
    change: latest?.status === 'ranked' && previous?.status === 'ranked' ? previous.rank - latest.rank : null,
    observations: rows.length, ranked: valid.length};
}
export function albumRankGeometry(rows, start, end, gapMs = 36 * 3600000, maxRank = 100) {
  const width = 760, height = 280, left = 44, right = 20, top = 20, bottom = 32;
  const span = Math.max(1, end - start), paths = [], points = []; let segment = [], prev = null;
  const flush = () => {if (segment.length) paths.push(segment); segment = [];};
  for (const p of rows) {
    if (p.rank == null) {flush(); prev = null; continue;}
    if (prev && p.t - prev.t > gapMs) flush();
    const x = left + (p.t - start) / span * (width - left - right);
    const y = top + (p.rank - 1) / (maxRank - 1) * (height - top - bottom);
    const point = {...p, x: +x.toFixed(2), y: +y.toFixed(2)};
    segment.push(point); points.push(point); prev = p;
  }
  flush(); return {width, height, paths, points};
}
export function albumDemoSeries(hours = 168, end = Date.now()) {
  const ranks = [72, 67, 64, 68, 61, 54, 49, 46, 51, 40, 35, 38, 30, 24, 28, 22];
  return ranks.map((rank, i) => ({at: new Date(end - (ranks.length - 1 - i) * hours * 3600000 / (ranks.length - 1)).toISOString(), rank, status: 'ranked'}));
}
