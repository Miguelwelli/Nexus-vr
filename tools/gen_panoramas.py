#!/usr/bin/env python3
"""
Nexus VR — procedural equirectangular (360°) panorama generator.

Every world is generated from scratch with numpy + Pillow (no third-party
photography, so the repository has a clean license for everything it ships).

    night    — aurora over a dark mirror lake, moon and pines
    space    — nebula, ringed gas giant, bright star
    beach    — golden-hour ocean, sun glitter, clouds, distant islands
    cinema   — dark auditorium with velvet seats and a glowing screen
    virtual  — synthwave sunset with a neon perspective grid

Usage:
    python3 tools/gen_panoramas.py --preview                # 1536x768 previews
    python3 tools/gen_panoramas.py                         # final 4096x2048
    python3 tools/gen_panoramas.py --only beach --preview  # single world
"""
import argparse
import math
import os
import sys
import time

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "assets", "textures", "panoramas")
THUMB_DIR = os.path.join(ROOT, "assets", "textures", "thumbs")

TWO_PI = math.pi * 2.0

WORLDS = {
    "night":   {"label": "Noite",   "feature_lon": math.radians(158.0), "seed": 11},
    "space":   {"label": "Espaço",  "feature_lon": math.radians(302.0), "seed": 23},
    "beach":   {"label": "Praia",   "feature_lon": math.radians(242.0), "seed": 37},
    "cinema":  {"label": "Cinema",  "feature_lon": math.radians(270.0), "seed": 41},
    "virtual": {"label": "Virtual", "feature_lon": math.radians(270.0), "seed": 53},
}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0 + 1e-12), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def mix(a, b, t):
    a = np.asarray(a, dtype=np.float32)
    b = np.asarray(b, dtype=np.float32)
    t = np.asarray(t, dtype=np.float32)
    if t.ndim == 2:
        t = t[..., None]
    while a.ndim < t.ndim:
        a = a[None, ...]
    while b.ndim < t.ndim:
        b = b[None, ...]
    return a + (b - a) * t


def rgb(*c):
    return np.array(c, dtype=np.float32)


def normalize(v):
    v = np.asarray(v, dtype=np.float32)
    return v / (np.linalg.norm(v) + 1e-9)


def dot3(X, Y, Z, d):
    return X * d[0] + Y * d[1] + Z * d[2]


def ang_to(X, Y, Z, d):
    return np.arccos(np.clip(dot3(X, Y, Z, d), -1.0, 1.0))


# ---------------------------------------------------------------------------
# noise
# ---------------------------------------------------------------------------


class Noise:
    """Periodic 3D value noise sampled on the unit sphere (seamless)."""

    def __init__(self, seed, periods=(8, 16, 32, 64, 128, 256)):
        rng = np.random.default_rng(seed)
        self.grids = [rng.random((p, p, p), dtype=np.float32) for p in periods]

    @staticmethod
    def _tri(g, x, y, z):
        p = g.shape[0]
        half = p * 0.5
        fx, fy, fz = (x + 1.0) * half, (y + 1.0) * half, (z + 1.0) * half
        xi = np.floor(fx).astype(np.int64)
        yi = np.floor(fy).astype(np.int64)
        zi = np.floor(fz).astype(np.int64)
        tx = (fx - xi).astype(np.float32)
        ty = (fy - yi).astype(np.float32)
        tz = (fz - zi).astype(np.float32)
        x0, y0, z0 = xi % p, yi % p, zi % p
        x1, y1, z1 = (xi + 1) % p, (yi + 1) % p, (zi + 1) % p
        c000, c100 = g[x0, y0, z0], g[x1, y0, z0]
        c010, c110 = g[x0, y1, z0], g[x1, y1, z0]
        c001, c101 = g[x0, y0, z1], g[x1, y0, z1]
        c011, c111 = g[x0, y1, z1], g[x1, y1, z1]
        c00 = c000 + (c100 - c000) * tx
        c10 = c010 + (c110 - c010) * tx
        c01 = c001 + (c101 - c001) * tx
        c11 = c011 + (c111 - c011) * tx
        c0 = c00 + (c10 - c00) * ty
        c1 = c01 + (c11 - c01) * ty
        return c0 + (c1 - c0) * tz

    def sample(self, x, y, z, octaves=4, gain=0.5, freq=1.0, stretch=(1, 1, 1)):
        shape = np.shape(x)
        x = (np.asarray(x, dtype=np.float32) * stretch[0] * freq).ravel()
        y = (np.asarray(y, dtype=np.float32) * stretch[1] * freq).ravel()
        z = (np.asarray(z, dtype=np.float32) * stretch[2] * freq).ravel()
        out = np.zeros(x.shape, dtype=np.float32)
        amp, total = 1.0, 0.0
        for g in self.grids[:octaves]:
            out += amp * self._tri(g, x, y, z)
            total += amp
            amp *= gain
        return (out / total).reshape(shape)

    def fbm(self, x, y, z, **kw):
        return (self.sample(x, y, z, **kw) - 0.5) * 2.0


def noise2d_periodic(h, w, seed, octaves=5, base=6, persistence=0.55):
    """Tileable horizontal noise field over a (h, w) grid in [0,1]."""
    rng = np.random.default_rng(seed)
    total = np.zeros((h, w), dtype=np.float32)
    amp, norm = 1.0, 0.0
    for o in range(octaves):
        gy = max(2, int(base * (2 ** (o * 0.5))))
        gx = gy * 2
        grid = rng.random((gy, gx), dtype=np.float32)
        ys = np.linspace(0, gy, h, endpoint=False)
        xs = np.linspace(0, gx, w, endpoint=False)
        y0 = ys.astype(np.int64)
        x0 = xs.astype(np.int64)
        fy = ys - y0
        fx = xs - x0
        fy = fy * fy * (3 - 2 * fy)
        fx = fx * fx * (3 - 2 * fx)
        y1 = (y0 + 1) % gy
        x1 = (x0 + 1) % gx
        c00 = grid[np.ix_(y0, x0)]
        c10 = grid[np.ix_(y0, x1)]
        c01 = grid[np.ix_(y1, x0)]
        c11 = grid[np.ix_(y1, x1)]
        c0 = c00 + (c10 - c00) * fx[None, :]
        c1 = c01 + (c11 - c01) * fx[None, :]
        total += amp * (c0 + (c1 - c0) * fy[:, None])
        norm += amp
        amp *= persistence
    return total / norm


# ---------------------------------------------------------------------------
# stars
# ---------------------------------------------------------------------------


def star_layer(W, H, seed, count, band_normal=None, band_boost=0.0,
               color_bias=(1.0, 1.0, 1.0), min_elevation=-1.0, glow=1.0):
    rng = np.random.default_rng(seed)
    layer = np.zeros((H, W, 3), dtype=np.float32)
    v = rng.normal(size=(int(count), 3))
    v /= np.linalg.norm(v, axis=1, keepdims=True)
    y = v[:, 1]
    keep = y > math.sin(max(-1.0, min_elevation))
    v, y = v[keep], y[keep]
    n = v.shape[0]
    lon = np.arctan2(v[:, 2], v[:, 0])
    u = (lon / TWO_PI) % 1.0
    lat = np.arcsin(np.clip(y, -1, 1))
    cx = u * W
    cy = (0.5 - lat / np.pi) * H
    mag = rng.random(n) ** 3.4
    bright = (0.16 + 0.95 * mag)
    if band_normal is not None:
        b = np.abs(v @ normalize(band_normal))
        bright = bright * (1.0 + band_boost * np.exp(-((1.0 - b) / 0.20) ** 2))
    temp = rng.random(n)
    cols = np.ones((n, 3), dtype=np.float32)
    cols[temp > 0.80] = (1.0, 0.78, 0.60)
    cols[temp < 0.20] = (0.72, 0.84, 1.0)
    cols *= np.array(color_bias, dtype=np.float32)
    sigma = np.maximum((0.6 + mag * 1.6) * (W / 4096.0), 0.32)
    rad = 2
    for i in range(n):
        b = float(bright[i])
        rr = float(sigma[i])
        x0 = int(cx[i]) - rad
        y0 = int(cy[i]) - rad
        ci = int(cx[i]) % W
        for dy in range(2 * rad + 1):
            py = y0 + dy
            if py < 0 or py >= H:
                continue
            for dx in range(2 * rad + 1):
                px = x0 + dx
                w = math.exp(-(((px - cx[i]) / rr) ** 2 + ((py - cy[i]) / rr) ** 2) * 0.5)
                if w < 0.02:
                    continue
                layer[py, px % W] += cols[i] * (b * w * glow)
    return layer


# ---------------------------------------------------------------------------
# painter helpers
# ---------------------------------------------------------------------------


def get_font(size, bold=True):
    paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    ]
    for p in paths:
        if os.path.exists(p):
            return ImageFont.truetype(p, int(size))
    return ImageFont.load_default()


def eq_xy(lon, lat, W, H):
    u = (lon / TWO_PI) % 1.0
    return u * W, (0.5 - lat / math.pi) * H


def dir_to_eq(x, y, z, W, H):
    return eq_xy(math.atan2(z, x), math.asin(max(-1.0, min(1.0, y))), W, H)


# ---------------------------------------------------------------------------
# world: NIGHT
# ---------------------------------------------------------------------------


def world_night(ctx):
    X, Y, Z, h, lon = ctx["X"], ctx["Y"], ctx["Z"], ctx["lat"], ctx["lon"]
    n = ctx["noise"]

    # sky gradient: deep blue overhead → teal-green glow at the horizon
    sky = mix(rgb(0.005, 0.012, 0.035), rgb(0.012, 0.045, 0.075),
              smoothstep(-0.05, 0.5, h))
    sky = mix(sky, rgb(0.09, 0.26, 0.24), np.exp(-((h - 0.015) / 0.10) ** 2) * 0.55)
    sky = mix(sky, rgb(0.20, 0.34, 0.28), np.exp(-((h - 0.006) / 0.035) ** 2) * 0.40)

    # aurora — vertical curtains. The 2D field index is warped by a 3D fbm so
    # streaks read as ribbons instead of stacked tiles.
    lon_n = (lon / TWO_PI) % 1.0
    warp = n.fbm(X, Y, Z, octaves=3, freq=1.2) * 0.06
    li = (np.clip(lon_n + warp, 0, 0.9999) * 511).astype(np.int32)
    n2 = ctx["noise2"]
    n2b = ctx["noise2b"]
    curtain_v = smoothstep(0.0, 0.30, h) * smoothstep(0.62, 0.18, h)
    streak = n2[(np.clip((0.5 - h / np.pi) * 127, 0, 127)).astype(np.int32), li % 512]
    streak2 = n2b[(np.clip((0.5 - h / np.pi) * 127, 0, 127)).astype(np.int32), li % 512]
    rows = np.linspace(0.02, 0.56, 128, dtype=np.float32)[:, None]
    # vertical development of each curtain (bottom brighter, faded top)
    vlen = smoothstep(0.62, 0.20, h)
    aur1 = smoothstep(0.50, 0.78, streak) * vlen * curtain_v
    aur2 = smoothstep(0.56, 0.86, streak2) * vlen * curtain_v
    au = aur1 * (0.55 + 1.1 * aur1) + aur2 * 0.45
    lo_col = mix(rgb(0.16, 1.0, 0.45), rgb(0.30, 1.0, 0.70),
                 smoothstep(0.0, 0.18, h)[..., None])
    hi_col = mix(rgb(0.05, 0.72, 0.60), rgb(0.48, 0.30, 1.0),
                 smoothstep(0.16, 0.46, h)[..., None])
    aur_col = mix(lo_col, hi_col, smoothstep(0.04, 0.38, h)[..., None])
    sky += aur_col * (au * 1.55)[..., None]
    sky += rgb(0.02, 0.14, 0.10) * (np.exp(-((h - 0.06) / 0.13) ** 2) * 0.55)[..., None]

    # moon
    moon = normalize((-0.52, 0.36, -0.78))
    a = ang_to(X, Y, Z, moon)
    mr = 0.040
    disc = smoothstep(mr, mr * 0.90, a)
    crater = 0.80 + 0.20 * n.sample(X * 33, Y * 33, Z * 33, octaves=4)
    sky = mix(sky, rgb(0.98, 0.97, 0.90) * crater[..., None], (disc * 0.96)[..., None])
    sky += rgb(0.60, 0.68, 0.80) * np.exp(-a / 0.09)[..., None] * 0.30
    sky += rgb(0.16, 0.26, 0.42) * np.exp(-a / 0.42)[..., None] * 0.12

    # mountains + pines silhouette
    mh = 0.010 + 0.075 * (
        0.50 * n.sample(np.cos(lon), np.zeros_like(lon), np.sin(lon), octaves=4, freq=1.8)
        + 0.34 * n.sample(np.cos(lon), np.zeros_like(lon), np.sin(lon), octaves=3, freq=5.0)
        + 0.16 * n.sample(np.cos(lon), np.zeros_like(lon), np.sin(lon), octaves=2, freq=13.0)
    )
    ridge_boost = np.exp(-((lon - math.radians(150.0)) / 0.5) ** 2) * 0.06
    mh = mh + ridge_boost
    mount = smoothstep(mh + 0.002, mh - 0.002, h) * smoothstep(-0.05, 0.0, h)
    graze = np.exp(-((h - mh) / 0.012) ** 2) * (0.35 + 0.65 * n.sample(X, Y, Z, octaves=4, freq=9.0))
    sky = mix(sky, rgb(0.006, 0.010, 0.020), (mount * 0.98)[..., None])
    sky += rgb(0.05, 0.16, 0.14) * (graze * mount * 0.5)[..., None]

    # lake
    below = smoothstep(0.003, -0.004, h)
    depth = smoothstep(0.0, -0.75, h)
    water = mix(rgb(0.024, 0.080, 0.088), rgb(0.004, 0.013, 0.022), depth[..., None])
    ripple = n.sample(X, Y * 14.0, Z, octaves=4, freq=9.0, stretch=(1.0, 0.10, 1.0))
    ripple2 = n.sample(X, Y * 40.0, Z, octaves=3, freq=5.0, stretch=(1.0, 0.05, 1.0))
    calm = smoothstep(-0.02, -0.45, h)
    water += rgb(0.030, 0.085, 0.085) * (ripple * 0.55 + ripple2 * 0.25)[..., None] * calm[..., None]
    # aurora reflection (mirror-ish, blurry)
    refl_h = -h * 1.5
    refl = smoothstep(0.50, 0.85, n2[((0.5 - np.clip(refl_h, -0.4, 0.4) / np.pi) * 127).astype(np.int32) % 128,
                                li % 512]) * np.exp(-((np.abs(h) - 0.10) / 0.22) ** 2)
    water += rgb(0.06, 0.34, 0.24) * (refl * 0.55)[..., None]
    # moon glitter
    mlon = math.atan2(moon[2], moon[0])
    dlon = np.abs(np.mod(lon - mlon + math.pi, TWO_PI) - math.pi)
    sparkle = smoothstep(0.62, 0.95, n.sample(X, Y * 40, Z, octaves=4, freq=30.0))
    glitter = np.exp(-(dlon / 0.06) ** 2) * np.exp(-np.abs(h) / 0.16) * sparkle
    water += rgb(0.85, 0.95, 1.0) * (glitter * 0.8)[..., None]
    # mirrored moon glow on the lake
    dmo = np.exp(-(dlon / 0.10) ** 2) * np.exp(-np.abs(h) / 0.10)
    water += rgb(0.35, 0.48, 0.62) * (dmo * 0.20)[..., None]
    sky = mix(sky, water, below[..., None])
    sky += rgb(0.03, 0.10, 0.10) * np.exp(-np.abs(h) / 0.030)[..., None]

    # foreground pines, left and right
    pines = ctx["pines"]
    if pines is not None:
        r0, r1 = ctx["row0"], ctx["row1"]
        sky = sky * pines[r0:r1]
    return sky
    return sky


# ---------------------------------------------------------------------------
# world: SPACE
# ---------------------------------------------------------------------------


def world_space(ctx):
    X, Y, Z, h, lon = ctx["X"], ctx["Y"], ctx["Z"], ctx["lat"], ctx["lon"]
    n = ctx["noise"]

    sky = rgb(0.0035, 0.0040, 0.0120) + rgb(0.010, 0.003, 0.025) * smoothstep(-0.4, 0.9, Y)[..., None]

    # nebula, two decorrelated domain-warped fbm fields
    wx = n.fbm(X, Y, Z, octaves=3, freq=1.1)
    wy = n.fbm(Y + 3.1, Z, X, octaves=3, freq=1.3)
    wz = n.fbm(Z + 7.7, X, Y, octaves=3, freq=0.9)
    qx, qy, qz = X + wx * 0.60, Y + wy * 0.60, Z + wz * 0.60
    d1 = n.sample(qx, qy, qz, octaves=5, freq=1.6)
    d2 = n.sample(qx * 2.1 + 5.0, qy * 2.1, qz * 2.1, octaves=4, freq=2.0)
    neb = smoothstep(0.40, 0.78, d1) * (0.35 + 0.65 * d2)
    nc = mix(rgb(0.36, 0.04, 0.48), rgb(0.03, 0.26, 0.50),
             smoothstep(0.25, 0.75, d2)[..., None])
    nc = mix(nc, rgb(0.85, 0.10, 0.32), smoothstep(0.55, 0.95, d1)[..., None])
    sky += nc * (neb * 0.55)[..., None]
    # dark dust lanes
    dust = smoothstep(0.50, 0.85, n.sample(qx * 1.4, qy * 1.4, qz * 1.4, octaves=5, freq=3.2))
    sky *= (1.0 - dust * 0.55)[..., None]

    # galactic band
    band_n = normalize((-0.40, 0.64, -0.66))
    b = dot3(X, Y, Z, band_n)
    band = np.exp(-((b / 0.15) ** 2))
    grain = n.sample(X, Y, Z, octaves=5, freq=7.0)
    glow = band * (0.30 + 0.70 * n.sample(X, Y, Z, octaves=4, freq=1.8))
    sky += rgb(0.60, 0.50, 0.80) * (glow * 0.30)[..., None]
    sky += rgb(1.0, 0.88, 0.72) * (band * smoothstep(0.6, 0.95, grain) * 0.35)[..., None]

    # ringed gas giant
    pdir = normalize((0.56, 0.30, -0.77))
    D, R = 9.2, 1.70
    C = pdir * D
    a = ang_to(X, Y, Z, pdir)
    r_ang = R / D
    sun = normalize((-0.86, 0.30, 0.22))
    axis = normalize((0.22, 0.94, 0.25))
    planet = smoothstep(r_ang, r_ang * 0.955, a)

    # rings (behind first, then planet, then front rings)
    ring_n = normalize((0.30, 0.86, 0.22))
    denom = dot3(X, Y, Z, ring_n)
    denom_safe = np.where(np.abs(denom) < 1e-5, 1e-5, denom)
    t = (C @ ring_n) / denom_safe
    valid = t > 0
    P = np.stack([X * t, Y * t, Z * t], axis=-1)
    rel = P - C
    rad = np.linalg.norm(rel, axis=-1)
    inner, outer = R * 1.30, R * 2.45
    in_ring = valid & (rad > inner) & (rad < outer)
    rings_tex = n.sample(rel[..., 0] * 0.7, rel[..., 1] * 0.7, rel[..., 2] * 0.7,
                         octaves=5, freq=5.5)
    stripe = 0.25 + 0.75 * smoothstep(0.30, 0.80, rings_tex)
    gap = 1.0 - 0.92 * np.exp(-((rad - (inner + outer) * 0.52) / (R * 0.055)) ** 2)
    ring_alpha = in_ring * stripe * gap
    # planet shadow on rings
    proj = dot3(P[..., 0], P[..., 1], P[..., 2], sun)
    closest = np.stack([P[..., 0] * sun[0], P[..., 1] * sun[1], P[..., 2] * sun[2]], axis=-1)
    dist2c = np.linalg.norm(closest - C, axis=-1)
    shadowed = (proj < 0) & (dist2c < R * 1.02)
    # sun-facing side brighter
    ring_light = 0.55 + 0.45 * np.exp(-(np.linalg.norm(P - C, axis=-1) / (R * 3)))
    ring_col = rgb(0.92, 0.80, 0.62) * ((ring_light * np.where(shadowed, 0.18, 1.0))[..., None])
    back_rings = in_ring & (t > D)  # sample is behind the planet centre
    front_rings = in_ring & (t <= D)
    sky = mix(sky, ring_col, (ring_alpha * back_rings)[..., None])

    if np.any(planet > 0.001):
        plat = dot3(X, Y, Z, axis)
        wobble = n.sample(X * 9, Y * 9, Z * 9, octaves=3) * 0.55
        bands = 0.5 + 0.5 * np.sin(plat * 26.0 + wobble * 5.0)
        base = mix(rgb(0.88, 0.66, 0.40), rgb(0.99, 0.91, 0.74),
                   smoothstep(0.15, 0.85, bands)[..., None])
        storm = smoothstep(0.60, 0.90, n.sample(X * 14, Y * 14, Z * 14, octaves=4))
        base = mix(base, rgb(0.62, 0.30, 0.22), (storm * 0.45)[..., None])
        light = np.clip(dot3(X, Y, Z, sun) * 1.05 + 0.30, 0, 1)
        limb = smoothstep(r_ang, r_ang * 0.62, a)
        planet_col = base * (0.10 + 1.05 * light[..., None]) * (0.62 + 0.38 * limb[..., None])
        sky = mix(sky, planet_col, planet[..., None])
        # atmosphere glow at the limb
        atm = np.exp(-((a - r_ang * 0.98) / (r_ang * 0.10)) ** 2)
        sky += rgb(0.30, 0.55, 1.0) * (atm * np.clip(dot3(X, Y, Z, sun) + 0.4, 0, 1) * 0.35)[..., None]

    sky = mix(sky, ring_col, (ring_alpha * front_rings)[..., None])

    # bright foreground star with flare, front-right
    star = normalize((0.80, 0.24, -0.55))
    sa = ang_to(X, Y, Z, star)
    sky += rgb(0.75, 0.88, 1.0) * np.exp(-(sa / 0.012) ** 2)[..., None] * 2.2
    sky += rgb(0.45, 0.65, 1.0) * np.exp(-(sa / 0.06) ** 2)[..., None] * 0.30
    sky += rgb(0.60, 0.50, 1.0) * np.exp(-(sa / 0.25) ** 2)[..., None] * 0.06

    return sky


# ---------------------------------------------------------------------------
# world: BEACH
# ---------------------------------------------------------------------------


def world_beach(ctx):
    X, Y, Z, h, lon = ctx["X"], ctx["Y"], ctx["Z"], ctx["lat"], ctx["lon"]
    n = ctx["noise"]

    sun = normalize((-0.62, 0.135, -0.77))
    sa = ang_to(X, Y, Z, sun)
    slon = math.atan2(sun[2], sun[0])
    dlon = np.abs(np.mod(lon - slon + math.pi, TWO_PI) - math.pi)

    # sky: warm horizon → blue zenith, with a warm halo around the sun
    sky = mix(rgb(1.00, 0.78, 0.52), rgb(0.24, 0.52, 0.86), smoothstep(-0.02, 0.80, h))
    sky = mix(sky, rgb(0.99, 0.55, 0.32), np.exp(-((h - 0.01) / 0.13) ** 2) * 0.55)
    sky += rgb(0.85, 0.45, 0.22) * np.exp(-sa / 0.55)[..., None] * 0.22

    # clouds — sampled on the (unit-sphere) direction field with vertical
    # stretching so they read as a deck of cumulus converging at the horizon.
    above = h > 0.004
    yc = np.maximum(Y, 0.012)
    cx3 = X / yc
    cz3 = Z / yc
    d_c = np.sqrt(cx3 * cx3 + cz3 * cz3)
    persp = 1.0 / (1.0 + d_c * 0.10)          # smaller blobs far away
    field = n.sample(cx3 * 0.85, yc * 2.2, cz3 * 0.85, octaves=5, freq=0.62)
    field2 = n.sample(cx3 * 2.1 + 4.0, yc * 4.0, cz3 * 2.1, octaves=4, freq=0.9)
    mixf = field * 0.62 + field2 * 0.38 * persp
    band = smoothstep(0.006, 0.024, h) * smoothstep(0.55, 0.10, h)
    cmask = smoothstep(0.42, 0.56, mixf) * band
    # brighter undersides near the sun, cool shadow tone elsewhere
    warm = np.exp(-sa / 0.55)
    ccol = mix(rgb(0.60, 0.56, 0.66), rgb(1.0, 0.97, 0.92),
               smoothstep(0.46, 0.70, mixf)[..., None])
    ccol = mix(ccol, rgb(1.0, 0.80, 0.58), (warm * 0.85)[..., None])
    ccol += rgb(0.30, 0.18, 0.08) * np.exp(-sa / 0.28)[..., None]
    sky = mix(sky, ccol, (cmask * 0.97)[..., None])

    # sun
    disc = smoothstep(0.028, 0.020, sa)
    sky = mix(sky, rgb(1.0, 0.98, 0.90), (disc * 0.98)[..., None])
    sky += rgb(1.0, 0.86, 0.60) * np.exp(-sa / 0.10)[..., None] * 0.65
    sky += rgb(1.0, 0.70, 0.42) * np.exp(-sa / 0.32)[..., None] * 0.22

    # distant islands
    island = np.zeros_like(h)
    for ic_lon, ic_w, ic_h, wob in (
        (math.radians(152.0), 0.16, 0.036, 0.7),
        (math.radians(163.0), 0.08, 0.020, 1.3),
        (math.radians(28.0), 0.12, 0.028, 0.9),
        (math.radians(12.0), 0.07, 0.016, 1.7),
    ):
        d = np.abs(np.mod(lon - ic_lon + math.pi, TWO_PI) - math.pi)
        island = np.maximum(island, ic_h * np.exp(-(d / ic_w) ** 2) *
                            (0.8 + 0.2 * np.sin(d * 60 + wob)))
    imask = smoothstep(island + 0.0012, island - 0.0012, h) * smoothstep(-0.02, -0.002, h)
    sky = mix(sky, rgb(0.16, 0.26, 0.34), (imask * 0.88)[..., None])

    # ocean
    below = smoothstep(0.001, -0.003, h)
    depth = smoothstep(0.0, -0.85, h)
    ocean = mix(rgb(0.06, 0.40, 0.52), rgb(0.01, 0.16, 0.34), depth[..., None])
    ocean = mix(ocean, rgb(0.13, 0.05, 0.14), (0.55 * np.exp(-sa / 1.0) * (1 - depth))[..., None])
    wave = n.sample(X, Y * 8.0, Z, octaves=4, freq=11.0, stretch=(1.0, 0.22, 1.0))
    wave2 = n.sample(X, Y * 30.0, Z, octaves=3, freq=5.0, stretch=(1.0, 0.10, 1.0))
    ocean += rgb(0.05, 0.20, 0.22) * (wave * 0.75 + wave2 * 0.35)[..., None]
    spec = smoothstep(0.60, 0.95, n.sample(X, Y * 44, Z, octaves=3, freq=24.0))
    glitter = spec * np.exp(-(dlon / 0.16) ** 2) * np.exp(-np.abs(h) / 0.26) * 3.2
    ocean += rgb(1.0, 0.92, 0.70) * glitter[..., None]
    shore = np.exp(-((h + 0.36) / 0.10) ** 2)
    ocean = mix(ocean, rgb(0.10, 0.52, 0.52), (shore * 0.35)[..., None])
    sky = mix(sky, ocean, below[..., None])

    # beach: sand ring around the nadir
    sand = smoothstep(-0.40, -0.47, h)
    sand_n = n.sample(X, Y, Z, octaves=5, freq=16.0)
    sand_tone = mix(rgb(0.88, 0.75, 0.56), rgb(0.70, 0.57, 0.41),
                    smoothstep(-0.55, -1.35, h)[..., None])
    sand_tone = sand_tone * (0.90 + 0.18 * sand_n[..., None])
    sky = mix(sky, sand_tone, sand[..., None])
    # wet sand strip + foam
    wet = np.exp(-((h + 0.405) / 0.028) ** 2)
    sky = mix(sky, rgb(0.50, 0.42, 0.32), (wet * 0.45)[..., None])
    foam = np.exp(-((h + 0.375) / 0.014) ** 2) * smoothstep(0.30, 0.75, sand_n)
    sky += rgb(0.95, 0.95, 0.88) * (foam * 0.7)[..., None]
    # dune shading + warm bounce
    dune = n.sample(X * 1.4, Y, Z * 1.4, octaves=5, freq=3.2)
    sky = mix(sky, rgb(0.94, 0.80, 0.60), (smoothstep(0.55, 0.85, dune) * sand * 0.35)[..., None])
    sky *= (1.0 - 0.22 * (smoothstep(0.6, 0.9, dune) * sand))[..., None]


    sky *= 1.05
    return sky


# ---------------------------------------------------------------------------
# helpers for painted overlays (cinema seats etc.)
# ---------------------------------------------------------------------------


def project_flat(x, y, z, W, H):
    return dir_to_eq(x, y, z, W, H)


def screen_art(W=1024, H=576):
    """Cinema title card — returns float32 (H, W, 3) in linear-ish sRGB."""
    W, H = int(W), int(H)
    yy, xx = np.mgrid[0:H, 0:W]
    u = xx / W
    v = yy / H
    # deep indigo → violet gradient with a soft violet core glow
    px = np.zeros((H, W, 3), dtype=np.float32)
    px[..., 0] = 0.045 + 0.16 * (v ** 1.6)
    px[..., 1] = 0.012 + 0.03 * (v ** 2.0)
    px[..., 2] = 0.130 + 0.30 * (v ** 1.1)
    core = np.exp(-(((u - 0.5) * 1.55) ** 2 + ((v - 0.46) * 1.15) ** 2) * 4.2)
    px += rgb(0.36, 0.10, 0.55) * core[..., None] * 1.05
    # subtle vertical light shafts
    shafts = (0.5 + 0.5 * np.sin(u * 90.0 + 0.7)) * (0.5 + 0.5 * np.sin(u * 37.0 + 2.1))
    px += rgb(0.08, 0.04, 0.14) * (shafts * (0.25 + 0.75 * v))[..., None] * 0.55
    # thin horizontal rule lines
    for vv in (0.24, 0.78):
        line = np.exp(-(((v - vv) / 0.0022) ** 2))
        px += rgb(0.35, 0.42, 0.60) * line[..., None] * 0.35
    img = Image.fromarray((np.clip(px, 0, 1) * 255).astype(np.uint8))
    draw = ImageDraw.Draw(img, "RGBA")
    font_big = get_font(H * 0.235)
    font_small = get_font(H * 0.052)
    font_tiny = get_font(H * 0.036)
    text = "NEXUS"
    bbox = draw.textbbox((0, 0), text, font=font_big)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    tx, ty = W * 0.5 - tw / 2, H * 0.35 - th / 2
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.text((tx, ty), text, font=font_big, fill=(150, 225, 255, 220))
    glow = glow.filter(ImageFilter.GaussianBlur(H * 0.045))
    img = Image.alpha_composite(img.convert("RGBA"), glow)
    draw = ImageDraw.Draw(img, "RGBA")
    draw.text((tx, ty), text, font=font_big, fill=(248, 253, 255, 255))
    sub = "V  R     E X P E R I E N C E"
    bbox = draw.textbbox((0, 0), sub, font=font_small)
    sw = bbox[2] - bbox[0]
    draw.text((W * 0.5 - sw / 2, H * 0.615), sub, font=font_small,
              fill=(200, 180, 255, 235))
    cap = "A  P R E S E N T A T I O N   B Y   M I G U E L   W E L L I"
    bbox = draw.textbbox((0, 0), cap, font=font_tiny)
    cw = bbox[2] - bbox[0]
    draw.text((W * 0.5 - cw / 2, H * 0.86), cap, font=font_tiny,
              fill=(150, 160, 200, 200))
    # small diamond glyphs
    for dx in (-0.30, 0.30):
        cx = W * (0.5 + dx)
        cy = H * 0.63
        r = H * 0.008
        draw.polygon([(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)],
                     fill=(140, 220, 255, 200))
    img = img.convert("RGB").filter(ImageFilter.GaussianBlur(H * 0.0022))
    return np.asarray(img, dtype=np.float32) / 255.0


def raycast_cinema(X, Y, Z, noise, chunk_rows=None):
    """March the seating heightfield; returns (rgb, mask_seat, mask_floor)."""
    hgt, wid = X.shape
    out_rgb = np.zeros((hgt, wid, 3), dtype=np.float32)
    seat_mask = np.zeros((hgt, wid), dtype=bool)
    floor_mask = np.zeros((hgt, wid), dtype=bool)

    down = Y < 0.02
    if not np.any(down):
        return out_rgb, seat_mask, floor_mask

    steps = 52
    ts = np.geomspace(0.9, 17.0, steps).astype(np.float32)
    hit_t = np.full((hgt, wid), np.inf, dtype=np.float32)
    for ti in ts:
        active = (hit_t == np.inf) & down
        if not np.any(active):
            break
        px = X * ti
        py = Y * ti
        pz = Z * ti
        sh = seat_height(px, pz)
        inside = active & (py < (sh - EYE_H))
        hit_t = np.where(inside, ti, hit_t)
    # bisection refinement for crisper silhouettes
    t_hi = hit_t
    t_lo = np.maximum(hit_t - (ts[1] - ts[0]), 0.4)
    for _ in range(4):
        tm = (t_lo + t_hi) * 0.5
        inside = (Y * tm) < (seat_height(X * tm, Z * tm) - EYE_H)
        t_hi = np.where(inside, tm, t_hi)
        t_lo = np.where(inside, t_lo, tm)
    hit = np.isfinite(t_hi)
    px = X * np.where(hit, t_hi, 1.0)
    py = Y * np.where(hit, t_hi, 1.0)
    pz = Z * np.where(hit, t_hi, 1.0)

    # height field normal via finite differences
    eps = 0.045
    h0 = seat_height(px, pz)
    hx = seat_height(px + eps, pz) - seat_height(px - eps, pz)
    hz = seat_height(px, pz + eps) - seat_height(px, pz - eps)
    nx = -hx / (2 * eps)
    nz = -hz / (2 * eps)
    ny = np.ones_like(nx)
    ln = np.sqrt(nx * nx + ny * ny + nz * nz) + 1e-6
    nx, ny, nz = nx / ln, ny / ln, nz / ln

    # lighting: key light from the screen, cool ambient, warm side sconces
    sx_, sy_, sz_ = 0.0, 0.55, -4.0
    lx = sx_ - px
    ly = (sy_ + EYE_H) - (py + EYE_H)
    lz = sz_ - pz
    ll = np.sqrt(lx * lx + ly * ly + lz * lz) + 1e-6
    lx, ly, lz = lx / ll, ly / ll, lz / ll
    diff = np.clip(nx * lx + ny * ly + nz * lz, 0.0, 1.0)
    falloff = 1.0 / (1.0 + 0.055 * t_hi * t_hi)
    key = diff * (0.35 + 1.25 * falloff)

    amb = 0.030 + 0.075 * np.clip(ny, 0, 1)
    # warm sconce counter light from both sides
    warm = np.clip(nx * 0.8 + ny * 0.35 + 0.25, 0, 1) * np.exp(-t_hi * 0.10) * 0.16

    base = rgb(0.20, 0.020, 0.038)
    col = base[None, None, :] * (amb[..., None] + key[..., None])
    col += rgb(1.0, 0.55, 0.24) * warm[..., None]
    # screen rim light on top faces (violet)
    rim = np.clip(ny, 0, 1) ** 2 * (0.25 + 0.75 * falloff)
    col += rgb(0.30, 0.19, 0.55) * (rim * 0.30)[..., None]
    # distance darkening
    col *= np.exp(-t_hi * 0.035)[..., None]

    out_rgb = np.where(hit[..., None], col, out_rgb)
    seat_mask = hit

    # floor & aisle for rays that miss the seating
    floor_only = down & ~hit
    if np.any(floor_only):
        tf = np.where(floor_only, EYE_H / np.maximum(-Y, 1e-4), 0.0)
        fx = X * tf
        fz = Z * tf
        carpet = noise.sample(fx * 2.0, np.zeros_like(fx), fz * 2.0, octaves=4, freq=3.0)
        fcol = rgb(0.030, 0.0125, 0.021) * (0.65 + 0.55 * carpet[..., None])
        fcol *= (0.30 + 0.70 * np.exp(-tf * 0.11))[..., None]
        # carpet runner down the centre aisle
        aisle = (np.abs(fx) < BLOCK_INNER) & (tf < 16.0)
        fcol = np.where(aisle[..., None], fcol * 1.6 + rgb(0.012, 0.004, 0.018), fcol)
        # small guide lights along the aisle
        for i, lz0 in enumerate(-np.arange(2.0, 15.0, 1.4)):
            for lxx in (-0.42, 0.42):
                dl = np.sqrt((fx - lxx) ** 2 + (fz - lz0) ** 2)
                g = np.exp(-(dl / 0.10) ** 2) * 1.8 + np.exp(-(dl / 0.55) ** 2) * 0.22
                fcol += rgb(1.0, 0.62, 0.26) * (g * (dl < 3.0))[..., None]
        fcol = np.where(aisle[..., None], fcol, fcol * 0.85)
        out_rgb = np.where(floor_only[..., None], fcol, out_rgb)
        floor_mask = floor_only
    return out_rgb, seat_mask, floor_mask


def world_cinema(ctx):
    X, Y, Z, h = ctx["X"], ctx["Y"], ctx["Z"], ctx["lat"]
    n = ctx["noise"]
    eye = 1.55

    sky = mix(rgb(0.026, 0.022, 0.040), rgb(0.042, 0.044, 0.078), smoothstep(-0.4, 0.9, h))
    wall = n.sample(X, Y, Z, octaves=4, freq=4.0)
    sky *= (0.75 + 0.50 * wall)[..., None]
    panel = 0.5 + 0.5 * np.sin(Z * 24.0) * np.sin(Y * 16.0)
    walls = smoothstep(0.85, 0.55, np.abs(Y))
    sky *= (1.0 - 0.24 * (panel * walls))[..., None]
    ceil = smoothstep(0.40, 0.95, h)
    coffer = 0.5 + 0.5 * np.sin(X * 16.0) * np.sin(Z * 16.0)
    sky *= (1.0 - 0.16 * ceil * coffer)[..., None]

    # ------- screen (flat plane dead ahead) -------
    art = ctx["screen_art"]
    if art is not None:
        ah, aw = art.shape[:2]
        zf = -Z
        front = zf > 0.10
        tt = 4.0 / np.maximum(zf, 1e-3)
        sx = X * tt
        sy = Y * tt
        sw, sh = 5.4, 3.04
        byy = 0.78
        bx = sx / sw + 0.5
        by = 0.5 - (sy - byy) / sh
        inside = front & (bx > 0) & (bx < 1) & (by > 0) & (by < 1)
        ix = np.clip((bx * (aw - 1)), 0, aw - 1).astype(np.int64)
        iy = np.clip((by * (ah - 1)), 0, ah - 1).astype(np.int64)
        sky = mix(sky, art[iy, ix] * 1.1, inside[..., None])
        bez = front & (bx > -0.014) & (bx < 1.014) & (by > -0.02) & (by < 1.02) & ~inside
        sky = mix(sky, rgb(0.004, 0.004, 0.007), (bez * 0.96)[..., None])
        sdir = normalize((0.0, 0.12, -1.0))
        sa = ang_to(X, Y, Z, sdir)
        sky += rgb(0.34, 0.18, 0.55) * np.exp(-(sa / 0.42) ** 2)[..., None] * 0.80
        sky += rgb(0.10, 0.18, 0.36) * np.exp(-(sa / 1.15) ** 2)[..., None] * 0.32

    # ------- red velvet curtain walls at the sides -------
    for cdir in (normalize((-0.96, 0.08, -0.28)), normalize((0.96, 0.08, -0.28))):
        a = ang_to(X, Y, Z, cdir)
        curtain = np.exp(-(a / 0.40) ** 2)
        lon_cur = np.arctan2(Z, X)
        fold = 0.55 + 0.45 * np.sin(lon_cur * 170.0 + h * 1.5)
        fold *= 0.55 + 0.45 * n.sample(X * 4, Y * 4, Z * 4, octaves=3)
        sky = mix(sky, rgb(0.17, 0.010, 0.032) * fold[..., None],
                  (curtain * 0.72)[..., None])

    # ------- ceiling spotlights / wall sconces -------
    for lx in (-1.0, 1.0):
        for lz in (-2.2, -5.4, -8.6, -11.8):
            d = normalize((lx * 2.9, 1.5, lz))
            a = ang_to(X, Y, Z, d)
            sky += rgb(0.62, 0.38, 0.16) * np.exp(-(a / 0.045) ** 2)[..., None] * 1.0
            sky += rgb(0.22, 0.13, 0.05) * np.exp(-(a / 0.20) ** 2)[..., None] * 0.30
    for sx_, sz_ in ((-1.0, -6.2), (1.0, -6.2), (-1.0, -11.2), (1.0, -11.2)):
        d = normalize((sx_ * 3.2, 0.30, sz_))
        a = ang_to(X, Y, Z, d)
        sky += rgb(0.95, 0.52, 0.18) * np.exp(-(a / 0.06) ** 2)[..., None] * 0.80

    # ------- carpet floor (flat plane below the horizon) -------
    down = Y < -0.002
    if np.any(down):
        tf = np.where(down, eye / np.maximum(-Y, 1e-4), 0.0)
        fx = X * tf
        fz = Z * tf
        carpet = n.sample(fx * 2.0, np.zeros_like(fx), fz * 2.0, octaves=4, freq=3.0)
        fcol = rgb(0.030, 0.0125, 0.021) * (0.65 + 0.55 * carpet[..., None])
        fcol *= (0.26 + 0.74 * np.exp(-tf * 0.12))[..., None]
        aisle = np.abs(fx) < 1.05
        fcol = np.where(aisle[..., None], fcol * 1.55 + rgb(0.012, 0.004, 0.018), fcol)
        sky = np.where(down[..., None], fcol, sky)

    # ------- seating (painted in the overlay pass) — keep floor beneath -------
    sky = mix(sky, rgb(0.012, 0.006, 0.010), (smoothstep(-0.30, -0.42, h) * 0.55)[..., None])
    return sky


def paint_beach_palms(img, W, H):
    """Palm silhouettes standing on the sand, with dark trunk/leaf contrast."""
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay, "RGBA")
    rng = np.random.default_rng(9)
    base_line = int(H * (0.5 + 0.46 / math.pi))
    specs = [
        (188.0, 0.86, -0.20, 1),
        (201.0, 0.60, 0.12, -1),
        (214.0, 0.38, -0.06, 1),
        (322.0, 0.78, 0.16, -1),
        (334.0, 0.52, -0.12, 1),
        (346.0, 0.34, 0.05, -1),
        (10.0, 0.44, 0.06, -1),
    ]
    dark = (18, 15, 16, 255)
    for lon_deg, hf, lean, flip in specs:
        x = int((lon_deg / 360.0) % 1.0 * W)
        height = int(H * 0.50 * hf)
        base_y = base_line + int(H * 0.03 * hf)
        top_x = x + int(lean * height)
        segs = 26
        prev = (x, base_y)
        for i in range(1, segs + 1):
            t = i / segs
            px = int(x + (top_x - x) * (t ** 1.35))
            py = int(base_y - height * t)
            tw = max(2, int(W * (0.0042 * (1 - 0.52 * t))))
            d.line([prev, (px, py)], fill=dark, width=tw)
            prev = (px, py)
        for k in range(9):
            ang = math.radians(-96 + (k - 4) * 26 + rng.normal(0, 4))
            L = height * (0.21 + 0.06 * rng.random())
            ex = prev[0] + math.cos(ang) * L * flip
            ey = prev[1] + math.sin(ang) * L * 0.72
            mx = prev[0] + math.cos(ang) * L * flip * 0.55
            my = prev[1] + math.sin(ang) * L * 0.55 - L * 0.18
            d.line([prev, (mx, my)], fill=dark, width=max(2, int(W * 0.0048)))
            d.line([(mx, my), (ex, ey)], fill=dark, width=max(1, int(W * 0.0032)))
            for j in range(1, 6):
                tt = j / 6
                lx = mx + (ex - mx) * tt
                ly = my + (ey - my) * tt + L * 0.22 * tt * tt
                sw_ = L * 0.12 * (1 - tt)
                d.line([(lx, ly), (lx + sw_ * flip * 0.6, ly + sw_ * 0.5)],
                       fill=dark, width=max(1, int(W * 0.0015)))
                d.line([(lx, ly), (lx - sw_ * flip * 0.5, ly + sw_ * 0.5)],
                       fill=dark, width=max(1, int(W * 0.0015)))
        for k in range(3):
            cx0 = prev[0] + rng.normal(0, W * 0.002)
            cy0 = prev[1] + W * 0.004 + k * W * 0.001
            r = max(2, int(W * 0.0021))
            d.ellipse([cx0 - r, cy0 - r, cx0 + r, cy0 + r], fill=dark)
    overlay = overlay.filter(ImageFilter.GaussianBlur(max(0.4, W / 4000.0)))
    return Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")


def paint_cinema_overlay(img, W, H, ss=2):
    """Two seating blocks of a private screening room, drawn with supersampling."""
    Ws, Hs = W * ss, H * ss
    overlay = Image.new("RGBA", (Ws, Hs), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay, "RGBA")
    eye = 1.55
    pitch = 0.92
    seat_w = 0.58
    inner, outer = 1.15, 4.9

    def proj(x, y, z):
        lon = math.atan2(z, x)
        lat = math.asin(max(-1.0, min(1.0, y / math.sqrt(x * x + y * y + z * z))))
        return (lon / TWO_PI % 1.0) * Ws, (0.5 - lat / math.pi) * Hs

    def quad(a, b, c, e, fill):
        pts = [a, b, c, e]
        xs = [p[0] for p in pts]
        if max(xs) - min(xs) > Ws * 0.6:
            d.polygon(pts, fill=fill)
            return
        for sh in (-Ws, 0, Ws):
            if max(xs) + sh < 0 or min(xs) + sh > Ws:
                continue
            d.polygon([(x + sh, y) for x, y in pts], fill=fill)

    rows = 10
    for r in range(rows - 1, -1, -1):
        z = -(2.55 + r * pitch)
        floor = r * 0.14 - eye
        back_h = 1.04
        tone = 20 + int(r * 3.5)
        seats_per_block = int((outer - inner) / seat_w)
        for side in (-1, 1):
            for i in range(seats_per_block):
                x0 = side * (inner + i * seat_w)
                x1 = x0 + side * (seat_w - 0.05)
                lo, hi = min(x0, x1), max(x0, x1)
                bl = proj(lo, floor + 0.42, z)
                br = proj(hi, floor + 0.42, z)
                tr = proj(hi, floor + back_h, z - 0.10)
                tl = proj(lo, floor + back_h, z - 0.10)
                quad(bl, br, tr, tl, (tone, int(tone * 0.52), int(tone * 0.66), 255))
                quad(tl, tr, (tr[0], tr[1] + 2 * ss), (tl[0], tl[1] + 2 * ss),
                     (tone + 55, int(tone * 0.72), tone + 62, 235))
                cb = proj(lo, floor + 0.40, z + 0.50)
                cr = proj(hi, floor + 0.40, z + 0.50)
                quad(bl, br, cr, cb, (int(tone * 0.9), int(tone * 0.45), int(tone * 0.58), 255))
                am = proj(hi, floor + 0.62, z + 0.06)
                am2 = proj(hi, floor + 0.62, z + 0.36)
                quad(am, am2, (am2[0], am2[1] + 2 * ss), (am[0], am[1] + 2 * ss),
                     (tone + 22, int(tone * 0.6), tone + 26, 220))
    overlay = overlay.filter(ImageFilter.GaussianBlur(0.6 * ss))
    overlay = overlay.resize((W, H), Image.LANCZOS)
    out = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

    lights = Image.new("RGBA", (Ws, Hs), (0, 0, 0, 0))
    dl = ImageDraw.Draw(lights, "RGBA")
    for z in -np.arange(2.4, 12.5, 1.35):
        for x in (-1.02, 1.02):
            px_, py_ = proj(x, -eye + 0.03, z)
            rr = max(1.4 * ss, (0.06 / abs(z)) * Ws * 0.10)
            dl.ellipse([px_ - rr, py_ - rr * 0.45, px_ + rr, py_ + rr * 0.45],
                       fill=(255, 170, 84, 205))
    lights = lights.filter(ImageFilter.GaussianBlur(max(1.0, Ws / 900.0)))
    lights = lights.resize((W, H), Image.LANCZOS)
    out = Image.alpha_composite(out.convert("RGBA"), lights).convert("RGB")
    return out


# ---------------------------------------------------------------------------
# world: VIRTUAL
# ---------------------------------------------------------------------------


def world_virtual(ctx):
    X, Y, Z, h = ctx["X"], ctx["Y"], ctx["Z"], ctx["lat"]
    n = ctx["noise"]

    sky = mix(rgb(1.00, 0.20, 0.52), rgb(0.10, 0.012, 0.24), smoothstep(-0.01, 0.88, h))
    sky = mix(rgb(0.46, 0.04, 0.58), sky, smoothstep(-0.03, 0.40, h))
    sky += rgb(0.15, 0.02, 0.25) * np.exp(-((h - 0.55) / 0.35) ** 2)[..., None] * 0.3

    sun = normalize((0.0, 0.135, -0.99))
    sa = ang_to(X, Y, Z, sun)
    sr = 0.19
    disc_mask = smoothstep(sr, sr * 0.93, sa)
    grad = smoothstep(0.015, 0.20, h)
    sun_col = mix(rgb(1.0, 0.88, 0.38), rgb(1.0, 0.22, 0.55), grad[..., None])
    slit_phase = (h - 0.015) * 105.0
    slit = smoothstep(0.15, 0.45, np.sin(slit_phase) * 0.5 + 0.5)
    disc_mask = disc_mask * (0.30 + 0.70 * slit)
    sky = mix(sky, sun_col, disc_mask[..., None])
    sky += rgb(1.0, 0.28, 0.55) * np.exp(-sa / 0.17)[..., None] * 0.50
    sky += rgb(0.60, 0.16, 0.98) * np.exp(-sa / 0.55)[..., None] * 0.16

    # sparse stars
    stars = smoothstep(0.986, 1.0, n.sample(X, Y, Z, octaves=2, freq=42.0))
    sky += rgb(0.75, 0.80, 1.0) * (stars * smoothstep(0.06, 0.30, h) * 1.6)[..., None]

    # wireframe triangles
    tl = np.arctan2(Z, X)
    tb = np.arcsin(np.clip(Y, -1, 1))

    def tri(cx, cy, size, rot, thick=0.045):
        u = np.cos(rot) * (tl - cx) - np.sin(rot) * (tb - cy)
        v = np.sin(rot) * (tl - cx) + np.cos(rot) * (tb - cy)
        # distance to an equilateral triangle outline (Inigo Quilez)
        px = np.abs(u) - size * 0.5
        py = np.abs(v) - size * 0.5
        k = 0.8660254
        d = np.maximum(px * k + py * 0.5, py)
        return np.exp(-((d) / (size * thick)) ** 2)

    for cx, cy, sz, rot in ((2.15, 0.46, 0.13, 0.25), (2.72, 0.30, 0.075, 1.05),
                            (-2.40, 0.52, 0.12, 0.65), (-1.55, 0.75, 0.085, 0.15),
                            (1.05, 0.80, 0.06, 0.9)):
        sky += rgb(0.18, 0.98, 1.0) * (tri(cx, cy, sz, rot) * 1.6)[..., None]

    # horizon glow
    sky += rgb(0.25, 1.0, 1.0) * np.exp(-(np.abs(h - 0.0) / 0.0045) ** 2)[..., None] * 0.9

    # neon perspective grid below horizon (anti-aliased by evaluating a small
    # set of sub-ray samples and averaging coverage)
    ground = h < -0.0015
    yy = np.maximum(-Y, 1e-4)
    tt = 1.55 / yy
    px = X * tt
    pz = Z * tt
    line_cov = np.zeros_like(px)
    samples = 5
    for k in range(samples):
        off = (k + 0.5) / samples - 0.5
        fw = (0.012 * tt + 0.006) * (1.0 + off * 0.35)
        lx = np.abs(px - np.round(px))
        lz = np.abs(pz - np.round(pz))
        lx = np.minimum(lx + off * 0.0008, 0.5)
        lz = np.minimum(lz + off * 0.0008, 0.5)
        line_cov += smoothstep(fw, 0.0, lx) + smoothstep(fw, 0.0, lz)
    line_cov = np.clip(line_cov / samples, 0, 1)
    grid = line_cov
    fade = np.exp(-(tt / 26.0) ** 1.15)
    grid = grid * fade * ground
    gcol = mix(rgb(1.0, 0.14, 0.55), rgb(0.15, 0.95, 1.0),
               smoothstep(-0.06, -0.55, h)[..., None])
    sky = mix(sky, rgb(0.030, 0.004, 0.075), ground[..., None])
    sky += gcol * (grid * 1.05)[..., None]
    sky += rgb(0.95, 0.14, 0.55) * np.exp(-(np.abs(h) / 0.07))[..., None] * 0.22
    return sky


SHADERS = {
    "night": world_night,
    "space": world_space,
    "beach": world_beach,
    "cinema": world_cinema,
    "virtual": world_virtual,
}


# ---------------------------------------------------------------------------
# post
# ---------------------------------------------------------------------------


def tonemap(x):
    x = np.maximum(x, 0.0)
    k = 0.80
    hi = k + (1.0 - k) * np.tanh((x - k) / (1.0 - k) * 0.9) / math.tanh(0.9)
    return np.clip(np.where(x > k, hi, x), 0.0, 1.0)


def finish(rgb_img, seed=1, exposure=1.0, saturation=1.05, contrast=1.03):
    x = tonemap(rgb_img * exposure)
    luma = (x[..., 0] * 0.2126 + x[..., 1] * 0.7152 + x[..., 2] * 0.0722)[..., None]
    x = np.clip(luma + (x - luma) * saturation, 0, 1)
    x = np.clip((x - 0.5) * contrast + 0.5, 0, 1)
    rng = np.random.default_rng(seed)
    grain = rng.normal(0.0, 0.0028, size=(x.shape[0], x.shape[1], 1)).astype(np.float32)
    return (np.clip(x + grain, 0, 1) * 255.0 + 0.5).astype(np.uint8)


PINES_WORLDS = {"night"}


def make_pines(W, H, seed=5):
    """Pine silhouettes standing on the horizon; returns an (H, W, 1) darkening mask."""
    mask = Image.new("L", (W, H), 255)
    d = ImageDraw.Draw(mask)
    rng = np.random.default_rng(seed)
    horizon = int(H * 0.502)
    clusters = [(math.radians(196.0), 20, 13.0), (math.radians(344.0), 16, 10.0),
                (math.radians(118.0), 8, 8.0), (math.radians(60.0), 5, 6.0)]
    for base_lon, count, spread in clusters:
        for i in range(count):
            lon = base_lon + math.radians(rng.normal(0, spread))
            size_r = rng.random() ** 1.5
            height = int(H * (0.022 + 0.078 * size_r))
            x = int((lon / TWO_PI) % 1.0 * W)
            y = horizon + 2
            top = y - height
            trunk_w = max(1, int(W * 0.0007 * (0.5 + size_r)))
            d.rectangle([x - trunk_w, top + int(height * 0.5), x + trunk_w, y], fill=0)
            tiers = 7
            for t in range(tiers):
                frac = t / tiers
                ty = top + int(height * frac * 0.72)
                half_w = max(2, int(W * (0.0042 + 0.010 * size_r) * (0.28 + 0.82 * frac)))
                th = max(3, int(height * 0.20))
                d.polygon([(x - half_w, ty), (x + half_w, ty), (x, ty + th)], fill=0)
    mask = mask.filter(ImageFilter.GaussianBlur(max(0.8, W / 3000.0)))
    arr = np.asarray(mask, dtype=np.float32) / 255.0
    arr = 0.10 + 0.90 * arr
    return arr[..., None].astype(np.float32)


def render_world(world_id, W, H, preview=False):
    meta = WORLDS[world_id]
    t0 = time.time()
    seed = meta["seed"]
    noise = Noise(seed)

    extras = {}
    if world_id == "cinema":
        extras["screen_art"] = screen_art(1024, 576)
    if world_id == "night":
        extras["noise2"] = noise2d_periodic(128, 512, 91, octaves=4, base=4, persistence=0.6)
        extras["noise2b"] = noise2d_periodic(128, 512, 92, octaves=4, base=7, persistence=0.58)
        extras["pines"] = make_pines(W, H)

    rows = np.arange(H, dtype=np.float32) + 0.5
    lat_row = (0.5 - rows / H) * np.pi
    cols = np.arange(W, dtype=np.float32) + 0.5
    phi = (cols / W) * TWO_PI
    cos_lat = np.cos(lat_row).astype(np.float32)
    sin_lat = np.sin(lat_row).astype(np.float32)
    cos_phi = np.cos(phi).astype(np.float32)
    sin_phi = np.sin(phi).astype(np.float32)

    img = np.zeros((H, W, 3), dtype=np.float32)
    chunk = 96 if W >= 4096 else 128
    shader = SHADERS[world_id]
    big = W * H > 700_000
    for y0 in range(0, H, chunk):
        y1 = min(H, y0 + chunk)
        X = np.outer(cos_lat[y0:y1], cos_phi).astype(np.float32)
        Z = np.outer(cos_lat[y0:y1], sin_phi).astype(np.float32)
        Y = np.repeat(sin_lat[y0:y1, None], W, axis=1)
        LON = np.repeat(phi[None, :], y1 - y0, axis=0)
        LAT = np.repeat(lat_row[y0:y1, None], W, axis=1)
        ctx = {"X": X, "Y": Y, "Z": Z, "lat": LAT, "lon": LON, "noise": noise,
               "row0": y0, "row1": y1}
        ctx.update(extras)
        img[y0:y1] = shader(ctx)
        if big:
            sys.stdout.write(f"\r  {world_id}: {y1}/{H}  {time.time()-t0:5.1f}s")
            sys.stdout.flush()
    if big:
        print()

    # star fields
    if world_id == "night":
        img += star_layer(W, H, seed + 1, 9000 if W >= 4096 else 1100,
                          band_normal=(0.35, 0.55, -0.75), band_boost=2.0,
                          min_elevation=0.02) * 0.85
    elif world_id == "space":
        img += star_layer(W, H, seed + 1, 20000 if W >= 4096 else 2200,
                          band_normal=(-0.40, 0.64, -0.66), band_boost=3.2) * 1.10
    elif world_id == "virtual":
        img += star_layer(W, H, seed + 1, 700 if W >= 4096 else 130,
                          min_elevation=0.03) * 0.65

    exposure = {"night": 1.25, "space": 1.05, "beach": 1.0,
                "cinema": 1.55, "virtual": 1.05}[world_id]
    out = finish(img, seed=seed, exposure=exposure)

    pil = Image.fromarray(out, "RGB")
    if world_id == "cinema":
        pil = paint_cinema_overlay(pil, W, H)
        bloom = pil.filter(ImageFilter.GaussianBlur(W / 900.0))
        pil = Image.blend(pil, bloom, 0.14)
        warm = pil.filter(ImageFilter.GaussianBlur(W / 260.0))
        pil = Image.blend(pil, warm, 0.20)
    elif world_id == "beach":
        pil = paint_beach_palms(pil, W, H)
        bloom = pil.filter(ImageFilter.GaussianBlur(W / 1200.0))
        pil = Image.blend(pil, bloom, 0.14)
    elif world_id in ("space", "virtual"):
        bloom = pil.filter(ImageFilter.GaussianBlur(W / 1200.0))
        pil = Image.blend(pil, bloom, 0.16)
    elif world_id == "night":
        bloom = pil.filter(ImageFilter.GaussianBlur(W / 1400.0))
        pil = Image.blend(pil, bloom, 0.10)

    if preview:
        prev = pil.resize((1440, 720), Image.LANCZOS)
        path = os.path.join(OUT_DIR, f"_preview_{world_id}.jpg")
        prev.save(path, quality=90, progressive=True)
    else:
        path = os.path.join(OUT_DIR, f"{world_id}.jpg")
        pil.save(path, quality=90, progressive=True, optimize=True)
        lq = pil.resize((1024, 512), Image.LANCZOS)
        lq.save(os.path.join(OUT_DIR, f"{world_id}_lq.jpg"),
                quality=80, progressive=True, optimize=True)
        make_thumb(pil, world_id)
        print(f"  -> {path} ({os.path.getsize(path)/1e6:.2f} MB)")
    print(f"  {world_id} done in {time.time() - t0:.1f}s")
    return pil


def make_thumb(pil, world_id, out_w=640, out_h=360):
    W, H = pil.size
    lon_c = WORLDS[world_id]["feature_lon"]
    fov_lon = math.radians(106)
    fov_lat = math.radians(58)
    u0 = (lon_c - fov_lon / 2) / TWO_PI % 1.0
    u1 = u0 + fov_lon / TWO_PI
    v0 = 0.5 - fov_lat / math.pi
    v1 = 0.5 + fov_lat / math.pi
    arr = np.asarray(pil)
    x0, x1 = int(u0 * W), int(u1 * W)
    y0, y1 = int(v0 * H), int(v1 * H)
    if x1 <= W:
        crop = arr[y0:y1, x0:x1]
    else:
        crop = np.concatenate([arr[y0:y1, x0:], arr[y0:y1, :x1 - W]], axis=1)
    thumb = Image.fromarray(crop).resize((out_w, out_h), Image.LANCZOS)
    yy, xx = np.mgrid[0:out_h, 0:out_w].astype(np.float32)
    nx = (xx / out_w - 0.5) * 2
    ny = (yy / out_h - 0.5) * 2
    vig = 1.0 - 0.20 * np.clip((nx ** 2 + ny ** 2) * 0.55, 0, 1)
    grad = 1.0 - 0.32 * np.clip((yy / out_h - 0.55) / 0.45, 0, 1)
    t = np.asarray(thumb, dtype=np.float32) * (vig * grad)[..., None]
    os.makedirs(THUMB_DIR, exist_ok=True)
    Image.fromarray(np.clip(t, 0, 255).astype(np.uint8)).save(
        os.path.join(THUMB_DIR, f"{world_id}.jpg"), quality=88, progressive=True)
    print(f"  -> thumb {world_id}.jpg")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", action="store_true")
    ap.add_argument("--only", default=None)
    ap.add_argument("--width", type=int, default=4096)
    ap.add_argument("--height", type=int, default=2048)
    args = ap.parse_args()
    os.makedirs(OUT_DIR, exist_ok=True)
    worlds = [args.only] if args.only else list(WORLDS.keys())
    for wid in worlds:
        if wid not in WORLDS:
            print(f"Unknown world: {wid}")
            continue
        print(f"Rendering {wid} ...")
        if args.preview:
            render_world(wid, 1440, 720, preview=True)
        else:
            render_world(wid, args.width, args.height, preview=False)


if __name__ == "__main__":
    main()
