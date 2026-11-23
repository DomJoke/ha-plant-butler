"""Silhouette icon variants (side view butler serving a plant), single colour."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import sync_playwright

OUT = Path(__file__).parent / "out"
OUT.mkdir(exist_ok=True)

# Butler in profile facing right, holding a tray with a potted plant.
# Drawn in a 512 box; everything uses "currentColor" so one fill drives it.
FIGURE = """
<defs>
  <mask id="cut" maskUnits="userSpaceOnUse" x="0" y="0" width="512" height="512">
    <rect width="512" height="512" fill="#fff"/>
    <g fill="#000" stroke="#000" stroke-linecap="round" stroke-linejoin="round">
      <!-- shirt front -->
      <path stroke="none" d="M238 168 Q260 172 263 198 Q263 226 255 252 L247 252 Q252 216 244 188 Z"/>
      <!-- gap around the serving arm -->
      <path d="M240 190 Q264 232 292 238 Q318 224 326 188" stroke-width="38" fill="none"/>
    </g>
  </mask>
</defs>
<g fill="currentColor" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round">
  <g mask="url(#cut)">
    <!-- head, nose, slicked-back hair -->
    <circle cx="226" cy="112" r="30" stroke="none"/>
    <path stroke="none" d="M252 104 Q266 114 254 124 Z"/>
    <path stroke="none" d="M194 116 Q190 84 222 78 Q248 76 256 96 Q232 88 208 98 Z"/>
    <rect x="212" y="134" width="24" height="30" rx="6" stroke="none"/>
    <!-- torso with proud chest and coat tails -->
    <path stroke="none" d="M192 172 Q214 158 246 164 Q272 172 270 214 Q268 252 258 300
             L254 318 L206 318 Q196 300 190 270 Q184 230 192 172 Z"/>
    <path stroke="none" d="M194 248 Q176 312 170 380 L196 380 Q204 330 216 298 Z"/>
    <!-- legs and shoes -->
    <path d="M244 314 L248 436" stroke-width="26" fill="none"/>
    <path d="M216 314 L212 436" stroke-width="26" fill="none"/>
    <path stroke="none" d="M236 426 L276 426 Q290 428 290 444 L236 444 Z"/>
    <path stroke="none" d="M200 426 L240 426 Q252 428 252 444 L200 444 Z"/>
  </g>
  <!-- bow tie -->
  <path stroke="none" d="M245 168 L262 158 L262 178 Z M245 168 L230 159 L230 177 Z"/>
  <!-- serving arm -->
  <path d="M240 190 Q264 232 292 238 Q318 224 326 188" stroke-width="22" fill="none"/>
  <!-- tray -->
  <rect x="268" y="174" width="134" height="10" rx="5" stroke="none"/>
  <!-- pot -->
  <path stroke="none" d="M314 130 L362 130 L354 170 L322 170 Z"/>
  <rect x="308" y="122" width="60" height="12" rx="4" stroke="none"/>
  <!-- plant: three broad leaves on stems -->
  <path d="M338 122 L316.0 108.2" stroke-width="6" fill="none"/><path d="M338 122 L338.0 92.0" stroke-width="6" fill="none"/><path d="M338 122 L360.0 108.2" stroke-width="6" fill="none"/>
  <g stroke="none"><path transform="translate(316.0 108.2) rotate(-58)" d="M0 0 C 19.8 -2.0 17.4 -30.0 0 -40.0 C -17.4 -30.0 -19.8 -2.0 0 0 Z"/><path transform="translate(338.0 92.0) rotate(0)" d="M0 0 C 22.8 -2.3 20.0 -34.5 0 -46.0 C -20.0 -34.5 -22.8 -2.3 0 0 Z"/><path transform="translate(360.0 108.2) rotate(58)" d="M0 0 C 19.8 -2.0 17.4 -30.0 0 -40.0 C -17.4 -30.0 -19.8 -2.0 0 0 Z"/></g>
</g>
"""

# The figure spans roughly x 176..400, y 48..444 -> centre it
FIG = f'<g transform="translate(-32 10)">{FIGURE}</g>'


def svg(body: str, color: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" '
        f'width="1024" height="1024" style="color:{color}">{body}</svg>'
    )


def inner(scale: float, color: str) -> str:
    """Figure scaled into the middle of a button, in the given colour."""
    offset = 256 * (1 - scale)
    return (
        f'<g transform="translate({offset} {offset}) scale({scale})" style="color:{color}">{FIG}</g>'
    )


VARIANTS = {
    "A_silhouette": lambda c: svg(FIG, c),
    "B_circle_filled": lambda c: svg(
        f'<circle cx="256" cy="256" r="250" fill="{c}"/>' + inner(0.98, "#ffffff"), c
    ),
    "C_square_filled": lambda c: svg(
        f'<rect x="6" y="6" width="500" height="500" rx="112" fill="{c}"/>'
        + inner(0.98, "#ffffff"),
        c,
    ),
    "D_circle_ring": lambda c: svg(
        f'<circle cx="256" cy="256" r="236" fill="none" stroke="{c}" stroke-width="28"/>'
        + inner(0.86, c),
        c,
    ),
}
COLORS = {"green": "#2e7d32", "blue": "#039be5"}

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1024, "height": 1024})
    for name, build in VARIANTS.items():
        for cname, color in COLORS.items():
            page.set_content(
                f"<html><body style='margin:0;background:transparent'>{build(color)}</body></html>"
            )
            page.locator("svg").screenshot(path=str(OUT / f"{name}_{cname}.png"), omit_background=True)
    browser.close()


def trim(img: Image.Image) -> Image.Image:
    img = img.crop(img.getbbox())
    side = int(max(img.size) * 1.04)
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(img, ((side - img.width) // 2, (side - img.height) // 2))
    return canvas


# Contact sheet: each variant big + small, on light and dark
font = ImageFont.load_default(size=26)
cols = [(n, c) for n in VARIANTS for c in COLORS]
cell = 300
sheet = Image.new("RGBA", (cell * len(VARIANTS), cell * 2 * 2 + 40), (255, 255, 255, 255))
draw = ImageDraw.Draw(sheet)
for i, name in enumerate(VARIANTS):
    draw.text((i * cell + 16, 6), name.split("_", 1)[0], fill=(0, 0, 0), font=font)
    for j, cname in enumerate(COLORS):
        img = trim(Image.open(OUT / f"{name}_{cname}.png").convert("RGBA"))
        y0 = 40 + j * cell * 2
        # light background
        sheet.alpha_composite(img.resize((200, 200), Image.LANCZOS), (i * cell + 50, y0 + 10))
        sheet.alpha_composite(img.resize((40, 40), Image.LANCZOS), (i * cell + 20, y0 + 230))
        # dark background
        dark = Image.new("RGBA", (cell - 20, cell - 20), (28, 28, 28, 255))
        dark.alpha_composite(img.resize((200, 200), Image.LANCZOS), (40, 10))
        dark.alpha_composite(img.resize((40, 40), Image.LANCZOS), (10, 225))
        sheet.alpha_composite(dark, (i * cell + 10, y0 + cell))
sheet.convert("RGB").save(Path(__file__).parent / "sheet.png")
print("ok")
