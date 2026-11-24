export function gameFontNotices() {
  return RPG_FONT_NOTICES;
}

// Use packed bytes so the game keeps its offline CSP, including font-src 'none'.
export function activateGameFonts() {
  if (typeof FontFace === 'undefined' || !document.fonts) return Promise.resolve([]);
  return Promise.allSettled(Object.entries(RPG_FONT).map(async ([family, packed]) => {
    const binary = atob(packed);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < bytes.length; i++) bytes[i] = binary.charCodeAt(i);
    const face = new FontFace(family, bytes.buffer, {weight:'400', style:'normal'});
    document.fonts.add(face);
    return face.load();
  }));
}
