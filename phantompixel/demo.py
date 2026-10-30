"""One-key demo: builds its own cover image, hides a message, recovers it, makes a card.

It needs no external files, so it also works unchanged inside the single-file .exe.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np
from PIL import Image

from . import analyzer, workflows
from .config import WORKSPACE
from .i18n import t

DEMO_DIR = WORKSPACE / "demo"
DEMO_PASSWORD = "phantom"


@dataclass
class DemoResult:
    folder: Path
    cover: Path
    stego: Path
    card: Path
    message: str
    recovered: str
    comparison: analyzer.Comparison
    stored_bytes: int
    password: str | None


def make_cover(path: Path, w: int = 1280, h: int = 800, seed: int = 7) -> Path:
    """Generates a red/black plasma image (with camera-like noise so it looks natural)."""
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    v = (np.sin(x / 90) + np.sin(y / 70) + np.sin((x + y) / 120)
         + np.sin(np.hypot(x - w / 2, y - h / 2) / 60))
    v = (v - v.min()) / (v.max() - v.min())
    r = 255 * np.clip(v * 1.5 - 0.25, 0, 1) ** 1.6
    g = 70 * v ** 3
    b = 95 * (1 - v) ** 2 + 25 * v
    rgb = np.stack([r, g, b], axis=2)
    rgb += np.random.default_rng(seed).normal(0, 2.0, rgb.shape)
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8)).save(path)
    return path


def run(message: str | None = None, password: str | None = DEMO_PASSWORD,
        on_step: Callable[[str], None] = lambda s: None) -> DemoResult:
    message = message if message is not None else t("demo.message")
    on_step(t("demo.step_cover"))
    cover = make_cover(DEMO_DIR / "demo_cover.png")

    on_step(t("demo.step_hide"))
    res = workflows.hide(cover, text=message, password=password, output=DEMO_DIR / "demo_hidden.png")

    on_step(t("demo.step_extract"))
    recovered = workflows.extract(res.output, password).text or ""

    on_step(t("demo.step_card"))
    card = workflows.make_card(cover, res.output, DEMO_DIR / "demo_card.png")

    return DemoResult(DEMO_DIR, cover, res.output, card, message, recovered,
                      analyzer.compare(cover, res.output), res.stored_bytes, password)
