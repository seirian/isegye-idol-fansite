# 단체 이미지 히어로 검토

사용자가 대화에 제공한 두 번째 첨부 이미지(이세돌단체.png)를 오른쪽 초대장 대신 사용합니다. 이 변경은 feature/readability 검토본에만 반영합니다.

- 기존 YOU ARE INVITED TO / OUR UNIVERSE 초대장과 겹치던 영문 장식을 제거합니다.
- 960×540 원본의 전체 구도를 유지해 800×450 WebP로 최적화했습니다. 인물 자르기·생성형 편집·색조 필터는 사용하지 않습니다.
- PC: 문구 오른쪽의 가로 이미지 프레임. 960px 이하: 문구 아래로 재배치하며 모바일에서도 이미지를 숨기지 않습니다.
- 기존 지니뮤직 프로필 6장, 가독성 개선, 간소화된 소개는 유지합니다. 이미지 출처나 제작자를 임의로 만들어 표시하지 않습니다.
- scripts/build_group_hero.py가 기존 검토 빌드를 실행한 뒤 템플릿·CSS·이미지·오프라인 HTML을 구성합니다. production 모드는 거부합니다.
- tests/group_hero_smoke.py는 이미지 체크섬·커밋·기존 초대장 제거·9개 화면 폭·전체 비율·모바일 재배치·다크 모드·200% 글자 확대·오프라인 파일을 검사합니다.
- 검토 URL: https://seirian.github.io/isegye-idol-fansite/previews/feature-readability/

main/develop 병합 및 인아워넷 운영 배포는 하지 않습니다. 실제 게시 성공은 Actions와 게시 후 브라우저 결과로 확인합니다.
