# 이세돌 별빛 배송부 — 단일 미니게임 검토본

이 문서는 `feature/isegye-fangames`에서 승인된 검토본의 제작·검증 기록이다. 아래 검토 빌드 명령은 해당 브랜치 기준이며, 승인 후 놀이터 운영 통합과 현재 배포 방법은 [PLAYGROUND_PRODUCTION.md](PLAYGROUND_PRODUCTION.md)를 따른다.

2026-11-18 사용자 요청: 기존 우당탕 이세돌·세돌 원정대·합방 탈출을 폐기하고, 이전에 지정한 팬게임 3개의 표현과 완성도를 참고하여 신규 캐릭터·게임 이미지를 생성한 단일 미니게임을 만든다.

## 참고 기록과 적용

- 삼초고력: https://3chogomem.pages.dev/ — 한눈에 이해되는 한 판, 시작 버튼과 핵심 규칙 집중.
- 세돌체스: https://sedol-chess.pages.dev/ — 큰 캐릭터 일러스트, 일관된 게임용 카드와 무대 연출.
- 왁타 서바이버즈: https://waktasurvivors.pluckyiris34.chatgpt.site/ — 선택한 캐릭터가 실제 플레이에서도 같은 게임 이미지로 이어짐.

이전 조사 워크플로 `inspect-fangames.yml`, 실행 `44143718703`의 `fan-game-reference-observations`에 있는 브라우저 관찰 JSON과 스크린샷을 재검토했다. 이는 저장된 화면에 대한 관찰이며 세 게임 전체를 새로 플레이했다고 주장하지 않는다. 참고작의 이미지·코드를 복사하지 않았다.

## 새 게임

- 단일 75초 배달 액션. 이동하여 별빛 편지를 모은 뒤 중앙 우체통에 자동 배송한다.
- 세 차례 배송(4/6/8개)과 점점 늘어나는 유령, 대시와 멤버별 특기.
- 아이네 보호막, 징버거 느리게 하기, 릴파 질주, 주르르 자석, 고세구 밀어내기, 비챤 회복.
- 두 배송 사이 선물 선택(이동 속도/추가 체력/수집 범위). 선택 중에는 시간 정지.
- 승리·시간 초과·체력 소진, 배달 점수·콤보·등급·최고 기록·즉시 재도전.
- PC 방향키/WASD, Space 대시, E 특기. 모바일 조이스틱, 방향 버튼, 대시·특기 버튼.
- 일시정지, 화면 이탈 시 자동 정지, 소리 선택, 모션 감소 설정 지원.
- 음원 대신 사용자 동작 이후 브라우저가 합성하는 짧은 효과음만 사용한다.

## 새 이미지

내장 ImageGen 도구로 3개의 원본 이미지를 새로 생성했다. 기존 프로필은 멤버의 머리색·눈색 등 식별 특징 확인에만 사용했고, 새 게임에 기존 프로필 파일을 삽입하지 않았다.

| 원본 | 웹 배포본 | 내용 |
| --- | --- | --- |
| `fangames/art-source/characters.png` | `fangames/assets/characters.webp` | 새 배송부 의상·포즈의 멤버 6명, 3×2 투명 아틀라스 |
| `fangames/art-source/plaza.png` | `fangames/assets/plaza.webp` | 별빛 우편 광장, 1536×1024 배경 |
| `fangames/art-source/items.png` | `fangames/assets/items.webp` | 편지·유령·박쥐·보호막·하트·우체통, 3×2 투명 아틀라스 |

선택 화면, 캐릭터 소개, 실제 필드, 결과 화면에서 같은 신규 캐릭터 아틀라스를 사용한다. 원본 PNG는 보존하고 구도·투명도를 유지해 WebP 품질 87로 배포용 변환했다. 생성 프롬프트는 `fangames/art-source/PROMPTS.md`에 보관한다. 생성 방식은 내장 ImageGen이며 API/CLI 대체 경로를 사용하지 않았다.

## 폐기와 배포 범위

이전 세 게임의 소스와 화면 탐색을 제거했다. 과거 Git 커밋과 기존 서버의 불변 릴리스는 배포 복구 기록으로 남으며, 새 활성 검토본에서는 제공하지 않는다.

검토 주소: https://isegye-idol.kr/review-playground/
브랜치: `feature/isegye-fangames`.

새 이미지까지 단일 HTML의 data URI로 포함하며 외부 연결 없는 해시 CSP를 유지한다. 기존 관리자 인증 경로를 재사용하고, `.review-playground` 내 릴리스와 활성 포인터만 게시한다. 운영 놀이터 메뉴 통합은 검토 후 별도 단계이다. 이전 퀴즈 기록·계정·배치·운영 UI를 읽거나 수정하지 않는다.

저장 키는 `isegye:review:courier:v2`이며 선택 멤버·효과음 설정·최고 점수만 해당 브라우저에 저장한다. 저장 불가/손상 시에도 플레이 가능하다.

## 검증

```sh
node --check fangames/engine.js
node --check fangames/app.js
node --test tests/courier-engine.test.js
python scripts/build_fangames.py
python -m unittest discover -s tests -p test_fangames.py -v
python tests/fangames_browser.py
```

단위 검증은 재현 가능한 게임 시뮬레이션과 경계·상태 전이를 확인한다. 브라우저 검증은 HTTP에서 실제 UI 조작, 캐릭터 이미지, 키보드와 터치, PC·모바일 레이아웃, 일시정지·저장·결과 흐름을 확인한다. 게시 완료는 Actions 성공만이 아니라 `review-fangames-deployment.json`의 `gated_preview_published_and_verified`, 실제 게시 바이트 재조회, 기존 운영 및 인증 격리 유지 확인으로 판단한다. 실제 사용자 계정을 가장해 로그인하지 않는다.

2026-11-18 로컬 최종 검증: 엔진 9개, 빌드·배포 격리 12개, 브라우저 88개 검사를 통과했다. 실제 키보드 입력으로 3회 배송·2회 강화·4455점 A등급 승리를 확인했고, 320/390/768/1440px 화면과 1280×720 결과 버튼 클릭을 검증했다. JavaScript/CSP 오류와 외부 요청은 0건이다. 브라우저 검증 HTML SHA256은 `e2dd2c375ba5b95fbb991206ae3fa5b48ad03bf3e6d422be62a59377402d1c55`이며, 검사 동안 빌드 바이트가 바뀌지 않았다.
