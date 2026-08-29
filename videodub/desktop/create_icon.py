"""Generate VideoDub icons: Windows .ico and macOS .icns."""

import math
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

SIZES_ICO = (16, 24, 32, 48, 64, 128, 256)
SIZES_ICNS = (16, 32, 64, 128, 256, 512, 1024)


def create_logo(size: int) -> Image.Image:
    """Draw the VideoDub logo: rounded-rect gradient background + star + brackets."""
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
        color = tuple(
            round(start[ch] + (end[ch] - start[ch]) * ratio) for ch in range(3)
        )
        for x in range(size):
            pixels[x, y] = (*color, 255)
    image = Image.composite(gradient, image, mask)

    draw = ImageDraw.Draw(image)
    cx = size * 0.5
    cy = size * 0.45
    outer = size * 0.28
    inner = size * 0.10
    points = []
    for idx in range(8):
        angle = -math.pi / 2 + idx * math.pi / 4
        r = outer if idx % 2 == 0 else inner
        points.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
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


def create_ico(output: Path) -> None:
    """Generate Windows .ico with multiple sizes."""
    ico_images = []
    for s in SIZES_ICO:
        ico_images.append(create_logo(s))
    ico_images[0].save(
        output,
        format="ICO",
        sizes=[(s, s) for s in SIZES_ICO],
    )
    print(f"Created {output}")


def _run_iconutil(iconset_dir: Path, icns_output: Path) -> None:
    """Pack an iconset directory into .icns using iconutil."""
    result = subprocess.run(
        ["iconutil", "-c", "icns", "-o", str(icns_output), str(iconset_dir)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"iconutil warning: {result.stderr}", file=sys.stderr)
        raise RuntimeError(f"iconutil failed: {result.stderr}")


def create_icns(output: Path) -> None:
    """Generate macOS .icns using iconutil (requires Xcode Command Line Tools)."""
    # Check for iconutil availability
    if subprocess.call(["which", "iconutil"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) != 0:
        print("[SKIP] iconutil not found — install Xcode Command Line Tools to generate .icns")
        return

    with tempfile.TemporaryDirectory(prefix="videodub_icns_") as tmpdir:
        iconset = Path(tmpdir) / "VideoDub.iconset"
        iconset.mkdir(parents=True)

        # Generate 1x and 2x variants for each size
        for size in SIZES_ICNS:
            logo = create_logo(size)
            logo.save(iconset / f"icon_{size}x{size}.png")
            logo2x = create_logo(size * 2)
            logo2x.save(iconset / f"icon_{size}x{size}@2x.png")

        _run_iconutil(iconset, output)

    print(f"Created {output}")


def main() -> None:
    desktop_dir = Path(__file__).resolve().parent

    # Windows .ico
    ico_path = desktop_dir / "VideoDub.ico"
    create_ico(ico_path)

    # macOS .icns (optional — requires iconutil)
    icns_path = desktop_dir / "VideoDub.icns"
    try:
        create_icns(icns_path)
    except Exception as exc:
        print(f"[WARN] Could not generate .icns: {exc}", file=sys.stderr)


if __name__ == "__main__":
    main()
