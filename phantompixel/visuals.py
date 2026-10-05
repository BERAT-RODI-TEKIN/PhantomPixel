"""Visuals: difference map, LSB plane and a shareable comparison card."""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

from .analyzer import Comparison
from .config import APP_NAME, BG_RGB, PANEL_RGB, RED_RGB
from .engine import load_array
from .utils import human_size

_BOLD_FONTS = ("DejaVuSans-Bold.ttf", "arialbd.ttf", "Arial Bold.ttf", "segoeuib.ttf")
_MONO_FONTS = ("DejaVuSansMono-Bold.ttf", "consolab.ttf", "Menlo.ttc", "cour.ttf")


def _font(size: int, mono: bool = False) -> ImageFont.ImageFont:
    for name in (_MONO_FONTS if mono else _BOLD_FONTS):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    try:
        return ImageFont.load_default(size)
    except TypeError:  # eski Pillow
        return ImageFont.load_default()


def diff_map(original: str | Path, stego: str | Path, max_side: int = 640) -> Image.Image:
    """Shows changed pixels in red on top of a darkened original."""
    a = load_array(original)[..., :3]
    b = load_array(stego)[..., :3]
    changed = (a != b).any(axis=2).astype(np.uint8) * 255

    h, w = changed.shape
    scale = min(1.0, max_side / max(h, w))
    size = (max(1, int(w * scale)), max(1, int(h * scale)))
    # BOX downscaling keeps even a single changed pixel in a block above zero
    mask = Image.fromarray(changed).resize(size, Image.BOX)
    mask = Image.fromarray(((np.array(mask) > 0) * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(5))

    base = Image.fromarray(a).resize(size, Image.LANCZOS).convert("L").convert("RGB")
    base = ImageEnhance.Brightness(base).enhance(0.28)
    return Image.composite(Image.new("RGB", size, RED_RGB), base, mask)


def lsb_plane(path: str | Path) -> Image.Image:
    """Renders only the least significant bit plane in red and black."""
    arr = load_array(path)[..., :3]
    level = ((arr & 1).sum(axis=2) * 85).astype(np.uint8)  # 0, 85, 170, 255
    out = np.stack([level, level // 6, level // 6], axis=2)
    return Image.fromarray(out)


def comparison_card(original: str | Path, stego: str | Path, output: str | Path,
                    stats: Comparison, hidden_bytes: int, encrypted: bool) -> Path:
    """1920x1080 share card: original | with hidden data | difference map."""
    W, H, PAD, GAP, BOX = 1920, 1080, 60, 40, 560
    card = Image.new("RGB", (W, H), BG_RGB)
    d = ImageDraw.Draw(card)

    # Title
    d.text((W // 2, 85), APP_NAME.upper(), font=_font(92), fill=RED_RGB, anchor="mm")
    d.text((W // 2, 160), "Which one hides a secret?", font=_font(38), fill=(210, 210, 215), anchor="mm")

    panels = [
        ("ORIGINAL", Image.open(original).convert("RGB")),
        ("HIDDEN DATA INSIDE", Image.open(stego).convert("RGB")),
        ("DIFFERENCE MAP", diff_map(original, stego)),
    ]
    x0 = (W - (3 * BOX + 2 * GAP)) // 2
    for i, (label, img) in enumerate(panels):
        x, y = x0 + i * (BOX + GAP), 230
        d.rectangle((x - 3, y - 3, x + BOX + 3, y + BOX + 3), fill=PANEL_RGB, outline=RED_RGB, width=2)
        card.paste(ImageOps.pad(img, (BOX, BOX), Image.LANCZOS, color=PANEL_RGB), (x, y))
        d.text((x + BOX // 2, y + BOX + 38), label, font=_font(30), fill=(235, 235, 240), anchor="mm")

    # Stats strip
    psnr = "∞" if stats.psnr == float("inf") else f"{stats.psnr:.1f} dB"
    items = [
        ("PSNR", psnr),
        ("CHANGED PIXELS", f"{stats.changed_pixels_pct:.3f}%"),
        ("HIDDEN DATA", human_size(hidden_bytes)),
        ("PROTECTION", "AES-256-GCM" if encrypted else "None"),
    ]
    slot = (W - 2 * PAD) // len(items)
    for i, (k, v) in enumerate(items):
        cx = PAD + slot * i + slot // 2
        d.text((cx, 905), v, font=_font(44, mono=True), fill=RED_RGB, anchor="mm")
        d.text((cx, 955), k, font=_font(22), fill=(150, 150, 158), anchor="mm")

    d.text((W // 2, 1030), "LSB steganography  •  The lowest bit of every colour channel carries data",
           font=_font(24), fill=(110, 110, 118), anchor="mm")

    out = Path(output)
    out.parent.mkdir(parents=True, exist_ok=True)
    card.save(out, format="PNG")
    return out

