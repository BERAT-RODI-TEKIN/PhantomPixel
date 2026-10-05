"""Small shared helpers."""
from pathlib import Path

from .config import LOSSY_EXTENSIONS


def human_size(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    if n < 1024 ** 2:
        return f"{n / 1024:.1f} KB"
    return f"{n / 1024 ** 2:.1f} MB"


def bar(ratio: float, width: int = 20) -> str:
    """Turns a 0..1 value into a text bar."""
    filled = max(0, min(width, round(ratio * width)))
    return "█" * filled + "░" * (width - filled)


def unique_path(path: Path) -> Path:
    """Returns `path`, or 'name (1).ext', 'name (2).ext'... if it already exists."""
    path = Path(path)
    if not path.exists():
        return path
    n = 1
    while True:
        candidate = path.with_name(f"{path.stem} ({n}){path.suffix}")
        if not candidate.exists():
            return candidate
        n += 1


def is_lossy(path: Path) -> bool:
    return Path(path).suffix.lower() in LOSSY_EXTENSIONS
