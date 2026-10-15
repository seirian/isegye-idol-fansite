# 검토 및 운영 배포 안내

## 현재 상태를 구분하세요

코드 쓰기 권한과 GitHub Actions 워크플로 작성 권한, GitHub Pages 관리자 설정, inour 서버 SSH 접근은 각각 별개입니다. 저장소가 초기에는 비어 있었고 기존 workflow/배포 설정은 없었습니다. 연결된 Desktop Commander 장치는 오프라인이었으며, 인아워넷 계정·서버 접속 설정은 확인되지 않았습니다. 비밀키를 채팅이나 공개 이슈에 붙여 넣지 마세요.

## A. 권장 검토 주소: GitHub Pages

1. 저장소 Settings > Pages > Build and deployment > Source를 **GitHub Actions**로 설정합니다.
2. Settings > Secrets and variables > Actions > Variables에서 `ENABLE_PAGES_PREVIEW`를 `true`로 설정합니다.
3. Settings > Environments > github-pages의 배포 허용 브랜치를 develop으로 설정합니다.
4. develop에 커밋하거나 해당 워크플로를 다시 실행합니다. Actions의 `pages-preview` 성공과 실제 접속을 확인합니다.
5. 예상 주소: `https://seirian.github.io/isegye-idol-fansite/`. 성공 전에는 배포 완료 주소로 취급하지 마세요.

**isegye-idol.kr을 이 Pages에 연결하지 않습니다.** Pages는 develop 검토 전용입니다. 저장소 기본 브랜치 main에는 아직 워크플로가 없으므로 workflow_dispatch 버튼이 보이지 않을 수 있습니다. 이 경우 develop의 정상 push로 실행할 수 있습니다.

공식 참고: https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages

## B. 별도 설정 없이 코드 화면 검토

공개 develop의 index.html은 raw.githack.com 같은 제3자 GitHub 파일 미리보기 서비스로 검토할 수 있습니다. 검토 목적에 한정하며 운영 호스팅을 대체하지 않습니다. 이용 시 해당 서비스가 접속 정보를 처리하고 콘텐츠를 캐시할 수 있습니다. 최초 접속에 목적지 확인 화면이 나올 수 있습니다.

개발 주소 형식: `https://raw.githack.com/seirian/isegye-idol-fansite/develop/index.html`
커밋 고정 주소 형식: `https://rawcdn.githack.com/seirian/isegye-idol-fansite/COMMIT_SHA/index.html`

실제 주소는 HTTP 응답 및 브라우저 작동 확인 후 안내해야 합니다. 서비스 정책/가용성 때문에 동작하지 않을 수 있습니다. CDN에 한 번 노출한 자료는 장기 캐시될 수 있으므로 공개·검수 자료만 사용합니다.

가장 확실한 로컬 방법은 Actions의 site-review 아티팩트를 내려받아 웹서버로 여는 것입니다. file:// 더블클릭은 ES module 보안 정책 때문에 지원하지 않습니다.

## C. inour 운영 연결 전에 확인할 사항

- 계정이 웹호스팅/FTP형인지, SSH가 가능한 Linux 서버형인지
- isegye-idol.kr용 별도 document root와 기존 mir.yeop.net 문서 루트
- SSH 호스트/포트/배포 계정 및 공개키 등록 가능 여부
- DNS 관리 권한, 실제 A/AAAA/CNAME 상태, SSL 발급·자동 갱신 방법
- 심볼릭 링크를 웹 document root로 사용할 수 있는지
- 공개 운영자 연락처 및 비공개 권리 요청 채널

연결된 장치가 오프라인인 상태에서 도메인의 DNS 장애 여부를 단정하지 마세요. DNS/HTTP 검사는 각 실행 환경의 네트워크 제한을 구분해야 합니다.

## D. main 운영 배포 (사전 설정 전 절대 활성화하지 않기)

production.yml은 main만 허용하고 repository variable `PRODUCTION_ENABLED=true`일 때만 실행됩니다. **main 보호와 production 승인자를 코드로 설정한 것은 아닙니다.** 관리자가 아래를 설정해야 합니다.

- main: 직접 push 제한, PR 필수, CI 필수, 사용자 승인 후 병합
- production 환경: required reviewer와 main만 배포 허용
- production 환경 secrets:
  - INOUR_SSH_HOST
  - INOUR_SSH_PORT (미설정 시 22)
  - INOUR_SSH_USER
  - INOUR_SSH_PRIVATE_KEY (전용 배포 키)
  - INOUR_SSH_KNOWN_HOSTS (별도 신뢰 경로로 검증한 호스트 키)
  - INOUR_DEPLOY_ROOT (예: `/home/USER/sites/isegye-idol`, 반드시 전용 경로)

`ssh-keyscan` 결과를 검증 없이 신뢰하지 않습니다. SSH는 StrictHostKeyChecking=yes로 연결합니다. secret은 공개 저장소나 로컬 파일로 커밋하지 않습니다.

서버 관리자가 전용 경로를 만들고 `.isegye-fansite-root` 빈 소유 마커 파일을 만든 후, document root를 해당 경로의 `current`로 지정해야 합니다. **mir.yeop.net 기존 document root를 사용하면 안 됩니다.**

배포는 검증·브라우저 테스트 후 전용 `releases/COMMIT-RUN-ATTEMPT` 디렉터리에 업로드하고 `current` 심볼릭 링크를 원자적으로 전환합니다. 기존 릴리스와 다른 사이트는 삭제하지 않습니다. 이전 링크 대상은 `previous-release.txt`에 보관합니다.

이 스크립트는 Linux/bash/GNU tar/coreutils/scp 및 심볼릭 링크를 가정합니다. 공유 FTP 호스팅이면 실행하지 말고 SFTP/FTP 지원 범위에 맞게 별도 배포 어댑터를 작성해야 합니다.

운영 빌드에서는 robots 허용 및 production canonical을 설정합니다. 현재 UI는 여전히 검토 범위를 알리는 배너를 유지합니다. 운영 시작 전에 연락처/콘텐츠 범위/기능 상태를 함께 확정해야 합니다.

## E. 운영 체크와 롤백

배포 활성화 전 검토: nginx/Apache의 MIME 타입, HTTPS, 보안 헤더, document root, SPA 해시 링크, 모바일, 민감 자료 부재를 확인합니다. 운영 활성화 후 `build-info.json` 커밋과 실제 응답을 확인하세요. 실패 시 관리자 검토 아래 `current`를 previous-release.txt의 검증된 릴리스로 교체합니다. 기존 서비스 설정을 자동 변경하는 코드는 없습니다.
