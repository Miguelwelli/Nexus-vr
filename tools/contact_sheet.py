#!/usr/bin/env python3
"""Build a contact sheet of the panorama previews (dev helper)."""
import os
from PIL import Image
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src = os.path.join(root, "assets", "textures", "panoramas")
names = ["night", "space", "beach", "cinema", "virtual"]
w, h = 640, 320
sheet = Image.new("RGB", (w * 2, h * 3), (10, 10, 14))
for i, n in enumerate(names):
    p = os.path.join(src, f"_preview_{n}.jpg")
    if not os.path.exists(p):
        continue
    im = Image.open(p).resize((w, h), Image.LANCZOS)
    sheet.paste(im, ((i % 2) * w, (i // 2) * h))
sheet.save(os.path.join(root, "docs", "screenshots", "panoramas_sheet.jpg"), quality=88)
print("ok")
