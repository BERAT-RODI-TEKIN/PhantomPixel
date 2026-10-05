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

DEMO_DIR = WORKSPACE / "demo"
DEMO_PASSWORD = "phantom"
DEMO_MESSAGE = (
    "SECRET DOCUMENT\n"
    "---------------\n"
    "This text was hidden inside the pixels of an image.\n"
    "Only the lowest bit of each red, green and blue value was changed:\n"
    "a colour moves by at most 1/255, which the human eye cannot notice.\n\n"
    "Without the password the text cannot be read (AES-256-GCM), and the hidden\n"
    "bits are scattered across the whole image, so there is no pattern to find.\n\n"
    "- PhantomPixel"
)


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


def run(message: str = DEMO_MESSAGE, password: str | None = DEMO_PASSWORD,
        on_step: Callable[[str], None] = lambda s: None) -> DemoResult:
    on_step("Generating a cover image")
    cover = make_cover(DEMO_DIR / "demo_cover.png")

    on_step("Hiding the message inside the pixels")
    res = workflows.hide(cover, text=message, password=password, output=DEMO_DIR / "demo_hidden.png")

    on_step("Extracting it again to verify")
    recovered = workflows.extract(res.output, password).text or ""

    on_step("Building the comparison card")
    card = workflows.make_card(cover, res.output, DEMO_DIR / "demo_card.png")

    return DemoResult(DEMO_DIR, cover, res.output, card, message, recovered,
                      analyzer.compare(cover, res.output), res.stored_bytes, password)
