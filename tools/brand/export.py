"""Export the chosen icon (D: ring, green) as Home Assistant brand images."""
import sys
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).parent))
import build  # noqa: E402  (renders option sheet as a side effect)

out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)
COLORS = {"": "#2e7d32", "dark_": "#66bb6a"}

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1024, "height": 1024})
    for prefix, color in COLORS.items():
        page.set_content(
            "<html><body style='margin:0;background:transparent'>"
            f"{build.VARIANTS['D_circle_ring'](color)}</body></html>"
        )
        raw = out / f"{prefix}raw.png"
        page.locator("svg").screenshot(path=str(raw), omit_background=True)
        img = Image.open(raw).convert("RGBA")
        img = img.crop(img.getbbox())
        for name, size in (("icon.png", 256), ("icon@2x.png", 512)):
            img.resize((size, size), Image.LANCZOS).save(out / f"{prefix}{name}", optimize=True)
        raw.unlink()
    browser.close()
print("exported")
