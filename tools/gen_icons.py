#!/usr/bin/env python3
"""Generate the Nexus VR icon set (PWA + Apple touch icons) from one SVG."""
import math, os, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets", "icons")
os.makedirs(OUT, exist_ok=True)

def radial_bg(size, s=None):
    n = size
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float32) / (n - 1)
    cx, cy = 0.5, 0.46
    d = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    # deep space gradient
    core = np.clip(1 - d * 1.45, 0, 1) ** 1.5
    img = np.zeros((n, n, 3), dtype=np.float32)
    img[..., 0] = 0.020 + 0.075 * core
    img[..., 1] = 0.030 + 0.130 * core
    img[..., 2] = 0.075 + 0.300 * core
    # aurora teal bottom-left, violet top-right
    img[..., 1] += 0.10 * np.clip(1 - np.sqrt((xx - 0.18) ** 2 + (yy - 0.92) ** 2) * 1.7, 0, 1) ** 2
    img[..., 2] += 0.02 * np.clip(1 - np.sqrt((xx - 0.18) ** 2 + (yy - 0.92) ** 2) * 1.7, 0, 1) ** 2
    img[..., 0] += 0.10 * np.clip(1 - np.sqrt((xx - 0.88) ** 2 + (yy - 0.10) ** 2) * 1.8, 0, 1) ** 2
    img[..., 2] += 0.16 * np.clip(1 - np.sqrt((xx - 0.88) ** 2 + (yy - 0.10) ** 2) * 1.8, 0, 1) ** 2
    # stars
    rng = np.random.default_rng(3)
    for _ in range(size // 3):
        sx, sy = rng.integers(0, size, 2)
        b = 0.25 + 0.75 * rng.random() ** 3
        r = 0
        for dy in range(0):
            pass
        img[max(0,sy), max(0,sx)] += b
        if 0 < sy < size-1 and 0 < sx < size-1:
            img[sy-1, sx] += b*0.35; img[sy+1, sx] += b*0.35
            img[sy, sx-1] += b*0.35; img[sy, sx+1] += b*0.35
    return np.clip(img, 0, 1)

def draw_mark(img):
    size = img.size[0]
    d = ImageDraw.Draw(img, "RGBA")
    cx, cy = size / 2, size * 0.48
    R = size * 0.26

    # orbit ellipses — clipped to the icon, drawn with tapering opacity
    orbits = ((22, 1.55, 0.46, (95, 228, 255), 215),
              (-42, 1.62, 0.40, (168, 140, 255), 170))
    for ang, rx, ry, col, alpha in orbits:
        w = max(1, int(round(size * 0.014)))
        a = math.radians(ang)
        n = 240
        segs = []
        for i in range(n + 1):
            t = i / n * 2 * math.pi
            x = rx * R * math.cos(t)
            y = ry * R * math.sin(t)
            xr = x * math.cos(a) - y * math.sin(a)
            yr = x * math.sin(a) + y * math.cos(a)
            segs.append((cx + xr, cy + yr))
        # draw back half first (dim), then front half (bright)
        back = segs[: n // 2 + 1]
        front = segs[n // 2:]
        d.line(back, fill=col + (int(alpha * 0.42),), width=w, joint="curve")
        d.line(front, fill=col + (alpha,), width=w, joint="curve")

    # core sphere with radial gradient
    steps = 48
    r0 = R * 0.62
    for i in range(steps):
        t = i / (steps - 1)
        rr = r0 * (1 - t * 0.965)
        col = (int(14 + 176 * t), int(186 + 65 * t), int(222 + 33 * t), 255)
        d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=col)
    # soft outer glow around the core
    glow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse([cx - r0 * 1.5, cy - r0 * 1.5, cx + r0 * 1.5, cy + r0 * 1.5],
               fill=(60, 220, 255, 70))
    glow = glow.filter(ImageFilter.GaussianBlur(size * 0.085))
    img.alpha_composite(glow)
    # re-draw core over the glow
    for i in range(steps):
        t = i / (steps - 1)
        rr = r0 * (1 - t * 0.965)
        col = (int(14 + 176 * t), int(186 + 65 * t), int(222 + 33 * t), 255)
        d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=col)
    # specular highlight
    hi = Image.new("RGBA", img.size, (0, 0, 0, 0))
    hd = ImageDraw.Draw(hi)
    hd.ellipse([cx - r0 * 0.66, cy - r0 * 0.80, cx + r0 * 0.10, cy - r0 * 0.16],
               fill=(255, 255, 255, 150))
    hi = hi.filter(ImageFilter.GaussianBlur(size * 0.022))
    img.alpha_composite(hi)
    # bold N monogram
    font = None
    for fp in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
               "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"):
        if os.path.exists(fp):
            from PIL import ImageFont
            font = ImageFont.truetype(fp, int(size * 0.165))
            break
    if font:
        txt = "N"
        bb = d.textbbox((0, 0), txt, font=font)
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
        d.text((cx - tw / 2 - bb[0], cy - th / 2 - bb[1] - size * 0.004), txt,
               font=font, fill=(2, 26, 38, 240))
    return img


def rounded(img, radius_frac=0.225, size=None):
    w, h = img.size
    r = int(min(w, h) * radius_frac)
    mask = Image.new("L", (w, h), 0)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle([0, 0, w - 1, h - 1], radius=r, fill=255)
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    out.paste(img, (0, 0), mask)
    return out

def make(size, rounded_corners=True):
    bg = radial_bg(size)
    base = Image.fromarray((bg * 255).astype(np.uint8)).convert("RGBA")
    mark = draw_mark(base)
    return rounded(mark, 0.225) if rounded_corners else mark

def svg_mark():
    return '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <defs>
    <radialGradient id="core" cx="42%" cy="38%" r="62%">
      <stop offset="0%" stop-color="#eaffff"/>
      <stop offset="45%" stop-color="#5ce9ff"/>
      <stop offset="100%" stop-color="#1477c8"/>
    </radialGradient>
    <linearGradient id="orbit" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#7ff0ff"/>
      <stop offset="100%" stop-color="#8b6bff"/>
    </linearGradient>
  </defs>
  <ellipse cx="32" cy="30" rx="26" ry="8.5" fill="none" stroke="url(#orbit)" stroke-width="1.7" opacity=".85" transform="rotate(-24 32 30)"/>
  <ellipse cx="32" cy="30" rx="27" ry="7" fill="none" stroke="#3be8ff" stroke-width="1.1" opacity=".5" transform="rotate(36 32 30)"/>
  <circle cx="32" cy="30" r="9.5" fill="url(#core)"/>
  <circle cx="28.6" cy="26.4" r="3.1" fill="#ffffff" opacity=".75"/>
</svg>
'''

def main():
    for s in (32, 48, 96, 128, 180, 192, 256, 512):
        img = make(s)
        name = "favicon-%d.png" % s if s == 32 else ("apple-touch-icon.png" if s == 180 else "icon-%d.png" % s)
        img.save(os.path.join(OUT, name))
        print("wrote", name, img.size)
    # maskable (extra padding, no rounding)
    m = make(512, rounded_corners=False)
    canvas = Image.new("RGBA", (512, 512), (5, 8, 18, 255))
    inner = m.resize((410, 410), Image.LANCZOS)
    canvas.alpha_composite(inner, (51, 51))
    canvas.save(os.path.join(OUT, "maskable-512.png"))
    print("wrote maskable-512.png")
    # logo mark used in the UI
    mark = draw_mark(Image.fromarray((radial_bg(256) * 255).astype(np.uint8)).convert("RGBA"))
    mark.save(os.path.join(OUT, "logo.png"))
    with open(os.path.join(OUT, "logo-mark.svg"), "w") as f:
        f.write(svg_mark())
    with open(os.path.join(OUT, "logo.svg"), "w") as f:
        f.write(svg_mark())
    print("wrote logo.png / logo-mark.svg / logo.svg")

if __name__ == "__main__":
    main()
