# 두 번째 디자인 — 현재 운영 선택안

2026-10-22 사용자가 검토안을 선택하고 main 반영·운영 배포를 요청했습니다.
기존 main은 `backup/main1st`에 보존하며 새 디자인의 운영 완료 여부는 배포 Actions를 기준으로 확인합니다.

코랄·라벤더·크림색 배경, 여섯 멤버 포토카드, 하트 즐겨찾기, 음악 쇼케이스, 일정 메모, 상단 8개 메뉴와 모바일 3×2 카드를 사용합니다.
기존 출처 기반 데이터, 검색·달력·문서 연결·즐겨찾기 기능은 공유합니다.

## 빌드

- 공통 빌드: `npm run build` → `dist/` (Pillow 11.3.0, Node 22+, Python 3.10+).
- 운영 빌드: main에서 `DEPLOY_ENV=production npm run build`.
- 독립 검토: `python scripts/build_second.py` → `second-dist/`.
- 템플릿: `second/compose.py`, 스타일: `second/theme.css`, 포장·운영 메타데이터: `scripts/build_selected.py`.
- 운영 패키지는 공개 HTML과 로컬 이미지·출처 JSON만 포함하며 검토용 단일 HTML은 제외합니다.

## 이미지

공식 프로필 임시본과 나무위키 원본 미확인 안내는 유지합니다. 운영 승인으로 이미지 라이선스 확인이 완료되는 것은 아닙니다.
원본 URL과 체크섬은 `second/portraits.json`, 운영 결과의 출처는 `assets/portraits/sources.json`에서 확인합니다.
이미지 원본 파일은 새로 생성하거나 다른 캐릭터로 바꾸지 않았습니다.

## 검증 및 배포

브라우저 공통 기능 9개와 44개 디자인 검사를 운영 URL에서 실행하고, 비공개 경로 차단 및 기존 미르·개인 사이트 보존을 확인합니다.
preview는 noindex, production만 index/follow 및 운영 canonical을 사용합니다.
develop Pages는 `/second/`를 함께 게시하지만 다른 모든 feature 브랜치의 자동 보존은 별도 작업입니다.
운영 경계와 복구는 `docs/PRODUCTION.md`를 참조하세요.
