"""Operating UI adapter; preserve byte-pinned historical review sources."""
from pathlib import Path
from review_2nd_polish import one

ROOT = Path(__file__).resolve().parents[1]


def adapt_app(code):
    code = one(code, 'function thumb(r){', (ROOT/'site/music-source-availability.js').read_text() + '\n' +
        'function thumb(r){if(r.kind===\'song\'&&sourceAvailabilityBlocked(r))return `<div class="thumb" data-video-availability="unavailable"><div class="fallback">${icon(\'music\')}<span>영상 확인 불가</span></div></div>`;')
    code = one(code, "${r.videoSource?.kind==='fan_backup'?badge('팬 백업','warning'):''}",
        "${sourceAvailabilityBlocked(r)?badge('영상 확인 불가','warning'):r.videoSource?.kind==='fan_backup'?badge('팬 백업','warning'):''}")
    code = one(code, "${sourceKind==='fan_backup'?badge('현재 연결: 팬 백업','warning'):''}",
        "${sourceAvailabilityBlocked(s)?badge('영상 확인 불가','warning'):sourceKind==='fan_backup'?badge('현재 연결: 팬 백업','warning'):''}")
    code = one(code,
        "${external(s.url||(s.videoId?'https://www.youtube.com/watch?v='+s.videoId:''),sourceKind==='fan_backup'?'팬 백업 영상 보기':'연결된 영상 보기','button primary')}",
        "${sourceAvailabilityAction(s,sourceKind==='fan_backup'?'팬 백업 영상 보기':'연결된 영상 보기')}")
    code = one(code, '<h3>${esc(s.videoSource?.channel||\'자료 제공처 확인\')}</h3>',
        '${sourceAvailabilityNotice(s)}<h3>${esc(s.videoSource?.channel||\'자료 제공처 확인\')}</h3>')
    code = one(code, '${s.originalVideoId&&s.originalVideoId!==s.videoId?',
        '${s.originalVideoId&&s.originalVideoId!==s.videoId&&(!sourceAvailabilityBlocked(s)||s.originalVideoId!==s.videoSource?.reviewedVideoId)?')
    return code


def adapt_albums(code):
    # The album wrapper replaces songView after the base operating adaptation.
    # Its search buttons remain searches; a known failed video ID stays absent.
    return one(code, 'return `<section class="ai-panel ai-streaming">',
               'return sourceAvailabilityNotice(s)+`<section class="ai-panel ai-streaming">')
