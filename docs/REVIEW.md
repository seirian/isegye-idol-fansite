# 개발 검토 안내

검토 주소: https://seirian.github.io/isegye-idol-fansite/

이전 raw.githack 임시 주소 대신 위 GitHub Pages 주소를 사용합니다.
`develop`의 검증이 통과하면 Pages로 갱신하며, 배포 후 `build-info.json`의 커밋과
실제 브라우저의 메뉴·검색·모바일 화면을 다시 검사합니다.

사이트는 1차 검토판입니다. main 병합이나 isegye-idol.kr 운영 배포를 의미하지 않습니다.

## 확인 순서

1. PC와 모바일에서 첫 화면과 8개 메뉴를 확인합니다.
2. 음악 목록에서 음반 상세·수록곡·출처·관련 멤버로 이동합니다.
3. 검색에 `ㅇㅇㄴ`을 입력해 아이네 결과를 확인합니다.
4. 문서 즐겨찾기, 새로고침, 테마 전환을 확인합니다.
5. 아직 없는 콘텐츠와 자동 연동이 준비 중으로 표시되는지 확인합니다.

## 결과물

- `site-review-<commit>`: 정적 사이트 및 설치 없이 여는 review.html.
- `browser-review-<commit>`: 빌드/오프라인 브라우저 검사 화면.
- `pages-live-<commit>`: 배포된 Pages의 PC·모바일 캡처와 result.json.
- `hosting-audit-<run>`: DNS·HTTPS·repository-scope 비밀값 존재 여부만 기록한 읽기 전용 감사.

인아워넷의 경로 격리와 아직 필요한 설정은 [DEPLOYMENT.md](DEPLOYMENT.md)를 확인하세요.
