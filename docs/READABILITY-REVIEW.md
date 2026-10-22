# 가독성 개선 검토판 + 지니뮤직 프로필

브랜치 `feature/readability`, PR #4. 검토 주소: https://seirian.github.io/isegye-idol-fansite/previews/feature-readability/

2026-10-22 사용자가 지정한 지니뮤직 그룹 페이지에서 연결된 6명의 개인 아티스트 페이지를 확인했습니다. 각 페이지의 크게 보기 링크에 실제 연결된 600×600 JPEG를 사용합니다. 200px 썸네일, 기존 패러블 아바타, 나무위키 미러 이미지는 이 검토본에 포함하지 않습니다. 출처와 멤버 연결을 확인했다는 의미이지 나무위키와의 동일성이나 제3자 이용허락 취득을 주장하지 않습니다.

## 구현 및 실행

`review/portraits.json`에 멤버명, 지니 아티스트 ID, 개인 페이지, 원본 URL, 확인 시각, 원본/WebP 체크섬을 관리합니다. 기술 정보는 방문자 화면에 표시하지 않습니다.

`prepare_genie_portraits.py`는 허용된 지니 이미지 호스트에서 검증한 6개 원본만 가져와 체크섬을 확인하고 WebP로 준비합니다. 원본 변경·다른 멤버·임의 URL·리디렉션·경로 이탈은 거부합니다. 원본 확보 실패를 구 아바타로 대체하지 않습니다. 생성한 파일을 배포 패키지에 포함하므로 방문자 브라우저는 지니 서버에 자동 이미지 요청을 하지 않습니다.

```sh
python -m pip install pillow==11.3.0
python scripts/prepare_genie_portraits.py
python scripts/build_readability.py
python -m http.server 4180 --bind 127.0.0.1 --directory readability-dist
```

홈·멤버 목록·각 상세·단일 HTML이 같은 프로필을 사용합니다. 정사각형 비율과 object-fit:contain으로 원본을 자르지 않고 색조도 변경하지 않습니다. 이미지 버전 식별자를 URL에 포함합니다.

소개는 기존 3개 섹션에 `프로필 이미지: 지니뮤직` 한 줄만 추가합니다. 파일명·브랜치·대조 과정·오류 코드 등은 노출하지 않습니다. 본문 16px/보조 14px, 대비, 모바일 2열 등 이전 개선을 유지합니다.

## 검증과 경계

원본 검증/멤버 매핑 단위 검사, 이미지별 HTTP 바이트 일치, 홈/목록/상세/오프라인 디코딩, 14개 화면과 4개 화면 폭, 200% 글자 확대, 소개 간소화, 다크 테마, 외부 이미지 자동 요청이 없는지 검사합니다. 실제 결과는 Actions 아티팩트에 기록합니다.

Pages에는 기존 develop 루트와 /second/를 보존하며 이번 검토 주소만 갱신합니다. main/develop 병합, SFTP, 운영 배포, backup/main1st, 미르 경로와 공유 라우터는 변경하지 않습니다.
