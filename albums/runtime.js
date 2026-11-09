/* Production-only runtime data adapter. Approved album presentation stays unchanged. */
function albumAcceptRuntime(next) {
  if (!albumValidSnapshot(next) || next.feed !== 'daily-albums') return false;
  const at = Date.parse(next.generatedAt), base = Date.parse(albumInsights.generatedAt);
  if (at < base || at > Date.now() + 600000) return false;
  const mappings = {covers: {}, brands: {}, badges: {}};
  for (const [group, target] of Object.entries(mappings)) {
    const rows = next.assets?.[group] || {};
    if (!rows || typeof rows !== 'object' || Array.isArray(rows) || Object.keys(rows).length > 500) return false;
    for (const [key, row] of Object.entries(rows)) {
      const sha = row?.sha256;
      if (!/^[a-f0-9]{64}$/.test(sha || '') || row.path !== `albums/asset-cache/${sha}.webp`) return false;
      if (group !== 'brands' && key !== sha) return false;
      if (group === 'brands' && !['melon','genie','bugs','apple','youtube','youtube_music'].includes(key)) return false;
      target[key] = `/api/albums/assets/${sha}.webp`;
    }
  }
  Object.assign(ALBUMS_ART, mappings.covers);
  Object.assign(ALBUMS_BRANDS, mappings.brands);
  Object.assign(ALBUMS_BADGES, mappings.badges);
  return true;
}
