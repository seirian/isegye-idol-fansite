# LIVE 검토

이세돌 사전 메뉴를 LIVE로 바꾸고 홈 진입 즉시 여섯 멤버의 방송 상태를 제공합니다. 기존 가독성, 지니뮤직 프로필, 단체 이미지, 소개 간소화를 유지합니다. 사전 문서 원본은 참조 보존을 위해 삭제하지 않되 메뉴와 홈 진입점은 제거하고 기존 dictionary 경로는 LIVE로 연결합니다.

검토 브랜치 feature/live, 빌드 `python scripts/build_live.py`, 출력 live-dist. 기존 운영 기본 빌드·배포는 변경하지 않으며 이 빌드는 production 모드를 거부합니다.

검토 URL: https://seirian.github.io/isegye-idol-fansite/previews/feature-live/#/live

## 참고 화면

2026-10-23 SBO https://segubaseball.com/war-room/ 의 공개 렌더링을 확인했습니다. 방송 인원 집계, 카드, 이름/방송 제목 검색, 시청자/이름/최근 순 정렬, 공식 SOOP 연결을 참고했습니다. SBO 자산·코드·광고는 복제하지 않고 해당 API를 데이터 공급원으로 사용하지 않습니다.

## 실제 데이터

패러블 Creator Network의 공식 SOOP 링크와 각 공개 채널 응답의 user_id/user_nick을 대조했습니다. 아이네 inehine, 징버거 jingburger1, 릴파 lilpa0309, 주르르 cotton1217, 고세구 gosegu2, 비챤 viichan6.

방문자 브라우저가 `https://chapi.sooplive.co.kr/api/{id}/station`을 30초 간격으로 조회합니다. 홈과 LIVE에서 하나의 메모리 상태를 공유합니다. credentials:omit, no-store, 9초 제한; 수동 조회는 10초 간격입니다. 다른 메뉴·숨긴 탭에서는 자동 요청을 멈춥니다. KST 원본 확인 시각과 자동 갱신 상태를 표시합니다.

유효한 채널/현재 시각/명시적인 broad:null일 때만 방송 종료입니다. broad_no가 있는 방송 객체만 LIVE입니다. 응답 누락·채널 불일치·오류·429·시간 초과는 확인 필요입니다. 정상 상태도 90초를 넘으면 확인 필요로 바뀝니다. 과거 station.broad_start와 누적 시청수를 현재 방송 정보로 사용하지 않습니다. 제목·동시 시청수는 해당 필드가 있을 때만 표시합니다.

별도 로그인·Secret·공용 프록시·영상 재송출·자동재생·회원 추적은 없습니다. 프로필은 기존 로컬 이미지를 사용합니다. 플랫폼의 정상 공개 접근 범위만 사용합니다.

공개 웹 채널 응답 연동이며 제휴 Open API의 장기 지원/이용허락을 얻었다고 주장하지 않습니다. SOOP가 응답 구조·CORS 정책을 바꾸면 확인 필요로 처리하고 공식 채널 링크를 유지합니다. 운영 확장 시 플랫폼 정책과 부하를 재검토해야 합니다.

## 검증과 경계

단위·상태전환 UI 검사는 합성 데이터로 수행하며 현재 방송이라고 게시하지 않습니다. 별도 real check는 가로채기 없이 여섯 실제 응답과 Pages 동작을 확인합니다. 결과·스크린샷은 구분합니다. 제목에 임의 HTML을 넣지 않고 새 탭에는 noopener/noreferrer를 사용합니다.

검토 게시 외 main/develop/backup/main1st, 인아워넷·미르·공용 라우터·DNS·Secret은 변경하지 않습니다. 운영 승격 시 LIVE 컴파일러를 기본 빌드에 연결하고 외부 통신을 기존 회귀 검사에 반영해야 합니다.
