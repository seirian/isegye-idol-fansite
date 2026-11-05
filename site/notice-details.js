/* Display bounded public announcement facts; never insert source HTML. */
function archiveNoticeHighlights(row) {
 const items=row?.contentHighlights;
 if(!Array.isArray(items)||!items.length)return `<section class="notice-box" aria-label="공지 상세 내용"><strong>원문 상세 확인</strong><p>현재 이 공지의 상세 내용은 검증되지 않았습니다. 공식 원문에서 확인해 주세요.</p></section>`;
 const checked=row.contentCheckedAt?`<p class="data-note">본문 주요 내용 확인 ${esc(stamp(row.contentCheckedAt))} · 전문과 변경 사항은 공식 원문 우선</p>`:'';
 return `<section class="section panel" aria-label="공개 공지 주요 내용"><h2>공지 주요 내용</h2><ul class="notice-facts">${items.map(item=>`<li>${esc(item)}</li>`).join('')}</ul>${checked}</section>`;
}
