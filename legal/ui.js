/* Canonical public policies, rendered within the same header/footer as fan guide. */
function legalDocumentView(kind){
 const title=kind==='terms'?'이용약관':'개인정보처리방침';
 const tabs=[['terms','이용약관'],['privacy','개인정보처리방침'],['guide','팬가이드']];
 const tools=kind==='privacy'?`<section class="legal-storage" aria-labelledby="legal-storage-title"><h2 id="legal-storage-title">브라우저 저장정보 관리</h2><p>즐겨찾기와 화면 테마는 이 브라우저에 저장됩니다. 아래 버튼은 이 사이트의 브라우저 설정만 지우며 회원 탈퇴나 로그아웃을 대신하지 않습니다.</p><button class="button secondary" data-action="clear-data">이 사이트의 저장 정보 지우기</button></section>`:'';
 return `<div class="legal-shell legal-in-site" id="document-top" aria-label="${title}"><nav class="legal-tabs" aria-label="이용 안내 문서">${tabs.map(([id,label])=>`<a href="#/${id}"${id===kind?' aria-current="page"':''}>${label}</a>`).join('')}</nav><article class="legal-document" data-policy="${kind}" data-version="1.0">${LEGAL_DOCUMENTS[kind]}</article>${tools}</div>`;
}
function legalDocumentMount(){
 const {parts,params}=parseRoute(location.hash),kind=parts[0],section=params.get('section');
 if(!['terms','privacy'].includes(kind)||!section)return;
 if(section!=='document-top'&&!new RegExp('^'+kind+'-\\d{2}$').test(section))return;
 const target=document.getElementById(section);
 if(!target?.closest('.legal-shell'))return;
 target.setAttribute('tabindex','-1');target.focus({preventScroll:true});
 target.scrollIntoView({behavior:'instant',block:'start'});
}
document.addEventListener('click',event=>{
 if(event.defaultPrevented||event.button!==0||event.metaKey||event.ctrlKey||event.shiftKey||event.altKey)return;
 const link=event.target.closest('a[href]');if(!link||link.target==='_blank'||link.hasAttribute('download'))return;
 const href=link.getAttribute('href');let kind=null,section=null;
 if(link.closest('.legal-in-site')&&/^#(?:terms-\d{2}|privacy-\d{2}|document-top)$/.test(href)){
  kind=parseRoute(location.hash).parts[0];section=href.slice(1);
 }else{
  let url;try{url=new URL(link.href,location.href);}catch{return;}
  if(![location.origin,'https://isegye-idol.kr'].includes(url.origin)||url.search)return;
  kind=({'/auth/terms':'terms','/auth/privacy':'privacy'})[url.pathname];
  if(url.hash&&/^#(?:terms-\d{2}|privacy-\d{2}|document-top)$/.test(url.hash))section=url.hash.slice(1);
 }
 if(!['terms','privacy'].includes(kind))return;
 event.preventDefault();const next='#/'+kind+(section?'?section='+encodeURIComponent(section):'');
 if(location.hash===next){if(section)legalDocumentMount();return;}
 location.hash=next;
});
