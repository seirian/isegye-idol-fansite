# 운영 공통 잠금과 제한된 복구

2026-11-27 배치 장애 분석 후 우선순위별 개선을 승인받아, 기존 공통 쓰기 큐와
서버 잠금을 유지하면서 소유권 기록 및 취소 정리를 보완한다. 계정·접근 정책,
시크릿, 정규 수집 일정, 미르·공용 경로는 변경하지 않는다.

## 작성자 잠금

`scripts/production_lock.py`의 `acquire`/`release`를 공통 `.deploy-lock` 작성자가
사용한다. exclusive mkdir와 고정 경로·소유 UID·심볼릭 링크 검사는 유지한다.
잠금 안의 `owner.json`에는 repository, workflow, run/attempt, commit, 임의 nonce,
획득 시각과 마지막 단계가 들어간다. 원문 nonce는 보고서에 노출하지 않는다.

SIGINT/SIGTERM은 기존 트랜잭션의 rollback/finally 경로로 전달한다. 정상 정리는
정확한 owner bytes를 확인한 후 디렉터리를 고유한 `.released-<nonce>` 경로로
덮어쓰기 없는 SFTP rename으로 옮긴다. 그 안의 자기 owner 파일과 빈 디렉터리만
제거한다. 정리 중 중단되어도 익명의 빈 `.deploy-lock`을 새로 남기지 않는다.
단계 checkpoint의 updatedAt은 마지막으로 기록한 시각이며 주기적 생존 보장을
뜻하지 않는다. 이 시각이 오래됐다는 이유로 다른 잠금을 해제하지 않는다.

mkdir 요청 응답이 끊기고 자기 owner bytes를 확인할 수 없으면 acquire_unknown이다.
경로가 비어 있다는 이유만으로 소유권을 추정하거나 지우지 않는다. 상태는
`busy`, `acquire_unknown`, `interrupted`, `cleanup_failed`,
`released_cleanup_pending`, `released`로 구분한다.

## 감사와 회수

`scripts/recover_production_lock.py audit`는 원격 쓰기 없이 진단한다. 현재 main,
현재 recovery 작업의 공통 큐, 모든 활성 상태의 실행 목록과 실제 job, 라우터,
access entry, 릴리스 build-info, 모니터 manifest/data, 관련 피드 포인터,
공용·미르 보호 파일의 해시를 확인한다. 계정·설정·세션 파일은 읽지 않는다.

실제 작성자 job이 실행 중이거나 source/실행 목록/페이지/권한 조회가 불완전하면
중단한다. 같은 공통 큐에 대기 중인 작성자는 실행 중인 작성자와 구분하며,
SFTP 자격이 없는 검증용 prepare 작업은 진행할 수 있다. API 요청은 최대 30회다.

`apply`는 직전 검증된 audit artifact와 명시적인 diagnosticSha256를 요구한다.
workflow wrapper는 artifact의 run/attempt/commit 출처, 크기, digest를 검증한다.
CLI는 별도 recovery guard를 exclusive하게 획득한 상태에서 main과 모든 작성자
상태를 다시 두 번 확인하고, 운영 상태가 감사 해시와 같을 때만 대상 잠금을
고유한 `.recovered-<nonce>` 경로로 원자 이동한다. 예상한 owner 파일 또는
명시적으로 허용된 legacy 빈 디렉터리만 삭제하고 모든 비대상 해시를 재조회한다.

`Production lock - audit first, explicitly rerun to recover` workflow의 최초 실행은
항상 audit이다. 코드 반영으로 생성된 push 실행은 진단 보고서를 검토한 뒤 **같은 job을
명시적으로 재실행**하면 직전 성공 attempt의 정확한 artifact를 검증해 apply를 요청한다.
수동 시작은 기본적으로 읽기 전용이며, `allow_recovery_on_rerun`을 명시한 경우에만
같은 절차를 허용한다. 직전 감사 실패, 이미 잠금이 없는 상태, 변조·만료·다른 출처의
진단은 삭제 요청으로 바뀌지 않는다. apply는 항상 현재 서버 상태를 다시 확인한다.

이번 legacy 감사의 사고 관련 실행은 production `45938564802`, attempt 1로 고정한다.
자동 예약이나 watchdog 복구 대상에 이 잠금 회수 workflow를 추가하지 않는다.

기존 빈 잠금은 `--allow-legacy-empty`와 사고 관련 run/attempt를 명시해야 한다.
`--legacy-owner-run-id`라는 CLI 인자는 기존 인터페이스 명칭이며 **실제 소유자
증명은 아니다**. 보고서는 `incidentRun`과 `ownerConfirmed: false`로 구분한다.
해당 run이 종료됐다는 사실만으로는 회수할 수 없으며, 공통 큐·recovery guard·
두 차례 완전 조회·정확한 경로/UID/타입/빈 상태·운영 해시 일치가 함께 필요하다.

새 owner 메타데이터가 있는 잠금은 정확한 run/attempt/commit/workflow가 종료된
것을 추가로 확인한다. 진행 중, 상태 미확정, 소유자 불일치, foreign 파일,
해시 변경, 일시정지는 회수하지 않는다. TTL, 강제 삭제, 기존 보호 검사 우회,
계정·인증 정책 변경은 사용하지 않는다.

## 제한 및 완료 기준

SIGKILL, 러너 소실 또는 원격 정리 중 통신 단절은 finally 실행을 보장하지 않는다.
특히 **recovery guard 자체가 강제 종료로 남으면 다음 실행은 안전하게 중단한다**.
이번 P0는 guard를 자동 회수하지 않는다. 그 경우 guard의 정확한 소유자 종료,
운영 상태와 작성자 부재를 별도로 감사하는 제한된 복구가 필요하며, 시간 경과만으로
해제하지 않는다. 회수 경로의 정상 종료와 SIGTERM 정리는 로컬 테스트로 검증한다.

로컬 테스트 통과는 운영 복구 완료가 아니다. 실제 `recovered_and_verified`,
lockAbsent, routingAndPointersUnchanged, protectedFilesUnchanged를 확인하고,
후속 운영 게시·앨범 현재 회차·관리자 모니터 최소 두 번의 재조회 증거를 확인한다.
실패 또는 미확정 단계와 기존 실패 회차는 보존한다.
