"""Start-up animation: a field of noise "pixels" resolves into the PHANTOMPIXEL banner,
then the tagline is typed out. It is the program's idea in miniature: a picture that
looks like noise and hides a message.

The animation is skipped (the caller prints the plain banner instead) when
  * the output is not a real terminal (pipes, files, CI),
  * --no-anim was given or the environment variable PHANTOMPIXEL_NO_ANIM is set,
  * the window is too small for it.
It needs `rich` only; the last frame is exactly the static banner.
"""
from __future__ import annotations

import os
import random
import time
from typing import Callable

from rich.console import Console
from rich.live import Live
from rich.text import Text

_NOISE = "░▒▓"
_DUST = "·:"
_NOISE_STYLES = ("#4a0a14", "#7a0f1f", "#b71c1c")   # dark -> bright red noise
_CURSOR = "▌"


def should_animate(console: Console, disabled: bool = False) -> bool:
    if disabled or os.environ.get("PHANTOMPIXEL_NO_ANIM"):
        return False
    return bool(console.is_terminal and not console.is_dumb_terminal)


def _frame(lines: list[str], gradient: list[str], progress: float, thresholds: list[list[float]],
           rng: random.Random, console_width: int) -> Text:
    """One animation frame: cells whose threshold has been passed show the real character."""
    out = Text(no_wrap=True, overflow="crop")
    for row, line in enumerate(lines):
        out.append(" " * max(0, (console_width - len(line)) // 2))
        final_style = gradient[row % len(gradient)]
        for col, ch in enumerate(line):
            if ch == " ":
                # faint static around the letters, fading as the picture sharpens
                if rng.random() < (1 - progress) * 0.07:
                    out.append(rng.choice(_DUST), style=_NOISE_STYLES[0])
                else:
                    out.append(" ")
                continue
            reveal_at = thresholds[row][col]
            if progress >= reveal_at:
                out.append(ch, style=final_style)
            elif progress >= reveal_at - 0.18:      # about to resolve: bright flicker
                out.append(rng.choice(_NOISE), style=_NOISE_STYLES[2])
            else:
                out.append(rng.choice(_NOISE), style=rng.choice(_NOISE_STYLES[:2]))
        if row != len(lines) - 1:
            out.append("\n")
    return out


def play(console: Console, lines: list[str], gradient: list[str], tagline: str, version: str,
         grey: str = "#9e9e9e", *, frames: int = 22, delay: float = 0.04, type_delay: float = 0.012,
         sleep: Callable[[float], None] = time.sleep, seed: int | None = None) -> bool:
    """Plays the animation. Returns False (and prints nothing) when it cannot run here."""
    if not lines:
        return False
    widest = max(len(line) for line in lines)
    if widest > console.width or len(lines) + 4 > console.height:
        return False

    rng = random.Random(seed)
    # A left-to-right sweep with random jitter, so the picture "develops" like a photograph
    thresholds = [[0.7 * rng.random() + 0.3 * (c / max(1, widest)) for c in range(len(line))] for line in lines]

    def tag_text(shown: int, cursor: bool) -> Text:
        pad = " " * max(0, (console.width - len(tagline) - len(version) - 5) // 2)
        txt = Text(no_wrap=True, overflow="crop")
        txt.append(pad)
        txt.append(tagline[:shown], style=grey)
        if shown >= len(tagline):
            txt.append(f"  •  v{version}", style=grey)
        elif cursor:
            txt.append(_CURSOR, style=gradient[2 % len(gradient)])
        return txt

    from rich.console import Group

    try:
        with Live(console=console, auto_refresh=False, transient=False, vertical_overflow="visible") as live:
            try:
                for i in range(frames + 1):
                    progress = (i / frames) * 1.2          # >1 so every cell has resolved by the end
                    live.update(Group(_frame(lines, gradient, progress, thresholds, rng, console.width),
                                      Text(""), tag_text(0, True)), refresh=True)
                    sleep(delay)
                picture = _frame(lines, gradient, 2.0, thresholds, rng, console.width)
                for n in range(len(tagline) + 1):
                    live.update(Group(picture, Text(""), tag_text(n, True)), refresh=True)
                    sleep(type_delay)
            except KeyboardInterrupt:                       # Ctrl+C = skip the show
                pass
            live.update(Group(_frame(lines, gradient, 2.0, thresholds, rng, console.width),
                              Text(""), tag_text(len(tagline), False)), refresh=True)
    except Exception:  # noqa: BLE001  # a cosmetic feature must never stop the program
        return False
    console.print()
    return True
