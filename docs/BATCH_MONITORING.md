# 관리자 전용 배치 모니터링 — 운영 구성

2026-11-17 운영자가 남은 구현 완료와 운영 배포를 승인했다. 기존 수집 배치의
주기·복구 로직·중지 정책은 유지하며 조회 전용 운영 모니터링을 추가한다.

## 접근 경계

주소는 `https://isegye-idol.kr/ops/batches/`이다. 기존 Google 로그인으로 확인된
`role=admin` **및** `allowed=true`인 세션만 허용한다. 단순 로그인은 충분하지 않다.
일반 회원은 403, 비로그인은 401이다. 사이트가 공개 상태여도 이 정책은 동일하다.
HTML, CSS, JS, `data.json` 모두 서버 측으로 검사한다. URL 쿼리·헤더·클라이언트
플래그는 권한을 부여하지 않는다. 쓰기 메서드는 허용하지 않는다.

전체 응답은 `private, no-store`, `Vary: Cookie`, 검색 제외, 엄격한 CSP를 적용한다.
`.batch-monitoring`의 원본과 인증 런타임은 직접 HTTP 접근이 차단된다.
기존 계정·로그인 정책·세션 수명은 바꾸지 않으며 관리자 계정을 새로 만들지 않는다.

## 실제 갱신

`batch-monitoring.yml`은 main에서 매시 07·17·27·37·47·57분, 수동 실행,
모니터링 소스 변경, 성공한 운영 배포 완료 이벤트로 동작한다. 정기 실행은 기존
수집 배치를 실행하거나 재실행하지 않고 GitHub 실행과 검증 산출물만 GET으로 읽는다.
권한은 `contents: read`, `actions: read`이며 기존 일시적 `github.token`을 사용한다.
새 토큰·유료 서비스·계정 권한 변경이 없다.

화면 60초 새로고침과 실제 상태 수집 10분 예약은 다르다. GitHub 예약과 공통
쓰기 대기열은 지연될 수 있어 정각·실시간 갱신을 보장하지 않는다. 45분 이상
오래된 자료, 새 회차 이후 아직 확인하지 않은 자료, 조회 실패는 정상으로 표시하지
않는다. 확인 시각과 기준 회차를 항상 남긴다. `PRODUCTION_PAUSED` 또는
`ISEGYE_MONITOR_PAUSED=true`이면 게시를 중지하며 UI의 오래됨 경고는 유지된다.

상태 수집은 원문 수집·배치 dispatch·취소·이슈 변경을 수행하지 않는다. 데이터와
UI를 게시할 때 기존 production 공통 대기열과 `.deploy-lock`, SFTP 서버 지문,
경로·소유자·해시·재조회 검사를 유지한다. 정기 갱신은 인증 런타임과 운영 UI,
수집 피드를 수정하지 않고 모니터링 전용 상태 포인터만 바꾼다.

## 실행과 반영 구분

수집 6개, 독립 멜론 관측, 운영 배포와 복구 점검을 포함한 9개 항목이다. 실행 상태, 소요·대기,
다음 회차, 출처별 결과, 검증 시각, 원본 실행 링크, 복구 제어기 판단을 구분한다.
성공 배지만으로 정상 처리하지 않으며 현재 KST 회차 및 게시·재조회 근거를 대조한다.
과거 차트 공백과 현재 회차 장애, 새벽 중지는 각각 별도로 표시한다.

독립 관측은 읽기 전용 9번째 행이다. 기존 8개 수동 실행 허용 목록은 늘리지 않는다.
두 원본 차트와 정확한 sourceAt/run/attempt를 확인하며 기존 배치의 게시와 별도
결과를 표시한다. 9/9 점검과 9개 모두 정상이라는 뜻도 구분한다.

`slotLedger`는 도래한 필수 회차를 먼저 만들고 확인한 결과를 연결한다. 실행이 없거나
증거를 읽지 못한 회차도 `unverified`로 남기며 임의 성공/실패로 채우지 않는다.
첫 실패·취소·부분 결과, 이후 검증, 복구 확인 시각과 원래 readback 시각을 별도로
보존한다. 점검 장애가 이전 검증을 지우지 않는다. 원장 적용 전의 과거 회차 성과를
소급 생성하지 않으며 범위를 `observed_snapshots_only`로 표시한다. 기존 비공개
스냅샷 안에서 최대 90일/5,000회차/회차당 최근 4개 상태 변경을 보관한다.
음악은 `officialPublicationVerified`와 `backupAvailability`를 분리한다. 공식 수집·
게시가 검증돼도 승인된 백업 가용성 일부가 실패하면 행은 attention, 원장은 partial로
남고 원래 가용/미확인 수량을 함께 보관한다. 같은 수집을 반복하지 않는 복구 판단과
전체 링크 정상 판정을 혼동하지 않는다. `generatedAt`는 결과 생성 시각이며 단일
원문 기준시각이 없는 일일 피드의 `sourceAt`는 null이다. 실제 쓰기 직후 publishedAt,
바이트 재조회 성공 직후 readbackAt를 기록한다. 변경 없는 검증은 publishedAt를 새로
만들지 않고 `unchanged_verified`와 실제 readbackAt를 남긴다.
보관 시에는 `schemaVersion: 2`, `encoding: gzip+base64`로 원장 전체를 압축한다.
`sha256`은 해제된 JSON의 해시이며 `uncompressedBytes`, `entryCount`,
`coverageStartAt`, `coverageEndAt`, `checkedAt`, `retentionDays`를 함께 검증한다.
해제는 최대 12MB/5,000회차, base64 본문은 최대 3MB로 제한한다. 손상·크기 초과·
해시/범위 불일치는 실패 처리하며 보관 중인 실패나 회차를 지워 맞추지 않는다.
기존 schema 1 원장도 읽는다. 전체 게시 JSON의 4MB 제한은 유지하고 화면은
압축 원장 대신 각 배치의 `slotSummary`를 읽는다. 91일째에는 보존 범위의 시작만
하루 이동하며 오늘만 남기도록 초기화하지 않는다.

승인된 비공개 스냅샷의 원장을 로컬에서 읽는 helper는 다음과 같다. 압축 방식은
보존 내용과 접근 권한을 바꾸지 않는다.

```python
import json, sys
from pathlib import Path
sys.path.insert(0, 'scripts')
from batch_slot_ledger import unpack_slot_ledger
snapshot = json.loads(Path('monitoring-dist/data.json').read_text())
ledger = unpack_slot_ledger(snapshot['slotLedger'])
```

운영 배포는 새 소형 `isegye-production-evidence-{run}-{attempt}` 산출물의
`auth-deployment.json`을 사용한다. 기존 대형 스크린샷·소스 묶음을 반복 내려받지
않는다. 현재 main 커밋과 실제 배포/브라우저/비공개 경로 검사 근거가 필요하다.

콘텐츠는 `catalog-publication.json`에서 빌드된 채널 시각·등록 영상 포함 여부와
실제 업로드 파일 해시의 연결을 검증한다. 배포 보고서가 해당 보고서의 SHA-256 및
업로드 바이트 일치를 증명해야만 현재 반영 여부를 판정한다. 소스가 오래됐으면
새 배포 성공으로 감추지 않는다. 전체 과거 영상 수집 범위는 현재 최신성과 구분한다.
새 증거가 없는 이전 배포는 확인 불가이며 과거 결과를 새 증거로 변환하지 않는다.

실행 이력은 현재 attempt 순으로 판정하며, 워크플로당 최대 20페이지 × 100건,
전체 200 GET의 명시적 조회 예산을 적용한다. 중간 건수 변동·중복·상한 초과는
불완전 조회로 표시한다. 산출물 출처·attempt·커밋·크기·해시·JSON 형식을 검사하며
그 안의 코드를 실행하지 않는다. 원본 로그·인증정보는 UI에 복사하지 않는다.

## 보관 및 복구

현재 스냅샷은 실제 확인한 회차 요약을 90일, 최대 30,000개 포함한다. 과거 미관측
회차를 정상으로 채우지 않는다. 멜론 관측표는 최근 7일이다.

물리 스냅샷은 활성·직전 복구본을 포함해 최근 24개를 유지한다. 삭제는 명확하게
소유한 `.batch-monitoring/releases/m[0-9a-f]{12}` 안의 정확한 5개 파일에 한정한다.
소유권·심볼릭링크·파일 목록·manifest·내용 해시와 활성 포인터를 재검증한 후에만
정리한다. 알 수 없는 파일은 삭제하지 않고 보관 오류로 남긴다. 250개 검사 상한에
도달하면 무제한 업로드하지 않고 중단한다. 기존 인증 런타임·다른 피드·계정 파일은
정리 대상이 아니다. 정기 갱신은 `previous.json` 한 개만 사용해 백업 폴더를 늘리지
않는다. 설치 시 인증 entry 백업은 기존 배포 안전 규칙에 따라 보존한다.

게시 후 바이트·익명 접근 검증 실패 시 동시 변경이 없는 경우에만 이전 포인터로
되돌린다. 보관 정리 오류와 게시 실패를 혼동하지 않으며 보고서에 따로 기록한다.

## 운영 배포 통합

`production.yml`과 CI가 `build_batch_monitor_host.py` 및 관리자 권한 브라우저
검사를 포함한다. 이후 전체 팬사이트 배포가 모니터링 경로를 지우지 않는다.
전체 운영 배포 뒤 초기 상태를 설치하며, 배포 완료 이벤트가 상태를 다시 확인한다.
feature 브랜치는 비밀값 없는 검증만 수행하고 운영에 게시하지 않는다.

실제 운영 데이터 `monitoring-dist/data.json`은 Git이나 공개 Actions 산출물에
포함하지 않는다. 배포 결과 보고서만 저장한다. 설치 완료는
`gated_monitor_production_verified`, 정기 갱신 완료는 `monitor_snapshot_verified`와
원격 바이트 재조회·익명 차단 결과로 판정한다. 코드 병합이나 워크플로 시작은 완료가 아니다.

## 검증

`npm test`, `python -m unittest discover -s tests -p 'test_*.py'`,
`python scripts/build_batch_monitor_host.py`, `python tests/batch_monitor_host_browser.py`.
검증은 시각 경계, GET-only, 산출물 무결성, 배포 파일 연결, 보관 상한·삭제 경계,
롤백, 계정 없는 방문/일반 회원/관리자 및 공개·점검 상태를 포함한다.
브라우저 테스트는 격리된 TLS와 합성 계정으로만 수행한다. 실제 서버에서는 설치
코드·데이터 바이트와 비로그인 차단을 검증하며 실제 관리자 계정 로그인을 가장하지 않는다.
