"""Export the courier animation drawings as two foot-aligned, transparent WebP atlases."""
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1] / 'fangames'
SOURCE = ROOT / 'art-source' / 'motion'
MEMBERS = ('ine', 'jing', 'lilpa', 'jururu', 'gosegu', 'viichan')
CELL = 192
GROUND = round(CELL * .94)


def read_poses(path, columns, rows):
    with Image.open(path) as sheet:
        if 'A' not in sheet.getbands():
            raise ValueError(f'Missing sprite transparency in {path}')
        for row in range(rows):
            for col in range(columns):
                area = (round(col * sheet.width / columns), round(row * sheet.height / rows),
                        round((col + 1) * sheet.width / columns), round((row + 1) * sheet.height / rows))
                frame = sheet.crop(area).convert('RGBA')
                alpha = frame.getchannel('A')
                # The transparent gutters in the source paintings carry faint matte noise.
                frame.putalpha(alpha.point(lambda value: 0 if value < 12 else value))
                box = alpha.point(lambda value: 255 if value >= 60 else 0).getbbox()
                if box is None:
                    raise ValueError(f'Empty sprite at {row}, {col} in {path}')
                yield frame.crop(box)


def place(atlas, frame, col, row):
    scale = min(CELL * .88 / frame.height, CELL * .92 / frame.width)
    frame = frame.resize((round(frame.width * scale), round(frame.height * scale)), Image.Resampling.LANCZOS)
    # Register the torso as arms, the far boot and trailing hair change the outer silhouette.
    waist = frame.getchannel('A').crop((0, round(frame.height * .48), frame.width, round(frame.height * .61)))
    weights = waist.resize((frame.width, 1), Image.Resampling.BOX).tobytes()
    center = sum((x + .5) * weight for x, weight in enumerate(weights)) / max(sum(weights), 1)
    left = max(2, min(CELL - frame.width - 2, round(CELL / 2 - center)))
    atlas.alpha_composite(frame, (col * CELL + left, row * CELL + GROUND - frame.height))


def main():
    walk = Image.new('RGBA', (CELL * 4, CELL * len(MEMBERS)))
    for row, member in enumerate(MEMBERS):
        for col, frame in enumerate(read_poses(SOURCE / f'{member}.png', 2, 2)):
            place(walk, frame, col, row)
    standing = Image.new('RGBA', (CELL * 3, CELL * 2))
    for index, frame in enumerate(read_poses(SOURCE / 'standing.png', 3, 2)):
        place(standing, frame, index % 3, index // 3)
    for name, atlas in (('walk', walk), ('standing', standing)):
        atlas.save(ROOT / 'assets' / f'{name}.webp', quality=86, method=6)


if __name__ == '__main__':
    main()
