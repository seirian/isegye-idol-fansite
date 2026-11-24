# 이파리 연대기 아트 소스

생성일: 2026-11-18. Built-in `image_gen.imagegen` 사용. API/CLI fallback 미사용.
모든 이미지는 새 게임을 위한 생성 이미지이며 공식 게임/일러스트가 아니다.
원본 PNG는 이 디렉터리에 보존하고, 런타임은 `../assets/*.webp`를 사용한다.
Pillow는 픽셀 편집 없이 WebP 인코딩에만 사용했다. 캐스트 여백 수정은 imagegen으로 수행했다.

## 런타임 atlas 계약

| 파일 | 크기 | 격자 / 셀 | 순서 (왼쪽→오른쪽, 위→아래) | 투명도 |
|---|---|---|---|---|
| worlds.webp | 2172×724 | 3×2 / 724×362 | 2021 마을, 2022 겨울봄 숲, 2023 책 도시, 2024 극장, 2025 천체 경기장, 2026 고양이 도시 | RGB 불투명 |
| members.webp | 1536×1024 | 3×2 / 512×512 | 아이네, 징버거, 릴파, 주르르, 고세구, 비챤 | RGBA |
| cast.webp | 1254×1254 | 3×3 / 418×418 | 이파리, 무대 자동인형, 서리 사슴, 책 미믹, 극장 기사, 천체 지휘자, 고양이 광대, 우왁굳 시험관, 앙코르 티켓 | RGBA |

WebP 품질: worlds 88, members/cast 90; method=6, 캐릭터 파일 exact=True.
총 런타임 이미지 크기: 1,638,756 bytes (약 1.56 MiB).
CSS 배경으로 atlas를 사용하는 경우 `background-size: 300% 200%` 또는 `300% 300%`와 셀 위치를 사용한다.
세계 셀 비율은 2:1, 캐릭터 셀은 1:1이다.
멤버 및 캐스트 파일의 alpha 범위는 각각 0–254 및 0–255로 실제 투명도를 가진다.
각 셀은 정사각형 프레임 기준으로 잘라 렌더링한다. 캐스트 여백은 최종 수정판에서 확보했다.

## 참고 이미지

`catalog/members.json`과 `home-review/soop-cache/{ine,jingburger,lilpa,jururu,gosegu,viichan}.webp`를 모두 열어 확인했다.
입력 이미지 개수 제한(최대 5)으로 실제 멤버 생성에는 앞의 다섯 프로필만 reference로 첨부했다.
비챤은 확인한 프로필의 밝은 갈색 단발/초록 눈 특징을 프롬프트에 명시했다.
모든 판타지 의상 및 포즈는 새로 생성했다. 원본 프로필을 잘라 붙이거나 기존 미니게임 sprite를 재사용하지 않았다.
우왁굳 시험관은 녹색 망토와 짧은 수염의 창작 만화 캐릭터다.

## 검증

- 생성된 이미지의 6개/9개 셀 순서 및 전체 피사체를 확인했다.
- 월드의 균등 격자와 장면별 색감, 바닥 공간을 확인했다.
- 멤버 얼굴/머리색/눈색 특징과 여섯 명의 전신을 확인했다.
- 캐스트 초안에서 잘린 응원봉/사슴뿔을 발견해 imagegen으로 여백 수정했다.
- PNG/WebP 크기와 alpha를 Pillow로 확인했다.
- `view_image` 도구의 로컬 RGBA 미리보기는 일부 색상만 표시하는 현상이 있어 imagegen 반환 이미지 및 alpha 픽셀 검사를 함께 사용했다. 브라우저에서는 RGBA 파일을 그대로 표시한다.

## 월드 생성 프롬프트

```text
Use case: illustration-story.
Asset type: landscape background atlas for a polished browser fantasy RPG, six precisely equal panels in a seamless THREE COLUMN by TWO ROW grid; widescreen overall composition ideally 3072x1152, each individual panel landscape 16:9. This is original game background art, not a screenshot, no UI.
Primary request: six locations from a journey through years of a virtual idol fandom, connected visually by glowing gold leaf motes and an amber light trail. Style is beautiful hand-painted storybook watercolor mixed with crisp anime background painting, rich forest emerald, warm parchment amber, midnight ink blue, luminous lighting. Detailed environments with playable floor and clear quiet middle areas where characters/UI can sit. Distinct from a pixel arcade game. No people or characters in any panel.
EXACT CELLS, read left to right top then bottom:
TOP LEFT: a nostalgic hillside village at golden sunset, small wooden outdoor music stage and bunting, cozy pale stucco houses, cobblestone square with a winding path to distant mountains.
TOP MIDDLE: an enchanted woodland transitioning from frosty blue winter at left to blooming peach spring at right, ancient tree arch over a clear path and glimmering pond, warm green heart.
TOP RIGHT: a magical storybook city built from giant open books, floating paper bridges and luminous teal portals, warm rose rooftops; quiet plaza in center.
BOTTOM LEFT: approach to a grand moonlit theater/concert hall, dramatic ink-navy towers and gilded architecture, stair promenade, deep blue and amber lanterns, no readable signs.
BOTTOM MIDDLE: vast celestial outdoor arena with rings of golden seats, starry indigo sky, floating astrolabe forms, sweeping gentle stage approach with emerald banners; celebration of reaching a larger world.
BOTTOM RIGHT: whimsical bright cat-themed city with subtle cat-ear roofs, pastel blue towers, emerald gardens, tall old clock and levitating blank tickets, sunset; playful fantasy, no actual character.
Constraints: equal cells with boundaries exactly one-third and two-thirds across and halfway down. Each scene fills its entire cell edge to edge. Absolutely no outer margin, gutters, gridlines, frames, labels, lettering, numbers, logos, watermarks, user interface, text. Consistent rendering quality in all six cells. Opaque painting.
```

## 멤버 생성 프롬프트

```text
Use case: stylized-concept.
Asset type: 3 COLUMN by 2 ROW transparent full-body character atlas, six virtual-idol fantasy companions for a storybook RPG. Overall 1536x1024 landscape; six equally sized square cells. Each figure centered separately with at least 9% clear margin on every edge, full body fully visible, feet at matching 90% cell height, similar height about 80% cell. No background, true alpha transparency.
Input images: the five attached reference images define face, hair and eye identity only, in order INE, JINGBURGER, LILPA, JURURU, GOSEGU. VIICHAN uses the sixth character description below, based on her reviewed official profile. Redesign clothing into original tasteful fantasy-adventure outfits, do not copy the references' compositions or add microphones/headsets.
Style: elegant collectible storybook anime character art, watercolor shading, crisp confident silhouette, expressive warm faces, slightly stylized proportions (about 4.5 heads tall), intricate but readable costume layers, muted emerald/amber/ink-navy shared palette with each member's color accent. Consistent lighting and polish.
EXACT cell order left to right, top then bottom:
TOP LEFT INE: long flowing white/silver hair, rich violet eyes, calm gentle smile; lavender and ivory healer's long dress and elegant short cape, holding an amber glowing flower lantern.
TOP MIDDLE JINGBURGER: golden blonde bob/shoulder-length hair with bangs and small yellow hair clips, red eyes, cheerful smile; golden-yellow tunic and red-brown adventurer cape, leather boots, carrying a small gold shield and hand bell.
TOP RIGHT LILPA: straight dark navy-black short hair with blue accent streak, golden amber eyes, confident smile; deep navy and silver knight jacket over modest skirt/leggings, small subtle bat-wing shoulder motif, holding an elegant dark rapier pointing safely down.
BOTTOM LEFT JURURU: dark plum-brown hair gathered with soft braids and cute heart hair clip, pink-magenta eyes, playful knowing smile; rose-pink and plum mage dress, light stockings/boots, open spellbook floating at hand.
BOTTOM MIDDLE GOSEGU: silver-white short hair and distinctive blue plus hair clip, bright blue eyes, mischievous smile; sky-blue and white explorer outfit, navy shorts/leggings, airy capelet, holding a small sky-blue magical key.
BOTTOM RIGHT VIICHAN: ash-beige/light brown bob with tiny black hairpin, vivid lime green eyes, welcoming smile; fresh green and charcoal ranger outfit, leaf-shaped cape and comfortable boots, holding a small glowing green lyre.
Constraints: only six characters, do not merge cells. No text, labels, watermark, scenery, opaque panels, checkerboard pattern, cell dividers or ground planes. Each figure has clear silhouette, complete hands and feet inside its cell. Transparent alpha background.
```

## 캐스트 생성 프롬프트

```text
Use case: stylized-concept.
Asset type: 3 COLUMN by 3 ROW transparent creature/hero sprite atlas for a hand-painted storybook fantasy RPG. Square 1536x1536. Exactly nine equal square cells, isolated full-body subjects, all inside each cell with generous 12% clear margins and matching foot baseline at 87% cell height.
Style: charming richly painted watercolor/anime adventure game characters, crisp readable silhouettes, warm amber highlights, forest emerald and midnight ink-navy, gentle collectible RPG art, around 3.5-4 heads tall. True transparent alpha background. No scene, tiles, labels, shadows spanning cells, or UI.
EXACT ORDER top row left to right then middle then bottom:
1 TOP LEFT: the FAN HERO, an endearing gender-neutral little adventurer wearing a deep green pointed hood shaped like a fresh leaf, tiny visible friendly face, cream tunic, brown boots, gold satchel, holding a luminous pale green concert lightstick like a wand. Small leaf emblem on cape, courageous friendly pose.
2 TOP MIDDLE: STAGE AUTOMATON guardian, small charming brass and wood robot shaped like a vintage stage spotlight, glowing amber lens eye, little winding key, theater-curtain shoulder tassels, two feet, no weapon.
3 TOP RIGHT: FROST STAG guardian, an elegant compact ice-blue deer with branching crystal antlers and tender white fur, touches of spring flowers budding near hooves; complete animal visible.
4 MIDDLE LEFT: STORYBOOK MIMIC guardian, open plum and amber spellbook creature with friendly fierce glowing eyes on its binding, paper legs and fanned paper wings, a few floating pages close to body.
5 MIDDLE MIDDLE: THEATER KNIGHT guardian, empty ornate navy-blue and silver suit of armor with gold trim, closed helmet and glowing cyan slit, tiny bat-wing motif, cape, shield and slim stage-baton sword; non-human.
6 MIDDLE RIGHT: CELESTIAL CONDUCTOR guardian, floating star-headed magical conductor in a midnight cloak, amber astrolabe around shoulders, white glove hands, baton and tiny stars closely grouped, no human face.
7 BOTTOM LEFT: CAT JESTER guardian, cute sky-blue and white bipedal fantasy cat with a short navy jester cloak, gold bells, expressive eyes, oversized magic ticket card, playful pose.
8 BOTTOM MIDDLE: FRIENDLY FINAL EXAMINER inspired by Woowakgood's stylized green avatar, adult cheerful man with brown hair and short brown goatee, eyes as playful dark smiling arcs, long emerald hooded cloak over cream-and-brown fantasy clothes, round gold clasp, holding a little wooden judge baton, expressive good-natured smirk; cartoon fantasy character, not realistic likeness.
9 BOTTOM RIGHT: THE FINALE CREST, a beautiful floating amber concert ticket with an embossed green leaf surrounded by six tiny multicolored stars, ornate gold edges and green ribbon, no letters or numbers.
Constraints: 9 subjects, one per equal cell, no subject crossing boundary, all fully visible. Crisp alpha transparency. No text, no watermark, no square opaque backgrounds, no grid lines, no checkerboard texture, no scene. Whimsical, safe, friendly boss-trial game mood.
```

## 캐스트 안전 여백 수정 프롬프트

```text
Use case: precise-object-edit. Edit the provided 3x3 transparent RPG character atlas. Preserve exactly these same nine character designs, order, colors, illustration style and alpha transparency. ONLY repair the atlas framing: scale every character/group down to fit entirely within its own equal square cell, centered with a safe 12% transparent margin on EACH of the four sides. Current top-left lightstick and top-right stag antlers are cut off: restore their full forms, entirely inside safe margins. The book wings must never extend into its neighbor. The cat and examiner must have complete visible feet and no overlap with the next cells. Exact equal 3-column and 3-row divisions. Give every character approximately 74% cell height and fit width too. Keep exact original one-per-cell order. Actual transparent background, no solid fill, no gray/black/checkerboard background, no text or guides. All nine complete subjects must remain beautiful and legible.
```

## 첫 만남 이벤트 일러스트

기존 `members.webp`를 인물과 의상 참고로 사용해 내장 이미지 생성기로 제작했다. 원본은 `meetings.png`, 게임 파일은 `../assets/meetings.webp`(품질 90)다. 좌상단부터 장 순서에 맞춘 2열 3행 구성이며 컷씬에서 한 칸씩 사용한다.

```text
Use case: illustration-story. Create one original game asset, a visual novel event CG atlas of six horizontal illustrations. The reference sheet is identity and costume guidance for the same six heroines. Arrange in TWO COLUMNS and THREE ROWS, each cell EXACTLY the same size, every individual image cinematic landscape 16:9; entire atlas roughly 6:5 or square. Edge to edge. No gutters or borders. No text, no interface. Every panel is its own visual novel keyframe, an arresting face-forward waist-up shot with face in upper middle third, environmental storytelling, different camera angles, active hands in foreground, detailed high-end anime film illustration with rich atmospheric color, natural proportions. Top left: JINGBURGER blonde red-eyed red-cape adventurer leans down to the viewer from an old wooden rehearsal stage at sunset, extending her bell; small warm lights behind her. Top right: INE long silver hair and violet eyes, lavender healer holding amber lantern up toward a frost-covered blossom in blue winter forest, cold breath, enchanted light. Middle left: JURURU plum brown hair heart pin and pink eyes, mischievous, stepping through an open book in a rose-lit city of paper, holding a loose illustrated page toward viewer. Middle right: LILPA short dark navy hair golden eyes in navy silver knight uniform pulls open heavy indigo curtains to reveal a moonlit concert hall, backstage spotlights sweep behind her. Bottom left: VIICHAN ash-beige bob green eyes, ranger holding a green lyre, turning to the viewer as she listens for the distant audience beneath thousands of green arena lights. Bottom right: GOSEGU short white hair blue plus pin blue eyes sky-blue cape and playful grin holding an enchanted blue key, approaching viewer on a pastel blue clocktower roof with paper cats. Beautiful chapter-specific colors and convincing backgrounds. No montage within cells. Six separate faces, same character identities as reference.
```

## 지형과 건물 소품

`scenery.png`를 내장 이미지 생성기로 제작해 투명 WebP(품질 90)로 저장했다. 탐색과 전투에서 같은 소품을 사용한다.

```text
Use case: stylized-concept. Build a professionally painted isometric terrain prop sprite atlas for a Korean fantasy tactics RPG. A precise uniform FOUR COLUMN by THREE ROW contact sheet of TWELVE isolated individual environment objects. Single transparent RGBA background, no ground plane, no drop shadow outside each cell, no lettering, outlines or frames. Each object is centered at exactly the middle of its own cell and its base at 90 percent cell height, keep generous 10 percent margins so no bleeding, complete silhouettes. View down from 35 degrees above with visible three-dimensional volume, facing viewer at three quarters, designed for clean readable silhouettes at tiny 64-pixel game size, exquisitely detailed retro 32-bit hand-painted pixel art in the style of a cozy classic tactical fantasy RPG. Crisp light and dark pixel clusters, distinct hues, warm directional lighting, rich vibrant earthy tones. ROW 1: a tall deep green layered conifer pine; broad deciduous tree lush rounded emerald leafy crown with brown trunk; blue-green frosty pine with snow-tipped branches; flowering pastel pink cherry blossom tree. ROW 2: small timber market hut with russet tiled roof and one golden window; little wooden fairground market stall with cream and rust striped canopy; a medieval blue slate roof theater annex with golden lantern and purple festival banner; a rose-walled whimsical bookshop with a giant open book on roof. ROW 3: moss-covered rocky outcrop of chunky granite boulders; pile of worn wooden backstage storage crates with brass fittings and a coiled rope; thick flowering low shrub, yellow and blue flowers with leaves; freestanding ornate brass oil street lantern on a dark wood post. No characters, no scenery, no terrain floor squares, no icons, no repetitive symbols, each item completely separate, alpha transparency between objects. Make the canvas exactly 4:3 landscape.
```

