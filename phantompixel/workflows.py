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
from .i18n import t
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


def make_payload(text: str | None = None, file: str | Path | None = None) -> Payload:
    """Builds the secret from a message or a file (exactly one of them)."""
    if (text is None) == (file is None):
        raise StegoError(t("err.need_one"))
    if file is not None:
        p = Path(file)
        if not p.is_file():
            raise StegoError(t("err.file_not_found", path=p))
        return Payload("file", p.name, p.read_bytes())
    return Payload("text", "", text.encode("utf-8"))  # text needs no file name


def hide(cover: str | Path, text: str | None = None, file: str | Path | None = None,
         password: str | None = None, output: str | Path | None = None,
         verify: bool = True) -> HideResult:
    payload = make_payload(text, file)
    cover = Path(cover)
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


def capacity_info(path: str | Path) -> dict:
    """Size and capacity of an image (bytes of incompressible data)."""
    w, h = engine.image_size(path)
    return {"width": w, "height": h,
            "capacity_bytes": engine.capacity_for(w, h),
            "capacity_bytes_with_password": engine.capacity_for(w, h, True)}


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


# --------------------------------------------------------------------------
# Plain-data views of the results (used by `--json`; keys are stable and language independent)
# --------------------------------------------------------------------------
def hide_to_dict(res: HideResult) -> dict:
    return {"output": str(res.output), "stored_bytes": res.stored_bytes, "original_bytes": res.original_bytes,
            "compressed": res.compressed, "encrypted": res.encrypted, "verified": res.verified,
            "capacity_bytes": res.capacity_bytes, "usage": round(res.usage, 6)}


def extract_to_dict(res: Extracted) -> dict:
    out: dict = {"kind": res.payload.kind, "size": len(res.payload.data)}
    if res.text is not None:
        out["text"] = res.text
    else:
        out["name"] = res.payload.name
        out["saved"] = str(res.saved)
    return out


def inspection_to_dict(r: Inspection) -> dict:
    out: dict = {
        "signature": r.signature,
        "detection": {"chi2": r.detection.chi2, "suspicion": r.detection.suspicion, "level": r.detection.level},
        "comparison": None,
    }
    if r.comparison:
        c = r.comparison
        out["comparison"] = {"psnr": None if c.psnr == float("inf") else c.psnr,
                             "changed_pixels_pct": c.changed_pixels_pct,
                             "changed_values_pct": c.changed_values_pct, "max_diff": c.max_diff}
    return out
