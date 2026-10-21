/** Public, source-backed content. No private facts, copied media, or unreviewed submissions. */
export const SITE = Object.freeze({name:'이세돌 아카이브',version:'0.1.0',reviewedAt:'2026-10-15',repo:'https://github.com/seirian/isegye-idol-fansite',mode:'preview'});
export const SOURCES = {
  network:{title:'Creator Network',publisher:'패러블',url:'https://parable-asia.com/creator-network/',checkedAt:'2026-10-15'},
  policy:{title:'팬 제작 콘텐츠 가이드라인',publisher:'패러블',url:'https://parable-asia.com/guideline/',publishedAt:'2026-05-02',checkedAt:'2026-10-15'},
  cat:{title:'NO CAT, NO LIFE!',publisher:'패러블',url:'https://parable-asia.com/portfolio-item/no-cat-no-life/',publishedAt:'2026-09-28',checkedAt:'2026-10-15'},
  smile:{title:'Smile For You',publisher:'패러블',url:'https://parable-asia.com/portfolio-item/smile-for-you/',publishedAt:'2026-06-19',checkedAt:'2026-10-15'},
  white:{title:'화이트 (White)',publisher:'패러블',url:'https://parable-asia.com/portfolio-item/%ED%99%94%EC%9D%B4%ED%8A%B8-white/',publishedAt:'2025-12-19',checkedAt:'2026-10-15'},
  light:{title:'Be My Light',publisher:'패러블',url:'https://parable-asia.com/portfolio-item/be-my-light/',publishedAt:'2025-11-03',checkedAt:'2026-10-15'},
  stars:{title:'Stargazers',publisher:'패러블',url:'https://parable-asia.com/portfolio-item/stargazers/',publishedAt:'2025-05-18',checkedAt:'2026-10-15'},
  misty:{title:'Misty Rainbow',publisher:'패러블',url:'https://parable-asia.com/portfolio-item/misty-rainbow/',publishedAt:'2025-04-25',checkedAt:'2026-10-15'},
  smileNews:{title:'이세계아이돌, Smile For You 발매',publisher:'패러블',url:'https://parable-asia.com/이세계아이돌-smile-for-you-음원-발매/',publishedAt:'2026-06-19',checkedAt:'2026-10-15'},
  replay:{title:'이세계페스티벌, 이세계아이돌 Part 함께보기',publisher:'패러블',url:'https://parable-asia.com/이세계페스티벌-이세계아이돌-part-soop-limited-streaming/',publishedAt:'2025-12-20',checkedAt:'2026-10-15'},
  pepero:{title:'이세계아이돌, 빼빼로 컬래버레이션 진행',publisher:'패러블',url:'https://parable-asia.com/이세계아이돌-빼빼로-콜라보레이션/',publishedAt:'2025-10-12',checkedAt:'2026-10-15'},
  discography:{title:'Discography',publisher:'패러블',url:'https://parable-asia.com/discography/',checkedAt:'2026-10-15'}
};
export const MEMBERS = [
  {id:'ine',name:'아이네',en:'INE',mark:'I',tone:'lavender'},
  {id:'jingburger',name:'징버거',en:'JINGBURGER',mark:'J',tone:'apricot'},
  {id:'lilpa',name:'릴파',en:'LILPA',mark:'L',tone:'indigo'},
  {id:'jururu',name:'주르르',en:'JURURU',mark:'J',tone:'rose'},
  {id:'gosegu',name:'고세구',en:'GOSEGU',mark:'G',tone:'sky'},
  {id:'viichan',name:'비챤',en:'VIICHAN',mark:'V',tone:'sage'}
];
const all = MEMBERS.map(m=>m.id);
export const RECORDS = [
  ...MEMBERS.map(m=>({id:m.id,kind:'member',title:m.name,subtitle:m.en,members:[m.id],sourceIds:['network','replay'],status:'verified',visibility:'published',tags:['이세계아이돌',m.en],summary:'이세계아이돌 멤버. 공개 음악과 관련 활동을 모아봅니다.',body:['그룹 참여 음악과 관련 기록을 이 페이지에서 함께 탐색할 수 있습니다.','세부 프로필·취향·별명은 공개 출처를 확보한 뒤 추가합니다. 아래 연결은 현재 등록된 자료의 범위이며 전체 활동 목록은 아닙니다.']})),
  {id:'no-cat-no-life',kind:'music',title:'NO CAT, NO LIFE!',subtitle:'고세구 · 솔로 싱글',date:'2026-09-28',members:['gosegu'],sourceIds:['cat'],status:'verified',visibility:'published',tags:['솔로','정식 발매','고양이가 세상을 구한다','Your Turn','PUMP JUMP BUMP'],summary:'고세구의 솔로 싱글. 세 곡을 통해 서로 다른 에너지를 선보입니다.',body:['패러블의 공식 소개에 따르면 이세계아이돌 솔로 프로젝트의 첫 번째 음반입니다.','발매 정보와 수록곡 제목을 정리했습니다. 음원·가사·앨범 이미지는 복제하지 않으며, 상세 제작 정보는 원문에서 확인할 수 있습니다.'],tracks:['고양이가 세상을 구한다!','Your Turn','PUMP JUMP BUMP'],tone:'sky',art:'cat',related:['gosegu','single','official-source']},
  {id:'smile-for-you',kind:'music',title:'Smile For You',subtitle:'이세계아이돌 · 스페셜 싱글',date:'2026-06-19',members:all,sourceIds:['smile'],status:'verified',visibility:'published',tags:['단체','정식 발매','팬송'],summary:'팬들에게 전하는 감사의 마음. 멤버들이 작사에 참여한 스페셜 싱글입니다.',body:['공식 소개는 어쿠스틱 기타가 어우러진 미디엄 템포 발라드로 설명합니다.','이 페이지는 공식 소개의 요약이며, 가사 전문과 음원을 제공하지 않습니다.'],tracks:['Smile For You'],tone:'apricot',art:'smile',related:['smile-special-clip','single']},
  {id:'white',kind:'music',title:'화이트 (White)',subtitle:'이세계아이돌 · 리메이크 싱글',date:'2025-12-19',members:all,sourceIds:['white'],status:'verified',visibility:'published',tags:['단체','정식 발매','리메이크','핑클'],summary:'데뷔 4주년과 연말을 기념해 선보인 리메이크 싱글입니다.',body:['패러블 공식 안내에 따르면 핑클의 화이트를 이세계아이돌이 새롭게 해석한 음반입니다.'],tracks:['화이트 (White)'],tone:'sage',art:'white',related:['remake','cover']},
  {id:'be-my-light',kind:'music',title:'Be My Light',subtitle:'이세계아이돌 · 싱글',date:'2025-11-03',members:all,sourceIds:['light'],status:'verified',visibility:'published',tags:['단체','정식 발매','Nameless'],summary:'Be My Light와 Nameless, 두 곡의 서로 다른 사운드를 담았습니다.',body:['공식 소개는 타이틀곡의 피아노·밴드·현악 구성과 Nameless의 전자음 기반 사운드를 설명합니다.'],tracks:['Be My Light','Nameless'],tone:'lavender',art:'light',related:['single']},
  {id:'stargazers',kind:'music',title:'Stargazers',subtitle:'이세계아이돌 · 5번째 공식 싱글',date:'2025-05-18',members:all,sourceIds:['stars'],status:'verified',visibility:'published',tags:['단체','정식 발매','ELEVATE','MEMORY'],summary:'Stargazers, ELEVATE, MEMORY를 담은 싱글입니다.',body:['패러블은 세 곡이 두 번째 콘서트에서 먼저 공개되었다고 소개합니다. 상세 공연 기록은 별도 출처 검수를 거쳐 추가할 예정입니다.'],tracks:['Stargazers','ELEVATE','MEMORY'],tone:'indigo',art:'stars',related:['single','setlist']},
  {id:'misty-rainbow',kind:'music',title:'Misty Rainbow',subtitle:'이세계아이돌 · 4번째 공식 싱글',date:'2025-04-25',members:all,sourceIds:['misty','discography'],status:'verified',visibility:'published',tags:['단체','정식 발매'],summary:'패러블 공식 음반 안내에 등록된 네 번째 공식 싱글입니다.',body:['현재 검토판에는 공식 발매일과 제목을 우선 등록했습니다. 전체 트랙·제작진은 세부 정보 확인 후 확장합니다.'],tone:'rose',art:'rainbow',related:['single']},
  {id:'smile-special-clip',kind:'video',title:'Smile For You 스페셜 클립 안내',subtitle:'공식 콘텐츠 안내 · 원문 연결',date:'2026-06-19',members:all,sourceIds:['smileNews'],status:'verified',visibility:'published',tags:['스페셜 클립','음악','공식 안내'],summary:'패러블 발매 공지에서 공식 유튜브 채널의 스페셜 클립 공개를 안내했습니다.',body:['직접 영상 주소와 원본 공개 상태는 아직 등록하지 않았습니다. 현재 버튼은 영상 재생이 아니라 패러블의 공개 안내로 연결됩니다.','방송 회차·타임스탬프는 원본을 직접 확인한 항목만 추가합니다. 검토판에 임의의 방송 기록이나 가짜 장면은 넣지 않았습니다.'],related:['smile-for-you','timestamp'],tone:'apricot'},
  {id:'replay-2025',kind:'event',title:'이세계페스티벌 2025 함께보기',subtitle:'Limited Streaming · 지난 활동',date:'2025-12-28',time:'20:00',members:all,sourceIds:['replay'],status:'verified',visibility:'published',tags:['행사','온라인','함께보기'],summary:'2025년 12월 28일 오후 8시로 공지된 함께보기 일정입니다.',body:['공식 공지에는 이세계아이돌 멤버 여섯 명과 우왁굳이 참여한다고 안내되어 있습니다.','과거에 공지된 일정의 기록입니다. 공지 확인과 실제 진행 여부 확인은 구분하며, 현재 재시청 또는 티켓 구매가 가능하다는 의미가 아닙니다.'],related:['setlist']},
  {id:'pepero-2025',kind:'event',title:'빼빼로 × 이세계아이돌',subtitle:'브랜드 협업 · 공식 출시 안내 기록',date:'2025-10-13',members:all,sourceIds:['pepero'],status:'verified',visibility:'published',tags:['협업','굿즈','출시'],summary:'2025년 10월 13일 공식 출시로 안내된 컬래버레이션 기록입니다.',body:['패러블의 공개 안내를 바탕으로 출시일과 협업명을 기록합니다.','현재 판매 여부, 재고, 거래 가격은 확인하지 않았으며 구매 가능하다고 안내하지 않습니다. 중고 거래·공동구매·모금 기능은 제공하지 않습니다.']},
  {id:'single',kind:'entry',title:'싱글',subtitle:'음악을 읽는 작은 사전',members:[],sourceIds:[],status:'editorial',visibility:'published',tags:['음악','입문'],summary:'이 사이트에서는 공식 발매 안내에 싱글로 표시된 음반을 이 분류로 묶습니다.',body:['사이트 내 분류를 설명하는 운영진 작성 문서입니다. 곡 하나와 음반 하나는 같지 않을 수 있으므로, 음반 상세에서 수록곡을 별도로 보여줍니다.'],related:['no-cat-no-life','stargazers']},
  {id:'cover',kind:'entry',title:'커버',subtitle:'음악을 읽는 작은 사전',members:[],sourceIds:[],status:'editorial',visibility:'published',tags:['음악','입문'],summary:'다른 곡을 가창한 공개 콘텐츠를 정식 발매 음반과 구별하기 위한 분류입니다.',body:['이 사이트의 편집 기준입니다. 영상 커버, 방송 중 가창, 정식 발매 리메이크를 서로 구별하며, 원곡 정보와 공개 원본이 확인되어야 등록합니다.'],related:['remake','white']},
  {id:'remake',kind:'entry',title:'리메이크',subtitle:'음악을 읽는 작은 사전',members:[],sourceIds:[],status:'editorial',visibility:'published',tags:['음악','입문'],summary:'기존 곡을 새롭게 해석해 발표한 경우, 공식 발매 안내의 표현을 따라 분류합니다.',body:['사이트 내 분류 안내입니다. 일반 커버 영상과 정식 발매된 리메이크 음반을 구별합니다. 예시 음반의 근거는 해당 상세 페이지에서 확인할 수 있습니다.'],related:['white','cover']},
  {id:'timestamp',kind:'entry',title:'타임스탬프',subtitle:'방송 기록을 읽는 작은 사전',members:[],sourceIds:[],status:'editorial',visibility:'published',tags:['방송','영상','입문','타임코드'],summary:'원본 영상에서 특정 장면이 시작되는 시간 위치입니다.',body:['타임스탬프에는 원본 주소와 확인 시점을 함께 기록하도록 설계했습니다. 원본 삭제·편집으로 위치가 달라지면 다시 검수합니다.','아직 장면 단위로 검수된 방송은 없습니다. 이 문서는 기능 설명이며 실제 방송의 장면 기록이 아닙니다.'],related:['smile-special-clip']},
  {id:'setlist',kind:'entry',title:'세트리스트',subtitle:'공연 기록을 읽는 작은 사전',members:[],sourceIds:[],status:'editorial',visibility:'published',tags:['공연','음악','입문'],summary:'공연에서 선보인 곡과 그 순서를 정리하는 목록입니다.',body:['공식 공개 자료 또는 검수 가능한 공개 근거가 있는 경우에만 등록합니다. 팬 제보는 검수 전까지 사실로 공개하지 않습니다.'],related:['stargazers']},
  {id:'getting-started',kind:'guide',title:'처음 만나는 이세계아이돌',subtitle:'세 단계로 시작하는 아카이브',members:[],sourceIds:['network','discography'],status:'editorial',visibility:'published',tags:['입문','멤버','음악'],summary:'여섯 멤버를 알아보고, 공개 음악에서 관심 있는 기록으로 이어가세요.',body:['첫 번째, 입문·멤버에서 여섯 멤버와 연결된 음악을 살펴보세요.','두 번째, 음악에서 음반 정보와 수록곡을 읽고 공식 안내로 이동하세요.','세 번째, 낯선 표현은 사전에서 찾아보세요. 이 입문 순서는 운영진의 제안이며 공식 추천이 아닙니다.'],related:['ine','jingburger','lilpa','jururu','gosegu','viichan']},
  {id:'fan-policy',kind:'guide',title:'함께 지키는 팬 콘텐츠 기준',subtitle:'공식 원문을 먼저 확인하세요',members:[],sourceIds:['policy'],status:'editorial',visibility:'published',tags:['가이드','저작권','비공식','패러블'],summary:'비공식 표시, 공개 출처, 권리 존중을 기본으로 운영합니다.',body:['사이트는 팬이 제작·운영하는 비공식 프로젝트이며 아티스트나 패러블의 승인·후원·협찬과 관계없습니다.','광고·유료 회원·모금·상품 판매를 제공하지 않습니다. 원본 영상·음원·가사 전문·무허가 이미지를 복제하지 않습니다.','사생활, 미공개 일정, 추측성 정보를 게시하지 않습니다. 수정·중단 요청에 대응하기 위한 신고 창구를 마련합니다.','이는 사이트의 운영 방침과 공식 가이드의 요약입니다. 개별 자료 이용허락을 대신하지 않으며 최신 원문이 우선합니다.'],related:['official-source']},
  {id:'official-source',kind:'guide',title:'출처와 검수 상태 읽기',subtitle:'무엇을 확인했고, 무엇을 모르는지',members:[],sourceIds:[],status:'editorial',visibility:'published',tags:['출처','검수','정정'],summary:'공식 출처가 있는 사실과 운영진이 작성한 설명을 구분합니다.',body:['공식 출처 배지는 사이트의 공식 인증을 뜻하지 않습니다. 본문 사실에 연결된 출처가 공식 발표라는 의미입니다.','운영진 작성 배지는 분류·이용 안내처럼 사이트에서 직접 작성한 설명에 붙입니다.','마지막 확인일은 자동 갱신일이 아닙니다. 이후 원문이 변경될 수 있으며, 현재 등록 목록이 전체 활동을 포괄한다고 주장하지 않습니다.','제보는 GitHub의 공개 이슈로 접수합니다. 개인정보나 비공개 자료는 올리지 마세요. 검수되지 않은 제보는 사이트에 자동 반영되지 않습니다.'],related:['fan-policy']}
];
export const NAV = [
  {id:'home',name:'오늘의 이세돌',icon:'home',en:'TODAY'},
  {id:'members',name:'입문·멤버',icon:'users',en:'MEMBERS'},
  {id:'schedule',name:'소식·일정',icon:'calendar',en:'SCHEDULE'},
  {id:'music',name:'음악',icon:'music',en:'DISCOGRAPHY'},
  {id:'videos',name:'방송·영상',icon:'video',en:'ON AIR & VIDEO'},
  {id:'dictionary',name:'이세돌 사전',icon:'book',en:'DICTIONARY'},
  {id:'history',name:'활동 기록',icon:'clock',en:'TIMELINE'},
  {id:'guide',name:'팬 가이드',icon:'shield',en:'FAN GUIDE'}
];
export const KIND_LABELS = {member:'멤버',music:'음악',video:'방송·영상',event:'활동 기록',entry:'사전',guide:'팬 가이드'};
