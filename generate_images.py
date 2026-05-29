"""
Генератор изображений для бота «Центр Красок #1».
Создаёт welcome.png, banner.png, profile_photo.png
"""

import math
import random
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

random.seed(42)
np.random.seed(42)

# ─── Цвета ────────────────────────────────────────────────────────────────────
BG       = (7, 8, 16)
CYAN     = (0, 229, 255)
CORAL    = (255, 51, 86)
GOLD     = (255, 184, 0)
WHITE    = (255, 255, 255)
LGRAY    = (160, 170, 185)
DGRAY    = (40, 45, 60)

# ─── Шрифты ──────────────────────────────────────────────────────────────────
BOLD_FONT   = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
REG_FONT    = "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"
MONO_FONT   = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
MONO_BOLD   = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"


def font(path, size):
    return ImageFont.truetype(path, size)


# ─── Помощники рисования ──────────────────────────────────────────────────────

def dot_grid(draw, x0, y0, x1, y1, step=22, color=(255, 255, 255, 18)):
    for gx in range(x0, x1, step):
        for gy in range(y0, y1, step):
            draw.ellipse([gx - 1, gy - 1, gx + 1, gy + 1], fill=color)


def paint_splash(img, cx, cy, base_color, count=120, max_r=90, alpha_base=180):
    """Рисует реалистичное пятно краски через отдельный слой с маской."""
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    rng = random.Random(cx + cy)

    # Ядро
    for _ in range(count):
        angle = rng.uniform(0, 2 * math.pi)
        dist  = rng.uniform(0, max_r) ** 0.7 * max_r ** 0.3
        bx    = cx + dist * math.cos(angle)
        by    = cy + dist * math.sin(angle)
        r     = rng.uniform(2, max_r * 0.25)
        alpha = int(alpha_base * rng.uniform(0.4, 1.0))
        col   = tuple(
            max(0, min(255, c + rng.randint(-20, 20)))
            for c in base_color
        ) + (alpha,)
        d.ellipse([bx - r, by - r, bx + r, by + r], fill=col)

    # Брызги
    for _ in range(count // 2):
        angle = rng.uniform(0, 2 * math.pi)
        dist  = rng.uniform(max_r * 0.6, max_r * 2.2)
        bx    = cx + dist * math.cos(angle)
        by    = cy + dist * math.sin(angle)
        r     = rng.uniform(1, 6)
        alpha = int(alpha_base * rng.uniform(0.2, 0.7))
        col   = tuple(
            max(0, min(255, c + rng.randint(-30, 30)))
            for c in base_color
        ) + (alpha,)
        d.ellipse([bx - r, by - r, bx + r, by + r], fill=col)

    # Потёки — тонкие удлинённые эллипсы
    for _ in range(20):
        angle  = rng.uniform(math.pi * 0.3, math.pi * 0.7)
        dist   = rng.uniform(0, max_r * 0.5)
        bx     = cx + dist * math.cos(angle)
        by     = cy + dist * math.sin(angle)
        length = rng.uniform(max_r * 0.3, max_r * 1.0)
        width  = rng.uniform(2, 8)
        alpha  = int(alpha_base * rng.uniform(0.3, 0.8))
        col    = tuple(
            max(0, min(255, c + rng.randint(-15, 15)))
            for c in base_color
        ) + (alpha,)
        d.ellipse([bx - width, by - length, bx + width, by + length / 4], fill=col)

    layer = layer.filter(ImageFilter.GaussianBlur(radius=1.5))
    img.paste(layer, mask=layer)


def brush_stroke(img, x0, y0, x1, y1, color, width=14, alpha=200):
    """Мазок кисти — вдоль линии серия эллипсов с затуханием."""
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d     = ImageDraw.Draw(layer)
    steps = max(int(math.hypot(x1 - x0, y1 - y0) / 4), 2)
    for i in range(steps + 1):
        t  = i / steps
        bx = x0 + (x1 - x0) * t
        by = y0 + (y1 - y0) * t
        a  = int(alpha * (1 - abs(t - 0.5) * 0.6))
        w  = width * (1 - abs(t - 0.5) * 0.4)
        col = color + (a,)
        d.ellipse([bx - w, by - w * 0.4, bx + w, by + w * 0.4], fill=col)
    layer = layer.filter(ImageFilter.GaussianBlur(radius=1))
    img.paste(layer, mask=layer)


def pill_badge(draw, x, y, text, color, f):
    """Рисует pill-значок с текстом."""
    bbox  = draw.textbbox((0, 0), text, font=f)
    tw    = bbox[2] - bbox[0]
    th    = bbox[3] - bbox[1]
    pad_x, pad_y = 12, 6
    rx    = x + pad_x + tw + pad_x
    ry    = y + pad_y + th + pad_y
    r     = (th + pad_y * 2) // 2
    # border
    draw.rounded_rectangle([x, y, rx, ry], radius=r,
                            outline=color, width=2)
    # text
    draw.text((x + pad_x, y + pad_y - 1), text, font=f, fill=color)
    return rx + 10  # следующий x


def hline(draw, x0, x1, y, color, alpha=60, width=1):
    layer_col = color + (alpha,)
    draw.line([x0, y, x1, y], fill=layer_col, width=width)


# ══════════════════════════════════════════════════════════════════════════════
# 1. WELCOME.PNG  (1024 × 576)
# ══════════════════════════════════════════════════════════════════════════════

def make_welcome():
    W, H = 1024, 576
    img  = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img, "RGBA")

    SPLIT = 320  # граница paint / content зон

    # ── Краска (левая треть) ───────────────────────────────────────────────
    # Фоновый слой — чуть теплее
    paint_splash(img, 110, 200, CORAL,  count=160, max_r=100, alpha_base=200)
    paint_splash(img, 220, 350, GOLD,   count=100, max_r=70,  alpha_base=170)
    paint_splash(img, 60,  360, CORAL,  count=80,  max_r=55,  alpha_base=140)
    paint_splash(img, 260, 140, CYAN,   count=90,  max_r=60,  alpha_base=150)
    paint_splash(img, 170, 270, CYAN,   count=70,  max_r=45,  alpha_base=130)

    # Мазки кисти
    brush_stroke(img,  20, 180, 290, 420, CORAL, width=18, alpha=180)
    brush_stroke(img,  50, 300, 320, 160, CYAN,  width=12, alpha=160)
    brush_stroke(img, 120, 450, 310, 280, GOLD,  width=10, alpha=150)
    brush_stroke(img,  30,  80, 260, 350, CORAL, width=8,  alpha=120)

    # ── Диагональный разделитель ──────────────────────────────────────────
    for offset in range(-1, 2):
        alpha = 200 if offset == 0 else 60
        draw.line([SPLIT + offset - 30, 0, SPLIT + offset + 30, H],
                  fill=WHITE + (alpha,), width=1)

    # ── Правая зона (контент) ─────────────────────────────────────────────
    dot_grid(draw, SPLIT, 0, W, H, step=24, color=(255, 255, 255, 12))

    # Telegram logo — треугольник в круге
    tg_cx, tg_cy, tg_r = SPLIT + 100, 52, 22
    draw.ellipse(
        [tg_cx - tg_r, tg_cy - tg_r, tg_cx + tg_r, tg_cy + tg_r],
        outline=CYAN + (180,), width=2
    )
    # Paper-plane
    pts = [
        (tg_cx - 10, tg_cy + 6),
        (tg_cx + 14, tg_cy - 1),
        (tg_cx - 2,  tg_cy - 8),
    ]
    draw.polygon(pts, fill=CYAN + (200,))

    # Заголовок
    f_title = font(BOLD_FONT, 54)
    f_sub   = font(REG_FONT,  20)
    f_feat  = font(REG_FONT,  17)
    f_pill  = font(MONO_BOLD, 13)
    f_url   = font(MONO_FONT, 13)

    tx = SPLIT + 30
    draw.text((tx, 85),  "Центр Красок #1", font=f_title, fill=WHITE)
    draw.text((tx, 152), "AI Telegram-ассистент",  font=f_sub,   fill=CYAN)

    # Разделитель
    draw.line([tx, 185, W - 30, 185], fill=WHITE + (40,), width=1)

    # Фичи
    feats = [
        "Голосовые сообщения (Whisper STT)",
        "Контекст диалога + защита от галлюцинаций",
        "Оценка ответов + аналитика /stats",
        "Rate limiting · SQLite логирование",
    ]
    fy = 200
    for text in feats:
        draw.rectangle([tx, fy + 5, tx + 4, fy + 15], fill=CYAN)
        draw.text((tx + 14, fy), text, font=f_feat, fill=LGRAY)
        fy += 30

    # Badges
    draw.line([tx, fy + 5, W - 30, fy + 5], fill=WHITE + (40,), width=1)
    bx = tx
    bx = pill_badge(draw, bx, fy + 16, "LLaMA 3.1 8b", CORAL,  f_pill)
    bx = pill_badge(draw, bx, fy + 16, "Whisper",       GOLD,   f_pill)
    bx = pill_badge(draw, bx, fy + 16, "SQLite",        CYAN,   f_pill)

    # URL
    draw.text((tx, H - 32), "centr-krasok.kz  ·  Алматы  ·  Астана",
              font=f_url, fill=LGRAY + (180,))

    img.save("welcome.png", optimize=True)
    print("✓ welcome.png")


# ══════════════════════════════════════════════════════════════════════════════
# 2. BANNER.PNG  (1280 × 560)
# ══════════════════════════════════════════════════════════════════════════════

def make_banner():
    W, H  = 1280, 560
    img   = Image.new("RGB", (W, H), BG)
    draw  = ImageDraw.Draw(img, "RGBA")

    SPLIT = 480

    # ── Краска (левая зона) ───────────────────────────────────────────────
    paint_splash(img, 130, 220, CORAL,  count=200, max_r=130, alpha_base=210)
    paint_splash(img, 280, 390, GOLD,   count=120, max_r=90,  alpha_base=180)
    paint_splash(img,  60, 400, CORAL,  count=100, max_r=65,  alpha_base=150)
    paint_splash(img, 340, 130, CYAN,   count=130, max_r=80,  alpha_base=170)
    paint_splash(img, 200, 280, CYAN,   count=90,  max_r=55,  alpha_base=140)
    paint_splash(img,  80, 100, GOLD,   count=70,  max_r=50,  alpha_base=130)

    brush_stroke(img,  20, 200, 430, 460, CORAL, width=22, alpha=190)
    brush_stroke(img,  60, 320, 450, 140, CYAN,  width=15, alpha=170)
    brush_stroke(img, 150, 500, 460, 300, GOLD,  width=14, alpha=155)
    brush_stroke(img,  30,  70, 380, 380, CORAL, width=9,  alpha=120)

    # ── Разделитель ───────────────────────────────────────────────────────
    for offset in range(-1, 2):
        alpha = 210 if offset == 0 else 55
        draw.line([SPLIT + offset - 40, 0, SPLIT + offset + 40, H],
                  fill=WHITE + (alpha,), width=1)

    # ── Правая зона ───────────────────────────────────────────────────────
    dot_grid(draw, SPLIT, 0, W, H, step=26, color=(255, 255, 255, 11))

    f_tag    = font(MONO_FONT, 12)
    f_main   = font(BOLD_FONT, 72)
    f_num    = font(BOLD_FONT, 72)
    f_sub    = font(REG_FONT,  22)
    f_feat   = font(REG_FONT,  17)
    f_pill   = font(MONO_BOLD, 13)
    f_url    = font(MONO_FONT, 13)

    tx = SPLIT + 40

    # Теглайн
    draw.text((tx, 28), "// AI TELEGRAM ASSISTANT", font=f_tag, fill=CYAN + (160,))

    # Заголовок
    draw.text((tx, 55),  "Центр Красок",  font=f_main, fill=WHITE)
    draw.text((tx, 140), "#1",             font=f_num,  fill=CORAL)

    # Badges (под заголовком)
    bx = tx
    by = 230
    bx = pill_badge(draw, bx, by, "Python 3.11+",  CYAN,   f_pill)
    bx = pill_badge(draw, bx, by, "LLaMA 3.1 8b",  CORAL,  f_pill)
    bx = pill_badge(draw, bx, by, "Whisper STT",   GOLD,   f_pill)
    bx = pill_badge(draw, bx, by, "SQLite",        (140, 100, 255), f_pill)

    # Разделитель
    draw.line([tx, 270, W - 40, 270], fill=WHITE + (35,), width=1)

    # Фичи
    feats = [
        "—  Голосовые сообщения (Whisper STT)",
        "—  Контекст диалога + защита от галлюцинаций",
        "—  Кнопки оценки + аналитика /stats",
        "—  6 языковых режимов · Rate limiting",
    ]
    fy = 284
    for line in feats:
        draw.text((tx, fy), line, font=f_feat, fill=LGRAY)
        fy += 30

    # GitHub URL
    draw.text((tx, H - 58),
              "github.com/Sardrbek505/centr-krasok-bot",
              font=f_url, fill=CYAN + (160,))
    draw.text((tx, H - 36),
              "centr-krasok.kz  ·  Алматы  ·  Астана  ·  Казахстан",
              font=f_url, fill=LGRAY + (120,))

    img.save("banner.png", optimize=True)
    print("✓ banner.png")


# ══════════════════════════════════════════════════════════════════════════════
# 3. PROFILE_PHOTO.PNG  (512 × 512, круглое)
# ══════════════════════════════════════════════════════════════════════════════

def make_profile():
    SIZE = 512
    img  = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img, "RGBA")

    # ── Заполняем тёмный круг ─────────────────────────────────────────────
    draw.ellipse([0, 0, SIZE, SIZE], fill=BG + (255,))

    # ── Dot grid ─────────────────────────────────────────────────────────
    dot_grid(draw, 0, 0, SIZE, SIZE, step=20, color=(255, 255, 255, 14))

    # ── Краска по углам ───────────────────────────────────────────────────
    paint_splash(img, 80,  400, CORAL, count=90, max_r=70, alpha_base=160)
    paint_splash(img, 420, 100, CYAN,  count=80, max_r=65, alpha_base=150)
    paint_splash(img, 400, 420, GOLD,  count=50, max_r=45, alpha_base=130)

    # ── Кисть (центрирована, занимает верхние 2/3) ────────────────────────
    # Ручка
    draw.polygon(
        [(236, 60), (254, 60), (294, 230), (276, 230)],
        fill=(220, 225, 235, 230)
    )
    # Металл (ferrule)
    draw.rectangle([272, 228, 298, 260], fill=(160, 170, 180, 240))
    # Щетина
    bristle_pts = [
        (268, 258), (302, 258),
        (314, 340), (256, 355),
    ]
    draw.polygon(bristle_pts, fill=CORAL + (220,))
    # Капля краски
    drop_cx, drop_cy = 282, 365
    draw.ellipse([drop_cx - 9, drop_cy - 12, drop_cx + 9, drop_cy + 12],
                 fill=CORAL + (230,))
    draw.ellipse([drop_cx - 4, drop_cy + 8, drop_cx + 4, drop_cy + 20],
                 fill=CORAL + (200,))

    # Дуга цианом над кистью
    draw.arc([180, 50, 300, 120], start=200, end=340,
             fill=CYAN + (200,), width=3)

    # ── Текст (нижняя четверть) ───────────────────────────────────────────
    f_big   = font(BOLD_FONT, 66)
    f_small = font(REG_FONT,  19)

    draw.text((SIZE // 2, 420), "#1",
              font=f_big, fill=WHITE, anchor="mm")
    draw.text((SIZE // 2, 470), "Центр Красок",
              font=f_small, fill=CYAN, anchor="mm")

    # ── Двойное кольцо ────────────────────────────────────────────────────
    draw.ellipse([4, 4, SIZE - 4, SIZE - 4],
                 outline=CYAN + (150,), width=2)
    draw.ellipse([10, 10, SIZE - 10, SIZE - 10],
                 outline=WHITE + (30,), width=1)

    # Обрезаем по кругу
    mask = Image.new("L", (SIZE, SIZE), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, SIZE, SIZE], fill=255)
    result = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    result.paste(img, mask=mask)

    result.save("profile_photo.png", optimize=True)
    print("✓ profile_photo.png")


if __name__ == "__main__":
    import os
    os.chdir("/home/user/centr-krasok-bot")
    make_welcome()
    make_banner()
    make_profile()
    print("Все изображения созданы.")
