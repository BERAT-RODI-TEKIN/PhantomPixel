"""Tiny translation layer: English, Turkish and Russian. Standard library only.

    from . import i18n
    i18n.t("hide.done")                  # text in the current language
    i18n.t("err.capacity", need=5, cap=3)

Language order of precedence: --lang flag > PHANTOMPIXEL_LANG > saved choice > system language > English.
Missing keys fall back to English, so a half-finished translation never crashes the program.
"""
from __future__ import annotations

import json
import os
import sys

from .config import SETTINGS_FILE
from .locales import en, ru, tr

SUPPORTED = ("en", "tr", "ru")
NAMES = {"en": "English", "tr": "Türkçe", "ru": "Русский"}
_TABLES = {"en": en.S, "tr": tr.S, "ru": ru.S}
_ALIASES = {"english": "en", "turkish": "tr", "türkçe": "tr", "turkce": "tr", "russian": "ru", "русский": "ru"}
_current = "en"


def t(key: str, **kw) -> str:
    """Translated text for `key` in the current language (English fallback, then the key itself)."""
    text = _TABLES[_current].get(key) or _TABLES["en"].get(key) or key
    if kw:
        try:
            return text.format(**kw)
        except (KeyError, IndexError, ValueError):
            return text
    return text


def t_en(key: str) -> str:
    """The English text for `key`, whatever the current language is."""
    return _TABLES["en"].get(key, key)


def normalize(code: str | None) -> str | None:
    """'tr', 'TR', 'tr_TR', 'tr-TR.UTF-8', 'Türkçe' -> 'tr'. Unknown values -> None."""
    if not code:
        return None
    c = code.strip().lower()
    if c in _ALIASES:
        return _ALIASES[c]
    c = c.replace("-", "_").split(".")[0].split("_")[0]
    return c if c in SUPPORTED else None


def get_language() -> str:
    return _current


def set_language(code: str, persist: bool = False) -> str:
    """Switches the language. With persist=True the choice is remembered for the next start."""
    global _current
    lang = normalize(code)
    if lang is None:
        raise ValueError(f"unsupported language: {code!r}")
    _current = lang
    if persist:
        save_setting("language", lang)
    return lang


# --- remembered settings (~/PhantomPixel/settings.json) -----------------------
def load_settings() -> dict:
    try:
        data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_setting(key: str, value) -> None:
    """Best effort: a read-only home folder must never break the program."""
    try:
        data = load_settings()
        data[key] = value
        SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        SETTINGS_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


def system_language() -> str | None:
    if sys.platform.startswith("win"):
        try:
            import ctypes
            primary = ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3FF  # type: ignore[attr-defined]
            return {0x1F: "tr", 0x19: "ru", 0x09: "en"}.get(primary)
        except Exception:  # noqa: BLE001
            return None
    for var in ("LC_ALL", "LC_MESSAGES", "LANGUAGE", "LANG"):
        lang = normalize(os.environ.get(var, "").split(":")[0])
        if lang:
            return lang
    return None


def resolve(cli: str | None = None) -> str:
    return (normalize(cli) or normalize(os.environ.get("PHANTOMPIXEL_LANG"))
            or normalize(load_settings().get("language")) or system_language() or "en")


def init(cli: str | None = None) -> str:
    """Picks the language for this run (see the module docstring for the order)."""
    return set_language(resolve(cli))
