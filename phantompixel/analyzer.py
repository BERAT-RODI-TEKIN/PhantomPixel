"""Analysis tools: comparison with the original and a statistical LSB detector."""
from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .engine import load_array
from .errors import StegoError


@dataclass
class Comparison:
    psnr: float
    changed_pixels_pct: float
    changed_values_pct: float
    max_diff: int


@dataclass
class Detection:
    chi2: float
    suspicion: float  # 0..1
    verdict: str


def compare(original: str | Path, stego: str | Path) -> Comparison:
    a = load_array(original)[..., :3].astype(np.int16)
    b = load_array(stego)[..., :3].astype(np.int16)
    if a.shape != b.shape:
        raise StegoError("The two images have different sizes and cannot be compared.")
    diff = a - b
    mse = float(np.mean(diff.astype(np.float64) ** 2))
    psnr = float("inf") if mse == 0 else 10 * math.log10(255 ** 2 / mse)
    return Comparison(
        psnr=psnr,
        changed_pixels_pct=float((diff != 0).any(axis=2).mean() * 100),
        changed_values_pct=float((diff != 0).mean() * 100),
        max_diff=int(np.abs(diff).max()),
    )


def detect(path: str | Path) -> Detection:
    """Simplified Westfeld-Pfitzmann chi-square attack.

    LSB embedding equalises the counts of the value pairs (2k, 2k+1). The more
    balanced the pairs, the lower the chi-square value. This is a HEURISTIC: it is
    strong for heavily filled images and weak for lightly filled or scattered ones,
    and it can raise false alarms on natural images. A low score never proves
    that an image is clean.
    """
    vals = load_array(path)[..., :3].reshape(-1)
    hist = np.bincount(vals, minlength=256).astype(np.float64)
    even, odd = hist[0::2], hist[1::2]
    expected = (even + odd) / 2
    mask = expected > 5
    k = int(mask.sum()) - 1
    if k < 8:
        return Detection(0.0, 0.0, "Not enough data to analyse")

    chi2 = float((((even[mask] - expected[mask]) ** 2) / expected[mask]).sum())
    # Right-tail chi-square probability via the Wilson-Hilferty approximation (no scipy needed)
    z = ((chi2 / k) ** (1 / 3) - (1 - 2 / (9 * k))) / math.sqrt(2 / (9 * k))
    suspicion = 0.5 * math.erfc(z / math.sqrt(2))

    if suspicion > 0.9:
        verdict = "High suspicion: value pairs are unusually balanced"
    elif suspicion > 0.5:
        verdict = "Medium suspicion"
    else:
        verdict = "Low suspicion: no obvious LSB trace"
    return Detection(chi2, suspicion, verdict)
