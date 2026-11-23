"""Export the landscape wordmark (ring icon + name) used in the README."""
import base64
import sys
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

brand = Path(sys.argv[1])
COLORS = {"": "#2e7d32", "dark_": "#66bb6a"}

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1400, "height": 400})
    for prefix, color in COLORS.items():
        icon = base64.b64encode((brand / f"{prefix}icon@2x.png").read_bytes()).decode()
        page.set_content(
            "<html><body style='margin:0;background:transparent'>"
            "<div id='logo' style='display:inline-flex;align-items:center;gap:32px;padding:0'>"
            f"<img src='data:image/png;base64,{icon}' style='width:256px;height:256px'>"
            f"<span style=\"font-family:'Fira Sans';font-weight:600;font-size:132px;"
            f"color:{color};letter-spacing:-1px;line-height:1\">Plant Butler</span>"
            "</div></body></html>"
        )
        page.wait_for_timeout(200)
        raw = brand / f"{prefix}logo_raw.png"
        page.locator("#logo").screenshot(path=str(raw), omit_background=True)
        img = Image.open(raw).convert("RGBA")
        img = img.crop(img.getbbox())
        # hDPI: 256 px high, normal: 128 px high (brands repo limits)
        for name, height in (("wordmark@2x.png", 256), ("wordmark.png", 128)):
            width = round(img.width * height / img.height)
            img.resize((width, height), Image.LANCZOS).save(brand / f"{prefix}{name}", optimize=True)
        raw.unlink()
    browser.close()
print("logos exported")
