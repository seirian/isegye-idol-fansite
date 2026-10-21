# 운영 배포 — 2026-10-21 승인

사용자가 main 병합 및 운영 배포를 명시적으로 승인했습니다. 기존 비활성 준비 단계를 종료하고, main push에서 production 환경을 사용하는 자동 배포를 활성화합니다. GitHub 환경의 승인·브랜치 제한은 그대로 적용됩니다.

- develop: GitHub Pages 검토판, noindex. 인아워넷 앱 배포 없음.
- main: 테스트 및 운영용 빌드 후 https://isegye-idol.kr/ 로 공개 베타 배포.
- 쓰기 대상은 `/web/_isegye_idol` 내부뿐입니다. 이미 연결한 공용 `.htaccess`, 미르 사이트, 개인 사이트, DNS는 수정하지 않습니다.
- 운영 활성화는 버전 관리된 production.yml에 명시했습니다. 이전 설명의 별도 PRODUCTION_ENABLED 저장소 변수 설정은 더 이상 필요하지 않습니다. 긴급 배포 중지는 production 환경 또는 저장소의 `PRODUCTION_PAUSED=true`로 설정합니다. 이미 실행 중인 작업의 취소와는 별개입니다.
- 자격 증명은 production 환경의 `ISEGYE_SFTP_PASSWORD`를 사용하며 읽어 내거나 출력하지 않습니다.
- 매 실행·재시도마다 별도 릴리스 폴더를 만들고 원본을 지우지 않습니다. build-info.json의 commit이 실제 main SHA입니다.
- 이전 이세돌 라우터를 비공개 `.release-backups`에 저장하고, 원자적으로 활성화합니다. 파일 바이트, 운영 도메인의 브라우저 9개 시나리오, PC·모바일 화면, canonical·robots·커밋, 기존 미르·개인 사이트 보존을 검증합니다.
- 검증 실패 시 이전 이세돌 라우터로 복구합니다. 외부에서 라우터가 변경됐으면 덮어쓰지 않고 수동 복구 필요를 보고합니다. 연결 종료·서버 장애로 복구가 실패할 가능성은 보고서의 manual_recovery_required로 확인합니다.
- 배포 결과는 Actions의 `isegye-production-<run>-<attempt>` 아티팩트에 남습니다. inour-report.json의 `deployed_and_verified`가 완료 조건입니다.

초기 공개 베타는 23개 공개 항목을 제공하며 전체 활동·음반·방송을 완전히 수집한 서비스가 아닙니다. 실시간 API, 회원·관리자 CMS, 비공개 신고 접수는 아직 제공하지 않습니다. 미구현 범위 및 자료 확인일은 화면에 표시합니다.

기존 README 및 DEPLOYMENT.md의 초기 main 미병합·운영 비활성 설명은 개설 준비 단계의 기록입니다. 현재 운영 절차는 본 문서와 production.yml 및 실제 Actions 결과를 기준으로 합니다.
