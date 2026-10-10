#!/usr/bin/env python3
"""Procedural renderer for mondweep-ruflo-journey.mp4.

Usage:
  render.py audio <out.wav>   write synthesized stereo soundtrack
  render.py frames            stream raw rgb24 frames to stdout

Everything is generated locally: vector shapes and text via Pillow,
audio via numpy sine/noise synthesis. Deterministic (fixed seeds).
"""
import math
import sys
import wave
from multiprocessing import Pool

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H, FPS = 1080, 1920, 30
SAFE_X0, SAFE_X1 = 100, 980          # side margins (100 px each)
SAFE_Y0, SAFE_Y1 = 230, 1600         # clear of top UI and bottom captions
TEXT_W = SAFE_X1 - SAFE_X0

BG_TOP, BG_BOT = (5, 8, 20), (9, 14, 38)
CYAN, VIOLET = (56, 225, 255), (157, 108, 255)
WHITE, MUTED = (240, 245, 255), (150, 165, 200)
CARD_FILL = (12, 19, 42, 228)

FD = "/usr/share/fonts/truetype/dejavu/"
_fonts = {}


def font(kind, size):
    name = {"bold": "DejaVuSans-Bold.ttf", "reg": "DejaVuSans.ttf",
            "mono": "DejaVuSansMono.ttf", "monob": "DejaVuSansMono-Bold.ttf"}[kind]
    key = (name, size)
    if key not in _fonts:
        _fonts[key] = ImageFont.truetype(FD + name, size)
    return _fonts[key]


def wrap(text, f, maxw):
    words, lines, cur = text.split(" "), [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if f.getlength(trial) <= maxw or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    for ln in lines:
        assert f.getlength(ln) <= maxw, f"text exceeds safe width: {ln!r}"
    return lines


def ease(x):
    x = min(max(x, 0.0), 1.0)
    return 1 - (1 - x) ** 3


# ---------------------------------------------------------------- sprites
def text_block(text, kind, size, color, maxw=TEXT_W, glow=None, align="left",
               spacing=1.18):
    f = font(kind, size)
    lines = wrap(text, f, maxw)
    lh = int(size * spacing)
    pad = 24
    w = int(max(f.getlength(l) for l in lines)) + pad * 2
    h = lh * len(lines) + pad * 2
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for i, ln in enumerate(lines):
        x = pad if align == "left" else pad + (w - 2 * pad - f.getlength(ln)) / 2
        d.text((x, pad + i * lh), ln, font=f, fill=color + (255,))
    if glow:
        g = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        gd = ImageDraw.Draw(g)
        for i, ln in enumerate(lines):
            x = pad if align == "left" else pad + (w - 2 * pad - f.getlength(ln)) / 2
            gd.text((x, pad + i * lh), ln, font=f, fill=glow + (120,))
        g = g.filter(ImageFilter.GaussianBlur(10))
        img = Image.alpha_composite(g, img)
    return img, pad


def card(lines, kind="mono", size=42, width=TEXT_W, prompt="›", accent=CYAN,
         header=True, line_color=WHITE):
    """Terminal-style card. Each entry in `lines` is one exact claim."""
    f = font(kind, size)
    pf = font("monob", size)
    inner = width - 64 - (int(pf.getlength(prompt + " ")) if prompt else 0)
    wrapped = [wrap(t, f, inner) for t in lines]
    lh = int(size * 1.3)
    gap = int(size * 0.55)
    head = 58 if header else 0
    body_h = sum(len(w) * lh for w in wrapped) + gap * (len(wrapped) - 1)
    h = head + body_h + 64
    m = 22
    img = Image.new("RGBA", (width + 2 * m, h + 2 * m), (0, 0, 0, 0))
    glow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(glow).rounded_rectangle((m, m, m + width, m + h), 26,
                                           outline=accent + (110,), width=6)
    img = Image.alpha_composite(img, glow.filter(ImageFilter.GaussianBlur(12)))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((m, m, m + width, m + h), 26, fill=CARD_FILL,
                        outline=accent + (170,), width=2)
    if header:
        for i, c in enumerate([(255, 95, 110), (255, 200, 90), (80, 220, 140)]):
            cx = m + 36 + i * 30
            d.ellipse((cx - 8, m + 29 - 8, cx + 8, m + 29 + 8), fill=c + (200,))
        d.line((m + 2, m + head, m + width - 2, m + head), fill=accent + (60,), width=2)
    y = m + head + 32
    px = m + 32
    tx = px + (int(pf.getlength(prompt + " ")) if prompt else 0)
    for wl in wrapped:
        if prompt:
            d.text((px, y), prompt, font=pf, fill=accent + (255,))
        for ln in wl:
            d.text((tx, y), ln, font=f, fill=line_color + (255,))
            y += lh
        y += gap
    return img, m


class El:
    """A sprite placed at (x, y) with a staggered fade/slide entrance."""

    def __init__(self, img, x, y, delay, slide=46):
        self.img, self.x, self.y, self.delay, self.slide = img, x, y, delay, slide

    def draw(self, base, tl, out_a):
        a = ease((tl - self.delay) / 0.55) * out_a
        if a <= 0.01:
            return
        dy = int((1 - ease((tl - self.delay) / 0.55)) * self.slide)
        s = self.img
        if a < 0.995:
            s = s.copy()
            s.putalpha(s.getchannel("A").point(lambda v: int(v * a)))
        base.alpha_composite(s, (int(self.x), int(self.y + dy)))


def place(sprite_pad, y, delay, x=SAFE_X0, center=False, slide=46):
    img, pad = sprite_pad
    px = (W - img.width) // 2 if center else x - pad
    return El(img, px, y - pad, delay, slide)


# ---------------------------------------------------------------- scenes
CHAPTERS = ["OPENING", "OBJECTIVE", "EXPERIMENTS", "TYPESAFE EVIDENCE",
            "RUFLO STACK", "GOVERNANCE OBSTACLE", "VERIFIED EXECUTION", "CLOSING"]
DUR = [2.8, 2.8, 3.0, 3.0, 3.0, 3.0, 3.6, 2.8]
STARTS = np.cumsum([0] + DUR[:-1]).tolist()
TOTAL = sum(DUR)
PIPE = ["prompt", "route", "write", "post-edit", "evidence"]
PIPE_NOTE = {1: "Prompt routed → coder (60%)",
             2: "Claude wrote one disposable file",
             3: "Post-edit learning event persisted"}


def build_scenes():
    S = []
    # 1 Opening
    S.append([
        place(text_block("FROM CURIOSITY TO VERIFIED EXECUTION", "bold", 104, WHITE,
                         glow=CYAN, spacing=1.08), 600, 0.15),
        place(text_block("Exploring rUv's recent work", "reg", 54, CYAN), 1180, 0.75),
    ])
    # 2 Objective
    S.append([
        place(text_block("Learn through live Federation evidence", "bold", 84, WHITE,
                         glow=CYAN, spacing=1.12), 640, 0.15),
        place(text_block("Then reproduce it hands-on", "reg", 60, VIOLET,
                         glow=VIOLET), 1090, 0.75),
    ])
    # 3 Experiments
    S.append([
        place(text_block("TWO EXPERIMENTS", "monob", 40, MUTED), 560, 0.1),
        place(card(["Typesafe calibrated decisions + abstention"], "bold", 54,
                   prompt="01", accent=CYAN, header=False), 660, 0.35),
        place(card(["Ruflo mod installation + execution"], "bold", 54,
                   prompt="02", accent=VIOLET, header=False), 1010, 0.75),
    ])
    # 4 Typesafe evidence
    S.append([
        place(text_block("Typesafe", "bold", 84, WHITE, glow=CYAN), 520, 0.1),
        place(card(["30 labels accepted", "Calibration remained false",
                    "Admission ≠ promoted decision head"], "mono", 46), 720, 0.4),
    ])
    # 5 Ruflo stack
    S.append([
        place(text_block("Ruflo stack", "bold", 84, WHITE, glow=VIOLET), 480, 0.1),
        place(card(["Claude Code 2.1.296", "Ruflo 3.56.3"], "mono", 50,
                   accent=VIOLET), 680, 0.4),
        place(text_block("ruflo-mods • ruflo-swarm • ruflo-console", "monob", 46,
                         CYAN, glow=CYAN, maxw=TEXT_W - 40, spacing=1.35),
              1130, 0.9),
    ])
    # 6 Governance obstacle
    S.append([
        place(text_block("Governance", "bold", 84, WHITE, glow=CYAN), 470, 0.1),
    ] + [
        place(card([t], "bold", 48, prompt="■", accent=c, header=False), 680 + i * 250,
              0.35 + i * 0.3)
        for i, (t, c) in enumerate([("Nonessential telemetry disabled", CYAN),
                                    ("Strict empty MCP configuration", VIOLET),
                                    ("Trusted sandbox only", CYAN)])
    ])
    # 7 Verified execution: vertical pipeline drawn dynamically + notes
    els = [place(text_block("Verified execution", "bold", 76, WHITE, glow=CYAN),
                 410, 0.05)]
    for i, name in enumerate(PIPE):
        y = PIPE_Y[i]
        els.append(place(text_block(name, "monob", 46, CYAN if i % 2 == 0 else VIOLET),
                         y - 30, 0.3 + i * 0.42, x=PIPE_X + 70, slide=24))
        if i in PIPE_NOTE:
            els.append(place(text_block(PIPE_NOTE[i], "reg", 42, WHITE,
                                        maxw=SAFE_X1 - PIPE_X - 70),
                             y + 34, 0.45 + i * 0.42, x=PIPE_X + 70, slide=24))
    S.append(els)
    # 8 Closing
    S.append([
        place(text_block("CONFIGURE →", "bold", 104, CYAN, glow=CYAN), 560, 0.1),
        place(text_block("ACTIVATE →", "bold", 104, (120, 170, 255),
                         glow=(120, 170, 255)), 700, 0.35),
        place(text_block("VERIFY", "bold", 104, VIOLET, glow=VIOLET), 840, 0.6),
        place(text_block("Evidence over assumptions", "reg", 58, WHITE), 1060, 1.0),
        place(text_block("Mondweep • Federation learning journey", "monob", 38, MUTED),
              1180, 1.3),
    ])
    return S


PIPE_X = 150
PIPE_Y = [590, 760, 930, 1100, 1270]


def chapter_sprites():
    out = []
    f = font("monob", 34)
    for i, name in enumerate(CHAPTERS):
        txt = f"{i + 1:02d}/08  {name}"
        img = Image.new("RGBA", (int(f.getlength(txt)) + 4, 46), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.text((0, 0), f"{i + 1:02d}/08", font=f, fill=CYAN + (255,))
        d.text((f.getlength(f"{i + 1:02d}/08  "), 0), name, font=f, fill=MUTED + (255,))
        out.append(img)
    return out


# ---------------------------------------------------------------- background
def static_bg():
    y = np.linspace(0, 1, H)[:, None, None]
    top, bot = np.array(BG_TOP, float), np.array(BG_BOT, float)
    g = top * (1 - y) + bot * y
    g = np.repeat(g, W, axis=1)
    yy, xx = np.mgrid[0:H, 0:W]
    r = np.hypot((xx - W * 0.5) / W, (yy - H * 0.42) / H)
    g += (np.clip(0.55 - r, 0, 1) * 34)[..., None] * np.array([0.25, 0.4, 1.0])
    grid = ((xx % 90 == 0) | (yy % 90 == 0)).astype(float) * 7
    g += grid[..., None] * np.array([0.5, 0.8, 1.0])
    return Image.fromarray(np.clip(g, 0, 255).astype(np.uint8)).convert("RGBA")


rng = np.random.default_rng(7)
N_NODES = 34
NODE_BASE = rng.uniform([0, 0], [W, H], (N_NODES, 2))
NODE_AMP = rng.uniform(30, 90, (N_NODES, 2))
NODE_FRQ = rng.uniform(0.05, 0.16, (N_NODES, 2))
NODE_PH = rng.uniform(0, 2 * math.pi, (N_NODES, 2))
NODE_COL = [CYAN if rng.random() < 0.6 else VIOLET for _ in range(N_NODES)]


def network(base, t):
    p = NODE_BASE + NODE_AMP * np.sin(2 * math.pi * NODE_FRQ * t + NODE_PH)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for i in range(N_NODES):
        for j in range(i + 1, N_NODES):
            dist = float(np.hypot(*(p[i] - p[j])))
            if dist < 330:
                a = int(70 * (1 - dist / 330))
                d.line((*p[i], *p[j]), fill=NODE_COL[i] + (a,), width=2)
    small = Image.new("RGBA", (W // 4, H // 4), (0, 0, 0, 0))
    sd = ImageDraw.Draw(small)
    for i in range(N_NODES):
        x, y = p[i]
        d.ellipse((x - 4, y - 4, x + 4, y + 4), fill=NODE_COL[i] + (190,))
        sx, sy = x / 4, y / 4
        sd.ellipse((sx - 4, sy - 4, sx + 4, sy + 4), fill=NODE_COL[i] + (110,))
    glow = small.filter(ImageFilter.GaussianBlur(4)).resize((W, H), Image.BILINEAR)
    base.alpha_composite(glow)
    base.alpha_composite(layer)


# ---------------------------------------------------------------- frames
BG = SCENES = CHAP = None


def init():
    global BG, SCENES, CHAP
    BG, SCENES, CHAP = static_bg(), build_scenes(), chapter_sprites()


def scene_at(t):
    for i in range(len(DUR) - 1, -1, -1):
        if t >= STARTS[i]:
            return i
    return 0


def draw_pipeline(img, tl, out_a):
    d = ImageDraw.Draw(img)
    x = PIPE_X
    for i in range(len(PIPE) - 1):
        y0, y1 = PIPE_Y[i], PIPE_Y[i + 1]
        k = ease((tl - (0.45 + i * 0.42)) / 0.4)
        d.line((x, y0, x, y1), fill=(60, 80, 120, int(150 * out_a)), width=4)
        if k > 0:
            d.line((x, y0, x, y0 + (y1 - y0) * k), fill=CYAN + (int(255 * out_a),),
                   width=4)
    for i, y in enumerate(PIPE_Y):
        k = ease((tl - (0.3 + i * 0.42)) / 0.35)
        c = CYAN if i % 2 == 0 else VIOLET
        d.ellipse((x - 22, y - 22, x + 22, y + 22), fill=(10, 16, 36, int(255 * out_a)),
                  outline=(70, 90, 130, int(255 * out_a)), width=3)
        if k > 0:
            r = 22 + 10 * (1 - k)
            d.ellipse((x - r, y - r, x + r, y + r),
                      outline=c + (int(255 * k * out_a),), width=4)
            d.ellipse((x - 9, y - 9, x + 9, y + 9), fill=c + (int(255 * k * out_a),))
    # travelling pulse
    tp = (tl - 0.3) / (0.42 * (len(PIPE) - 1))
    if 0 < tp < 1:
        seg = tp * (len(PIPE) - 1)
        i = int(seg)
        y = PIPE_Y[i] + (PIPE_Y[i + 1] - PIPE_Y[i]) * (seg - i)
        g = Image.new("RGBA", (120, 120), (0, 0, 0, 0))
        ImageDraw.Draw(g).ellipse((40, 40, 80, 80), fill=WHITE + (int(220 * out_a),))
        img.alpha_composite(g.filter(ImageFilter.GaussianBlur(9)), (x - 60, int(y) - 60))


def render_frame(n):
    t = n / FPS
    img = BG.copy()
    network(img, t)
    si = scene_at(t)
    tl = t - STARTS[si]
    out_a = 1.0
    if si < len(DUR) - 1:
        out_a = 1 - ease((tl - (DUR[si] - 0.35)) / 0.35)
    if si == 6:
        draw_pipeline(img, tl, out_a)
    for el in SCENES[si]:
        el.draw(img, tl, out_a)
    # chapter indicator + progress line (top, inside safe area)
    ca = ease(tl / 0.4) * (out_a if si < len(DUR) - 1 else 1)
    ch = CHAP[si].copy()
    ch.putalpha(ch.getchannel("A").point(lambda v: int(v * ca)))
    img.alpha_composite(ch, (SAFE_X0, SAFE_Y0))
    d = ImageDraw.Draw(img)
    py = SAFE_Y0 + 66
    seg_w = (TEXT_W - 7 * 10) / 8
    for i in range(8):
        x0 = SAFE_X0 + i * (seg_w + 10)
        d.rounded_rectangle((x0, py, x0 + seg_w, py + 6), 3, fill=(40, 52, 84, 255))
        fill = 1.0 if i < si else (min(tl / DUR[si], 1.0) if i == si else 0.0)
        if fill > 0:
            c = CYAN if i % 2 == 0 else VIOLET
            d.rounded_rectangle((x0, py, x0 + max(seg_w * fill, 6), py + 6), 3,
                                fill=c + (255,))
    # global fade in / out
    fade = min(ease(t / 0.5), ease((TOTAL - t) / 0.6))
    rgb = img.convert("RGB")
    if fade < 0.999:
        rgb = Image.eval(rgb, lambda v: int(v * fade))
    return rgb.tobytes()


def frames():
    n = int(round(TOTAL * FPS))
    out = sys.stdout.buffer
    with Pool(initializer=init) as pool:
        for buf in pool.imap(render_frame, range(n), chunksize=4):
            out.write(buf)
    out.flush()


# ---------------------------------------------------------------- audio
def audio(path, sr=48000):
    n = int(TOTAL * sr)
    t = np.arange(n) / sr
    r = np.random.default_rng(11)
    # ambient pad: A minor-ish drone with slow detune and LFO swell
    pad = np.zeros((n, 2))
    for f0, amp in [(55, 0.30), (82.41, 0.18), (110, 0.16), (164.81, 0.08),
                    (220, 0.05)]:
        for ch, det in enumerate((-0.15, 0.15)):
            pad[:, ch] += amp * np.sin(2 * np.pi * (f0 + det) * t +
                                       0.4 * np.sin(2 * np.pi * 0.07 * t))
    pad *= (0.55 + 0.45 * np.sin(2 * np.pi * t / 8 - np.pi / 2) ** 2)[:, None]
    # soft pulse every 0.75 s (80 bpm)
    pulse = np.zeros(n)
    for bt in np.arange(0, TOTAL, 0.75):
        i0 = int(bt * sr)
        k = np.arange(min(int(0.6 * sr), n - i0)) / sr
        f = 48 + 30 * np.exp(-k * 30)
        pulse[i0:i0 + len(k)] += 0.5 * np.sin(2 * np.pi * np.cumsum(f) / sr) * \
            np.exp(-k * 7) * (1 - np.exp(-k * 400))
    # transition tones + airy whoosh at each scene boundary
    tones = np.zeros((n, 2))
    notes = [659.25, 587.33, 523.25, 587.33, 659.25, 783.99, 880.0, 659.25]
    for si, st in enumerate(STARTS):
        i0 = int(st * sr)
        k = np.arange(min(int(1.6 * sr), n - i0)) / sr
        env = np.exp(-k * 3.2) * (1 - np.exp(-k * 250))
        bell = (np.sin(2 * np.pi * notes[si] * k) + 0.35 *
                np.sin(2 * np.pi * notes[si] * 2.01 * k) * np.exp(-k * 4))
        pan = 0.35 + 0.3 * (si % 2)
        tones[i0:i0 + len(k), 0] += 0.16 * bell * env * (1 - pan)
        tones[i0:i0 + len(k), 1] += 0.16 * bell * env * pan
        if si > 0:
            j0 = max(int((st - 0.4) * sr), 0)
            m = int(0.7 * sr)
            noise = np.convolve(r.standard_normal(m), np.ones(24) / 24, "same")
            wenv = np.sin(np.linspace(0, np.pi, m)) ** 2
            tones[j0:j0 + m] += (0.05 * noise * wenv)[:, None]
    mix = 0.5 * pad + 0.45 * pulse[:, None] + tones
    fade = np.minimum(np.clip(t / 1.0, 0, 1), np.clip((TOTAL - t) / 1.5, 0, 1))
    mix *= fade[:, None]
    mix *= 10 ** (-6 / 20) / np.max(np.abs(mix))   # peak -6 dBFS
    data = (mix * 32767).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(data.tobytes())


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "frames":
        frames()
    elif len(sys.argv) >= 3 and sys.argv[1] == "audio":
        audio(sys.argv[2])
    elif len(sys.argv) >= 4 and sys.argv[1] == "still":   # preview: still <t> <png>
        init()
        Image.frombytes("RGB", (W, H), render_frame(int(float(sys.argv[2]) * FPS))) \
            .save(sys.argv[3])
    else:
        sys.exit(__doc__)
