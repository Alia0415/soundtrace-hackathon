"""Split a transparent 2x2 object sheet into four safely padded assets."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image


OBJECTS = ("vinyl", "tape", "photo", "mailbox")


def split(source: Path, destination: Path, padding: int = 20) -> None:
    image = Image.open(source).convert("RGBA")
    width, height = image.size
    if width % 2 or height % 2:
        raise ValueError("The sheet width and height must be even for midpoint cuts")

    alpha = image.getchannel("A")
    mid_x, mid_y = width // 2, height // 2
    for label, strip in (
        ("vertical", alpha.crop((mid_x, 0, mid_x + 1, height))),
        ("horizontal", alpha.crop((0, mid_y, width, mid_y + 1))),
    ):
        if strip.point(lambda value: 255 if value > 16 else 0).getbbox():
            raise ValueError(f"An object crosses the {label} midpoint cut")

    regions = (
        (0, 0, mid_x, mid_y),
        (mid_x, 0, width, mid_y),
        (0, mid_y, mid_x, height),
        (mid_x, mid_y, width, height),
    )
    destination.mkdir(parents=True, exist_ok=True)
    for name, region in zip(OBJECTS, regions):
        quadrant = image.crop(region)
        visible = quadrant.getchannel("A").point(lambda value: 255 if value > 2 else 0)
        box = visible.getbbox()
        if box is None:
            raise ValueError(f"The {name} quadrant is empty")
        left = max(0, box[0] - padding)
        top = max(0, box[1] - padding)
        right = min(quadrant.width, box[2] + padding)
        bottom = min(quadrant.height, box[3] + padding)
        output = quadrant.crop((left, top, right, bottom))
        output.save(destination / f"{name}.png")
        print(f"{name}: {output.width}x{output.height}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--padding", type=int, default=20)
    args = parser.parse_args()
    split(args.source, args.destination, args.padding)
