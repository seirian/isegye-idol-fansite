# 멜론 차트 실측 누락 감소 — 경량 캡처와 검증된 복구

2026-11-18 사용자 요청: 이세계차트처럼 시간별 차트가 촘촘히 쌓이도록 기존 누락 구조를 보완한다.

## 범위 및 원칙

- **원본**: 멜론 공개 TOP100, HOT100(100일) 100곡 전체 순위와 원본 발표 시각만 검증한다. 우회·비공개 자료·가사·로그인·음원 다운로드 없음.
- **경량 수집**: `melon-chart-capture.yml`은 매시 KST 00시와 07~23시에 :11/:37 두 번 독립 실행한다. `isegye-melon-capture` 전용 동시 실행 그룹으로 기존 운영 SFTP/배포 대기열에 들어가지 않는다.
- **시간 증거**: `scripts/album_chart_capture.py`는 해당 시간의 완전한 1~100위와 곡 ID 100개, 멜론 발표 시각, 응답 SHA-256을 확인한다. 하나라도 실패하면 해당 차트를 기록하지 않는다. 부분 성공은 실패 상태와 함께 보존한다. 전체 표는 접근 제한된 GitHub Actions 아티팩트에만 30일 보관하며 사이트로 노출하지 않는다.
- **누락 병합**: 기존 `albums-daily.yml`의 `album_observation_archive.py`가 운영 누적 스냅샷을 복원한 후, 등록 곡의 시간별 누락에 해당하는 캡처 아티팩트만 조회한다. `album_capture_recovery.py`가 동일 저장소/main 워크플로, 해당 실행·attempt, SHA-256 ZIP, 멜론 출처 및 발표 시각, 전곡 순위의 유일성을 검증한다. **전체 100곡을 검증한 경우에만 차트 미진입(out)을 증명**한다.
- **발행**: 기존 앨범 작업이 누락 복구 점수를 병합한 후 검증 및 최신 멜론 수집을 수행한다. 원래 발표 시각을 유지하며 1시간치 순위를 추정하거나 현재 시각으로 덮어쓰지 않는다. 기존 이미 유효한 관측값은 우선하며 충돌은 보고한다. 게시·재조회, 기존 앨범·배포 잠금/중지/접근권한 정책은 유지한다.
- **새벽 중지**: KST 01:00~06:59는 경량 캡처도 수집하지 않는다. HOT100은 새벽 새 차트 발표가 없으며, TOP100도 기존 사용자 지정 운영시간 외에는 수집하지 않는다.
- **과거 기록**: 이 개선 이전 이미 지나간 시간의 순위는 이 새 작업만으로 생기지 않는다. 2026-11-18 KST 09/10/18시 누락은 별도 검증된 과거 원본/가이섬 등 출처의 자료가 확인될 때에만 별도 보충한다. 가이섬 연속 자동 크롤링을 새로 시작하지 않는다.
- **별도 스케줄러**: 이 캡처 역시 GitHub Actions를 사용하므로 GitHub 전체 예약 장애를 단독 해결하지는 못한다. 기존 독립 ChatGPT 시간별 복구 점검(설정됨)을 유지하며, 추가 서버 cron 등은 실제 인프라/권한과 비용 확인 후 구성한다. 새 환경 변수·토큰·유료 서비스를 만들지 않는다.

## 검증과 상태

- `python -m unittest tests/test_album_chart_capture.py -v` 또는 `python -m unittest discover -s tests -p 'test_*.py' -v`로 수집 시각, 원본 100순위, SHA·실행 시도 바인딩, 위조된 출처, 동일 시간 중복·충돌·차트 밖, 야간 중지, 운영 비밀값 분리를 검사한다.
- 아티팩트 이름은 `melon-chart-capture-{runId}-{attempt}`다. 같은 run 재실행도 새 attempt의 증거를 따로 남기며 overwrite로 이전 증거를 지우지 않는다. watchdog·모니터는 정확한 현재 attempt 이름을 우선하고, 그 이름 자체가 없을 때만 legacy `melon-chart-capture`를 JSON의 동일 run/attempt 검증 아래 읽는다. 새 이름의 증거가 손상·중복·만료됐으면 legacy로 바꾸어 정상 처리하지 않는다.
- 원본 `melon-chart-capture.json`의 `status`, `charts[*].sourceAt`, `errors`와 `daily-albums-*`의 `albums-recovery.json` (`sourceType: melon_public_full_chart`, `addedPoints`, `captureMissingAfter`)를 확인한다. 앨범 병합은 새 이름과 legacy를 모두 읽고 원본 attempt API로 검증하므로, 이전 attempt의 실제 원문 시각도 보존할 수 있다. 같은 attempt의 새 이름이 존재하면 legacy 사본으로 실패를 숨기지 않는다.
- 복구 소비자는 새 이름을 찾기 위해 저장소 artifact 목록을 최대 12페이지 조회한다. 기존 전체 복구 deadline 120초와 후보 80개 상한을 유지한다. `captureInspection`에 요청한 원시각 범위(`targetSourceWindow*`)·호출 수·페이지/후보 예산·확인 건수·목록 완전성을 남기며, 상한에서 끝난 목록은 `CaptureListingIncomplete`와 남은 `captureMissingAfter`로 보고한다. `listingScope=repository_artifacts`의 `listingComplete`는 목록 열거의 완전성으로, 48시간 전체 증거 확보나 모든 차트 공백 해소를 뜻하지 않는다.
- 저장소 목록이 불완전하면 후보 run의 artifact 목록을 추가로 완전히 확인한 뒤 검증된 일부만 병합한다. 이 목록은 run당 최대 100개 한 페이지로 제한하고, 확인된 결과는 그 검사 안에서만 재사용한다. 목록 미확인·이름 중복·명시된 새 이름 존재 시 legacy 채택을 거부하며 고정 `reason`을 보존한다. 추가 요청도 `apiCalls`와 `runArtifactQueries`에 포함한다.
- 녹색 워크플로·캡처 아티팩트만으로 운영 반영 완료가 아니다. `albums-publication.json`의 `status=published`, `verifiedReadback=true`, 현재 시각 원본, 실제 사이트 그래프의 원본 시간 기록 및 앞선 누락 해소 여부를 함께 대조한다.
- 기준 지표는 정상 발표 대상 슬롯 중 **양쪽 차트+등록 곡 전체가 검증된 비율**이다. 목표 99.5%를 설정할 수 있지만 실제 측정 전 달성했다고 주장하지 않는다.
- 보존 기간은 차트 관측 최근 30일, 캡처 아티팩트 30일이며, 확인되지 않은 순위는 계속 공백으로 표시한다.

관련 구현: `.github/workflows/melon-chart-capture.yml`, `scripts/album_chart_capture.py`, `scripts/album_capture_recovery.py`, `scripts/album_observation_archive.py`, `tests/test_album_chart_capture.py`.
