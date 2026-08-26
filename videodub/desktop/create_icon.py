"""Generate the Windows ICO matching the VideoDub web brand mark."""

import math
from pathlib import Path

from PIL import Image, ImageDraw


SIZES = (16, 24, 32, 48, 64, 128, 256)


def create_logo(size: int) -> Image.Image:
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    mask = Image.new("L", (size, size), 0)
    mask_draw = ImageDraw.Draw(mask)
    margin = max(1, round(size * 0.02))
    radius = max(2, round(size * 0.24))
    mask_draw.rounded_rectangle(
        (margin, margin, size - margin - 1, size - margin - 1),
        radius=radius,
        fill=255,
    )

    gradient = Image.new("RGBA", (size, size))
    pixels = gradient.load()
    start = (92, 124, 250)
    end = (34, 211, 238)
    for y in range(size):
        ratio = y / max(size - 1, 1)
        color = tuple(round(start[channel] + (end[channel] - start[channel]) * ratio) for channel in range(3))
        for x in range(size):
            pixels[x, y] = (*color, 255)
    image = Image.composite(gradient, image, mask)

    draw = ImageDraw.Draw(image)
    cx = size * 0.5
    cy = size * 0.45
    outer = size * 0.28
    inner = size * 0.10
    points = []
    for index in range(8):
        angle = -math.pi / 2 + index * math.pi / 4
        radius_value = outer if index % 2 == 0 else inner
        points.append((cx + radius_value * math.cos(angle), cy + radius_value * math.sin(angle)))
    stroke = max(1, round(size * 0.055))
    draw.line(points + [points[0]], fill="white", width=stroke, joint="curve")

    line = max(1, round(size * 0.045))
    for x1, y1, x2, y2 in (
        (size * 0.22, size * 0.16, size * 0.22, size * 0.29),
        (size * 0.78, size * 0.71, size * 0.78, size * 0.84),
        (size * 0.16, size * 0.22, size * 0.29, size * 0.22),
        (size * 0.71, size * 0.78, size * 0.84, size * 0.78),
    ):
        draw.line((x1, y1, x2, y2), fill="white", width=line)
    return image


def main() -> None:
    output = Path(__file__).resolve().parent / "VideoDub.ico"
    create_logo(256).save(output, format="ICO", sizes=[(size, size) for size in SIZES])
    print(f"Created {output}")


if __name__ == "__main__":
    main()
