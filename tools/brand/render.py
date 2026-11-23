"""Render the brand icon (light/dark) to trimmed square PNGs."""
import sys
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

src = Path(sys.argv[1]).read_text()
out = Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)

VARIANTS = {
    "": {"COAT_TOP": "#34495e", "COAT_BOTTOM": "#22303f", "LAPEL": "#1a2530"},
    "dark_": {"COAT_TOP": "#6f8fb0", "COAT_BOTTOM": "#56769a", "LAPEL": "#46617f"},
}


def trimmed_square(png: Path, size: int) -> Image.Image:
    img = Image.open(png).convert("RGBA")
    box = img.getbbox()
    img = img.crop(box)
    side = int(max(img.size) * 1.04)
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(img, ((side - img.width) // 2, (side - img.height) // 2))
    return canvas.resize((size, size), Image.LANCZOS)


with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1024, "height": 1024})
    for prefix, colors in VARIANTS.items():
        svg = src
        for key, value in colors.items():
            svg = svg.replace(key, value)
        svg = svg.replace('width="512" height="512"', 'width="1024" height="1024"')
        page.set_content(f"<html><body style='margin:0;background:transparent'>{svg}</body></html>")
        raw = out / f"{prefix}raw.png"
        page.locator("svg").screenshot(path=str(raw), omit_background=True)
        for name, size in (("icon.png", 256), ("icon@2x.png", 512)):
            trimmed_square(raw, size).save(out / f"{prefix}{name}", optimize=True)
        raw.unlink()
    browser.close()

# Preview on light and dark backgrounds
preview = Image.new("RGBA", (1100, 560), (255, 255, 255, 255))
dark_bg = Image.new("RGBA", (540, 540), (28, 28, 28, 255))
preview.paste(dark_bg, (550, 10))
preview.alpha_composite(Image.open(out / "icon@2x.png"), (14, 24))
preview.alpha_composite(Image.open(out / "dark_icon@2x.png"), (564, 24))
preview.convert("RGB").save(out.parent / "preview.png")
print("ok")
