"""Workflows: glue between engine / analyzer / visuals.

Both the interactive UI (ui.py) and the command line (main.py) call these
functions, so the logic lives in exactly one place.

Output location rule: results are written NEXT TO the input image, so the user
always knows where to find them.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from . import analyzer, engine, visuals
from .engine import HideResult, Payload
from .errors import StegoError
from .utils import unique_path


@dataclass
class Extracted:
    payload: Payload
    text: str | None   # the message, if the secret was text
    saved: Path | None  # where the file was written, if the secret was a file


@dataclass
class Inspection:
    signature: dict | None
    detection: analyzer.Detection
    comparison: analyzer.Comparison | None


def hide(cover: str | Path, text: str | None = None, file: str | Path | None = None,
         password: str | None = None, output: str | Path | None = None,
         verify: bool = True) -> HideResult:
    if (text is None) == (file is None):
        raise StegoError("Provide either a text message or a file to hide (exactly one).")
    cover = Path(cover)
    if file is not None:
        p = Path(file)
        if not p.is_file():
            raise StegoError(f"File not found: {p}")
        payload = Payload("file", p.name, p.read_bytes())
    else:
        payload = Payload("text", "", text.encode("utf-8"))  # text needs no file name

    out = Path(output).with_suffix(".png") if output else unique_path(cover.with_name(f"{cover.stem}_phantom.png"))
    return engine.hide(cover, payload, out, password, verify)


def extract(stego: str | Path, password: str | None = None,
            outdir: str | Path | None = None) -> Extracted:
    stego = Path(stego)
    payload = engine.extract(stego, password)
    if payload.kind == "text":
        return Extracted(payload, payload.data.decode("utf-8", "replace"), None)

    # Never trust the file name stored inside an image: strip folders and illegal characters.
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", Path(payload.name).name).strip(". ") or "hidden_file.bin"
    folder = Path(outdir) if outdir else stego.parent / f"{stego.stem}_extracted"
    folder.mkdir(parents=True, exist_ok=True)
    target = unique_path(folder / name)
    target.write_bytes(payload.data)
    return Extracted(payload, None, target)


def save_text(text: str, near: str | Path) -> Path:
    near = Path(near)
    out = unique_path(near.with_name(f"{near.stem}_message.txt"))
    out.write_text(text, encoding="utf-8")
    return out


def inspect(stego: str | Path, original: str | Path | None = None) -> Inspection:
    return Inspection(
        signature=engine.inspect(stego),
        detection=analyzer.detect(stego),
        comparison=analyzer.compare(original, stego) if original else None,
    )


def make_card(original: str | Path, stego: str | Path, output: str | Path | None = None) -> Path:
    info = engine.inspect(stego) or {"stored_bytes": 0, "encrypted": False}
    out = Path(output) if output else unique_path(Path(stego).with_name(f"{Path(stego).stem}_card.png"))
    return visuals.comparison_card(
        original, stego, out, analyzer.compare(original, stego),
        info["stored_bytes"], info["encrypted"],
    )


def save_lsb_plane(path: str | Path, output: str | Path | None = None) -> Path:
    path = Path(path)
    out = Path(output) if output else unique_path(path.with_name(f"{path.stem}_lsb.png"))
    visuals.lsb_plane(path).save(out)
    return out


def open_file(path: str | Path) -> None:
    """Opens a file with the system's default app (silent on failure)."""
    try:
        if sys.platform.startswith("win"):
            os.startfile(str(path))  # type: ignore[attr-defined]
        else:
            cmd = "open" if sys.platform == "darwin" else "xdg-open"
            subprocess.Popen([cmd, str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:  # noqa: BLE001
        pass


def reveal(path: str | Path) -> None:
    """Shows a file in its folder (selected in Explorer / Finder where possible)."""
    path = Path(path)
    try:
        if sys.platform.startswith("win"):
            subprocess.Popen(f'explorer /select,"{path}"')
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R", str(path)])
        else:
            open_file(path.parent)
    except Exception:  # noqa: BLE001
        open_file(path.parent)
