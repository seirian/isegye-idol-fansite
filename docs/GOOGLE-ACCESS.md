# Google 로그인과 최초 관리자 가입 후 접근 제한

## 상태와 적용 경계

이번 브랜치의 자동 작업은 서명 검증·회원 저장·화면을 테스트하고 **비활성 런타임과 빈 저장소만** 인아워넷의 이세돌 전용 경로에 준비합니다. 운영 `.htaccess`나 현재 홈페이지는 변경하지 않습니다. Google Client ID 등록과 활성화 검토 전에는 로그인이나 공사중 전환이 발생하지 않습니다. 관리자 계정을 미리 생성하거나 테스트 계정으로 가입 조건을 대신 충족하지 않습니다.

## 필요한 Google 설정

Google Cloud / Google Auth Platform에서 웹 애플리케이션 OAuth Client ID를 준비합니다.

- Authorized JavaScript origin: `https://isegye-idol.kr`
- Google Identity Services의 공식 버튼 + JavaScript callback으로 ID token을 같은 출처의 `/auth/google`에 POST합니다. OAuth redirect URI나 Client Secret은 이 방식에서 사용하지 않습니다.
- 저장소 Actions repository variable `ISEGYE_GOOGLE_CLIENT_ID`에 Client ID를 등록합니다. 비밀키나 비밀번호를 이슈·채팅·소스에 쓰지 않습니다.
- Google 동의 화면이 Testing이면 지정 관리자 계정을 테스트 사용자로 추가합니다. 일반 사용자 로그인을 허용하려면 Google의 공개 상태·테스트 사용자 제한을 별도로 확인합니다.
- 공개 홈페이지와 `/auth/privacy`의 개인정보 안내가 실제 서비스와 일치해야 합니다.

현재 preflight에서 이 이름의 Client ID 설정을 찾지 못했습니다. 앱 연결 권한과 웹사이트의 Google OAuth Client ID는 다른 설정입니다.

## 정보 최소화

기존 호스팅 PHP 8.5.12는 PDO MySQL은 지원하지만 PDO SQLite를 지원하지 않았습니다. 다른 프로젝트 DB나 별도 유료 서비스를 임의로 쓰지 않고, 초기 규모를 위한 전용 비공개 파일 회원 원장을 사용합니다. 전용 잠금 파일, 공유/배타 flock, fsync와 원자적 rename으로 저장하고 10,000계정/2MiB 한도를 넘으면 실패합니다. 계정 규모가 커지면 동일 인터페이스를 독립 DB로 이전해야 합니다.

회원 원장 `accounts.json`의 계정 필드는 `HMAC-SHA256(사이트 비밀키, Google sub)`와 `member/admin` 권한뿐입니다. 원본 sub, 이메일, 이름, 사진, 인증 토큰, IP, User-Agent, 가입·최근 로그인 시각은 회원 원장에 저장하지 않습니다. 관리자를 이미 등록했는지 판단할 단일 관리자 키와 스키마 번호도 보관합니다. HMAC 식별값은 계정을 다시 알아보는 값이므로 완전한 익명정보라고 주장하지 않습니다.

Google 서명이 확인된 이메일을 일시적으로 승인 관리자 이메일의 keyed digest와 비교합니다. 그 뒤 Google sub를 변환한 키로 고정하여, 이메일 값만 바뀌거나 다른 계정이 같은 이메일을 주장해도 관리자 바인딩을 옮기지 않습니다. 사용자 지정 관리자 이메일의 평문은 설정 파일에도 저장하지 않습니다.

PHP 임시 세션에는 변환된 계정 키, CSRF, 발급·활동 시각과 로그인 전 10분짜리 nonce만 남깁니다. Google token은 POST 메모리에서 검증 후 폐기합니다. 최대 12시간/비활동 30분 만료, 로그인 후 세션 ID 변경, Secure·HttpOnly·SameSite=Lax·Path=/·Domain 없는 `__Host-ISEGYE` 쿠키를 적용합니다. 앱은 토큰/개인정보를 로그로 출력하지 않습니다. 호스팅·Google의 자체 접속 로그까지 없다고 주장하지 않습니다.

## 가입 및 공사중 전환

- 최초 일반회원·비로그인: 현재 사이트를 계속 봅니다.
- Google 서버 서명, iss/aud/azp/exp/iat/nonce와 verified email을 통과한 지정 관리자: 첫 가입 원자적 저장과 함께 공사중 상태를 활성화합니다.
- 이후 관리자: 기존 사이트 사용. 일반회원·비로그인: `현재 사이트는 공사중입니다.` + 기존 단체 이미지의 연한 배경. 일반회원의 Google 자동가입은 허용하되 내용 접근 권한은 주지 않습니다.
- 관리자 로그아웃·세션 만료는 사이트를 다시 공개하지 않습니다. 로그인 화면과 개인정보 안내는 차단 중에도 열립니다.
- 회원 저장소 누락·손상 시 공개 상태를 새로 만들지 않고 오류로 차단합니다.

브라우저의 로컬 스토리지/이메일/role 값을 권한 근거로 쓰지 않습니다. 파일 경로까지 PHP gateway에서 검사해야 하므로 프런트엔드 화면 덮개만으로 활성화하지 않습니다. 이미 열린 화면은 보조 status poll로 갱신되지만, 실제 접근 통제는 요청마다 서버에서 수행합니다.

## 경로와 활성화 전 필수 점검

비활성 코드: `/web/_isegye_idol/.auth-runtime/g<digest>/`
회원·설정·세션: `/web/_isegye_idol/.auth-private/` (디렉터리0700/파일0600/HTTP차단)
다른 프로젝트, `/web/.htaccess`, DNS, 인증서, 기존 시크릿에는 손대지 않습니다.

활성화는 아직 자동 실행하지 않습니다. 먼저 Client ID를 설정하고 정상 Google 계정 선택 화면까지 확인한 다음, 이세돌 전용 라우팅을 allowlist gateway로 연결해야 합니다. 모든 `/src`, 데이터, 오래된 릴리스 URL도 통제해야 하며, 기존 정적 배포가 gate를 덮어쓰지 않도록 배포 검증도 함께 전환해야 합니다. 이전 라우터로의 자동 복구는 관리자 가입 전까지만 가능하고, 관리자 가입 후에는 인증을 해제하는 복구를 해서는 안 됩니다.

현재 GitHub Pages 검토본은 별도의 공개 정적 사이트입니다. 실제 운영 접근 제한을 활성화할 때 모든 Pages 경로를 운영 도메인으로 연결하는 안내 페이지로 바꿔 우회 경로를 남기지 않아야 합니다. 공개 GitHub 저장소/기존 인터넷 캐시의 소스까지 비공개가 되는 것은 아닙니다. 저장소 공개 범위 변경은 별도 결정입니다.

## 검사

`php tests/auth/store_test.php`: 최초 관리자 조건·일반회원 차단·동시성·최소 저장·손상 차단.
`php tests/auth/jwt_test.php`: 실제 JWT 라이브러리로 생성한 합성 서명의 무결성, 발급자/대상/nonce/만료/미검증 이메일/알고리즘 혼동.
`python tests/auth/browser.py`: 임시 로컬 TLS에서 합성 인증 응답으로 가입 전후·쿠키·CSRF·파일 직접 접근·로그아웃·모바일 화면 검사. 실제 Google 로그인 완료로 오인하지 않습니다.

참고: Google ID token 검증 https://developers.google.com/identity/gsi/web/guides/verify-google-id-token · 설정 https://developers.google.com/identity/gsi/web/guides/get-google-api-clientid · OWASP 세션 https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html
