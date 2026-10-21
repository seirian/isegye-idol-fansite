# 배포 및 경로 격리

## 고정 구조

| 대상 | 브랜치 | 공개 주소 | SFTP 기준 경로 |
|---|---|---|---|
| 개발 검토 | develop | https://seirian.github.io/isegye-idol-fansite/ | GitHub Pages; 인아워넷에 쓰지 않음 |
| 이세돌 운영 | main | https://isegye-idol.kr/ | `/web/_isegye_idol` |
| 기존 미르 운영 | 별도 저장소 main | https://mir.yeop.net/ | `/web/_mir_site`; 읽기 검증만 |
| 개인 사이트·공용 설정 | 별도 관리 | https://yeop.net/ | `/web`; 수정 금지 |

`develop`의 검토가 끝나기 전에는 main에 병합하지 않습니다. 이세돌 운영 경로는
미르의 하위 경로나 공용 웹 루트가 아닌 독립된 형제 디렉터리입니다.
DNS를 같은 IP로 연결한 것만으로 도메인의 문서 루트가 분리되지는 않습니다.

## 기존 프로젝트에서 확인한 설정

참고 저장소: `seirian/mir-cheongwoon-site`의 `main`.
- `scripts/mir_shared_root_deploy_ci.py`: 미르 루트 `/web/_mir_site`.
- `scripts/yeop_deploy_ci.py`: SFTP `seirian.inour.net:1922`, 계정 `seirian`, 소유 UID 5048.
- 호스트 키는 기존 배포 코드의 ssh-ed25519 SHA256 지문으로 고정합니다.
- 기존 프로젝트의 Secrets 값을 읽어오거나 출력·복제하지 않습니다.

2026-10-21 읽기 전용 감사에서 `isegye-idol.kr`, `mir.yeop.net`, `yeop.net`은
115.160.56.166을 반환했습니다. isegye-idol.kr의 HTTPS는 200이었지만
응답 본문 해시가 yeop.net과 같았습니다. 이는 독립 문서 루트 확인 완료를 뜻하지 않습니다.
감사 당시 이 저장소의 repository-scope `ISEGYE_SFTP_PASSWORD`와 `YEOP_SFTP_PASSWORD`는
사용할 수 없었습니다. production environment에만 있는 비밀값은 이 감사 범위 밖입니다.

## GitHub Pages 검토

Settings > Pages의 Source는 GitHub Actions, Repository variable
`ENABLE_PAGES_PREVIEW=true`, github-pages 환경의 배포 허용 브랜치는 develop을 포함해야 합니다.
2026-10-21 Actions run 39521400030에서 최초 Pages 배포 성공을 확인했습니다.
커스텀 도메인을 isegye-idol.kr로 지정하지 않습니다. 운영 도메인은 인아워넷에 유지합니다.
새 CI는 배포 후 실제 URL에서 커밋, 검색, 모바일 화면까지 확인하고 스크린샷을 남깁니다.

## 인아워넷 최초 준비

1. 호스팅 관리에서 `isegye-idol.kr`의 문서 루트를 **SFTP 경로 기준 `/web/_isegye_idol`**에
   연결합니다. 관리 화면이 실제 서버 절대 경로를 요구하면 이 SFTP 경로에 해당하는 경로를
   호스팅 업체에 확인합니다. 공용 `/web/.htaccess`나 미르 설정을 덮어쓰지 않습니다.
   독립 문서 루트 지정이 불가능한 상품이면 여기서 중단하고 별도 호스트 라우팅안을 검토합니다.
2. 이 저장소 Settings > Environments > production 또는 Repository secrets에
   `ISEGYE_SFTP_PASSWORD`를 등록합니다. 값은 채팅·코드·이슈에 쓰지 않습니다.
   이 저장소에 이미 `YEOP_SFTP_PASSWORD`가 등록된 경우 같은 값의 명시적 fallback만 지원합니다.
   다른 저장소의 Secret이 자동 공유되는 것은 아닙니다.
3. production 환경은 main만 배포 허용, 승인자 설정을 권장합니다. main에는 PR 및 CI 통과를
   요구하는 브랜치 보호를 설정합니다. 2026-10-21 조회 당시 두 브랜치의 protected는 false였습니다.
4. 실제 최초 초기화를 승인할 때 `ISEGYE_INITIALIZE_EMPTY_ROOT=true`를 변수로 설정합니다.
   전용 경로가 없거나 완전히 비어 있을 때만 소유 마커와 차단용 라우터를 생성합니다.
   이미 다른 파일이 있으면 덮어쓰지 않고 중단합니다. 최초 성공 이후에는 이 변수를 false로 바꿉니다.
5. 검토 후 main 병합 및 운영 준비가 끝나면 **Repository variable** `PRODUCTION_ENABLED=true`를
   설정합니다. 이 값은 job 조건에서 읽으므로 environment 변수만으로는 충분하지 않습니다.
   기본은 비활성입니다. 활성화 후 main push 또는 main workflow_dispatch로 배포합니다.

## 자동 안전장치

`scripts/inour_sftp.py`만 운영 전송을 수행합니다. 이전 SSH/rsync 셸은 이 스크립트로
위임하며 임의의 배포 경로·SSH 셸 명령을 더 이상 받지 않습니다.

- main/운영 활성화/production 빌드/커밋 일치가 모두 필요합니다.
- 쓰기·삭제·이름 변경 경로는 `/web/_isegye_idol/` 내부로 제한합니다.
- `..`, 중복 슬래시, 심볼릭 링크, 실제 경로 별칭, 다른 소유자를 거부합니다.
- 미르와 공용 핵심 파일은 전후 해시 비교만 수행합니다. 수정하지 않습니다.
- 원격 서버 지문 확인 전 비밀번호를 보내지 않습니다.
- 전용 디렉터리의 임시 검증 파일이 `https://isegye-idol.kr/`에서 정확히 제공되는지 확인합니다.
- 같은 검증 파일이 mir.yeop.net 또는 yeop.net에서 노출되면 중단합니다.
- 개별 릴리스 `/web/_isegye_idol/_isegye_releases/r<커밋12자리>`는 새로 생성하고
  기존 릴리스를 덮어쓰거나 자동 삭제하지 않습니다.
- 활성 라우터는 전용 루트의 `.htaccess` 한 파일만 원자적으로 교체합니다.
  공개 파일 검증 실패 시 해당 라우터만 직전 상태로 복구합니다.
- 미지원 원자적 rename, 수동 변경된 라우터, 기존 배포 잠금은 중단 사유입니다.

도메인 연결 실패 시 전용 폴더의 초기 소유 마커·차단 라우터가 남을 수 있습니다.
이는 운영 성공이 아닙니다. 다음 실행에서는 같은 소유 마커를 확인하고 재검증합니다.
부분 업로드 릴리스와 오류 후 남은 임시 파일은 자동 삭제하지 않습니다.
같은 커밋의 릴리스 폴더가 남으면 재실행은 안전하게 중단됩니다. 운영자가 해당 경로를
확인한 뒤 별도 커밋으로 새 릴리스를 생성하는 방식으로 복구합니다.

## 검증

```sh
npm test
python -m unittest discover -s tests -p test_deployment.py -v
# Apache 2.4가 있는 격리된 Linux 개발 환경에서만:
python tests/apache_isolation.py
```

경로·소유권·심볼릭 링크·빌드·도메인 오연결 검사 20개와 로컬 Apache 라우팅 검사
12개를 추가했습니다. 로컬 검증은 인아워넷 실서버 배포 검증과 다릅니다.
실서버 성공은 `inour-report.json`의 deployed와 공개 URL 확인이 있어야 인정합니다.

참고: https://httpd.apache.org/docs/2.4/vhosts/name-based.html
https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets
