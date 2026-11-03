"""Remove the four owner-marked controls from the final shared/home UI.

Historical review sources and LIVE polling are deliberately not modified.
This removes markup rather than hiding interactive elements with CSS.
"""
from __future__ import annotations

REMOVALS = {
    'archiveBadge': '<a href="#/about">FAN ARCHIVE <span>02</span></a>',
    'searchKeyHint': '<kbd>/</kbd>',
    'membersShortcut': '<a class="nav-note" href="#/members">멤버 만나기 ${icon(\'arrow\')}</a>',
    'homeLiveRefresh': '<button class="live-refresh" data-live-action="refresh" data-live-key="home-refresh" aria-label="방송 상태 새로고침">새로고침</button>',
}


def compose(app: str, css: str, meta: dict) -> tuple[str, str]:
    # Validate every anchor before changing output; never silently ship a partial cleanup.
    for name, markup in REMOVALS.items():
        if app.count(markup) != 1:
            raise ValueError('UI cleanup anchor changed: ' + name)
    for markup in REMOVALS.values():
        app = app.replace(markup, '', 1)
    meta['uiCleanup'] = {
        'removed': list(REMOVALS),
        'searchPreserved': True,
        'liveAutomaticRefreshPreserved': True,
        'livePageManualRefreshPreserved': True,
    }
    return app, css
