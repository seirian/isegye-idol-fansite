'use strict';
(() => {
  const container = document.querySelector('#google-signin');
  if (!container) return;
  const error = document.querySelector('#signin-error');
  const fail = () => {
    error.hidden = false;
    error.textContent = '로그인을 완료하지 못했습니다. 페이지를 새로고침한 뒤 다시 로그인해 주세요.';
    document.querySelector('#signin-loading').hidden = true;
  };
  let busy = false;
  const begin = () => {
    if (!window.google?.accounts?.id) { fail(); return; }
    google.accounts.id.initialize({
      client_id: container.dataset.clientId,
      nonce: container.dataset.nonce,
      auto_select: false,
      callback: async ({credential}) => {
        if (busy || typeof credential !== 'string') return;
        busy = true; error.hidden = true;
        try {
          const response = await fetch('/auth/google', {
            method: 'POST', credentials: 'same-origin', cache:'no-store',
            headers: {'Content-Type':'application/json','X-CSRF-Token':container.dataset.csrf},
            body: JSON.stringify({credential})
          });
          credential = null;
          const result = await response.json();
          if (!response.ok || result.ok !== true) throw new Error('Login rejected');
          window.location.replace('/');
        } catch { fail(); }
        finally { busy = false; }
      }
    });
    const host = document.querySelector('#google-button');
    let renderedWidth = 0;
    const render = () => {
      const width = Math.max(200, Math.min(280, Math.floor(host.clientWidth)));
      if (width === renderedWidth) return;
      renderedWidth = width;
      host.replaceChildren();
      google.accounts.id.renderButton(host, {
        type:'standard', theme:'outline', size:'large', text:'continue_with', shape:'pill', locale:'ko', width
      });
    };
    render();
    if (window.ResizeObserver) new ResizeObserver(render).observe(host);
    else window.addEventListener('resize', render);
    document.querySelector('#signin-loading').hidden = true;
  };
  if (document.readyState === 'complete') begin();
  else window.addEventListener('load', begin, {once:true});
})();
