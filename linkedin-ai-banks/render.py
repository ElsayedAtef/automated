"""Animated LinkedIn clip renderer for the "Enabling AI in Banks" series.

Usage:
  python3 render.py spec.json stills OUT_DIR     # key frames to check layout
  python3 render.py spec.json video OUT.mp4      # full 1080x1350, 30 fps, ~15 s

spec.json:
{
  "episode": 2,
  "hook":    {"top": "The board wants", "big": "AI", "sub": "in 90 days.", "ar": "والكل بيبص عليك",
              "count": 90},                                  # optional: animates the first number in "sub" from 0
  "cards":   {"title": "The reality", "ar": "الواقع",
              "items": [["English line", "سطر عربي"], ... up to 4]},
  "options": {"title": "Where do you start?", "ar": "تبدأ بإيه؟",
              "items": [["A", "English", "sub line (ar or en)"], ... up to 4]},   # optional; omit for no options scene
  "cta":     {"line1": "...", "line2": "...", "highlight": "...", "button": "...", "ar": "..."}
}
Arabic is shaped with Raqm (Cairo font in this folder). Long lines shrink to fit automatically.
"""
import sys, os, re, json, math, subprocess
from PIL import Image, ImageDraw, ImageFont, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
W, H, FPS = 1080, 1350, 30
BG = (9, 22, 44); TEAL = (25, 205, 185); AMBER = (255, 180, 40)
WHITE = (240, 244, 250); MUTED = (150, 168, 195); CARD = (20, 40, 72)

def _inter_dir():
    for d in ["/usr/share/fonts/opentype/inter/", os.path.join(HERE, "fonts/")]:
        if os.path.exists(os.path.join(d, "Inter-Bold.otf")): return d
    return None
INTER = _inter_dir()
CAIRO = os.path.join(HERE, "Cairo.ttf")
_fc = {}
def f(name, size):
    k = (name, size)
    if k not in _fc:
        if name == "ar" or INTER is None:
            ft = ImageFont.truetype(CAIRO, size, layout_engine=ImageFont.Layout.RAQM)
            weight = {"ar": "Bold", "Inter-Black.otf": "Black", "Inter-ExtraBold.otf": "ExtraBold"}.get(name, "Bold")
            try: ft.set_variation_by_name(weight)
            except Exception: pass
        else:
            ft = ImageFont.truetype(INTER + name, size)
        _fc[k] = ft
    return _fc[k]

def is_ar(s): return any("؀" <= ch <= "ۿ" for ch in s)
def fit(name, size, s, maxw):
    while size > 18:
        ft = f(name, size)
        kw = {"direction": "rtl", "language": "ar"} if is_ar(s) else {}
        if ft.getlength(s, **kw) <= maxw: return ft
        size -= 2
    return f(name, size)

def clamp(x, a=0.0, b=1.0): return max(a, min(b, x))
def ease(x): x = clamp(x); return 1 - (1 - x) ** 3
def back(x):
    x = clamp(x); c1 = 1.70158; c3 = c1 + 1
    return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2
def prog(t, s, d): return clamp((t - s) / d)

def text(img, xy, s, font, fill, alpha=1.0, anchor="mm"):
    if alpha <= 0 or not s: return
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    kw = {"direction": "rtl", "language": "ar"} if is_ar(s) else {}
    ImageDraw.Draw(layer).text(xy, s, font=font, fill=fill + (int(255 * alpha),), anchor=anchor, **kw)
    img.alpha_composite(layer)

def rrect(img, box, r, fill, alpha=1.0, outline=None, width=0):
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).rounded_rectangle(box, r, fill=fill + (int(255 * alpha),),
        outline=(outline + (int(255 * alpha),)) if outline else None, width=width)
    img.alpha_composite(layer)

def make_bg():
    b = Image.new("RGBA", (W, H), BG + (255,)); d = ImageDraw.Draw(b)
    for y in range(40, H, 60):
        for x in range(40, W, 60):
            d.ellipse((x - 1.5, y - 1.5, x + 1.5, y + 1.5), fill=(40, 70, 110, 255))
    return b
BGIMG = make_bg()
NODES = [(140, 210), (930, 170), (980, 620), (90, 760), (880, 1150), (200, 1210), (560, 90)]

def background(t):
    img = BGIMG.copy(); layer = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(layer)
    pts = [(x + 18 * math.sin(t * 0.6 + i), y + 14 * math.cos(t * 0.5 + i * 1.3)) for i, (x, y) in enumerate(NODES)]
    for i in range(len(pts)):
        for j in range(i + 1, len(pts)):
            if math.hypot(pts[i][0] - pts[j][0], pts[i][1] - pts[j][1]) < 700:
                d.line([pts[i], pts[j]], fill=TEAL + (28,), width=2)
    for i, p in enumerate(pts):
        pu = 0.5 + 0.5 * math.sin(t * 2 + i); r = 5 + 3 * pu
        d.ellipse((p[0] - r, p[1] - r, p[0] + r, p[1] + r), fill=TEAL + (int(90 + 80 * pu),))
    img.alpha_composite(layer); return img

def sa(t, s, e, fade=0.35): return clamp(min((t - s) / fade, (e - t) / fade))

class Clip:
    def __init__(self, spec):
        self.s = spec
        has_opt = bool(spec.get("options"))
        self.t_hook = (0.0, 3.8)
        self.t_cards = (3.8, 8.0)
        self.t_opt = (8.0, 12.4) if has_opt else None
        cs = 12.4 if has_opt else 8.0
        self.t_cta = (cs, cs + 3.2)
        self.dur = cs + 2.6

    def frame(self, t):
        s = self.s; img = background(t)
        text(img, (W // 2, 90), f"ENABLING AI IN BANKS  ·  EP. {s['episode']}", f("Inter-SemiBold.otf", 30), TEAL, 0.9)

        hk = s["hook"]; S, E = self.t_hook; a = sa(t, S - 1, E)
        if a > 0:
            p1 = ease(prog(t, 0.2, 0.6))
            text(img, (W // 2, 470 - 30 * (1 - p1)), hk["top"], fit("Inter-SemiBold.otf", 64, hk["top"], 940), WHITE, a * p1)
            p2 = back(prog(t, 0.7, 0.6))
            if p2 > 0:
                big = hk["big"]; ft = fit("Inter-Black.otf", max(10, int(260 * p2)), big, 960)
                g = Image.new("RGBA", (W, H), (0, 0, 0, 0))
                kw = {"direction": "rtl", "language": "ar"} if is_ar(big) else {}
                ImageDraw.Draw(g).text((W // 2, 650), big, font=ft, fill=TEAL + (int(200 * a),), anchor="mm", **kw)
                img.alpha_composite(g.filter(ImageFilter.GaussianBlur(28)))
                text(img, (W // 2, 650), big, ft, WHITE, a)
            p3 = ease(prog(t, 1.5, 0.5)); sub = hk.get("sub", "")
            if hk.get("count"):
                n = int(round(hk["count"] * ease(prog(t, 1.5, 1.2))))
                sub = re.sub(r"\d+", str(n), sub, count=1)
            text(img, (W // 2, 860), sub, fit("Inter-ExtraBold.otf", 92, hk.get("sub", ""), 960), AMBER, a * p3)
            p4 = ease(prog(t, 2.4, 0.5))
            text(img, (W // 2, 1010 + 20 * (1 - p4)), hk.get("ar", ""), fit("ar", 64, hk.get("ar", ""), 960), MUTED, a * p4)

        cd = s["cards"]; S, E = self.t_cards; a = sa(t, S, E)
        if a > 0:
            text(img, (W // 2, 250), cd["title"], fit("Inter-ExtraBold.otf", 72, cd["title"], 960), WHITE, a)
            text(img, (W // 2, 335), cd.get("ar", ""), f("ar", 54), TEAL, a)
            for i, (en, ar) in enumerate(cd["items"][:4]):
                p = ease(prog(t, S + 0.4 + i * 0.45, 0.5))
                if p <= 0: continue
                y = 450 + i * 190; x0 = 90 + int(260 * (1 - p))
                rrect(img, (x0, y, x0 + 900, y + 160), 28, CARD, a * p)
                rrect(img, (x0, y, x0 + 14, y + 160), 7, AMBER, a * p)
                text(img, (x0 + 60, y + 58), en, fit("Inter-Bold.otf", 40, en, 800), WHITE, a * p, anchor="lm")
                if is_ar(ar):
                    text(img, (x0 + 860, y + 115), ar, fit("ar", 36, ar, 800), MUTED, a * p, anchor="rm")
                else:
                    text(img, (x0 + 60, y + 112), ar, fit("Inter-Medium.otf", 32, ar, 800), MUTED, a * p, anchor="lm")

        if self.t_opt:
            op = s["options"]; S, E = self.t_opt; a = sa(t, S, E)
            if a > 0:
                text(img, (W // 2, 250), op["title"], fit("Inter-ExtraBold.otf", 72, op["title"], 960), WHITE, a)
                text(img, (W // 2, 335), op.get("ar", ""), f("ar", 58), AMBER, a)
                hl_t = t - (S + 2.4); hl = int(hl_t / 0.35) % len(op["items"][:4]) if hl_t > 0 else -1
                for i, (k, en, sub) in enumerate(op["items"][:4]):
                    p = back(prog(t, S + 0.4 + i * 0.35, 0.5))
                    if p <= 0: continue
                    y = 450 + i * 190; on = (i == hl); al = a * clamp(p)
                    rrect(img, (90, y, 990, y + 160), 28, (28, 60, 100) if on else CARD, al, outline=TEAL if on else None, width=4)
                    cx, cy = 175, y + 80; rr = int(50 * p)
                    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
                    ImageDraw.Draw(layer).ellipse((cx - rr, cy - rr, cx + rr, cy + rr), fill=(TEAL if on else AMBER) + (int(255 * a),))
                    img.alpha_composite(layer)
                    text(img, (cx, cy - 2), k, f("Inter-Black.otf", 52), BG, al)
                    text(img, (265, y + 58), en, fit("Inter-Bold.otf", 42, en, 690), WHITE, al, anchor="lm")
                    if is_ar(sub):
                        text(img, (950, y + 115), sub, fit("ar", 34, sub, 680), MUTED, al, anchor="rm")
                    else:
                        text(img, (265, y + 112), sub, fit("Inter-Medium.otf", 32, sub, 690), MUTED, al, anchor="lm")

        ct = s["cta"]; S, E = self.t_cta; a = sa(t, S, E + 0.6)
        if a > 0:
            p1 = ease(prog(t, S + 0.1, 0.6))
            text(img, (W // 2, 470), ct.get("line1", ""), fit("Inter-Bold.otf", 60, ct.get("line1", ""), 960), WHITE, a * p1)
            text(img, (W // 2, 550), ct.get("line2", ""), fit("Inter-Bold.otf", 52, ct.get("line2", ""), 960), WHITE, a * p1)
            p2 = ease(prog(t, S + 0.7, 0.6))
            text(img, (W // 2, 680), ct.get("highlight", ""), fit("Inter-ExtraBold.otf", 58, ct.get("highlight", ""), 960), AMBER, a * p2)
            p3 = ease(prog(t, S + 1.3, 0.5)); bob = 14 * math.sin((t - S) * 6)
            rrect(img, (150, 870, 930, 1010), 70, TEAL, a * p3)
            text(img, (W // 2, 940), ct.get("button", ""), fit("Inter-ExtraBold.otf", 48, ct.get("button", ""), 720), BG, a * p3)
            text(img, (W // 2, 1100 + bob), "↓", f("Inter-Black.otf", 90), TEAL, a * p3)
            text(img, (W // 2, 1210), ct.get("ar", ""), fit("ar", 46, ct.get("ar", ""), 940), MUTED, a * p3)
        return img.convert("RGB")

if __name__ == "__main__":
    spec = json.load(open(sys.argv[1], encoding="utf-8")); mode = sys.argv[2]; out = sys.argv[3]
    c = Clip(spec)
    if mode == "stills":
        os.makedirs(out, exist_ok=True)
        mids = [1.0, 3.0, 6.5] + ([10.2] if c.t_opt else []) + [c.t_cta[0] + 1.8]
        ims = [c.frame(x) for x in mids]
        for x, im in zip(mids, ims): im.save(os.path.join(out, f"still_{x:.1f}.png"))
        sheet = Image.new("RGB", (360 * len(ims), 450))
        for i, im in enumerate(ims): sheet.paste(im.resize((360, 450)), (i * 360, 0))
        sheet.save(os.path.join(out, "sheet.png"))
    else:
        tmp = out[:-4] + ".tmp.mp4"
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
               "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", "-movflags", "+faststart", tmp]
        p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        for i in range(int(c.dur * FPS)): p.stdin.write(c.frame(i / FPS).tobytes())
        p.stdin.close()
        if p.wait() != 0: sys.exit("ffmpeg failed")
        os.replace(tmp, out)
