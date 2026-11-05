"""Render validated official-public detail notes on archive notice routes."""
from review_2nd_polish import one
DETAILS_JS = """
function archiveNoticeDetails(row) {
 const official=['berriz-notice','parable-web'].includes(row?.sourceId);
 const checked=typeof row?.contentCheckedAt==='string' && Number.isFinite(Date.parse(row.contentCheckedAt));
 const facts=official&&checked&&Array.isArray(row.contentHighlights)
   ? [...new Set(row.contentHighlights.filter(x=>typeof x==='string'&&x.length>=8&&x.length<=170&&!/[<>]/.test(x)))].slice(0,6):[];
 return '<section class="panel section" aria-label="공지 상세 내용"><h2>공지 상세 내용</h2>'+
  (facts.length
   ? '<p class="muted">공개 원문에서 확인한 주요 안내</p><ul class="archive-notice-facts">'+
     facts.map(line=>'<li>'+esc(line)+'</li>').join('')+'</ul>'+
     '<p class="data-note">내용 확인: '+esc(stamp(row.contentCheckedAt))+'</p>'
   : '<p class="muted">원문 상세 내용이 확인되지 않아 제목과 출처만 보존했습니다. 공개된 원문에서 확인해 주세요.</p>')+
  '<p class="data-note">안내 내용은 게시 이후 변경될 수 있습니다. 신청·구매·참여 전에는 원문에서 최신 안내를 확인해 주세요.</p></section>';
}
"""
def adapt_app(app):
    a=app.index('function noticeView(id)')
    b=app.index('function eventView(id)',a)
    c=app.index('function albumCard(',b)
    notice=app[a:b]
    event=app[b:c]
    fragment='<p class="detail-copy">'+'$'+'{esc(r.summary)}</p>'
    notice=one(notice,fragment,fragment+'$'+'{archiveNoticeDetails(r)}')
    event=one(event,fragment,fragment+'$'+'{archiveNoticeDetails(D.notices.find(n=>n.sourceUrl===r.sourceUrl&&n.contentHighlights?.length)||r)}')
    app=app[:a]+notice+event+app[c:]
    return one(app,'function noticeView(id)',DETAILS_JS+'\nfunction noticeView(id)')
