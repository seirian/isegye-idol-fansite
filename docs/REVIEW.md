# 1차 화면 검토 안내

## 웹에서 보기

임시 후보 주소: https://raw.githack.com/seirian/isegye-idol-fansite/develop/index.html

이 주소는 공개 GitHub 파일을 표시하는 제3자 미리보기 서비스이며 운영 호스팅이 아닙니다. 첫 접속에서 External Content Notice가 나오면 **Open the page**를 선택합니다. 안내 페이지에 표시되는 제3자 광고는 이 팬사이트에 넣은 광고가 아닙니다. 이 임시 서비스에 개인정보나 비밀번호를 입력하지 마세요.

최종 동작 여부는 최신 push Actions의 `browser-review-커밋/test-results`가 아닌 아티팩트 루트 `preview-access.json`의 `browser[].passed`를 확인하세요. HTTP 200만으로 화면 작동을 판정하지 않습니다. 자세한 최종 검토 결과는 PR #1에 남깁니다.

## 파일로 보기

Actions의 **site-review-커밋** 아티팩트를 내려받아 압축을 풀고 **review.html**을 브라우저로 엽니다. CSS/JavaScript/로고를 포함한 단일 파일이며 별도 설치·웹서버 없이 사용할 수 있습니다. 일반 모듈형 `index.html`은 웹서버가 필요하므로 둘을 구분하세요.

로컬에서 다시 만들기:

```bash
npm test
npm run build
node scripts/standalone.mjs
# dist/review.html 열기
```

## 검토 순서

홈 → 음악 → 솔로 음반 필터 → NO CAT, NO LIFE! 상세 → 출처/관련 멤버 → 즐겨찾기 → 검색에서 `ㅇㅇㄴ` → 월별 달력 → 모바일 메뉴를 확인하세요. 1차에는 구조/디자인/동작을 먼저 검토하고, 방송·밈·취향 등은 실제 원본 검수가 완료된 항목부터 늘립니다.

## 운영과 분리

main 미병합, 인아워넷 배포 미실행, 운영 DNS와 기존 사이트 설정 변경 없음. GitHub Pages는 관리자의 활성화 전까지 사용할 수 없습니다. 2026-10-15 Actions runner에서 두 도메인 isegye-idol.kr과 mir.yeop.net이 같은 IP를 반환했습니다. 이것만으로 같은 문서 루트라고 판단할 수는 없으나, 운영 연결 전 별도 가상호스트/document root를 반드시 확인해야 합니다.

파일·웹 검토판은 공개 자료만 포함하며 비공식 표시와 noindex 설정을 유지합니다. noindex는 접근 제한이 아닙니다.
