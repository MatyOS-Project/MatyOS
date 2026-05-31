#!/usr/bin/env python3
"""Generate the MatyOS file-type icon set (black & white).

Design language: one minimalist rounded-square "tile" per file type, carrying an
invented mathematical glyph and the extension label. Source files are black-on-
white; the sealed project archive (.matyos) is inverted (white-on-black) with a
"binding" on the spine to read as a bundle of many files.

    .thm   theorem      forall   (a universally-quantified statement)
    .prf   proof        QED tombstone (a completed derivation)
    .hyp   hypothesis   there-exists (an assumed truth)
    .test  test         check mark (a verified experiment)
    .elk   definitions  lambda (terms / the vocabulary)
    .matyos project      Sigma  (a "sigma of files" — the sealed archive)

Outputs, for each type, into this directory: NAME.svg, NAME.png (256px),
NAME.ico (multi-size). Plus contact_sheet.png.
Run:  python assets/icons/generate_icons.py
"""

import os
import matplotlib
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
TTF = os.path.join(matplotlib.get_data_path(), "fonts", "ttf")
SANS = os.path.join(TTF, "DejaVuSans.ttf")
MONO = os.path.join(TTF, "DejaVuSansMono.ttf")

BLACK = (17, 17, 17, 255)
WHITE = (255, 255, 255, 255)
TRANSPARENT = (255, 255, 255, 0)

# type -> (glyph, extension label, inverted?)
ICONS = {
    "thm":    ("∀", ".thm",    False),   # for all
    "prf":    ("∎", ".prf",    False),   # QED
    "hyp":    ("∃", ".hyp",    False),   # there exists
    "test":   ("✓", ".test",   False),   # check
    "elk":    ("λ", ".elk",    False),   # lambda
    "matyos": ("Σ", ".matyos", True),    # Sigma (sigma of files)
}

S = 1024  # supersample canvas; downscaled to 256


def _rounded(draw, box, r, **kw):
    draw.rounded_rectangle(box, radius=r, **kw)


def render_png(glyph, ext, inverted):
    img = Image.new("RGBA", (S, S), TRANSPARENT)
    d = ImageDraw.Draw(img)
    fg, bg = (WHITE, BLACK) if inverted else (BLACK, WHITE)

    m, r, lw = 90, 150, 46
    box = (m, m, S - m, S - m)
    # tile
    _rounded(d, box, r, fill=bg, outline=fg, width=lw)

    # archive "binding" on the spine (only for the sealed .matyos tile)
    if inverted:
        x = m + 70
        for _ in range(3):
            d.line([(x, m + 120), (x, S - m - 120)], fill=fg, width=22)
            x += 60

    # glyph
    gfont = ImageFont.truetype(SANS, 560)
    bb = d.textbbox((0, 0), glyph, font=gfont)
    gw, gh = bb[2] - bb[0], bb[3] - bb[1]
    gx = (S - gw) / 2 - bb[0] + (60 if inverted else 0)
    gy = (S - gh) / 2 - bb[1] - 70
    d.text((gx, gy), glyph, font=gfont, fill=fg)

    # extension label
    lfont = ImageFont.truetype(MONO, 150)
    lb = d.textbbox((0, 0), ext, font=lfont)
    lw2 = lb[2] - lb[0]
    lx = (S - lw2) / 2 - lb[0]
    ly = S - m - 220
    d.text((lx, ly), ext, font=lfont, fill=fg)

    return img.resize((256, 256), Image.LANCZOS)


SVG_TMPL = """<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256" viewBox="0 0 256 256">
  <rect x="22" y="22" width="212" height="212" rx="38" fill="{bg}" stroke="{fg}" stroke-width="11"/>
  {binding}
  <text x="{gx}" y="150" font-family="Georgia, 'Times New Roman', serif" font-size="150"
        fill="{fg}" text-anchor="middle" dominant-baseline="middle">{glyph}</text>
  <text x="128" y="208" font-family="'JetBrains Mono', 'DejaVu Sans Mono', monospace"
        font-size="36" fill="{fg}" text-anchor="middle">{ext}</text>
</svg>
"""


def render_svg(glyph, ext, inverted):
    fg = "#ffffff" if inverted else "#111111"
    bg = "#111111" if inverted else "#ffffff"
    binding = ""
    gx = 128
    if inverted:
        gx = 140
        binding = ("".join(
            f'<line x1="{48 + i*16}" y1="52" x2="{48 + i*16}" y2="204" '
            f'stroke="{fg}" stroke-width="5"/>' for i in range(3)))
    return SVG_TMPL.format(bg=bg, fg=fg, glyph=glyph, ext=ext,
                           binding=binding, gx=gx)


def main():
    pngs = {}
    for name, (glyph, ext, inv) in ICONS.items():
        png = render_png(glyph, ext, inv)
        png.save(os.path.join(HERE, f"{name}.png"))
        png.save(os.path.join(HERE, f"{name}.ico"),
                 sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
        with open(os.path.join(HERE, f"{name}.svg"), "w", encoding="utf-8") as f:
            f.write(render_svg(glyph, ext, inv))
        pngs[name] = png
        print(f"  wrote {name}.svg / .png / .ico")

    # contact sheet
    order = ["matyos", "thm", "prf", "hyp", "test", "elk"]
    pad, w = 24, 256
    sheet = Image.new("RGBA", (w * len(order) + pad * (len(order) + 1),
                               w + pad * 2), (250, 250, 250, 255))
    for i, n in enumerate(order):
        sheet.paste(pngs[n], (pad + i * (w + pad), pad), pngs[n])
    sheet.save(os.path.join(HERE, "contact_sheet.png"))
    print("  wrote contact_sheet.png")


if __name__ == "__main__":
    main()
