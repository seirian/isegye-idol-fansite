# ISEGYE! — 이세계아이돌 비공식 팬 아카이브

## 현재 선택한 디자인

2026-10-22 운영자의 요청에 따라 두 번째 포토카드형 디자인을 운영 대상으로 선택했습니다.
첫 번째 운영 소스는 **`backup/main1st`**, 커밋 `885e818063eeccedf468d52ce148a4760819c97d`에 보존됩니다.
브랜치 백업과 실제 서버의 이전 릴리스 보존은 별개이며, 운영 배포 성공 여부는 Actions 보고서를 확인해야 합니다.

- `npm run build`: 선택한 두 번째 디자인을 `dist/`에 검토용으로 생성합니다. Pillow 11.3.0이 필요합니다.
- `DEPLOY_ENV=production npm run build`: main에서 canonical·robots·운영 문구를 적용한 공개 번들을 생성합니다.
- `PYTHON=/path/to/python`으로 격리된 Python 환경을 지정할 수 있습니다.
- `python scripts/build_second.py`: 독립적인 `/second/` 검토용 패키지를 `second-dist/`에 생성합니다.
- `src/app.js`는 공유 기능과 합성 기준을 유지합니다. 새 화면의 템플릿은 `second/compose.py`, 스타일은 `second/theme.css`입니다.
- 멤버 프로필은 검토판에서 사용한 패러블 공식 소개 이미지의 임시본입니다. 나무위키 원본 일치나 별도 이용허락을 확인했다고 주장하지 않습니다.
- 현재는 23개 공개 항목의 공개 베타이며 실시간 데이터·회원·CMS·비공개 신고 시스템은 아직 없습니다.

개발 실행:

```sh
python3 -m venv .venv
.venv/bin/pip install pillow==11.3.0
PYTHON="$PWD/.venv/bin/python" npm run dev
```

배포 및 복구: [docs/PRODUCTION.md](docs/PRODUCTION.md). 디자인·빌드: [docs/SECOND.md](docs/SECOND.md).
초기 개설 당시 문서는 백업 브랜치에서 확인할 수 있습니다.
