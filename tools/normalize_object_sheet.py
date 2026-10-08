"""Re-space a generated 2x2 object sheet before rectangular cutting."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image


SIZE = (1536, 1024)
OBJECTS = (
    ("vinyl", (0, 0, 768, 512), (473, 320), (384, 256)),
    ("tape", (768, 0, 1536, 512), (435, 290), (1152, 256)),
    ("photo", (0, 512, 768, 1024), (368, 395), (384, 756)),
    ("mailbox", (768, 512, 1536, 1024), (445, 380), (1152, 756)),
)


def normalize(source: Path, destination: Path) -> None:
    image = Image.open(source).convert("RGBA")
    if image.size != SIZE:
        raise ValueError(f"Expected a {SIZE[0]}x{SIZE[1]} sheet, got {image.size}")

    alpha = image.getchannel("A")
    for label, strip in (
        ("vertical", alpha.crop((768, 0, 769, 1024))),
        ("horizontal", alpha.crop((0, 512, 1536, 513))),
    ):
        if strip.point(lambda value: 255 if value > 16 else 0).getbbox():
            raise ValueError(f"An object crosses the {label} midpoint; regenerate first")

    output = Image.new("RGBA", SIZE, (0, 0, 0, 0))
    for name, region, maximum, center in OBJECTS:
        quadrant = image.crop(region)
        visible = quadrant.getchannel("A").point(lambda value: 255 if value > 2 else 0)
        box = visible.getbbox()
        if box is None:
            raise ValueError(f"The {name} quadrant is empty")
        sprite = quadrant.crop(box)
        scale = min(1.0, maximum[0] / sprite.width, maximum[1] / sprite.height)
        if scale < 1:
            sprite = sprite.resize(
                (round(sprite.width * scale), round(sprite.height * scale)),
                Image.Resampling.LANCZOS,
            )
        left = round(center[0] - sprite.width / 2)
        top = round(center[1] - sprite.height / 2)
        output.alpha_composite(sprite, (left, top))
        print(f"{name}: {sprite.width}x{sprite.height} at ({left},{top})")

    destination.parent.mkdir(parents=True, exist_ok=True)
    output.save(destination)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    normalize(args.source, args.destination)
