#!/usr/bin/env python3
"""
Nexus VR — procedural UI sound design.

Renders short, iOS-friendly WAV files (16-bit PCM, 44.1 kHz, mono) for the
interface, plus loop-ready ambience beds. Everything is synthesized here so the
repository carries no third-party audio.

    python3 tools/gen_audio.py
"""
import math
import os
import struct
import wave

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets", "audio")
SR = 44100


def envelope(n, attack=0.004, decay=0.18, curve=3.0):
    a = int(SR * attack)
    d = n - a
    env = np.ones(n, dtype=np.float32)
    if a > 0:
        env[:a] = np.linspace(0, 1, a) ** 0.6
    env[a:] = np.exp(-np.linspace(0, curve, d))
    return env


def sine(freq, dur, phase=0.0):
    t = np.arange(int(SR * dur), dtype=np.float32) / SR
    return np.sin(2 * np.pi * freq * t + phase).astype(np.float32)


def swept(f0, f1, dur, curve=2.0):
    n = int(SR * dur)
    t = np.linspace(0, 1, n, dtype=np.float32)
    f = f0 + (f1 - f0) * (t ** curve)
    phase = 2 * np.pi * np.cumsum(f) / SR
    return np.sin(phase).astype(np.float32)


def noise(dur, decay=2.0, lp=0.0):
    n = int(SR * dur)
    rng = np.random.default_rng(1234)
    x = rng.normal(0, 1, n).astype(np.float32)
    if lp > 0:
        # one-pole lowpass
        a = math.exp(-2 * math.pi * lp / SR)
        y = np.zeros_like(x)
        acc = 0.0
        for i in range(n):
            acc = a * acc + (1 - a) * x[i]
            y[i] = acc
        x = y
    else:
        # highpass-ish for clicks
        x = np.diff(np.concatenate([[0], x])).astype(np.float32)
    return (x * np.exp(-np.linspace(0, decay, n))).astype(np.float32)


def normalize(x, peak=0.85):
    m = np.max(np.abs(x)) + 1e-9
    return (x / m * peak).astype(np.float32)


def fft_filter(x, lo=None, hi=None):
    n = len(x)
    X = np.fft.rfft(x)
    freqs = np.fft.rfftfreq(n, 1 / SR)
    mask = np.ones_like(freqs)
    if lo:
        mask *= 1 / (1 + (lo / np.maximum(freqs, 1e-3)) ** 4)
    if hi:
        mask *= 1 / (1 + (freqs / hi) ** 4)
    return np.fft.irfft(X * mask, n).astype(np.float32)


def write_wav(name, samples, stereo=False, peak=0.85):
    samples = np.asarray(samples, dtype=np.float32)
    if samples.ndim == 1:
        samples = samples[:, None]
    samples = normalize(samples, peak)
    n, ch = samples.shape
    path = os.path.join(OUT, name)
    with wave.open(path, "wb") as w:
        w.setnchannels(ch)
        w.setsampwidth(2)
        w.setframerate(SR)
        ints = (np.clip(samples, -1, 1) * 32767).astype(np.int16)
        w.writeframes(ints.tobytes())
    print(f"  {name:22s} {n/SR:.2f}s  {ch}ch  {os.path.getsize(path)/1024:.1f} KB")


def make_click():
    """A soft, tactile UI click: two short sine blips + a filtered noise tick."""
    a = swept(1500, 900, 0.055, 2.5) * envelope(int(SR * 0.055), 0.001, 0.05, 4.0)
    b = sine(2600, 0.035) * envelope(int(SR * 0.035), 0.0008, 0.03, 5.0) * 0.5
    t = noise(0.02, 6.0) * 0.18
    out = np.zeros(int(SR * 0.09), dtype=np.float32)
    out[:len(a)] += a * 0.75
    out[:len(b)] += b
    out[:len(t)] += t
    return fft_filter(out, lo=220, hi=9000)


def make_hover():
    a = sine(1320, 0.06) * envelope(int(SR * 0.06), 0.002, 0.055, 3.2)
    b = sine(1980, 0.05) * envelope(int(SR * 0.05), 0.002, 0.045, 3.6) * 0.35
    out = np.zeros(int(SR * 0.09), dtype=np.float32)
    out[:len(a)] += a * 0.42
    out[:len(b)] += b
    return fft_filter(out, lo=400, hi=9000)


def make_select():
    """Confirming 'open' chord — a rising three-note arpeggio with air."""
    total = 0.34
    out = np.zeros(int(SR * total), dtype=np.float32)
    notes = [(523.25, 0.00, 0.26, 0.42), (783.99, 0.055, 0.24, 0.32), (1046.5, 0.11, 0.22, 0.24)]
    for f, start, dur, gain in notes:
        s = int(SR * start)
        n = int(SR * dur)
        sig = sine(f, dur) * envelope(n, 0.004, dur * 0.8, 3.0) * gain
        sig += sine(f * 2, dur) * envelope(n, 0.004, dur * 0.7, 3.6) * gain * 0.16
        out[s:s + n] += sig
    air = fft_filter(noise(0.22, 3.2, lp=6000), lo=2000) * 0.06
    out[:len(air)] += air
    return out


def make_back():
    sig = swept(760, 380, 0.19, 1.6) * envelope(int(SR * 0.19), 0.003, 0.18, 3.4)
    tail = sine(380, 0.19) * envelope(int(SR * 0.19), 0.003, 0.19, 4.0) * 0.3
    sig = sig + tail
    return fft_filter(sig, lo=140, hi=7000)


def make_error():
    a = sine(196, 0.14) * envelope(int(SR * 0.14), 0.004, 0.13, 3.0)
    b = sine(164.8, 0.18) * envelope(int(SR * 0.18), 0.004, 0.17, 2.6)
    out = np.zeros(int(SR * 0.34), dtype=np.float32)
    out[:len(a)] += a * 0.55
    out[int(SR * 0.10):int(SR * 0.10) + len(b)] += b * 0.45
    return fft_filter(out, lo=90, hi=1800)


def make_open():
    """Portal 'whoosh': band-passed noise sweep + low tone bloom."""
    dur = 0.85
    n = int(SR * dur)
    t = np.linspace(0, 1, n, dtype=np.float32)
    rng = np.random.default_rng(7)
    nz = rng.normal(0, 1, n).astype(np.float32)
    # sweeping bandpass via short-time FFT blocks
    out = np.zeros(n, dtype=np.float32)
    block = 2048
    hop = 1024
    win = np.hanning(block).astype(np.float32)
    for i in range(0, n - block, hop):
        seg = nz[i:i + block] * win
        frac = i / (n - block)
        center = 300 + 3600 * math.sin(frac * math.pi * 0.9) ** 2
        X = np.fft.rfft(seg)
        f = np.fft.rfftfreq(block, 1 / SR)
        band = np.exp(-((f - center) / (center * 0.7 + 200)) ** 2)
        out[i:i + block] += np.fft.irfft(X * band, block).astype(np.float32) * win
    out *= np.sin(np.linspace(0, math.pi, n)) ** 1.2
    bloom = (sine(110, dur) * 0.16 + sine(165, dur) * 0.10) * np.sin(np.linspace(0, math.pi, n))
    return fft_filter(out * 0.9 + bloom, lo=60, hi=7000)


def make_coin():
    out = np.zeros(int(SR * 0.30), dtype=np.float32)
    for f, start, dur, g in [(1046.5, 0.0, 0.10, 0.5), (1568, 0.075, 0.20, 0.45)]:
        s = int(SR * start)
        n = int(SR * dur)
        out[s:s + n] += sine(f, dur)[:n] * envelope(n, 0.002, dur, 3.5) * g
    return out


def make_hit():
    thump = swept(160, 48, 0.28, 1.4) * envelope(int(SR * 0.28), 0.002, 0.27, 2.4)
    crack = noise(0.22, 3.0, lp=1800) * 0.4
    out = np.zeros(int(SR * 0.34), dtype=np.float32)
    out[:len(thump)] += thump * 0.8
    out[:len(crack)] += crack
    return fft_filter(out, lo=40, hi=5000)


def make_ambient_calm():
    """Night lake: soft wind + low drone. 8 s seamless loop."""
    dur = 8.0
    n = int(SR * dur)
    rng = np.random.default_rng(21)
    wind = fft_filter(rng.normal(0, 1, n).astype(np.float32), lo=90, hi=900)
    # slow LFO on level with an exactly loop-periodic shape
    t = np.linspace(0, 1, n, dtype=np.float32)
    lfo = 0.55 + 0.45 * np.sin(2 * np.pi * t * 2)
    wind *= lfo
    drone = np.zeros(n, dtype=np.float32)
    for f in (55, 82.5, 110):
        drone += np.sin(2 * np.pi * f * t * dur + np.sin(2 * np.pi * t) * 0.6) * 0.12
    drone *= 0.5 + 0.5 * np.sin(2 * np.pi * t * 1)
    mix = wind * 0.55 + drone * 0.28
    # seamless crossfade at the ends
    fade = int(SR * 0.6)
    mix[:fade] *= np.linspace(0, 1, fade)
    mix[-fade:] *= np.linspace(1, 0, fade)
    return fft_filter(mix, lo=35, hi=1600)


def main():
    os.makedirs(OUT, exist_ok=True)
    print("Rendering UI sounds…")
    write_wav("click.wav", make_click(), peak=0.7)
    write_wav("hover.wav", make_hover(), peak=0.42)
    write_wav("select.wav", make_select(), peak=0.72)
    write_wav("back.wav", make_back(), peak=0.6)
    write_wav("error.wav", make_error(), peak=0.55)
    write_wav("open.wav", make_open(), peak=0.7)
    write_wav("coin.wav", make_coin(), peak=0.6)
    write_wav("hit.wav", make_hit(), peak=0.8)
    write_wav("ambient-calm.wav", make_ambient_calm(), peak=0.55)
    print("Done.")


if __name__ == "__main__":
    main()
