// Activity facts are a curated snapshot of visuals/history.json and
// catalog/album-releases.json. Dialogue, geography and combat are fan fiction.
export const CONTENT = {
  title: '이파리 연대기', subtitle: '마지막 앙코르',
  fictionNotice: '공개 활동 기록에서 출발한 비공식 팬 창작 RPG입니다. 인물의 대사·모험·전투는 창작이며 실제 발언이나 사건이 아닙니다.',
  playtime: '첫 모험 40–50분 목표 · 자유 탐험 포함 1시간 이내 목표',
  prologue: [
    '상자를 정리하던 이파리는 날짜가 지워진 오래된 공연 티켓을 발견했다. 뒷면에는 작은 문장이 남아 있었다. “마지막 앙코르에서 만나요.”',
    '티켓을 펼치자 방바닥 위로 낯선 길이 이어졌다. 한쪽에는 작은 첫 무대, 다른 쪽에는 아직 불이 꺼진 거대한 공연장. 그 사이에 여섯 해의 풍경이 접혀 있었다.',
    '이 모험의 주인공은 당신, 이파리다. 여섯 멤버와 기록의 길을 복원하고, 마지막 무대의 시험관에게 도전하자.',
    '방향키·WASD 또는 화면 방향 버튼으로 이동한다. 물건과 인물 옆에서 상호작용한다. 전투는 차례를 기다려 주므로 적의 다음 행동을 읽고 천천히 선택하자. 장면마다 이 기기에 자동 저장된다.'
  ],
  ending: [
    '시험관이 옆으로 한 발 물러섰다. “이 길을 끝까지 걸어왔네. 이제 네 자리로 가 봐.”',
    '징버거가 첫 조명을 켜고, 아이네가 얼어 있던 길을 녹였다. 주르르가 닫힌 페이지를 펼쳤고, 릴파가 마지막 문을 받쳤다. 비챤이 흩어진 박자를 연결하자 고세구가 티켓을 올바른 방향으로 뒤집었다.',
    '처음의 작은 무대부터 숲, 책 속 도시와 긴 계단까지. 걸어온 길이 객석을 둘러싼 하나의 공연장이 되었다.',
    '이파리는 검 대신 응원봉을 들었다. 무대 위에는 여섯 멤버, 객석에는 함께 기다린 사람들. 마지막 앙코르의 마지막 한 조각은 처음부터 당신의 자리였다.',
    '티켓 뒷면에 날짜 대신 새 문장이 나타났다. “다음 페이지에서도, 함께.”'
  ]
};

export const MEMBERS = {
  jingburger: { id: 'jingburger', name: '징버거', color: '#f7cc69', skill: { name: '첫 불빛', cost: 2, description: '방어를 뚫고 공격력의 2.3배 피해. 첫 무대에서 받은 용기.' }, ending: '첫 조명을 밝혀 앙코르의 시작을 연다.' },
  ine: { id: 'ine', name: '아이네', color: '#bca1e5', skill: { name: '봄의 숨', cost: 2, description: '최대 체력의 36% 회복하고 이번 적 공격을 약화한다.' }, ending: '얼어 있던 객석의 시간을 녹인다.' },
  jururu: { id: 'jururu', name: '주르르', color: '#f3a8bd', skill: { name: '진짜 페이지', cost: 2, description: '환영과 방어를 무시해 피해. 다음 두 번의 공격도 방어를 무시한다.' }, ending: '여섯 해의 페이지를 하나의 이야기로 펼친다.' },
  lilpa: { id: 'lilpa', name: '릴파', color: '#819ae6', skill: { name: '무대의 날개', cost: 2, description: '이번 적 공격을 85% 막고 피해를 준다. 다음 공격력이 크게 오른다.' }, ending: '마지막 무대의 문이 닫히지 않도록 날개를 편다.' },
  viichan: { id: 'viichan', name: '비챤', color: '#a9d384', skill: { name: '초록 연결', cost: 2, description: '두 번 연속 공격하고 응원 1 회복. 연계 규칙의 빈틈을 연다.' }, ending: '멀리 떨어진 객석의 박자를 한데 잇는다.' },
  gosegu: { id: 'gosegu', name: '고세구', color: '#87cee5', skill: { name: '규칙 뒤집기', cost: 2, description: '피해를 주고 이번 적 공격을 취소한다. 뒤집힌 방어도 해제한다.' }, ending: '티켓을 뒤집어 이파리가 앉을 자리를 찾아낸다.' }
};

export const UPGRADES = [
  { id: 'heart', name: '단단한 마음', description: '최대 체력 +24. 긴 전투에서 여유 있게 버틴다.' },
  { id: 'spark', name: '선명한 불빛', description: '공격력 +3. 기본 공격과 모든 공격 지원기가 강해진다.' },
  { id: 'bond', name: '함께하는 박자', description: '응원 행동으로 얻는 응원 +1, 응원 최대치 +1.' }
];

const GROUP = 'https://namu.wiki/w/이세계아이돌';
const DISCO = `${GROUP}/디스코그래피`;
const EVENTS = `${GROUP}/공연%20및%20행사`;
function fact(id, date, title, text, url, sourceTitle = '활동 기록의 출처') {
  return { id, date, title, text, url, sourceTitle, type: 'fact' };
}
const MAPS = [
  ['###############','#.............#','#...##....##..#','#.............#','#.............#','#.............#','#..##....##...#','#.............#','###############'],
  ['###############','#.............#','#.....#.......#','#.....#.......#','#.............#','#.............#','#.....#.......#','#.............#','###############'],
  ['###############','#.............#','#..#.......#..#','#.............#','#.............#','#.............#','#..#.......#..#','#.............#','###############']
];
export const LEGACY_MAPS = MAPS;
// Hand-authored scenery layouts: a clear central aisle remains in every room.
// These change exploration shapes without padding the journey with forced walks.
const CHAPTER_WALLS = {
  'winter-spring': [[[4,2],[4,3],[4,5],[4,6],[10,2],[10,3],[10,5],[10,6]],[[6,2],[6,3],[7,3],[7,5],[8,5],[8,6]],[[3,2],[3,3],[3,5],[3,6],[11,2],[11,3],[11,5],[11,6]]],
  'paper-city': [[[2,3],[3,3],[4,3],[9,5],[10,5],[11,5]],[[5,2],[6,2],[7,2],[7,6],[8,6],[9,6]],[[2,2],[3,2],[4,2],[10,6],[11,6],[12,6]]],
  'going-out': [[[5,2],[6,2],[8,2],[9,2],[3,6],[4,6],[10,6],[11,6]],[[4,2],[4,3],[4,5],[4,6],[12,2],[12,3],[12,5],[12,6]],[[5,3],[6,3],[8,3],[9,3],[5,5],[6,5],[8,5],[9,5]]],
  'together': [[[6,2],[7,2],[8,2],[4,3],[10,3],[4,5],[10,5],[6,6],[7,6],[8,6]],[[6,3],[7,2],[8,3],[6,5],[7,6],[8,5]],[[6,2],[7,2],[8,2],[3,3],[11,3],[3,5],[11,5],[6,6],[7,6],[8,6]]],
  'next-page': [[[4,2],[4,3],[6,5],[6,6],[9,2],[9,3],[11,5],[11,6]],[[4,2],[4,3],[6,5],[6,6],[10,2],[10,3],[12,5],[12,6]],[[3,2],[3,3],[6,5],[6,6],[9,2],[9,3],[12,5],[12,6]]]
};
function roomTiles(chapter, index) {
  const walls = CHAPTER_WALLS[chapter.id]?.[index];
  if (!walls) return MAPS[index];
  const rows = Array.from({length:9}, (_, y) => Array.from({length:15}, (_, x) => x === 0 || x === 14 || y === 0 || y === 8 ? '#' : '.'));
  for (const [x,y] of walls) rows[y][x] = '#';
  return rows.map(row => row.join(''));
}
function object(id, type, name, x, y, icon, description = '', extra = {}) { return { id, type, name, x, y, icon, description, ...extra }; }
function rooms(chapter) {
  const p = chapter.puzzle;
  return [
    { id: `${chapter.id}-arrival`, title: chapter.locations[0], description: chapter.atmosphere[0], tiles: roomTiles(chapter, 0), objects: [
      object('member', 'member', MEMBERS[chapter.member].name, 7, 4, '✦', '함께 길을 열 동료.', { member: chapter.member }),
      object('record-0', 'record', '시간의 기록', 3, 2, '▤', chapter.facts[0].title),
      object('rest', 'rest', '이파리 쉼터', 5, 6, '♧', '체력과 응원을 채운다.'),
      object('memory', 'memory', chapter.memories[0].title, 12, 2, '◇', chapter.memories[0].lines[0]),
      object('forward', 'portal', '다음 장소', 13, 4, '→', chapter.locations[1])
    ] },
    { id: `${chapter.id}-puzzle`, title: chapter.locations[1], description: chapter.atmosphere[1], tiles: roomTiles(chapter, 1), objects: [
      object('back', 'portal', '이전 장소', 1, 4, '←', chapter.locations[0]),
      object('clue', 'clue', p.clueTitle, 3, 2, '≡', p.clue.join(' ')),
      ...p.controls.map((c, i) => object(`control-${i}`, 'puzzle', c.name, [5, 9, 11][i], [3, 2, 6][i], c.icon || '○', c.description, { control: i })),
      object('guardian', 'battle', chapter.encounters[0].name, 10, 4, '⚔', chapter.encounters[0].description, { encounter: 0 }),
      object('memory', 'memory', chapter.memories[1].title, 3, 6, '◇', chapter.memories[1].lines[0]),
      object('forward', 'portal', '기록의 문', 13, 4, '→', chapter.locations[2])
    ] },
    { id: `${chapter.id}-stage`, title: chapter.locations[2], description: chapter.atmosphere[2], tiles: roomTiles(chapter, 2), objects: [
      object('back', 'portal', '이전 장소', 1, 4, '←', chapter.locations[1]),
      object('record-1', 'record', '이어지는 기록', 5, 2, '▤', chapter.facts[1].title),
      object('rest', 'rest', '무대 앞 쉼터', 4, 6, '♧', '보스 전에 체력과 응원을 채운다.'),
      object('boss', 'battle', chapter.encounters[1].name, 10, 4, '⚔', chapter.encounters[1].description, { encounter: 1 }),
      object('exit', 'exit', '다음 해로', 13, 4, '✧', '이 장을 마치고 기록의 길을 잇는다.')
    ] }
  ];
}
const chapters = [
  {
    id: 'first-light', year: '2021', title: '처음 켜진 무대', member: 'jingburger', theme: 'amber',
    locations: ['티켓의 골목', '꺼진 조명실', '첫 번째 객석'],
    atmosphere: ['낡은 포스터 사이로 여섯 개의 불빛이 새어 나온다. 아직 아무도 앉지 않은 객석이 첫 손님을 기다린다.', '전선이 매듭처럼 엉켜 있다. 문을 열려면 조명의 순서를 복원하고 소음 요정을 달래야 한다.', '작은 무대의 커튼이 흔들린다. 시작을 두려워하는 그림자가 마지막 불빛을 감추었다.'],
    intro: ['너도 그 티켓을 따라왔구나. 저 조명이 켜져야 첫 무대가 시작된대.', '여기에서는 기록이 길이 돼. 먼저 손을 내밀고, 같이 준비하고, 그다음에 무대에 오르는 거야. 조명실의 메모를 읽어 봐.', '내가 첫 불빛을 빌려줄게. 응원 2로 방어를 뚫는 지원기를 쓸 수 있어. 하지만 길을 걷는 건 너야, 이파리!'],
    outro: ['무대는 작아도 불빛은 충분히 멀리 닿네.', '처음의 티켓에 한 줄이 새겨졌다. “모든 긴 여정에도, 처음 함께 켠 불빛이 있다.”'],
    facts: [fact('event-2021-08-26-5', '2021-08-26', '여섯 멤버 최종 선발 · 그룹 결성', '아이네·징버거·릴파·주르르·고세구·비챤이 최종 멤버로 선정되었다.', GROUP, '나무위키 · 이세계아이돌'), fact('event-2021-12-17-41', '2021-12-17', 'RE : WIND 발매 · 정식 데뷔', '이세계아이돌의 그룹 데뷔 싱글. 이 장의 무대와 조명 이야기는 이 기록에서 출발한 창작이다.', DISCO, '나무위키 · 디스코그래피')],
    memories: [{ title: '첫 관객의 쪽지', lines: ['“첫 공연이라 길을 헤맬까 봐 일찍 왔어요.” 접힌 쪽지 아래에는 객석 배치도가 그려져 있다.', '텅 빈 줄 알았던 객석에도 누군가는 벌써 마음을 놓아두었다.'] }, { title: '공구 상자', lines: ['상자에는 서로 다른 색의 장갑 여섯 켤레가 있다.', '무대의 빛은 한 사람의 손으로만 켜지지 않는다는 것을, 작은 흔적들이 알려준다.'] }],
    puzzle: { kind: 'sequence', title: '세 번의 시작', clueTitle: '무대 감독의 메모', clue: ['불빛은 “모집 → 함께 준비 → 첫 무대”의 순서로 켠다.', '시작 버튼을 잘못 누르면 순서만 초기화된다. 정답 날짜를 외울 필요는 없다.'], controls: [{ name: '모집 조명', description: '첫걸음을 내딛는 주황빛.' }, { name: '준비 조명', description: '여섯 갈래로 나뉘는 노란빛.' }, { name: '무대 조명', description: '객석으로 향하는 흰빛.' }], solution: [0, 1, 2] },
    encounters: [{ name: '소음 요정', description: '공격 예고를 배우는 첫 상대. 크게 숨을 들이쉬면 방어하자.', mechanic: 'plain' }, { name: '막 오른 그림자', description: '막으로 몸을 감싼 동안은 첫 불빛이 방어를 뚫는다.', mechanic: 'armor' }]
  },
  {
    id: 'winter-spring', year: '2022', title: '겨울을 건너는 숲', member: 'ine', theme: 'lavender',
    locations: ['서리 내린 입구', '두 계절의 정원', '해빙의 연못'],
    atmosphere: ['나무 아래에는 아직 녹지 않은 눈과 막 돋아난 새싹이 나란히 있다.', '물길과 얼음길이 교차한다. 모든 것을 봄으로 바꾼다고 길이 열리는 것은 아니다.', '연못의 얼음 속에서 오래된 종소리가 들린다. 수호자가 겨울의 마지막 잠을 지킨다.'],
    intro: ['추웠던 시간이 없어져야 봄이 오는 건 아닌가 봐. 봐, 눈 옆에서도 새싹이 자라고 있어.', '정원의 세 표지판에 알맞은 계절을 골라 줘. 얼음 다리는 겨울에만, 씨앗과 물레는 봄에만 힘을 내.', '내 봄의 숨은 체력을 회복해 줘. 응원을 모아 두면 조금 어려운 길에서도 다시 걸을 수 있을 거야.'],
    outro: ['겨울의 길도, 봄의 길도 다 지나왔구나.', '티켓에 작은 잎맥이 생겼다. “기다린 시간도 길의 일부였다.”'],
    facts: [fact('event-2022-03-11-42', '2022-03-11', '겨울봄 발매', '이세계아이돌의 그룹 싱글 겨울봄이 발매되었다.', DISCO, '나무위키 · 디스코그래피'), fact('event-2022-08-10-8', '2022-08-10', '공식 웹툰 제작 계획 공개', '웹툰 제작 계획과 관련 공모전이 공개되었다. 이 시점은 연재 시작과 구분된다.', GROUP, '나무위키 · 이세계아이돌')],
    memories: [{ title: '녹지 않는 눈사람', lines: ['눈사람의 목도리에 작은 새싹 자수가 있다.', '누군가 겨울에도 봄을 기억해 두었다.'] }, { title: '먼 도시의 엽서', lines: ['엽서 속 도시는 건물 대신 책등으로 이루어져 있다.', '“이야기가 곧 길이 됩니다.” 다음 해로 향하는 인사처럼 보인다.'] }],
    puzzle: { kind: 'seasons', title: '겨울과 봄 사이', clueTitle: '정원사의 계절 표', clue: ['얼음 다리는 겨울, 잠든 씨앗은 봄, 멈춘 물레도 봄.', '각 장치의 계절을 골라 세 곳을 동시에 연결하자.'], controls: [{ name: '얼음 다리', description: '녹으면 건널 수 없는 짧은 다리.' }, { name: '잠든 씨앗', description: '햇살을 기다리는 씨앗.' }, { name: '멈춘 물레', description: '흐르는 물이 필요한 물레.' }], solution: ['winter', 'spring', 'spring'] },
    encounters: [{ name: '서리 방울', description: '결빙 예고 뒤에는 큰 공격. 방어하면 체력 손실을 줄인다.', mechanic: 'frost' }, { name: '얼어붙은 수호자', description: '결빙 다음의 해빙 순간은 공격 기회다.', mechanic: 'frost' }]
  },
  {
    id: 'paper-city', year: '2023', title: '책 너머의 도시', member: 'jururu', theme: 'rose',
    locations: ['책등 광장', '두 겹의 거리', '빈 페이지 극장'],
    atmosphere: ['책장을 넘기는 소리가 바람을 대신한다. 서로 다른 이야기의 문들이 같은 광장으로 통한다.', '거리는 현실과 이야기 두 겹으로 포개져 있다. 같은 표지판도 어느 쪽에서 읽느냐에 따라 다르다.', '비어 있는 마지막 칸에 그림자 배우가 서 있다. 진짜 문장은 늘 같은 자리에 남아 있다.'],
    intro: ['책 속 길은 보기보다 조금 장난꾸러기야. 현실 쪽에서 찾은 문장이 이야기 쪽에서는 열쇠가 되거든.', '두 거리의 단서를 읽고 “이야기 → 노래 → 만남”으로 페이지를 묶어 봐. 두 겹 스위치로 거리의 면을 바꿀 수 있어.', '진짜 페이지는 환영과 방어를 걷어 줘. 적이 자신을 숨기면 내 지원기를 써 봐.'],
    outro: ['네가 빈 칸을 걸어서 채웠네. 이파리도 이제 이 이야기의 등장인물이야.', '티켓에 책갈피가 묶였다. “다른 세계의 이야기도 같은 노래로 만났다.”'],
    facts: [fact('event-2023-06-22-12', '2023-06-22', '마법소녀 이세계아이돌 연재 시작', '공식 웹툰이 카카오웹툰·카카오페이지에서 연재를 시작했다. 같은 날 관련 OST도 발매되었다.', GROUP, '나무위키 · 이세계아이돌'), fact('event-2023-08-18-43', '2023-08-18', 'KIDDING 발매', '2023년에는 두 공식 웹툰의 연재와 OST, 그룹 싱글 KIDDING 등 서로 다른 매체의 활동이 이어졌다.', DISCO, '나무위키 · 디스코그래피')],
    memories: [{ title: '빈 말풍선', lines: ['말풍선 안에는 아직 대사가 없다.', '이파리는 작은 글씨로 “잘 보고 있어요”라고 적었다. 말풍선의 테두리가 조금 밝아졌다.'] }, { title: '접힌 종이배', lines: ['종이배는 책장을 바다처럼 건넌다.', '그 위에 놓인 세 글자: “계속 가.”'] }],
    puzzle: { kind: 'layers', title: '세 장의 제본', clueTitle: '도시의 제본 규칙', clue: ['현실에서 “이야기”와 “만남”을, 이야기 속에서 “노래”를 찾을 수 있다.', '두 겹 스위치로 전환하고 페이지 보관함에서 “이야기 → 노래 → 만남” 순서로 꺼낸다.'], controls: [{ name: '두 겹 스위치', description: '현실 / 이야기 거리를 전환한다.' }, { name: '페이지 보관함', description: '현재 거리에서 발견한 페이지를 꺼낸다.' }, { name: '제본대', description: '모은 세 페이지를 순서대로 묶는다.' }], solution: ['story', 'song', 'meeting'] },
    encounters: [{ name: '잉크 번짐', description: '환영 상태에서는 일반 공격이 약해진다. 진짜 페이지로 드러내자.', mechanic: 'illusion' }, { name: '빈칸의 배우', description: '환영·큰 공격·빈틈이 반복된다. 책을 읽듯 다음 행동을 보자.', mechanic: 'illusion' }]
  },
  {
    id: 'going-out', year: '2024', title: '무대 밖으로', member: 'lilpa', theme: 'blue',
    locations: ['밤의 계단', '날개 달린 기계실', '밖으로 열린 무대'],
    atmosphere: ['길고 가파른 계단 끝에 문 하나가 있다. 문틈 너머로 실제 객석처럼 넓은 빛이 흐른다.', '왼쪽과 가운데, 오른쪽 날개가 서로 맞물려 움직인다. 하나를 바꾸면 옆 날개도 돌아간다.', '무대의 바람이 세차다. 오래된 문지기는 한 번 버틴 사람에게만 길을 내준다.'],
    intro: ['화면 너머로 가는 길이 이렇게 긴 계단이었다니. 그래도 여기까지 왔잖아.', '기계실의 날개 셋을 모두 펼쳐야 문이 열려. 왼쪽 손잡이는 왼쪽과 가운데를, 가운데는 셋 모두를, 오른쪽은 가운데와 오른쪽을 움직여.', '큰 공격 앞에서는 내 무대의 날개를 펼쳐 봐. 버틴 뒤의 반격이 더 강해질 거야.'],
    outro: ['문 밖에도 우리가 함께 설 자리가 있네.', '티켓에 날개 문양이 새겨졌다. “한 번 버티고, 더 넓은 곳으로.”'],
    facts: [fact('event-2024-02-16-18', '2024-02-16 ~ 02-29', '이세돌팝업봤? 팝업스토어', '더현대 서울에서 이세계아이돌 팝업스토어가 열렸다.', EVENTS, '나무위키 · 공연 및 행사'), fact('event-2024-07-12-19', '2024-07-12 ~ 07-13', 'LILPACON : Going Out', '경희대학교 평화의전당에서 열린 릴파의 단독 오프라인 콘서트. 날짜는 공연 종료 보도를 따른다.', 'https://news.nate.com/view/20240716n27591', 'YTN · 릴파 단독 콘서트 종료 보도')],
    memories: [{ title: '계단의 스티커', lines: ['계단 한 칸마다 작은 응원 스티커가 붙어 있다.', '힘들면 한 칸씩. 이파리는 가장 가까운 불빛부터 바라보기로 했다.'] }, { title: '무대 뒤 작업표', lines: ['무대 뒤 작업표에는 조명, 소리, 문, 계단의 점검 표시가 가득하다.', '보이는 순간을 위해 보이지 않는 시간이 쌓여 있었다.'] }],
    puzzle: { kind: 'wings', title: '세 날개의 균형', clueTitle: '기계실 설명서', clue: ['왼쪽 손잡이 = 왼쪽·가운데 반전. 가운데 = 셋 모두 반전. 오른쪽 = 가운데·오른쪽 반전.', '세 날개가 모두 펼쳐지면 통과. 현재는 가운데 날개만 펼쳐져 있다. 막히면 날개를 초기화할 수 있다.'], controls: [{ name: '왼쪽 날개', description: '왼쪽과 가운데를 뒤집는다.' }, { name: '가운데 날개', description: '세 날개를 모두 뒤집는다.' }, { name: '오른쪽 날개', description: '가운데와 오른쪽을 뒤집는다.' }], solution: [true, true, true] },
    encounters: [{ name: '계단의 돌풍', description: '큰 공격을 막은 다음에는 반격 기회가 온다.', mechanic: 'storm' }, { name: '문턱의 파수꾼', description: '무대의 날개로 버틴 뒤 강화된 공격을 연결해 보자.', mechanic: 'storm' }]
  },
  {
    id: 'together', year: '2025', title: '함께 서는 곳', member: 'viichan', theme: 'green',
    locations: ['빛의 환승역', '객석의 연결로', '별을 담은 돔'],
    atmosphere: ['가상의 공간에서 출발한 길과 큰 공연장으로 향하는 길이 이 역에서 만난다.', '흩어진 응원 신호가 세 중계기를 찾는다. 서로 다른 역할을 이어 하나의 무대로 보내자.', '커다란 돔 안에 작은 불빛이 가득하다. 혼자서는 닿지 않는 거리도 함께하면 연결된다.'],
    intro: ['여기서는 멀리 있어도 박자를 맞출 수 있대. 보이지 않는 선이 우리를 연결하는 것처럼.', '세 중계기에 알맞은 역할을 놓자. 시작은 보호, 중간은 회복, 마지막은 돌파. 각 역할은 한 번씩만 쓸 수 있어.', '초록 연결은 두 번 공격하고 응원 하나를 돌려줘. 다른 행동 다음에 연결하면 연계 수호자의 빈틈도 열릴 거야.'],
    outro: ['작은 응원들이 모이니까 이렇게 넓어졌네.', '티켓에 여섯 빛을 잇는 선이 생겼다. “함께 서는 곳에는 거리가 없다.”'],
    facts: [fact('event-2025-03-03-30', '2025-03-03', '젠레스 존 제로 OST 콘서트 참여', '주르르·비챤이 VRChat에서 진행된 OST 콘서트에 참여했다. 그룹 전원 활동과 구분되는 기록이다.', EVENTS, '나무위키 · 공연 및 행사'), fact('event-2025-05-16-32', '2025-05-16 ~ 05-17', '이세계 페스티벌 2025 출연', '고척 스카이돔에서 이세계아이돌이 출연한 날짜. 전체 행사 기간과 구분된다. Stargazers·ELEVATE·MEMORY를 선공개했다.', EVENTS, '나무위키 · 공연 및 행사')],
    memories: [{ title: '멀리서 온 표', lines: ['표에는 서로 다른 도시의 이름이 적혀 있다.', '누군가의 긴 이동도 여기에서는 한 줄의 빛이 되었다.'] }, { title: '꺼지지 않는 응원봉', lines: ['작은 응원봉의 불빛이 중계기를 따라 건너편까지 전해진다.', '내 응원이 정말 닿을까 생각했던 날들이 문득 떠올랐다.'] }],
    puzzle: { kind: 'relay', title: '세 역할의 연결', clueTitle: '중계 기사 안내', clue: ['시작 중계기는 보호, 중간은 회복, 마지막은 돌파 역할을 받아야 한다.', '같은 역할을 다른 곳에 놓으면 이전 중계기에서 빠진다. 셋을 서로 다르게 연결하자.'], controls: [{ name: '시작 중계기', description: '신호를 처음 지켜 주는 자리.' }, { name: '중간 중계기', description: '지친 신호를 다시 채우는 자리.' }, { name: '마지막 중계기', description: '막힌 곳을 뚫고 객석으로 보내는 자리.' }], solution: ['guard', 'heal', 'break'] },
    encounters: [{ name: '끊어진 신호', description: '같은 공격을 반복하면 저항한다. 공격과 지원기를 바꾸어 써 보자.', mechanic: 'relay' }, { name: '거리의 수호자', description: '다른 행동을 이어 쓰면 연결이 생기고 큰 피해를 줄 수 있다.', mechanic: 'relay' }]
  },
  {
    id: 'next-page', year: '2026', title: '다음 페이지', member: 'gosegu', theme: 'cyan',
    locations: ['고양이의 갈림길', '뒤집힌 표지판 골목', '차원의 승강장'],
    atmosphere: ['고양이 발자국이 벽을 따라 거꾸로 나 있다. 지도 바깥에도 길이 있는 모양이다.', '표지판은 거꾸로 읽어야 한다. 익숙한 방향을 잠깐 내려놓고 새로운 규칙을 따라가자.', '여섯 해의 길이 한 장의 티켓 안으로 모인다. 이제 마지막 앙코르로 향할 시간이다.'],
    intro: ['어? 티켓 거꾸로 들었잖아. 아니, 여기서는 그게 맞을지도?', '이 골목은 표지판의 반대가 답이래. 해가 보이면 달, 왼쪽이면 오른쪽, 아래면 위! 안내를 읽고 세 표지를 뒤집어 봐.', '규칙 뒤집기는 적의 이번 행동도 멈추게 해. 마지막 시험 전에 나랑 확실히 연습하고 가자!'],
    outro: ['새 페이지는 우리가 아직 걷지 않은 쪽에 있었네.', '티켓의 마지막 빈칸이 빛났다. “처음부터 끝까지, 주인공은 이파리.”'],
    facts: [fact('event-2026-09-28-55', '2026-09-28', 'NO CAT, NO LIFE! 발매', '고세구의 솔로 음반. 그룹 전원의 음반으로 표시하지 않는다.', 'https://parable-asia.com/portfolio-item/no-cat-no-life/', '패러블 · NO CAT, NO LIFE!'), fact('across-dimensions', '2026-11-09', 'Across Dimensions 발매', '이세계아이돌의 두 번째 미니 앨범. 기존 앨범 카탈로그의 검증된 발매 기록을 반영했다.', 'https://www.melon.com/album/detail.htm?albumId=15120216', '멜론 · Across Dimensions')],
    memories: [{ title: '고양이 발자국', lines: ['발자국이 갑자기 벽으로 올라간다. 이파리는 잠시 고민하다 옆의 평범한 계단을 발견했다.', '모든 길을 똑같이 걸을 필요는 없었다.'] }, { title: '아직 쓰지 않은 포스터', lines: ['포스터의 제목 자리가 비어 있다.', '지난 기록을 다 지나와도 다음 이야기는 아직 남아 있다.'] }],
    puzzle: { kind: 'reverse', title: '반대편의 이정표', clueTitle: '고양이 안내문', clue: ['이 골목에서는 표지판과 반대인 답을 선택한다.', '해 표지 → 달. 왼쪽 표지 → 오른쪽. 아래 표지 → 위. 정답 세 개를 모두 맞추면 길이 열린다.'], controls: [{ name: '해 표지', description: '환한 해가 그려진 표지.' }, { name: '왼쪽 표지', description: '왼쪽을 가리키는 화살표.' }, { name: '아래 표지', description: '아래를 가리키는 화살표.' }], solution: ['moon', 'right', 'up'] },
    encounters: [{ name: '뒤집힌 경비', description: '공격 저항을 뒤집기 기술로 해제하고 적의 행동을 멈추자.', mechanic: 'reverse' }, { name: '차원의 고양이', description: '고세구의 규칙 뒤집기로 마지막 모험의 준비를 마친다.', mechanic: 'reverse' }]
  }
];

// Hints are offered through the player's optional help switch; the normal clue
// teaches a rule and leaves the player to apply it to the nearby objects.
const puzzleClues = [
  ['어떤 시작이든 사람을 모은 다음 함께 준비하고, 준비가 끝나야 관객을 맞는다.', '세 조명은 차례로 켜야 한다. 어긋나면 불빛 순서만 초기화된다.'],
  ['얼음은 추울 때 길을 만들고, 씨앗은 따뜻할 때 자란다.', '물레는 얼어붙은 물로 돌릴 수 없다. 세 곳에 알맞은 계절을 동시에 놓자.'],
  ['이야기가 시작되고 노래가 들리면, 마지막에 서로 만나게 된다.', '현실 거리에는 이야기와 만남이, 이야기 거리에는 노래가 있다. 페이지를 모아 제본대로 가져가자.'],
  ['왼쪽 손잡이는 왼쪽·가운데, 가운데는 셋 모두, 오른쪽은 가운데·오른쪽을 뒤집는다.', '현재 가운데만 펼쳐져 있다. 셋 모두 펼치면 통과. 같은 손잡이를 두 번 움직이면 원래대로 돌아온다.'],
  ['첫 중계기는 신호가 다치지 않게 지키고, 중간은 지친 신호를 다시 채운다.', '마지막은 막힌 벽을 깨고 객석에 닿아야 한다. 각 역할을 한 번씩만 배치하자.'],
  ['고양이는 모든 표지판의 반대편으로 걸어갔다.', '해의 반대, 왼쪽의 반대, 아래의 반대. 세 표지가 모두 고양이의 길을 가리켜야 한다.']
];
const puzzleHints = ['모집 조명 → 준비 조명 → 무대 조명.', '얼음 다리: 겨울 / 씨앗: 봄 / 물레: 봄.', '현실에서 이야기 → 이야기 거리에서 노래 → 현실에서 만남 → 제본대.', '처음 상태에서 왼쪽 손잡이, 오른쪽 손잡이를 한 번씩 움직인다.', '시작: 보호 / 중간: 회복 / 마지막: 돌파.', '해 표지는 달, 왼쪽 표지는 오른쪽, 아래 표지는 위.'];
export const CHAPTERS = chapters.map((chapter, index) => {
  const revised = { ...chapter, puzzle: { ...chapter.puzzle, clue: puzzleClues[index], hint: puzzleHints[index] } };
  return { ...revised, index, rooms: rooms(revised), encounters: chapter.encounters.map((e, i) => ({ ...e, id: `${chapter.id}-${i ? 'boss' : 'guardian'}`, maxHp: 140 + index * 45 + i * 70, attack: 10 + index * 3 + i * 3, boss: i === 1 })) };
});

export const FINALE = {
  id: 'encore', title: '마지막 앙코르', year: 'FINALE', theme: 'gold',
  room: { id: 'encore-gate', title: '마지막 객석의 문', description: '모든 길이 이곳에 이어졌다. 시험관 우왁굳이 여섯 불빛 앞에서 기다린다. 마지막 시험도 당신의 속도로 도전하면 된다.', tiles: MAPS[2], objects: [
    object('rest', 'rest', '앙코르 쉼터', 4, 6, '♧', '마지막 시험에 앞서 쉬어 간다.'),
    object('ensemble', 'ensemble', '여섯 동료', 6, 2, '✦', '함께 걸어온 동료들의 말을 듣는다.'),
    object('final-boss', 'battle', '우왁굳 · 최종 시험관', 10, 4, '⚔', '앞서 배운 방어, 연계, 지원을 확인하는 세 단계의 친선 시험.')
  ] },
  dialogue: ['여기까지 걸어온 게 너구나. 기록만 읽은 게 아니라 네 발로 길을 만들었네.', '마지막은 시험이야. 크게 휘두르면 막고, 규칙이 바뀌면 동료의 힘을 빌려. 혼자 증명할 필요는 없어.', '준비됐으면 시작하자. 저 문 너머에 네 자리가 있으니까.'],
  encounter: { id: 'final-trial', name: '우왁굳 · 최종 시험', maxHp: 330, attack: 24, boss: true, mechanic: 'final', description: '세 단계의 친선 시험. 단계마다 체력이 일부 회복된다.' },
  phases: ['첫 시험 · 버티는 용기', '두 번째 시험 · 달라지는 규칙', '마지막 시험 · 함께하는 앙코르']
};

export const ALL_FACTS = CHAPTERS.flatMap(chapter => chapter.facts);
