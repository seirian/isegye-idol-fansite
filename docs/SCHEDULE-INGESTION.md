# 소식·일정: 캘린더와 제한을 지키는 수집 (2026-10-30)

## 요청과 범위
소식·일정 하단의 ‘공식 발표 확인하기’ 블록을 제거하고 월간 캘린더, 날짜별 일정, 멤버·출처·종류 필터를 중심으로 재구성한다. 날짜가 없는 글은 최근 소식에만 표시한다. LIVE/홈/음악/멤버/회원 원장과 공사중 조건은 변경하지 않는다.

## 공개 접근 검사와 수집 제한
사용자가 지정한 카페 27842958의 345/1250 게시판과 22137397 글을 2026-10-30에 비로그인 브라우저로 일회성 확인했다. 목록의 카페/게시판/작성자/스탭·매니저 표시를 대조해 공지 30건, 제목에서 일정일을 명시한 5건, 날짜가 있는 팬 방송 참고 6건의 최소 메타데이터를 seed.json에 기록했다. 게시판 권한만으로 임의 작성자를 공식 멤버라고 판단하지 않았다. 본문·댓글·회원ID·팬 개인정보·건강정보를 데이터에 복제하지 않았다. 팬의 퍼센트 추측은 정량 확률로 재표시하지 않는다.

cafe.naver.com/robots.txt 및 apis.naver.com/robots.txt는 User-agent:* Disallow:/를 반환했다. 따라서 카페 및 내부 API에 대한 반복 크롤링을 구현하지 않는다. 로그인 쿠키·세션·프록시·CAPTCHA 우회는 사용하지 않는다. seed의 확인일을 예약 실행일로 덮어쓰지 않으며, 초기 카페 자료를 ‘자동 갱신 중’으로 표시하지 않는다. 검사 증거: Actions 40982638837, 40982947867의 단기 아티팩트.

## 자동 수집 경로
- **패러블 공식 뉴스룸**: parable-asia.com의 robots.txt를 매 실행 확인하고 허용된 뉴스룸에서 게시된 RSS URL을 찾아 읽는다. 피드가 없으면 공개 목록의 관련 링크만 최대8개 확인한다. 사이트 전체/다른 아티스트/댓글을 크롤링하지 않는다. RSS는 최대40개에서 이세돌·멤버 제목만 수집한다. 본문은 날짜 후보 판단에 일시 사용하고 저장하지 않는다. 제목만으로 날짜가 불명확하거나 다중 날짜/포스터 전용이면 ‘소식’으로 남긴다.
- **NAVER API HUB 카페글 검색 API**: ISEGYE_NAVER_CLIENT_ID / ISEGYE_NAVER_CLIENT_SECRET 두 Actions secrets가 있을 때만 사용한다. 값은 NAVER Cloud Platform의 NAVER API HUB Application에서 발급한 Client ID와 Client Secret이며 Google 로그인 Client ID 및 NCP 계정의 Access Key/Secret Key와 별개다. 기존 개발자센터가 아니라 API HUB에서 검색 API를 신청해야 한다. 키가 없으면 설정 필요 상태만 표시하며 패러블 수집은 계속한다. 카페 검색 응답에는 게시판/작성자 및 항목별 작성일이 없으므로 검색 발견 글은 ‘검색·미검증’으로 분리하고 캘린더에 확정 일정으로 만들지 않는다. lastBuildDate를 글 작성일로 사용하지 않는다. 검색 결과에서 제공된 공개 링크만 사용하고 본문을 다시 크롤링하지 않는다.
- **카페 직접 수집**: 해당 서비스의 적법한 읽기 API/제공자 허용 피드가 확보될 때 별도 어댑터로 추가할 수 있다. 현재 반복 수집은 비활성이다. 기존 회원의 계정으로 크롤링하지 않는다.

## 실행·저장
main에서 매시간 17분(UTC, 한국시간도 매시간17분) 예약, 수동실행, 성공한 운영배포 후 실행. GitHub 예약은 정확한 시각/실시간을 보장하지 않으며 지연·중단이 가능하다. PRODUCTION_PAUSED 또는 ISEGYE_SCHEDULE_PAUSED=true면 발행을 중지한다. sourceStates와 마지막 성공 시각을 보이며, 상위 서비스 오류를 ‘새 소식 없음’으로 치환하지 않는다.

기존 배포와 같은 concurrency 잠금을 사용하며 /web/_isegye_idol/.schedule-feed 안의 소유표식/현재JSON/직전JSON/작업잠금만 쓰고 원자적 교체한다. 공개 원문의 최소 제목·링크·날짜·멤버·출처·확인시각만 보관하고 배열별 최대600개로 제한한다. 잘못된 데이터/동시변경/소유자불일치/심볼릭링크는 거부한다. 기존 회원파일·인증키·운영라우터·다른 프로젝트는 쓰지 않는다. 현재/직전 스냅샷은 소스 수정 시 동기화할 수 있으나, 외부 삭제를 완전히 탐지한다고 주장하지 않는다. 삭제·권리 요청은 해당 URL의 항목을 제거한 다음 seed에서도 제거하여 재삽입을 막아야 한다.

/api/schedule은 기존 PHP 권한 확인을 통과한 경우에만 GET/HEAD로 제공한다. 공사중 일반회원/비회원는 접근할 수 없고, 관리자 세션을 대신 만들지 않는다. 외부자료 갱신에 Google 회원정보를 사용하지 않는다. 신선한 서버 피드가 없으면 빌드의 검증된 스냅샷을 표시한다. 페이지 새로고침 버튼과 화면이 열린 동안5분간격 조회는 원문 크롤링이 아니라 저장된 결과 읽기다.

## 날짜·신뢰 규칙
한국시간 기준. 글 게시일과 일정일은 별도. 작성자 확인을 거친 제목의 ‘오늘/내일’만 게시일 기준으로 변환하며 임의 미래 날짜·오전오후를 채우지 않는다. 여러 날짜나 날짜 범위는 자동 단일 일정으로 만들지 않는다. 시간 없는 일정을 00:00으로 표시하지 않는다. 변경·취소/추측은 별도표시하며, 팬 참고는 원문에 해당하는 그 날짜에만 표시한다. 방송 중 여부는 기존 LIVE에 맡긴다.

공식 게시물도 해석이 모호하면 전문을 확인해야 한다. 이 기능은 모든 게시글/이미지공지를 완전 자동 이해하는 시스템이 아니다. 1차 카페 메타데이터와 팬 참고는 초기 확인본이며 실시간 뱅온 예보가 아니다.

## 근거 문서
https://api.ncloud-docs.com/docs/naver-api-hub-search-cafearticle
https://api.ncloud-docs.com/docs/naver-api-hub-overview
https://guide.ncloud-docs.com/docs/apihub-migration
https://developers.naver.com/notice/article/32530
https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule
https://parable-asia.com/robots.txt
https://cafe.naver.com/robots.txt
https://apis.naver.com/robots.txt

## 2026-10-30 API HUB 이관 반영
이관 공지를 놓쳐 초기 구현이 구 개발자센터 endpoint/헤더를 사용했다. 사용자 안내 후 공식 이관 가이드와 API 명세를 확인하고 다음으로 전환했다.
- GET https://naverapihub.apigw.ntruss.com/search/v1/cafearticle
- X-NCP-APIGW-API-KEY-ID / X-NCP-APIGW-API-KEY 요청 헤더
- query, display=20, start=1, sort=date, format=json. 기존 8개 검색어와 매시17분 수집 유지.
- GitHub Secrets 이름 ISEGYE_NAVER_CLIENT_ID / ISEGYE_NAVER_CLIENT_SECRET은 유지하며 등록된 API HUB 값 사용. 키를 URL·로그·아티팩트·브라우저에 넣지 않는다.
- 전송 허용 목록에서 구 endpoint를 제거하고 새 정확한 HTTPS 호스트/경로만 허용한다. 리다이렉트는 따라가지 않으며 패러블 등 다른 출처로 인증 헤더를 보내지 않는다. 구 API 자동 fallback 없음.
- 중첩 API Gateway 오류와 Search 오류는 HTTP 상태 및 제한된 오류 코드만 보존한다. 상태 오류 시 기존 자료/마지막 성공시각 유지. 발행 보고서에 출처별 소식 건수를 추가해 연결 성공과 새 글 수를 구분한다.
- 검색 결과는 계속 검색·미검증 소식이며 작성일·일정일·공식 작성자를 추정하지 않는다. 카페 본문 자동 수집이나 일정 자동 확정 범위를 확대하지 않는다.
실제 연결 사전 검사 Actions 41002601224: 8개 요청 모두 HTTP200/items 확인, 기존 필터 기준 중복 제거 왁물원 후보64건. 이는 사전 검색 결과이며 운영 반영 건수는 이후 데이터 발행 보고서로 확인한다. NCP 앱 신청/요금제/사용량 제한/키 재발급은 이 변경에서 수행하지 않는다.
