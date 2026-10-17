"""Generate the 1200x630 link preview images: static/images/og-image.png (Croatian) and og-image-en.png.

Needs Pillow and the DejaVu Sans fonts (Debian/Ubuntu package fonts-dejavu-core):

    pip install pillow
    python scripts/make_og_image.py
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
ICON = ROOT / "static" / "images" / "icon-1024.webp"
FONTS = Path("/usr/share/fonts/truetype/dejavu")

WIDTH, HEIGHT = 1200, 630
BACKGROUND = "#ffb8b8"  # the icon's own background
TEXT = "#2b2838"        # --text in main.css; 8.7:1 on the background
MUTED = "#5b4a5a"

TITLE = "Baby Calculator"
VERSIONS = {
    "og-image.png": (["Dob bebe u tjednima,", "mjesecima i danima"], "uživo do sekunde · prekretnice"),
    "og-image-en.png": (["A baby's age in weeks,", "months and days"], "live to the second · milestones"),
}


def make(out, lines, footer):
    image = Image.new("RGB", (WIDTH, HEIGHT), BACKGROUND)
    icon = Image.open(ICON).convert("RGB").resize((HEIGHT, HEIGHT), Image.LANCZOS)
    image.paste(icon, (0, 0))

    draw = ImageDraw.Draw(image)
    x = HEIGHT - 10
    margin = 50
    # Largest title size that leaves the right margin free
    size = 64
    while True:
        bold = ImageFont.truetype(str(FONTS / "DejaVuSans-Bold.ttf"), size)
        if x + draw.textlength(TITLE, font=bold) <= WIDTH - margin:
            break
        size -= 2
    regular = ImageFont.truetype(str(FONTS / "DejaVuSans.ttf"), 38)
    small = ImageFont.truetype(str(FONTS / "DejaVuSans.ttf"), 28)

    y = 170
    draw.text((x, y), TITLE, font=bold, fill=TEXT)
    y += 110
    for line in lines:
        draw.text((x, y), line, font=regular, fill=TEXT)
        y += 54
    draw.text((x, y + 40), footer, font=small, fill=MUTED)

    image = image.quantize(colors=128, method=Image.Quantize.MEDIANCUT)
    image.save(out, optimize=True)
    print(f"{out.relative_to(ROOT)}: {out.stat().st_size // 1024} KB")


def main():
    for name, (lines, footer) in VERSIONS.items():
        make(ROOT / "static" / "images" / name, lines, footer)


if __name__ == "__main__":
    main()
