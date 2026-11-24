# 별빛 배송부 — 생성 이미지 프롬프트

## 배송부의 보행과 정지 자세

내장 ImageGen에 기존 `characters.png`를 의상·얼굴 참고 그림으로 전달했다. `motion/`의 멤버별 PNG에는 보행 네 장이, `motion/standing.png`에는 정지 자세 여섯 장이 들어 있다. Pillow를 설치한 환경에서 `python scripts/pack_courier_motion.py`를 실행하면 발 위치를 맞춘 `fangames/assets/walk.webp`와 `fangames/assets/standing.webp`를 다시 만들 수 있다.

### 보행 공통 프롬프트

Use case: identity-preserve. Create an actual transparent videogame walk-cycle spritesheet for the single courier identified below from the reference character inventory. Preserve that individual model, scale, costume, face, hairstyle and exquisite anime/chibi linework exactly. Deliver a SQUARE image with exactly four isolated full-body drawings of THE SAME PERSON in a regular 2-column x 2-row grid, one per square cell. View = right-facing side / slight 3/4 profile showing the near and far leg: face and nose towards screen RIGHT in ALL four frames. Strict animation consistency with only the step movement changing. The character is briskly walking carrying mail, arms swinging naturally. Row-major progression is a four-beat WALK CYCLE: top-left CONTACT, near leg straight far forward right (heel leads), far leg back left, near arm back. Top-right PASSING, near planted foot below hips and far bent knee coming through forward; legs visibly close under body. Bottom-left OPPOSITE CONTACT: far boot leads right, near boot trails back left, near arm swings ahead; show far leg partially obscured by near leg where anatomically appropriate. Bottom-right OPPOSITE PASSING: far planted leg central, near knee lifted coming through forward and bent near elbow back, returning to first pose. Big readable differences in knees/elbows and boots, subtle matching hair and cape drag. Absolutely no cloned identical running poses. Four stable heads, no angle changes. All standing scale, center, and ground line identical within their cell; whole figure 82% of cell height, clear alpha gutters around each including hair, feet, ribbons, and letter, no cell overlap. Clean dark fine outlines. Only four cutout drawings, genuinely transparent alpha; no shadows, no floor, no backplates, no text, no borders, no symbols, no motion lines. Reference shows six people; ignore the other five. Character to draw four times:

- `ine.png` — upper LEFT: silver lavender high ponytail and purple bow, two dark hair clips, purple eyes, lavender gold-trim star cape, purple satchel and boots, ivory pleated skirt, carrying a small white letter
- `jing.png` — upper MIDDLE: honey-blonde long loose hair, red eyes, hamburger beret and thin black ribbons, amber-gold postal mantle, ivory shirt, brown shorts satchel and boots
- `lilpa.png` — upper RIGHT: navy high ponytail with blue streak and bat-wing hair bow, amber eyes, navy-gold courier uniform and wing satchel, navy boots, envelope
- `jururu.png` — lower LEFT: deep plum long hair, dark cat-ear shaped ribbon with pink inside, heart hairpin, pink eyes, rose pink-gold cape, ruffled skirt, heart satchel and pink-laced boots
- `gosegu.png` — lower MIDDLE: white ice-blue twin tails, blue x-shaped hairclip and stars, blue eyes, sky-blue cape and shorts, blue star satchel and boots
- `viichan.png` — lower RIGHT: ash olive-brown low pigtails with green ribbons, black twin hairclips, green eyes, sage cape gold border and leaf clasp, ivory skirt, forest star satchel and green-laced boots

### 정지 자세 프롬프트

Use case: identity-preserve. Game asset: neutral idle sprite sheet of these exact six star-post couriers, all STANDING AT REST waiting to receive mail. Preserve the original 3 columns x 2 rows order of the reference, all character identities, hairstyles, ribbons, costume details, colors, polished chibi anime cel-shading. Row 1 silver/lavender ponytail purple cape holding a letter, hamburger beret blonde with amber cape, navy ponytail with bat bow and navy cape. Row 2 deep plum pink courier with cat-ear ribbon, ice-blue twin-tail sky blue courier, ash-brown twin low tails and forest-green courier with leaf clasp. All six face screen RIGHT (mild 3/4 profile), both boots solidly planted under hips, knees almost straight and relaxed, upper body upright, comfortable arms at rest holding envelope or strap. NO running, kicking, leaning, waving, jumping or balancing on one foot. Same head to body ratios and same costume as reference. Full-body, heels visible, every character centered in own regular square cell with 12% transparent space all around. Equal height and equal foot baselines. LANDSCAPE transparent 3:2 art exactly three columns and two rows; no environment, no shadows, no floor, no separators, no lettering, no extra object. Genuine transparent alpha. Clearly identifiable crisp silhouettes readable at 80px in game.

## 야간 배송 캠페인 추가 그림

장비·보스·무대 그림은 내장 ImageGen으로 제작했다. 원본 PNG와 게임에 포함하는 WebP를 함께 보관한다.

- `bosses.png` — 3×1 투명 아틀라스. 왼쪽부터 붉은 봉랍 방패를 든 우체통 골렘, 종을 쓴 청록빛 해파리 정령, 깃펜 왕관을 쓴 보랏빛 반송왕. 통통한 실루엣, 남색 윤곽선과 손으로 채색한 별빛 우체국 분위기. 바닥·자막·글자 없이 각 칸에 전신을 배치했다.
- `gear.png`는 4열 2행의 투명 장비 아틀라스다. 첫 줄에는 별 달린 운동화, 우편 가방, 나침반, 유성 펜촉을 놓았다. 둘째 줄에는 속기 태엽, 분류 날개, 앙코르 리본을 놓고 마지막 칸은 비웠다. 가장 작은 카드에서도 물건의 외곽선과 쓰임이 읽히도록 중앙에 한 점씩 배치했다.

### 배송지별 배경

공통 구도는 3:2 비율의 내려다본 광장이다. 이동 공간을 넓게 비우고 건물, 가로등, 풍경 소품을 가장자리로 보냈다. 무대마다 독립된 그림 한 장을 사용하며 플레이어, 적, 편지, 우체통은 게임에서 그린다. 첫 무대는 기존 `plaza.png`를 사용한다.

| 파일 | 무대 | 그림에 담은 특징 |
| --- | --- | --- |
| stage02.png | 바람개비 골목 | 종이 바람개비, 따뜻한 벽돌길과 가게 |
| stage03.png | 유리온실 길 | 유리 천장의 격자 그림자, 연녹색 석판과 화분 |
| stage04.png | 닻을 내린 부두 | 널빤지 부두, 닻과 밧줄, 선박의 불빛 |
| stage05.png | 반딧불 수로 | 청록빛 수로, 반딧불과 수초 |
| stage06.png | 달빛 인쇄소 | 적갈색 바닥, 오래된 인쇄기와 황동 장식 |
| stage07.png | 종탑 우체국 | 라벤더빛 돌바닥, 종탑의 아치와 긴 그림자 |
| stage08.png | 유성 철교 | 푸른 철제 상판과 나란한 철로 |
| stage09.png | 새벽 활주로 | 장밋빛 새벽, 활주로 표식과 격납고 |
| stage10.png | 마지막 환승역 | 별자리 상감 바닥, 중앙 시계와 자줏빛 커튼 |

생성일: 2026-11-18. 도구: 내장 `image_gen.imagegen`. 입력 사진/기존 프로필을 복사하거나 합성하지 않은 신규 생성. 생성 후 원본은 그대로 보존하고 배포용 WebP 변환만 적용. characters/items에는 `transparent_background: true`, plaza에는 false를 지정했다.

## characters.png

Use case: stylized-concept. Produce ONE production-ready transparent character sprite atlas, landscape aspect ratio 3:2, exactly 3 columns x 2 rows of evenly spaced cells. Draw entirely NEW original chibi fan-game characters from scratch. Six ISEGYE IDOL girls as star couriers, each full body, head-to-boot visible, 3-head-tall adorable proportions, expressive large eyes, thick refined indigo outlines, polished anime cel shading with soft painted highlights, high-quality collectible game sticker art. Every cell centered same height with 12% transparent padding, no overlap between cells. Row1 col1 INE: silver-lavender long high ponytail, violet eyes, calm smile, lavender courier capelet, white jacket, purple skirt, star satchel; row1 col2 JINGBURGER: long golden blonde hair, red eyes, burger-shaped beret, cheerful grin, amber short cape, brown boots, star parcel; row1 col3 LILPA: dark navy hair with blue streak and high side ponytail tied by black batlike ribbon, amber eyes, confident grin, midnight blue courier jacket, little wing motif satchel. Row2 col1 JURURU: dark plum long wavy hair, black cat-ear ribbon, pink eyes, pink-and-cream courier outfit, heart clasp, playful expression; row2 col2 GOSEGU: icy white-blue long twin tails, blue hair clips and blue eyes, sky blue courier jacket and shorts, energetic pose; row2 col3 VIICHAN: muted ash olive-brown long low pigtails, two black hairpins, bright green eyes, forest green courier capelet, leaf clasp, small star satchel. Each has a different lively ready-to-run pose facing slightly right, hands recognizable, unique silhouette, shared matching courier uniform design. Cute modest clothing, all fully clothed. Transparent alpha background, no checkerboard drawn, no ground, no shadows extending outside cells. No words, no names, no UI, no grid lines, no logos. This is the actual playable 6-character atlas, so strict grid spacing and complete full-body silhouettes are essential.

## plaza.png

Use case: stylized-concept. Asset type: actual 2D game arena background, landscape 3:2. Draw an exquisite hand-painted anime storybook nighttime courtyard for a cozy magical star-courier mini-game. Strict near-overhead 2.5D camera, horizonless, flat ground filling entire image. Main central 80% is open navigable dark lavender cobblestone plaza with a faint circular golden constellation ring in the center, thin glowing inlays and a few tiny scattered luminous specks, comfortable low-contrast readable floor so small characters and collectibles stand out clearly. Around only outer border: tiny cozy postal shops with turquoise and violet roofs, warm yellow lit windows, decorative celestial mailboxes, potted night-blooming flowers, cream stone railings, string lights, a small crescent moon hanging decoration. Upper border a charming empty miniature concert pavilion with golden arches and folded purple curtains, but no readable signs. Luxurious hand-painted game environment, crisp soft ink outlines, finely shaded roof shingles, fairy tale detail, midnight navy and periwinkle palette, warm amber lanterns, mint teal highlights. High polish independent-game visual quality, full bleed, no blank margins. No text, no characters, no creatures, no UI, no labels, no perspective horizon, no obstructions in central playing field. Intended logical game world 960x640.

## items.png

Use case: stylized-concept. Asset type: ONE game object sprite atlas. Landscape 3:2, EXACT regular 3 column x 2 row grid, six separate isolated objects centered in their cell, 20 percent transparent margin in every cell, objects never touch. Elegant kawaii anime fantasy game art matching polished chibi courier game, strong dark indigo outlines, hand-painted cel shading, jewel-like glow and clean silhouette. Row1 col1: golden five-pointed star sealed on a small ivory love-letter envelope with turquoise ribbon, delightful collectible; row1 col2: mischievous round plum-purple jelly ghost with two tiny arms, angry eyebrows, little translucent tail, adorable rather than scary, dangerous red eyes; row1 col3: a chubby midnight-blue bat imp with spread little wings, golden eyes, tiny grin, fully visible. Row2 col1: blue crystal shield with small white star and soft cyan aura; row2 col2: plump glowing pink heart with tiny gold winglets, recovery pickup; row2 col3: ornate mint and cream miniature star postbox on a round gold pedestal, gold star finial, big open slot and glowing purple interior, clear front three-quarter view. Uniform large object sizing relative to cells. Actual transparent alpha background, no painted backdrop or floor, no grid, no text, no letters, no logos, no watermark. Production-ready sprite sheet for actual canvas gameplay.
