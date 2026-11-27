# 준비·게시·모니터 설치 분리

2026-11-27 장애 후 운영 workflow를 세 단계로 분리한다. 본체 게시가 검증된 뒤
모니터 설치가 취소된 경우 전체 workflow 결론만 보고 본체를 다시 배포하지 않는다.
기존 main 제한, 일시정지 변수, 관리자 접근 정책, SFTP 지문·소유권·경로 검사는 유지한다.

## 단계와 증거

| job | 작업 | 시간 한도 | 공통 서버 쓰기 큐 | 증거 |
|---|---|---:|---|---|
| `prepare` | 테스트, 공개 소스 수집, 승인된 UI 조합, 후보 검증 | 35분 | 사용하지 않음 | 실행·커밋에 묶인 후보 및 소스 검사 결과 |
| `deploy` | 정확한 후보 검증, 운영 게시, 재조회·접근 차단 확인 | 40분 | `isegye-inour-production` | `auth-deployment.json`, 후보 출처, 콘텐츠 게시 근거 |
| `install-monitor` | 같은 후보의 보호된 모니터 설치, 상태 갱신 | 20분 | `isegye-inour-production` | 모니터 설치 보고서, 수집기 상태, 원래 배포 증거 참조 |

workflow 전체의 `isegye-production-release` 큐는 같은 생산 배포의 중복 준비를
직렬화한다. 실제 서버 작성 job만 기존 공통 큐를 획득한다. 모든 writer 큐는
`cancel-in-progress: false`, `queue: max`를 유지하며 작성 중인 작업을 교체하지 않는다.

## 후보 전달

`production_candidate.py`는 `dist`, 자격증명이 없는 `auth-bundle`, 콘텐츠·영상 검사
보고서만 전달한다. 준비 job의 출력에 기록된 SHA-256을 신뢰 기준으로 사용한다.
다운로드한 압축 파일 내부의 해시를 자기 승인 근거로 사용하지 않는다.

같은 저장소·main·run ID·커밋, 명시된 준비 attempt, 24시간 이내의 시각을 검증한다.
파일 수·개별 크기·전체 해제 크기를 제한하고 경로 이탈, 링크, 중복 경로, 미등록 파일,
목적지의 기존 비검증 파일을 거부한다. 모든 멤버와 목적지를 확인한 후 파일을 쓴다.
후보 복원으로 저장소의 배포 스크립트나 workflow 소스를 덮어쓸 수 없다.
실제 인증 설정, 계정·세션·시크릿은 이 후보에 포함하지 않는다.

각 writer는 최신 main을 작업 시작과 실제 게시 직전에 다시 확인한다. 준비 결과가
오래됐거나 main이 바뀌면 기존 후보를 게시하지 않는다.

## 부분 재실행

실패한 job만 재실행할 때 이전에 성공한 prepare의 정확한 후보 ID·해시·attempt를
재사용할 수 있다. 새 prepare가 실행됐으면 그 새 후보와 일치해야 한다.

모니터 설치만 재실행하면 실제 본체 게시 attempt를 새로 만들지 않는다. 따라서
`production-publication-reference.json`은 배포 job 출력의 원본 artifact ID·digest,
게시 attempt, 준비 attempt를 현재 모니터 attempt에 연결한다. 독자는 GitHub의 원본
attempt와 산출물 출처·해시, 후보 검증 보고서를 다시 확인한다. 원래 게시·재조회
시각을 보존하며 임의의 과거 성공 실행으로 대체하지 않는다.

본체 게시 근거가 검증돼도 후속 모니터 실패는 별도로 표시한다. workflow 성공,
배포 요청 접수, 후보 빌드 성공만으로 운영 반영 완료를 표시하지 않는다.

## 관련 운영 문서

- [소유 잠금 및 제한된 회수](PRODUCTION_LOCK_RECOVERY.md)
- [배치 복구와 회차별 근거](BATCH_RELIABILITY.md)
- [검토된 음악 소스의 가용성](MUSIC_SOURCE_AVAILABILITY.md)
- [관리자 전용 모니터](BATCH_MONITORING.md)
