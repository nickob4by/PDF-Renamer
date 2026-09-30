"""
Generate assets/app.ico (the packaged app's icon).

One-off tool, run with:  python tools/make_icon.py
Requires Pillow, which is already a project dependency.
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

SIZE = 256
ACCENT = (61, 123, 255, 255)
DARK = (23, 28, 36, 255)
TEXT = (232, 235, 241, 255)

out_dir = Path(__file__).resolve().parent.parent / "assets"
out_dir.mkdir(exist_ok=True)

img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
d = ImageDraw.Draw(img)

# Rounded dark tile
d.rounded_rectangle((8, 8, SIZE - 8, SIZE - 8), radius=52, fill=DARK)

# Accent document bar (stylized page)
d.rounded_rectangle((52, 44, SIZE - 52, 100), radius=20, fill=ACCENT)
d.rounded_rectangle((52, 112, SIZE - 52, 122), radius=5, fill=(61, 123, 255, 150))
d.rounded_rectangle((52, 130, SIZE - 150, 140), radius=5, fill=(61, 123, 255, 90))

# "PDF" label
font = None
for path in (r"C:\Windows\Fonts\seguisb.ttf", r"C:\Windows\Fonts\arialbd.ttf"):
    try:
        font = ImageFont.truetype(path, 84)
        break
    except OSError:
        continue
if font is None:
    font = ImageFont.load_default()

d.text((SIZE / 2, 188), "PDF", font=font, fill=TEXT, anchor="mm")

img.save(out_dir / "app.ico", sizes=[(16, 16), (24, 24), (32, 32),
                                     (48, 48), (64, 64), (128, 128),
                                     (256, 256)])
print(f"Wrote {out_dir / 'app.ico'}")
