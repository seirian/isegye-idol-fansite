# 운영 배포 — 두 번째 디자인 승격

2026-10-22 운영자가 온라인 검토판을 선택하고 main 반영·배포 및 기존 main의 백업을 요청했습니다.
실제 배포 완료 여부는 Actions의 `inour-report.json`의 `deployed_and_verified`로 확인합니다.

## 브랜치와 빌드

- 소스 백업: `backup/main1st` → `885e818063eeccedf468d52ce148a4760819c97d`. 백업 브랜치는 변경하지 않습니다.
- develop: noindex GitHub Pages 검토판. 인아워넷 앱 배포 없음.
- main: 테스트·운영 빌드 후 https://isegye-idol.kr/ 공개 베타 배포.
- 선택 기록: `second/release.json`. 운영자의 디자인 승인과 이미지 권리자의 이용허락을 구분합니다.
- `npm run build`는 `scripts/build_selected.py`로 두 번째 디자인을 패키징합니다. `scripts/build_second.py`의 noindex 중간 결과에 운영 계약을 적용하는 2단계 빌드입니다. 검토용 결과를 그대로 서버에 업로드하지 않습니다.
- production 모드에서만 canonical, index/follow, 운영 문구를 적용합니다. 검토판·다운로드 검토본은 noindex를 유지합니다.
- Node 22+, Python 3.10+, Pillow 11.3.0을 사용합니다. Actions는 별도 venv에 도구를 설치합니다.
- 이미지 원본 체크섬을 검증하고 6장을 정적 파일로 제공합니다. 브라우저에서 외부 이미지 핫링크 요청을 보내지 않습니다. 출처·미확인 상태는 화면과 `assets/portraits/sources.json`에 남습니다.

## 운영 경계와 검사

- 쓰기 대상은 `/web/_isegye_idol` 내부뿐입니다. 공용 `.htaccess`, 미르·개인 사이트 파일, DNS·인증서는 수정하지 않습니다.
- `production` 환경의 기존 승인·브랜치 제한을 적용하고 `ISEGYE_SFTP_PASSWORD`를 사용합니다. 비밀값을 읽어 내거나 출력하지 않습니다.
- 운영 활성화는 production.yml에 기록돼 있습니다. 긴급 중지는 production 환경 또는 저장소의 `PRODUCTION_PAUSED=true`입니다. 실행 중인 작업 취소와는 별개입니다.
- 매 실행·재시도마다 별도 릴리스 폴더를 만들며 이전 릴리스는 자동 삭제하지 않습니다. `build-info.json`의 commit이 실제 main SHA입니다.
- 이전 이세돌 라우터를 비공개 `.release-backups`에 저장하고 원자적으로 활성화합니다.
- 공개 파일 바이트, 기존 9개 기능 시나리오, 두 번째 디자인 44개 검사, PC·모바일, canonical·robots·커밋, 비공개 경로 및 기존 사이트 보존을 검증합니다.
- 운영 후 검사는 이전 라우터 복구가 가능한 구간 안에서 수행합니다. 실패하면 이전 이세돌 라우터로 복구하지만 동시 외부 변경은 덮어쓰지 않습니다. 연결 종료·서버 장애로 복구에 실패하면 `manual_recovery_required`를 확인합니다.
- develop Pages는 루트에 선택한 디자인을 게시하면서 `/second/`도 같이 보존합니다. 임의의 모든 feature 브랜치를 보존하는 시스템은 아닙니다.

## 첫 번째 디자인 복구

실제 서버에서는 배포 보고서의 `previous_router_backup`에 해당하는 이전 라우터와 이전 릴리스를 보존합니다.
소스 복구는 `backup/main1st`를 기준으로 별도 PR을 검토해 main에 반영합니다. main을 강제로 재설정하지 않습니다.
브랜치 백업만으로 자동 복구가 실행되지는 않으며, 배포 실패 시 복구 결과는 `rollback_restored_previous`로 확인합니다.

## 공개 범위

23개 공개 항목을 제공하는 공개 베타이며 전체 활동·방송을 수집한 완성본은 아닙니다.
실시간 API, 회원·관리자 CMS, 비공개 신고 접수는 아직 없습니다. 자료 확인일은 기존 검수일을 유지합니다.
패러블 공식 소개 이미지 임시본의 출처와 나무위키 대조·이용허락 미확인 안내를 유지합니다.
초기 DEPLOYMENT.md의 운영 비활성 설명은 개설 준비 단계 기록이며 현재 운영 절차는 이 문서와 production.yml을 따릅니다.
