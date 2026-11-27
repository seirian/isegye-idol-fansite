# 음악 영상 가용성 검증과 게시

## 목적과 적용 범위

2026-11-27 운영 배포에서 기존에 검토된 팬 백업 영상의 oEmbed 404가 반복되어
사이트 전체 게시가 중단됐다. 곡·발매·참여자 기록은 유지하면서, 현재 확인할 수 없는
기존 백업 영상의 재생 링크를 비활성화한 후보만 게시할 수 있도록 한다.
이 정책은 영상 삭제나 채널 폐쇄를 확정하지 않으며 재생·이용허락을 보증하지 않는다.

`check_music_video_sources.py`의 기본 모드는 기존과 같이 모든 선택 영상의 검사를
통과해야 성공한다. 운영 후보 준비 단계에서만
`--allow-reviewed-backup-unavailable`을 명시해 제한된 예외를 사용한다.
일일 음악 수집기 등 기존 실행은 파일의 존재만으로 이 정책에 들어오지 않는다.

## 게시 가능한 부분 실패

아래 조건을 모두 만족해야 한다.

- 기존 `video-sources.json` 및 `video-sources.tsv`를 해석한 전체 매핑의 SHA-256이
  `music_source_availability.REVIEWED_SELECTION_SHA256`과 일치한다.
- 같은 곡·선택 영상 ID·분류·업로더에 대한 `fan_backup` 검사다.
- 실패가 **메타데이터 조회 단계의 HTTP 404**다. 썸네일 404와 혼동하지 않는다.
- 나머지 모든 선택 영상을 빠짐없이 검사했고, 그 외 차단 오류는 없다.
- 게시 후보에서 해당 곡의 `videoId`와 재생 `url`이 제거됐다.
- `videoSource.reviewedVideoId`와 원래 영상 ID, 곡 ID·제목·발매일·참여자·출처는 남긴다.
- 목록·곡 상세에 `영상 확인 불가`를 표시하고 실제 재생 버튼·썸네일을 비활성화한다.
  같은 실패 ID를 원본 링크라는 이름으로 다시 노출하지 않는다.

공식 영상의 404, 업로더 불일치, 새로운 선택, 변조된 매핑, 썸네일 오류,
403/429/5xx/시간초과·기타 미확인 오류는 계속 게시를 막는다.
새 영상을 검색하거나 자동으로 다른 영상으로 대체하지 않는다.

## 증거와 상태

`test-results/music-sources/source-audit.json`은 `passed`, `failed`, `unavailable`,
`blockingFailures`, 채널별 `sourceStates`, 기존 `unresolved`를 분리한다.
백업 영상 79개를 비활성화한 경우 `passed=72`, `failed=79`, `unavailable=79`,
`blockingFailures=0`, `state=partial`이다. 기존 미연결 3곡은 `unresolved`로 별도 보존한다.
부분 실패를 `passed=151` 또는 `complete`로 바꾸지 않는다.

`source-availability.json`은 감사 원본 바이트의 SHA-256, 선택 매핑 SHA-256,
저장소·전체 커밋 SHA·run ID·attempt, 검사 시각, 비활성화할 정확한 곡·영상 ID를 묶는다.
두 파일은 같은 후보 아카이브에 보관한다. 빌드·게시 전 재검증은 다음을 요구한다.

1. 같은 저장소, 같은 커밋, 같은 run, 같은 준비 attempt.
2. 24시간 이내이며 2분 넘게 미래가 아닌 원본 검사 시각.
3. 두 파일의 바이트 해시·원본 검사 내용·재계산한 수량 및 상태 일치.
4. 모든 151개 선택에 대한 중복 없는 검사와 기존 미연결 3곡 유지.
5. 최종 운영 데이터와 런타임 음악 피드의 불변 기준 데이터 모두 재생 차단 유지.

후속 게시 단계만 재실행할 때 `MUSIC_SOURCE_AUDIT_ORIGIN_ATTEMPT`를 사용할 수 있다.
값은 양의 정수이며 현재 attempt보다 클 수 없다. 워크플로는 신뢰된 prepare 출력과
후보 manifest의 attempt가 일치하는 값을 제공해야 한다. 임의의 과거 산출물을 고르는
옵션이 아니며 run·커밋·24시간·아카이브 해시 검증을 완화하지 않는다.

## 워크플로 연결

단위 검사에는 요구 변수를 미리 주입하지 않는다. 공개 감사를 수행한 뒤 후보 빌드와
후속 게시 검사에 다음 값을 전달한다.

```text
MUSIC_SOURCE_AUDIT_REQUIRED=true
MUSIC_SOURCE_AUDIT_PATH=test-results/music-sources/source-audit.json
```

최종 앨범·놀이터 조합 이후, 그리고 후보 다운로드·해시 검증 후 원격 쓰기 이전에 실행한다.

```sh
python scripts/verify_music_source_availability.py --bundle dist
```

검증기는 최종 `src/data.js`, 런타임 기준인 `src/production-ui.js`, `build-info.json`의
증거 연결과 정확한 재생 ID를 대조한다. 검증 성공은 후보의 안전성 근거이며 운영 게시
성공으로 보고하지 않는다. 게시 성공은 기존 파일 재조회·권한 차단·후속 갱신 증거를
별도로 요구한다.

고정 검토본 원본이나 승인 해시를 덮어쓰지 않는다. 현재 운영 조합 단계의 adapter로
표시를 추가하며, 기존 `/api/music`는 비활성화된 불변 기준 기록을 유지한 채 검증된
공식 신규 자료만 추가한다. 가용성 복구도 다음 검증된 후보에서만 반영한다.

## 회귀검증

`tests/test_music_source_availability.py`는 당시 3개 채널의 79건 패턴을 재현한
합성 fixture, 업로더 변경·공식 영상 실패·미확인 오류, 매핑 변조, 누락/중복,
stale/다른 실행/해시 불일치, 최종 데이터·런타임 기준의 재생 링크 재유입을 검사한다.
`tests/music-source-availability.test.js`는 비활성·미확인 버튼과 일일 피드 반영 후
기존 차단 유지 여부를 검사한다. fixture 결과는 새로운 운영 관측으로 기록하지 않는다.

2026-11-27 로컬 통합검증에서는 위 79건 합성 fixture로 운영 baseline 빌드부터
review2 → albums → playground → monitor host까지 조합한 뒤 최종 후보 검증을 통과했다.
실제 Chromium에서 52개 정적 UI 검사를 수행해 79곡의 링크·썸네일 차단, 기존 154곡과
앨범 추가 5곡의 기록 보존, 공식 영상 연결 유지, 밝은/어두운 테마의
320·390·768·1440px 가로 넘침 없음과 JavaScript 예외 없음을 확인했다.
이 검증은 로컬 후보 동작 검증이며 현재 원본 영상의 가용성 관측이나 운영 배포 완료를
의미하지 않는다. 운영 실행은 새 감사와 해당 실행에 연결된 게시·재조회 증거를 요구한다.
