from PIL import Image, ImageDraw, ImageFont
import math, os

W, H = 640, 360

# ── colors ──────────────────────────────────────────────────────────────────
BG1        = (10,  4,  28)
BG2        = (38,  8,  82)
PURPLE     = (139, 92, 246)
PURPLE_LO  = (88,  50, 180)
PINK       = (232, 96, 200)
PINK_LT    = (249, 168, 212)
FUCHSIA    = (217, 70, 239)
WHITE      = (255, 255, 255)
GREY       = (180, 140, 220)
CARD_BG    = (28,  10,  58)
CARD_GLOW  = (100, 50, 200)

# ── fonts ────────────────────────────────────────────────────────────────────
def _ttf(size):
    for p in [
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/Arial.ttf",
        "/Library/Fonts/Arial.ttf",
        "/System/Library/Fonts/SFNS.ttf",
    ]:
        if os.path.exists(p):
            try: return ImageFont.truetype(p, size)
            except: pass
    return ImageFont.load_default()

FT = {s: _ttf(s) for s in [14, 17, 22, 30, 36]}

# ── easing ───────────────────────────────────────────────────────────────────
def ease_out3(t): return 1 - (1 - max(0, min(1, t))) ** 3
def ease_io(t):   t = max(0,min(1,t)); return t*t*(3-2*t)
def ease_out_back(t):
    t = max(0,min(1,t)); s = 1.70158
    return 1 + (s+1)*(t-1)**3 + s*(t-1)**2

# ── primitives ────────────────────────────────────────────────────────────────
def lerp_c(c1, c2, t):
    t = max(0,min(1,t))
    return tuple(int(c1[i]+(c2[i]-c1[i])*t) for i in range(3))

def gradient_bg(draw):
    for y in range(H):
        t  = y / H
        # add a subtle radial lighter center
        cx_dist = abs(W/2 - W/2) / (W/2)
        draw.line([(0, y), (W, y)], fill=lerp_c(BG1, BG2, t))

def heart_poly(cx, cy, size, n=120):
    pts = []
    for i in range(n):
        a = 2*math.pi*i/n
        x = 16*(math.sin(a)**3)
        y = -(13*math.cos(a)-5*math.cos(2*a)-2*math.cos(3*a)-math.cos(4*a))
        pts.append((cx + x*size, cy + y*size))
    return pts

def glow_circle(base, cx, cy, r, color, strength=120, layers=8):
    ov = Image.new("RGBA", (W,H), (0,0,0,0))
    d  = ImageDraw.Draw(ov)
    for i in range(layers):
        alpha = int(strength * (1 - i/layers) * (1 - i/layers))
        ri    = r + i * (r*0.35)
        d.ellipse([cx-ri, cy-ri, cx+ri, cy+ri],
                  fill=(*color, alpha))
    base.alpha_composite(ov)

def sparkle(draw, cx, cy, size, color, alpha=255):
    col = (*color, alpha) if len(color)==3 else color
    for ang in [0, 90, 180, 270]:
        r = math.radians(ang)
        draw.line([(cx, cy), (cx+size*math.cos(r), cy+size*math.sin(r))],
                  fill=col[:3], width=max(1, size//5))
    for ang in [45,135,225,315]:
        r = math.radians(ang)
        s2 = size*0.42
        draw.line([(cx, cy), (cx+s2*math.cos(r), cy+s2*math.sin(r))],
                  fill=col[:3], width=max(1, size//8))

def draw_card(base, x, y, w, h, title, sub, accent_col, alpha=1.0):
    ov = Image.new("RGBA", (W,H), (0,0,0,0))
    d  = ImageDraw.Draw(ov)
    a  = int(255*alpha)
    # glow border
    for i in range(6,0,-1):
        d.rounded_rectangle([x-i, y-i, x+w+i, y+h+i],
            radius=16+i, fill=(*accent_col, int(12*alpha*((7-i)/6))))
    # card body
    d.rounded_rectangle([x,y,x+w,y+h], radius=14,
        fill=(*CARD_BG, min(255, int(230*alpha))),
        outline=(*accent_col, int(120*alpha)), width=1)
    # accent bar left
    d.rounded_rectangle([x+10, y+12, x+14, y+h-12], radius=3, fill=(*accent_col, a))
    # texts
    d.text((x+26, y+12), title, fill=(*WHITE, a), font=FT[17])
    d.text((x+26, y+34), sub,   fill=(*GREY,  a), font=FT[14])
    base.alpha_composite(ov)

def draw_wish_item(base, x, y, w, name, price, done=False, alpha=1.0):
    ov = Image.new("RGBA", (W,H),(0,0,0,0))
    d  = ImageDraw.Draw(ov)
    a  = int(255*alpha)
    d.rounded_rectangle([x,y,x+w,y+46], radius=12,
        fill=(*CARD_BG, min(255,int(220*alpha))),
        outline=(*(PURPLE if done else (70,40,110)), int(100*alpha)), width=1)
    hcol = (*PINK, a) if done else (*(130,80,180), a)
    pts  = heart_poly(x+22, y+23, 0.5)
    if len(pts)>2: d.polygon(pts, fill=hcol[:3])
    d.text((x+42, y+8),  name,  fill=(*WHITE, a),  font=FT[17])
    d.text((x+42, y+26), price, fill=(*GREY,  a),  font=FT[14])
    if done:
        d.ellipse([x+w-36,y+12,x+w-14,y+34], fill=(*PURPLE, a))
        d.line([(x+w-31,y+23),(x+w-26,y+29),(x+w-16,y+17)],
               fill=(*WHITE,a), width=2)
    base.alpha_composite(ov)

# ── scene builders ────────────────────────────────────────────────────────────
CARDS = [
    ("Birthday",  "12 wishes",  (230, 80,  160)),
    ("Travel",    "8 wishes",   (100, 180, 255)),
    ("Home",      "5 wishes",   (100, 220, 150)),
]
WISHES = [
    ("Sony Headphones",  "$299",  True),
    ("Book collection",  "$45",   False),
    ("New Sneakers",     "$120",  False),
]
CW = 500  # card width
CX = (W - CW) // 2

def frame_splash(t):
    img = Image.new("RGBA",(W,H),(0,0,0,255))
    d   = ImageDraw.Draw(img)
    gradient_bg(d)

    scale = ease_out_back(t * 1.2)
    if scale > 0.05:
        glow_circle(img, W//2, H//2-10, int(70*scale), PURPLE, strength=80)
        pts = heart_poly(W//2, H//2-10, 4.5*scale)
        if len(pts) > 2:
            d2 = ImageDraw.Draw(img)
            d2.polygon(pts, fill=lerp_c(PINK_LT, FUCHSIA, 0.5))

    ta = ease_io(max(0,(t-0.35)*2.5))
    if ta > 0.01:
        col = lerp_c((50,20,80), WHITE, ta)
        d.text((W//2-46, H//2+55), "Wished", fill=col, font=FT[36])

    if t > 0.5:
        sp = ease_io((t-0.5)*3)
        sparkle(d, W//2+90, H//2-60, int(14*sp), WHITE)
        sparkle(d, W//2-88, H//2+38, int(9*sp),  PINK_LT)
        sparkle(d, W//2+30, H//2-75, int(6*sp),  PURPLE)
    return img.convert("RGB")

def frame_wishlists(t):
    img = Image.new("RGBA",(W,H),(0,0,0,255))
    d   = ImageDraw.Draw(img)
    gradient_bg(d)

    ta = ease_io(min(1,t*2.5))
    col = lerp_c((30,10,60), WHITE, ta)
    d.text((CX, 28), "Wishlists", fill=col, font=FT[30])

    # sparkle near title
    if t > 0.3:
        s = ease_io((t-0.3)*3)
        sparkle(d, CX+185, 42, int(8*s), PINK_LT)

    total_h = len(CARDS)*72 - 12
    top_y   = (H - total_h) // 2 + 20
    for i,(title,sub,acc) in enumerate(CARDS):
        delay = i * 0.18
        ct    = ease_out_back(max(0, (t - delay) * 2.2))
        if ct > 0.01:
            cy = top_y + i*72
            off_y = int((1-ct)*60)
            draw_card(img, CX, cy+off_y, CW, 56, title, sub, acc, alpha=min(1,ct*2))

    return img.convert("RGB")

def frame_wishes(t):
    img = Image.new("RGBA",(W,H),(0,0,0,255))
    d   = ImageDraw.Draw(img)
    gradient_bg(d)

    ta = ease_io(min(1,t*3))
    d.text((CX, 22), "Birthday", fill=lerp_c((30,10,60),WHITE,ta), font=FT[30])
    d.text((CX+170, 32), "· 12 wishes", fill=lerp_c((30,10,60),GREY,ta), font=FT[17])

    top_y = 80
    for i,(name,price,done) in enumerate(WISHES):
        ct = ease_out3(max(0,(t - i*0.15)*2.5))
        if ct > 0.02:
            wy  = top_y + i*58
            off = int((1-ct)*50)
            draw_wish_item(img, CX, wy+off, CW, name, price, done, alpha=min(1,ct*2))

    # new item slides in
    new_t = ease_out_back(max(0,(t-0.6)*2.5))
    if new_t > 0.02:
        wy  = top_y + 3*58
        off = int((1-new_t)*60)
        ov  = Image.new("RGBA",(W,H),(0,0,0,0))
        d2  = ImageDraw.Draw(ov)
        a   = int(min(255, new_t*400))
        d2.rounded_rectangle([CX, wy+off, CX+CW, wy+off+46], radius=12,
            fill=(*CARD_BG, min(220,a)),
            outline=(*PINK, min(200,a)), width=1)
        if new_t > 0.4:
            ta2 = min(1,(new_t-0.4)*2.5)
            pts = heart_poly(CX+22, wy+off+23, 0.5)
            if len(pts)>2: d2.polygon(pts, fill=(*PINK_LT, int(255*ta2)))
            d2.text((CX+42, wy+off+8),  "Camera",  fill=(*WHITE, int(255*ta2)), font=FT[17])
            d2.text((CX+42, wy+off+26), "$650",    fill=(*GREY,  int(255*ta2)), font=FT[14])
            d2.text((CX+CW-60, wy+off+14), "new", fill=(*PINK,  int(200*ta2)), font=FT[14])
        img.alpha_composite(ov)

    return img.convert("RGB")

def frame_share(t):
    img = Image.new("RGBA",(W,H),(0,0,0,255))
    d   = ImageDraw.Draw(img)
    gradient_bg(d)

    d.text((CX, 22), "Birthday", fill=WHITE, font=FT[30])
    d.text((CX+170, 32), "· 12 wishes", fill=GREY, font=FT[17])

    top_y = 80
    for i,(name,price,done) in enumerate(WISHES):
        draw_wish_item(img, CX, top_y+i*58, CW, name, price, done, alpha=1.0)

    # share button
    btn_t = ease_out_back(min(1, t*2.2))
    btn_y = top_y + 3*58 + 16
    BW    = CW
    if btn_t > 0.02:
        bw2 = int(BW * btn_t)
        bx  = CX + (BW - bw2)//2
        ov  = Image.new("RGBA",(W,H),(0,0,0,0))
        d2  = ImageDraw.Draw(ov)
        d2.rounded_rectangle([bx, btn_y, bx+bw2, btn_y+44], radius=22,
            fill=(*PURPLE, 230))
        if btn_t > 0.6:
            ta = min(1,(btn_t-0.6)*3)
            d2.text((CX + BW//2 - 26, btn_y+11), "Share ✦",
                    fill=(*WHITE, int(255*ta)), font=FT[22])
        img.alpha_composite(ov)

    # ripple rings
    if t > 0.45:
        for ri in range(3):
            rt = max(0, (t-0.45) - ri*0.18)
            if 0 < rt < 1:
                r  = int(22 + 120*rt)
                a  = int(160*(1-rt))
                ov = Image.new("RGBA",(W,H),(0,0,0,0))
                d2 = ImageDraw.Draw(ov)
                bcy = btn_y + 22
                bcx = CX + BW//2
                d2.ellipse([bcx-r,bcy-r,bcx+r,bcy+r],
                    outline=(*PURPLE, a), width=2)
                img.alpha_composite(ov)

    # sparkles
    if t > 0.5:
        sp = ease_io((t-0.5)*2.5)
        d.ink = None
        sparkle(d, CX+CW+20,   btn_y,      int(10*sp), PINK_LT)
        sparkle(d, CX-20,      btn_y+22,   int(8*sp),  PURPLE)
        sparkle(d, CX+CW//2,   btn_y-20,   int(6*sp),  PINK)

    return img.convert("RGB")

# ── assemble frames ───────────────────────────────────────────────────────────
frames    = []
durations = []

def add_scene(fn, n, hold, ms=42):
    for i in range(n):
        frames.append(fn(i/(n-1) if n>1 else 1))
        durations.append(ms)
    last = fn(1.0)
    for _ in range(hold):
        frames.append(last)
        durations.append(ms)

add_scene(frame_splash,     30, 12)   # ~1.75s
add_scene(frame_wishlists,  35, 15)   # ~2.1s
add_scene(frame_wishes,     35, 15)   # ~2.1s
add_scene(frame_share,      30, 15)   # ~1.9s

out = "/Users/anx/wished/wished-demo.gif"
frames[0].save(out, save_all=True, append_images=frames[1:],
               duration=durations, loop=0, optimize=False)
print(f"✓ {len(frames)} frames → {out}")
