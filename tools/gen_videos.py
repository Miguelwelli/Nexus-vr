#!/usr/bin/env python3
"""
Generate the two bundled 360° demo clips (equirectangular, H.264 MP4).

Both are rendered procedurally so the repository stays self-contained and the
output is small enough to ship with the web app (a few hundred KB each).

    python3 tools/gen_videos.py

Requires: numpy, imageio-ffmpeg.
"""

import os
import subprocess

import numpy as np
import imageio_ffmpeg

W, H = 1280, 640          # 2:1 equirectangular
FPS = 20
SECONDS = 8
OUT = os.path.join(os.path.dirname(__file__), "..", "assets", "video")


def ffmpeg():
    return imageio_ffmpeg.get_ffmpeg_exe()


def encode(name, frames_iter, frames_total):
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, name)
    cmd = [
        ffmpeg(), "-y", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24",
        "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
        "-c:v", "libx264", "-preset", "slow", "-crf", "30",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        "-an", path,
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for i, frame in enumerate(frames_iter):
        proc.stdin.write(frame.astype(np.uint8).tobytes())
        if i % 20 == 0:
            print(f"  {name}: {i}/{frames_total}", flush=True)
    proc.stdin.close()
    proc.wait()
    if proc.returncode:
        raise SystemExit(f"ffmpeg failed for {name}")
    print(f"  -> {path} ({os.path.getsize(path) / 1024:.0f} KB)")


# ---------------------------------------------------------------- helpers

def lat_lon():
    lon = (np.arange(W) / W) * 2 * np.pi - np.pi          # -pi..pi
    lat = (np.arange(H) / H) * np.pi - np.pi / 2          # -pi/2..pi/2
    return np.meshgrid(lon, lat)


def smoothstep(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


def starfield(seed, count, size=1.0):
    rng = np.random.default_rng(seed)
    lon = rng.uniform(-np.pi, np.pi, count)
    lat = np.arcsin(rng.uniform(-0.98, 0.98, count))
    mag = rng.uniform(0.25, 1.0, count) ** 2.2
    tint = rng.uniform(0.82, 1.0, count)
    return lon, lat, mag, tint


def add_stars(img, stars, lon_g, lat_g, rot=0.0, gain=1.0):
    lon, lat, mag, tint = stars
    lon = lon + rot
    # paint each star as a soft 2x2 gaussian-ish blob
    px = ((lon + np.pi) / (2 * np.pi) * W).astype(int) % W
    py = ((np.pi / 2 - lat) / np.pi * H).astype(int).clip(0, H - 1)
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            w = 1.0 if (dx == 0 and dy == 0) else 0.35
            np.add.at(img[..., 0], ((py + dy) % H, (px + dx) % W), mag * tint * w * gain)
            np.add.at(img[..., 1], ((py + dy) % H, (px + dx) % W), mag * w * gain)
            np.add.at(img[..., 2], ((py + dy) % H, (px + dx) % W), mag * w * gain * 1.05)


def nebula(lon_g, lat_g, seed):
    rng = np.random.default_rng(seed)
    total = np.zeros((H, W))
    for _ in range(7):
        cl = rng.uniform(-np.pi, np.pi)
        cb = rng.uniform(-0.7, 0.7)
        sx = rng.uniform(0.25, 0.8)
        sy = rng.uniform(0.15, 0.45)
        amp = rng.uniform(0.4, 1.0)
        d = ((lon_g - cl) / sx) ** 2 + ((lat_g - cb) / sy) ** 2
        total += amp * np.exp(-d * 1.6)
    return total


# ---------------------------------------------------------------- space

def space_frames():
    lon_g, lat_g = lat_lon()
    stars = starfield(7, 2600)
    neb = nebula(lon_g, lat_g, 11)
    neb2 = nebula(lon_g + 0.8, lat_g - 0.2, 23)
    base = np.zeros((H, W, 3), np.float32)
    # deep space vertical gradient
    v = (lat_g / (np.pi / 2) + 1) / 2
    base[..., 2] += 0.045 + v * 0.02
    base[..., 0] += 0.02 + v * 0.012
    neb = smoothstep(neb * 0.5) ** 1.5
    neb2 = smoothstep(neb2 * 0.45) ** 1.8
    base[..., 0] += neb * 0.32 + neb2 * 0.20
    base[..., 1] += neb * 0.10 + neb2 * 0.26
    base[..., 2] += neb * 0.42 + neb2 * 0.55

    total = FPS * SECONDS
    for i in range(total):
        t = i / total
        frame = base.copy()
        add_stars(frame, stars, lon_g, lat_g, rot=t * 2 * np.pi, gain=0.85)
        # a soft planet limb drifting through the lower half
        planet_lon = 0.6 + t * 2 * np.pi * 0.5
        d = np.sqrt(((lon_g - planet_lon) * np.cos(lat_g)) ** 2 + (lat_g + 0.45) ** 2)
        disc = smoothstep((0.60 - d) / 0.03)
        rim = np.exp(-((d - 0.60) / 0.035) ** 2)
        frame[..., 0] += disc * 0.05 + rim * 0.20
        frame[..., 1] += disc * 0.09 + rim * 0.44
        frame[..., 2] += disc * 0.14 + rim * 0.62
        yield np.clip(frame, 0, 1) * 255


# ---------------------------------------------------------------- aurora

def aurora_frames():
    lon_g, lat_g = lat_lon()
    stars = starfield(31, 1500)
    base = np.zeros((H, W, 3), np.float32)

    # gradient sky: near-black zenith → faint teal glow at the horizon
    up = np.clip((lat_g + 0.10) / 0.9, 0, 1)
    base[..., 0] += 0.012 + (1 - up) * 0.040
    base[..., 1] += 0.020 + (1 - up) * 0.100
    base[..., 2] += 0.038 + (1 - up) * 0.120

    total = FPS * SECONDS
    for i in range(total):
        t = i / total * 2 * np.pi
        frame = base.copy()
        add_stars(frame, stars, lon_g, lat_g, gain=0.55)

        # Three curtains, each with its own band of latitude and wobble.
        for k, (amp, band, speed, hue) in enumerate((
            (0.62, 0.34, 1.0, (0.08, 0.95, 0.50)),
            (0.46, 0.52, -1.3, (0.16, 0.68, 0.98)),
            (0.30, 0.70, 1.7, (0.46, 0.34, 0.98)),
        )):
            # slow large-scale undulation across longitude
            warp = (
                np.sin(lon_g * 2.1 + t * speed + k * 1.7) * 0.075
                + np.sin(lon_g * 0.7 - t * speed * 0.6 + k) * 0.055
                + np.sin(lon_g * 4.6 + t * speed * 1.4) * 0.020
            )
            centre = band + warp
            width = 0.20 + 0.06 * np.sin(lon_g * 1.3 + t * 0.7 + k)
            curtain = np.exp(-((lat_g - centre) / width) ** 2)

            # soft vertical striations that drift along the curtain
            stripe = (
                0.72
                + 0.18 * np.sin(lon_g * 11 + warp * 7 + t * 1.5 + k * 2)
                + 0.10 * np.sin(lon_g * 23 + warp * 4 + t * 2.1)
            )
            curtain = curtain * stripe * amp
            # the lower hem is brighter: light pools at the bottom of a curtain
            hem = smoothstep(((centre - lat_g) / width + 0.25) / 1.1)
            curtain = curtain * (0.55 + 0.75 * hem)

            frame[..., 0] += curtain * hue[0]
            frame[..., 1] += curtain * hue[1]
            frame[..., 2] += curtain * hue[2]

        # ground silhouette below the viewer's horizon
        ground = smoothstep((-0.03 - lat_g) / 0.06)
        frame[..., 0] *= 1 - ground * 0.96
        frame[..., 1] *= 1 - ground * 0.94
        frame[..., 2] *= 1 - ground * 0.90

        yield np.clip(frame, 0, 1) * 255


def main():
    print("Rendering 360° clips…")
    encode("space.mp4", space_frames(), FPS * SECONDS)
    encode("aurora.mp4", aurora_frames(), FPS * SECONDS)
    print("done")


if __name__ == "__main__":
    main()
