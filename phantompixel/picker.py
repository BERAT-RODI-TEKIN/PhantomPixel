"""Native file-open dialog (tkinter, ships with Python and with the .exe).

pick() returns None when the user cancels and raises PickerUnavailable when no
dialog can be shown (e.g. a headless server), so callers can fall back to typing a path.
"""
from __future__ import annotations

import sys
from pathlib import Path

IMAGE_TYPES = [("Images", "*.png *.jpg *.jpeg *.bmp *.webp *.tif *.tiff"), ("All files", "*.*")]
ANY_TYPES = [("All files", "*.*")]

_last_dir: str | None = None


class PickerUnavailable(Exception):
    """No file dialog can be shown in this environment."""


def pick(kind: str = "image", title: str = "Choose a file") -> Path | None:
    global _last_dir
    try:
        import tkinter as tk
        from tkinter import filedialog

        if sys.platform.startswith("win"):
            try:  # crisp dialogs on high-DPI screens (smartboards, laptops)
                import ctypes
                ctypes.windll.shcore.SetProcessDpiAwareness(1)
            except Exception:  # noqa: BLE001
                pass
        root = tk.Tk()
    except Exception as exc:  # noqa: BLE001
        raise PickerUnavailable(str(exc)) from exc

    try:
        root.withdraw()
        root.attributes("-topmost", True)
        root.update()
        options = {"parent": root, "title": title, "filetypes": IMAGE_TYPES if kind == "image" else ANY_TYPES}
        if _last_dir:
            options["initialdir"] = _last_dir
        name = filedialog.askopenfilename(**options)
    finally:
        root.destroy()

    if not name:
        return None
    _last_dir = str(Path(name).parent)
    return Path(name)
