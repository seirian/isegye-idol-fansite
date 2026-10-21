# 이세돌 아카이브

이세계아이돌의 **공개 정보와 출처를 연결**하는 비상업적·비공식 팬사이트입니다. 패러블/아티스트의 승인·후원·협찬과 관계없습니다.

**개발 검토 사이트:** https://seirian.github.io/isegye-idol-fansite/

## 1차 검토 구현

- 8개 상위 메뉴: 오늘의 이세돌 / 입문·멤버 / 소식·일정 / 음악 / 방송·영상 / 이세돌 사전 / 활동 기록 / 팬 가이드
- 반응형 화면, 밝은·어두운 테마, 키보드 탐색
- 통합 검색, 한글 초성 검색, 멤버·분류 필터, 제목·날짜 정렬
- 여섯 멤버 상세 및 관련 음반 연결, 6개 출처 확인 음반과 수록곡
- 문서 상세, 출처·확인일·관련 기록, KST 월별 달력
- 브라우저 즐겨찾기, 문서 링크 복사, GitHub 제보 작성 연결
- 무단 복제 미디어 없이 자체 추상 그래픽 사용, 외부 폰트·추적 스크립트 없음
- 실제 데이터와 미구현 상태를 구분. 가짜 LIVE·일정·방송 타임스탬프 없음

**아직 없음:** 계정, 관리자 CMS, 서버 저장, 실시간 방송/API 연동, 전체 과거 기록 수집, 비공개 권리 신고 창구. 검토판을 완성된 운영 서비스로 오인하지 마세요.

## 기술 구성

HTML + CSS + native ES modules, Node.js 22 빌드·테스트. 앱 런타임 및 npm 의존성 0개. 일반 정적 호스팅에서 실행되며 운영 서버에 Node가 필요하지 않습니다. 해시 라우팅을 사용합니다. 개별 문서 SEO/SSR은 후속 단계입니다.

```bash
# Node.js 22 이상. npm install 불필요.
npm test
python -m unittest discover -s tests -p test_deployment.py -v
npm run build
npm run preview  # http://127.0.0.1:4173
npm run dev
```

브라우저 테스트:

```bash
python -m venv .venv
. .venv/bin/activate
pip install playwright==1.56.0
python -m playwright install chromium
npm run build
python tests/browser_smoke.py
```

CI는 필요한 Linux 시스템 의존성도 설치합니다. 테스트는 실제 외부 제출을 하지 않으며, GitHub 이슈 이동은 가로채 검증합니다.

## 파일 구조

```text
index.html                 정적 셸·미리보기 noindex·CSP
src/data.js                검수된 공개 콘텐츠와 출처
src/lib.js                 검색·날짜·검증 순수 함수
src/app.js                 라우팅·화면·이벤트
src/styles.css             반응형 자체 디자인
scripts/build.mjs          검증 후 dist/ 생성
scripts/inour_sftp.py       경로가 고정된 인아워넷 SFTP 배포 및 롤백
scripts/deploy-inour.sh     위 SFTP 스크립트에 위임하는 호환 진입점
tests/                     콘텐츠·브라우저·배포 경계·Apache 격리·실제 Pages 검사
docs/                      배포·콘텐츠 운영 안내
.github/workflows/         develop 검토 및 main 운영 게이트
```

## 브랜치와 배포

- `develop`: push/PR마다 검증·테스트. push 성공 후 GitHub Pages 검토 배포와 실제 URL 검증.
- `main`: 사용자 검토 후 PR로 승격. 현재 사이트 코드는 main에 병합하지 않았습니다.
- GitHub Pages: `ENABLE_PAGES_PREVIEW=true` 설정 및 2026-10-21 최초 배포 성공. 운영 도메인을 Pages에 연결하지 않습니다.
- 인아워넷: 기존 미르 `/web/_mir_site`와 별도로 이세돌 `/web/_isegye_idol`을 사용하도록 고정합니다.
- SFTP 비밀값·전용 문서 루트·운영 승인·`PRODUCTION_ENABLED=true`가 준비되기 전 운영은 비활성입니다.
- `/web/.htaccess`, 개인 사이트, 미르 경로를 이 저장소의 배포 코드가 수정하지 않습니다.
- 검토판은 `noindex,nofollow`입니다. 이는 접근 제어가 아니며 공개 저장소·검토판은 누구나 접근할 수 있습니다.

자세한 설정과 미확인 사항은 [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md), 편집 원칙은 [docs/CONTENT.md](docs/CONTENT.md)를 참고하세요.

## 권리·연락

권리 침해 우려가 있는 자료는 공개 이슈에 민감한 증빙 없이 대상 항목 ID와 공개 요청만 남겨주세요. 운영 전 별도 비공개 연락처가 필요합니다. 정보 삭제 시 공개 번들·검색·연관 링크에서 함께 제거하고, Git 기록 및 이전 임시 CDN 캐시는 별도 조치가 필요할 수 있습니다.

이 저장소는 아티스트·제3자 콘텐츠에 대한 라이선스를 부여하지 않습니다. 사이트 그래픽과 공식 앨범 커버를 혼동하지 마세요.
