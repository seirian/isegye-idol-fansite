# 음악 입문 시리즈 — 공식 원본 연결

사용자 요청에 따라 운영 시리즈 `music-beginning`의 제목을 **Re:Wind 부터 만나보는 이세계아이돌**로 변경한다. 같은 시리즈 데이터를 사용하는 콘텐츠 > 시리즈·합방 목록에도 동일하게 표시한다.

순서: RE:WIND → 겨울봄 → KIDDING → Be My Light → Smile For You → REBELS.
카드의 이미지·제목·YouTube에서 보기 버튼은 해당 공식 YouTube 원본으로 직접 연결하며 영상 상세 링크는 별도로 제공한다. 앨범/곡 상세를 기본 연결로 사용하지 않는다.

원본 공개 메타데이터 확인: Actions `43775085793`, 2026-11-16 08:29:32 KST. 정확한 ID·채널·제목·영상 공개일·재생시간은 `catalog/music-beginning.json`에 보관한다. 전체 재생이나 권리 허가를 확인한 것은 아니다.

Smile For You의 확인된 공식 영상은 `8IY44RZHyw8` **Special Clip**이다. 원본을 MV로 잘못 표시하지 않고 공식 Special Clip으로 연결한다. 나머지 5편은 공식 MV다. 날짜는 앨범 발매일이 아니라 실제 원본 영상 공개일이다.

운영 빌드에만 적용한다. 기존 곡, 앨범, 차트, 원본 영상 기록, 외부 퍼포먼스, 다른 시리즈, 검토판 원본, 로그인 및 정기 수집 설정은 변경하지 않는다. 영상 기록을 새로 복제하지 않으며 기존 video ID를 사용해 저장과 시리즈 이전/다음 이동을 유지한다.

검사: `tests/test_music_beginning.py`, `tests/music_beginning_browser.py`. 브라우저 검사는 CI 및 운영 업로드 이전 단계에서 실행한다. 로컬 DOM/레이아웃 검사와 HTTP/CSP 검사는 구분한다.
