"""Remove only the three requested review UI items; keep operating footer/guide.

Applied after the heading/footer polish, only to the second-review build.
The first review, approved data, production renderers and hosting are untouched.
"""
from review_2nd_polish import between, one


def app(code):
    nav = '<span class="nav-tools"><a href="#/guide">팬 가이드</a><a href="#/settings" aria-label="화면 설정">${icon(\'settings\')}</a></span>'
    code = one(code, nav, '')
    code = one(code, '<a href="#/guide">팬 가이드</a><a href="#/settings">화면 설정</a>', '')
    code = one(code, between(code, 'function settingsView()', 'function statusView()'), '')
    code = one(code, "else if(root==='settings')html=settingsView();", '')
    # Old bookmarks no longer open the deleted settings page.
    code = one(code, 'function render(){let r=route();',
               "function render(){let r=route();if(r.parts[0]==='settings'){history.replaceState(null,'','#/home');r=route();}")
    code = one(code, '<a class="text-link" href="#/settings">제목·썸네일 가림 설정</a>', '')
    panel = '<section class="panel section"><h3>이 일정 알림</h3><p class="muted">알림 채널·발송 서버는 아직 연결하지 않았습니다. 검토 페이지에서는 알림 설정 화면만 살펴볼 수 있습니다.</p><a class="text-link" href="#/settings">알림 설계 보기 ${icon(\'arrow\')}</a></section>'
    code = one(code, panel, '')
    for prefix in (' const setting=event.target.dataset.setting;', " if(action==='reset-review'&&"):
        lines = [line for line in code.splitlines(keepends=True) if line.startswith(prefix)]
        if len(lines) != 1:
            raise ValueError('Settings handler anchor changed: ' + prefix)
        code = one(code, lines[0], '')
    # Deleted settings must not leave returning visitors with hidden cards or
    # permanently paused photos. Preserve theme, saved items and watched state.
    marker = "for(const k of ['gallery','spoilers','notifications'])prefs[k]=typeof prefs[k]==='boolean'?prefs[k]:defaults[k];"
    code = one(code, marker, marker + '\nprefs.gallery=true;prefs.spoilers=false;prefs.density=\'cards\';prefs.notifications=false;')
    start = '<section class="section panel"><h2>같은 합방, 다른 시점</h2>'
    a = code.index(start)
    b = code.index('</section>', a) + len('</section>')
    code = one(code, code[a:b], '')
    # Keep related record links, but neither the removed label nor an empty gap.
    records = "D.history.filter(h=>h.title.includes('이세계페스티벌')).slice(-3)"
    old = '<section class="section">${sectionHead(\'맥락을 더 살펴보기\')}<div class="list">${' + records + ".map(rowCard).join('')}</div></section>"
    new = '${' + records + '.length?`<section class="section"><div class="list">${' + records + ".map(rowCard).join('')}</div></section>`:''}"
    code = one(code, old, new)
    code = one(code, '2차 검토의 검색·저장함·설정은 별도 브라우저 저장소를 사용합니다.',
               '2차 검토의 검색·저장함은 운영과 분리되며 저장 목록과 테마는 별도 브라우저 저장소를 사용합니다.')
    if any(text in code for text in ('href="#/settings"', 'function settingsView(', '나에게 맞는 화면', '같은 합방, 다른 시점', '맥락을 더 살펴보기', 'data-setting=')):
        raise ValueError('Removed UI remains in generated second-review app')
    return code
