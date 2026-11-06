/* Operating site introduction. Keep this in sync with the seven current menus. */
function aboutView(){
 const archive=typeof REVIEW_DATA==='object'&&REVIEW_DATA?REVIEW_DATA:null;
 const videoCount=archive?.videos?.length||0;
 const complete=archive?.scope?.videoCoverageComplete||0;
 const channels=archive?.scope?.videoChannelCount||22;
 return heading('이세돌 팬 아카이브 소개','공식 공개 자료를 출처와 날짜 기준으로 모으는 비공식 팬 프로젝트입니다.','ABOUT THIS ARCHIVE')+`
 <div class="prose">
 <p>이 사이트는 이세계아이돌의 팬이 제작·운영하는 <strong>비공식 아카이브</strong>입니다. 이세계아이돌이나 소속사 패러블의 공식 사이트가 아니며, 승인·협찬·후원을 받았다는 뜻도 아닙니다.</p>
 <h2>현재 메뉴 안내</h2>
 <div class="review-status">
 <div class="info-note"><b><a href="#/home">오늘의 이세돌</a></b>공식 소식, 다음 일정과 최근 콘텐츠를 한눈에 확인합니다.</div>
 <div class="info-note"><b><a href="#/members">멤버 소개</a></b>여섯 멤버의 소개와 공개 채널, 관련 음악·영상으로 연결합니다.</div>
 <div class="info-note"><b><a href="#/schedule">소식·일정</a></b>공지 게시일과 실제 일정 날짜를 구분하여 달력과 날짜순 목록으로 제공합니다.</div>
 <div class="info-note"><b><a href="#/music">음악</a></b>발매곡·커버·음반·공식 음악 영상을 검색하고 원본 출처를 살펴볼 수 있습니다.</div>
 <div class="info-note"><b><a href="#/live">LIVE</a></b>연결된 공개 방송 정보와 확인 상태를 보여줍니다. 실제 방송 여부는 원본 플랫폼에서 확인하세요.</div>
 <div class="info-note"><b><a href="#/content">콘텐츠</a></b>최근 영상, 다시보기, 시리즈를 채널·날짜·영상 유형으로 찾아보고 원본 영상으로 이동합니다. 짧은 영상은 재생 길이만으로 쇼츠를 단정하지 않습니다.</div>
 <div class="info-note"><b><a href="#/history">활동 기록</a></b>확인된 음악·무대·활동 기록을 시간순으로 살펴봅니다.</div>
 </div>
 <h2>검색과 개인 설정</h2>
 <p>상단 통합 검색, 저장함, 화면 테마 설정과 팬 가이드를 이용할 수 있습니다. 저장한 항목 등 일부 개인 설정은 브라우저에 보관되며, Google 로그인과 계정 관련 처리는 별도의 인증 안내 및 개인정보처리방침을 따릅니다.</p>
 <h2>자료 수집·갱신 기준</h2>
 <p>공개된 공식 출처의 공지·일정·음악·영상을 정기적으로 확인하는 자동 수집 작업을 운영합니다. 수집 지연이나 원본 수정·삭제로 인해 누락 또는 이전 내용이 남을 수 있으며, 모든 자료의 실시간 정확성이나 과거 자료의 완전성을 보장하지 않습니다.</p>
 <p>영상 카탈로그는 ${channels}개 채널을 대상으로 관리하며, 현재 아카이브에 등록된 영상은 ${videoCount.toLocaleString('ko-KR')}건입니다. 전체 과거 영상 수집 완료 여부는 ${complete}/${channels}개 채널로 기록되어 있습니다. 실제 재생 가능 여부, 영상 분류와 최신 정보는 원본 YouTube 채널에서 확인하세요.</p>
 <h2>출처와 권리</h2>
 <p>공지의 게시 날짜를 방송 날짜로 간주하지 않습니다. 아티스트·소속사·플랫폼의 권리를 존중하며, 원본 영상·자료의 권리는 각 권리자에게 있습니다. 공식 출처를 확인하고 수정이 필요한 기록은 공개 제보 경로로 알려 주세요. 비공개 정보나 개인정보는 공개 이슈에 올리지 마세요.</p>
 <p><a href="#/guide">팬 가이드</a> · <a href="#/status">자료 확인 상태</a> · <a href="https://isegye-idol.kr/auth/terms">이용약관</a> · <a href="https://isegye-idol.kr/auth/privacy">개인정보처리방침</a> · <a href="https://github.com/seirian/isegye-idol-fansite">프로젝트 저장소</a></p>
 </div>`;
}
