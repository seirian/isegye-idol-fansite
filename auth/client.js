'use strict';
(() => {
  // Usability only. Every app/asset request is independently checked on the server.
  const link = document.createElement('a');
  link.className = 'isegye-account-link'; link.href = '/auth/login'; link.textContent = 'Google 로그인';
  document.body.appendChild(link);
  let inFlight = false;
  async function check() {
    if (inFlight || document.hidden) return;
    inFlight = true;
    try {
      const r = await fetch('/auth/status', {credentials:'same-origin', cache:'no-store'});
      if (!r.ok) return;
      const s = await r.json();
      if (s.allowed === false) { location.replace('/'); return; }
      link.textContent = s.administrator ? '관리자 · 계정' : s.authenticated ? '내 계정' : 'Google 로그인';
    } catch { /* Server still denies protected content if authentication is unavailable. */ }
    finally { inFlight = false; }
  }
  check(); setInterval(check, 15000);
  window.addEventListener('pageshow', check);
  document.addEventListener('visibilitychange', check);
})();
