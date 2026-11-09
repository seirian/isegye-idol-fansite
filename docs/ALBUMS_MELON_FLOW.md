# 멜론 전용 흐름 그래프 및 무료 API 상태 정정

범위: `feature/albums`, `/review-albums/`만. main 병합·운영 화면 전환·기존 일배치/월배치 변경 없음.

## 서비스 비용과 상태

- 이전 UI의 `API 확인`은 성공 상태의 라벨이었다. 추가 설정이 필요하다는 뜻으로 오해되지 않도록 `연결됨`과 확인한 데이터 종류·시각을 구분한다.
- YouTube Data API v3 공개 영상 조회수/좋아요는 무료 할당량 범위로 사용한다. 검증된 영상 ID를 한 videos.list 요청에 모은다. 조회수와 좋아요는 음악 차트 순위나 음원 재생수가 아니다.
- 기존 Actions의 `ISEGYE_YOUTUBE_API_KEY`를 그대로 사용한다. 성공 응답이 확인되면 사용자 추가 조치는 없다. 비밀값을 조회·출력하거나 교체하지 않는다.
- 키 미설정일 때에만: Google Cloud에서 YouTube Data API v3를 활성화하고 서버 실행용 API 키를 발급, API 사용 제한을 YouTube Data API v3로 설정하고 저장소 Repository secrets의 `ISEGYE_YOUTUBE_API_KEY`에 등록한다. 서버 실행환경에 맞지 않는 HTTP referrer 제한 키는 사용하지 않는다. 키 값은 채팅/프런트엔드/일반 variables에 넣지 않는다. 해당 검토 workflow를 feature/albums로 수동 실행해 확인한다.
- 연결 실패와 키 미설정, 공식 영상 미연결, 영상 비공개, 오래된 스냅샷은 별도 상태다. API 오류를 유료 전환 필요로 표시하지 않는다.
- Apple은 무료 공개 iTunes Search API의 미국 카탈로그 메타데이터와 곡 바로가기만 유지한다. 별도 키·결제·개발자 가입 불필요. 검색 응답과 곡 매칭은 별개이며 미발매 영상에 매칭을 강제하지 않는다.
- Apple Music API / MusicKit의 개발자 토큰·유료 Developer Program 의존 기능은 사용하지 않는다. 기본 Developer Program은 연 US$99(지역별 통화/조건 상이)이나 이 구현의 요구사항이 아니다.
- 유튜브 뮤직은 검색 링크만 제공하고 독립 재생 통계 연동으로 표시하지 않는다.

공식 확인 출처 (2026-11-09):
- https://developers.google.com/youtube/v3/getting-started
- https://developers.google.com/youtube/data/reference/rest/v3/videos/list
- https://performance-partners.apple.com/search-api
- https://developer.apple.com/documentation/applemusicapi/generating-developer-tokens
- https://developer.apple.com/help/account/membership/program-enrollment

## 흐름 영역

- 순위 시계열은 멜론 TOP100 / HOT100(100일)만 수집하고 표시한다. 지니/벅스 카탈로그 링크·Apple 무료 메타데이터·YouTube 공개 통계·이전 최고 성적 7종은 유지한다.
- Apple 한국 차트 및 지니/벅스 순위 수집 요청은 검토 수집 진입점에서 제외했다. 이전 URL의 metric=genie/bugs/apple은 실제 기록이 있는 멜론 차트로 정규화한다.
- 기본 기간은 최근 24시간. 7일/30일 선택 유지. 실제 관측 시간 간격을 보존하고 축은 관측된 구간 및 순위 범위에 맞춰 표시한다. 데이터를 같은 간격으로 재배열하지 않는다.
- 각 연속 관측 구간은 단조 cubic Hermite 곡선과 아래로 사라지는 녹색 그라데이션 영역으로 표현한다. 실제 점의 값은 보존하고 구간을 넘어선 가짜 최고/최저가 발생하지 않도록 기울기를 제한한다.
- 90분이 넘는 미수집 간격은 실선/채움으로 표시하지 않고 낮은 강조도의 점선 안내로 분리한다. 점선은 중간 순위를 관측했다는 뜻이 아니다. 차트 밖/명시적 수집 실패 전후는 점선도 연결하지 않는다.
- 한 건은 점 하나이며 가짜 추세선을 만들지 않는다. 예시 데이터는 demo=1로 명시적으로 선택한 경우에만 사용한다.
- 포인터/키보드 포커스에서 시각과 정확한 순위를 별도 읽기 영역에 표시하고 수치 표도 유지한다. 움직임 감소 설정을 존중한다.

## 검증

`npm test`, `python -m unittest discover -s tests -p 'test_albums*.py' -v`, `tests/albums_browser.py` 및 기존 인증/게시 검증을 실행한다. 곡선의 국소 최댓값/최솟값 비발생, 실제 시간 간격, 분리 구간, 상태별 무료 API 안내, 과거 non-Melon URL, 실제 7종 최고 기록/공식 배지 유지가 회귀 범위다.
