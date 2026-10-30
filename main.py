#!/usr/bin/env python3
"""PhantomPixel - single entry point.

Run without arguments for the interactive menu (this is also what double-clicking
the .exe does). Drag an image onto the program and it figures out what to do:
it extracts if the image holds hidden data, otherwise it starts hiding.

Scripting:

    python main.py                                   # interactive menu (with start-up animation)
    python main.py photo.png                         # smart mode (same as drag & drop)
    python main.py demo                              # one-key demo
    python main.py hide cover.png -m "secret text"   # hide a message
    python main.py hide cover.png -f report.pdf -p   # hide a file, ask for a password
    python main.py extract hidden.png -p             # extract (asks for the password)
    python main.py inspect hidden.png --original cover.png
    python main.py capacity cover.png                # how much fits?
    python main.py card cover.png hidden.png         # shareable comparison card

Options that work everywhere:
    --lang en|tr|ru     interface language (the menu remembers your choice)
    --no-anim           skip the start-up animation (or set PHANTOMPIXEL_NO_ANIM=1)
    --json              (hide / extract / inspect / capacity) machine-readable output;
                        in scripts the password can come from PHANTOMPIXEL_PASSWORD
"""
from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
from pathlib import Path

from phantompixel import __version__, i18n
from phantompixel.i18n import t

COMMANDS = {"demo", "hide", "extract", "inspect", "capacity", "card"}
REQUIRED = {"rich": "rich", "cryptography": "cryptography", "PIL": "pillow", "numpy": "numpy"}
_VALUE_OPTIONS = {"-m", "--message", "-f", "--file", "-o", "--output", "--original"}


def _missing_deps(skip: tuple[str, ...] = ()) -> list[str]:
    import importlib.util
    return [pkg for mod, pkg in REQUIRED.items() if mod not in skip and importlib.util.find_spec(mod) is None]


def ensure_deps(skip: tuple[str, ...] = ()) -> bool:
    """Offers to install missing libraries (source runs only). Returns True when ready."""
    if getattr(sys, "frozen", False):  # inside the .exe everything is already bundled
        return True
    missing = _missing_deps(skip)
    if not missing:
        return True

    import importlib
    import subprocess

    cmd = [sys.executable, "-m", "pip", "install", "-r", str(Path(__file__).with_name("requirements.txt"))]
    print(f"\n{t('cli.missing', libs=', '.join(missing))}")
    print(t("cli.python_in_use", path=sys.executable))
    try:
        answer = input(t("cli.install_ask")).strip().lower()
    except EOFError:
        answer = "n"
    if answer in ("", "y", "yes", "e", "evet", "д", "да"):
        if subprocess.call(cmd) == 0:
            importlib.invalidate_caches()
            return not _missing_deps(skip)
        print(f"\n{t('cli.install_failed')}")
        if sys.platform.startswith("linux"):
            print(t("cli.install_venv"))
    else:
        print(f"\n{t('cli.install_manual')}")
        print(f'    "{sys.executable}" -m pip install -r requirements.txt')
    return False


def split_global_options(argv: list[str]) -> tuple[list[str], str | None, bool]:
    """Removes --lang / --no-anim from argv wherever they appear (before or after the command)."""
    rest: list[str] = []
    lang: str | None = None
    no_anim = False
    i = 0
    while i < len(argv):
        a = argv[i]
        takes_value = bool(rest) and rest[-1] in _VALUE_OPTIONS   # `-m --lang` is a message, not an option
        if not takes_value and a == "--lang" and i + 1 < len(argv):
            lang, i = argv[i + 1], i + 2
        elif not takes_value and a.startswith("--lang="):
            lang, i = a.split("=", 1)[1], i + 1
        elif not takes_value and a == "--no-anim":
            no_anim, i = True, i + 1
        else:
            rest.append(a)
            i += 1
    return rest, lang, no_anim


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="PhantomPixel", description=t("cli.description"), epilog=t("cli.epilog"))
    p.add_argument("--version", action="version", version=f"PhantomPixel {__version__}")
    # Handled by split_global_options(); declared here so they show up in --help
    p.add_argument("--lang", choices=i18n.SUPPORTED, default=argparse.SUPPRESS, help=t("cli.h_lang"))
    p.add_argument("--no-anim", action="store_true", default=argparse.SUPPRESS, help=t("cli.h_noanim"))
    sub = p.add_subparsers(dest="cmd")

    sub.add_parser("demo", help=t("cli.h_demo"))

    h = sub.add_parser("hide", help=t("cli.h_hide"))
    h.add_argument("cover", help=t("cli.h_cover"))
    g = h.add_mutually_exclusive_group(required=True)
    g.add_argument("-m", "--message", help=t("cli.h_message"))
    g.add_argument("-f", "--file", help=t("cli.h_file"))
    h.add_argument("-p", "--password", action="store_true", help=t("cli.h_pw_hide"))
    h.add_argument("-o", "--output", help=t("cli.h_output"))
    h.add_argument("--card", action="store_true", help=t("cli.h_card"))
    h.add_argument("--no-verify", action="store_true", help=t("cli.h_noverify"))
    h.add_argument("--json", action="store_true", help=t("cli.h_json"))

    e = sub.add_parser("extract", help=t("cli.h_extract"))
    e.add_argument("stego", help=t("cli.h_stego"))
    e.add_argument("-p", "--password", action="store_true", help=t("cli.h_pw_extract"))
    e.add_argument("--json", action="store_true", help=t("cli.h_json"))

    i = sub.add_parser("inspect", help=t("cli.h_inspect"))
    i.add_argument("stego")
    i.add_argument("--original", help=t("cli.h_original"))
    i.add_argument("--json", action="store_true", help=t("cli.h_json"))

    k = sub.add_parser("capacity", help=t("cli.h_capacity"))
    k.add_argument("image", help=t("cli.h_capacity_image"))
    k.add_argument("--json", action="store_true", help=t("cli.h_json"))

    c = sub.add_parser("card", help=t("cli.h_card_cmd"))
    c.add_argument("original")
    c.add_argument("stego")
    return p


def _pw(flag: bool) -> str | None:
    if not flag:
        return None
    env = os.environ.get("PHANTOMPIXEL_PASSWORD")   # for scripts and --json use, where nobody can type
    return env if env else (getpass.getpass(t("cli.pw_prompt")) or None)


def run_json(args: argparse.Namespace) -> int:
    """Machine-readable mode: stdout carries exactly one JSON object, nothing else."""
    from phantompixel import workflows
    from phantompixel.errors import StegoError

    try:
        if args.cmd == "hide":
            res = workflows.hide(args.cover, text=args.message, file=args.file, password=_pw(args.password),
                                 output=args.output, verify=not args.no_verify)
            out = workflows.hide_to_dict(res)
            if args.card:
                out["card"] = str(workflows.make_card(args.cover, res.output))
        elif args.cmd == "extract":
            out = workflows.extract_to_dict(workflows.extract(args.stego, _pw(args.password)))
        elif args.cmd == "inspect":
            out = workflows.inspection_to_dict(workflows.inspect(args.stego, args.original))
        else:  # capacity
            out = workflows.capacity_info(args.image)
        result, code = {"ok": True, **out}, 0
    except StegoError as exc:
        result, code = {"ok": False, "error": str(exc), "code": type(exc).__name__}, 1
    except Exception as exc:  # noqa: BLE001
        result, code = {"ok": False, "error": repr(exc), "code": "UnexpectedError"}, 1
    print(json.dumps(result, ensure_ascii=False))
    return code


def run_cli(args: argparse.Namespace) -> None:
    # Heavy modules are imported only when needed (keeps the .exe start fast)
    from phantompixel import ui, workflows
    from phantompixel.utils import human_size

    c = ui.console
    if args.cmd == "demo":
        ui.banner()
        ui.flow_demo(interactive=False)
    elif args.cmd == "hide":
        res = workflows.hide(args.cover, text=args.message, file=args.file, password=_pw(args.password),
                             output=args.output, verify=not args.no_verify)
        c.print(f"[green]✓[/] {t('cli.written', path=res.output, pct=f'{res.usage * 100:.1f}', verified=t('cli.verified') if res.verified else '')}",
                highlight=False)
        if args.card:
            c.print(f"[green]✓[/] {t('common.card_done', path=workflows.make_card(args.cover, res.output))}", highlight=False)
    elif args.cmd == "extract":
        res = workflows.extract(args.stego, _pw(args.password))
        if res.text is not None:
            c.print(res.text, markup=False, highlight=False)
        else:
            c.print(f"[green]✓[/] {t('cli.file_saved', path=res.saved)}", highlight=False)
    elif args.cmd == "inspect":
        r = workflows.inspect(args.stego, args.original)
        sig = (t("cli.sig_found", size=human_size(r.signature["stored_bytes"]),
                 kind=t("common.with_password") if r.signature["encrypted"] else t("common.no_password"),
                 version=r.signature["version"]) if r.signature else t("cli.sig_none"))
        c.print(t("cli.signature", sig=sig), highlight=False)
        c.print(t("cli.suspicion", pct=f"{r.detection.suspicion * 100:.0f}", verdict=r.detection.verdict), highlight=False)
        if r.comparison:
            c.print(t("cli.psnr", psnr=f"{r.comparison.psnr:.1f}", pct=f"{r.comparison.changed_pixels_pct:.4f}"),
                    highlight=False)
    elif args.cmd == "capacity":
        info = workflows.capacity_info(args.image)
        c.print(t("cli.cap_size", w=info["width"], h=info["height"]), highlight=False)
        c.print(t("cli.cap_plain", cap=human_size(info["capacity_bytes"])), highlight=False)
        c.print(t("cli.cap_pw", cap=human_size(info["capacity_bytes_with_password"])), highlight=False)
    elif args.cmd == "card":
        c.print(f"[green]✓[/] {t('common.card_done', path=workflows.make_card(args.original, args.stego))}", highlight=False)


def main(argv: list[str] | None = None) -> int:
    if sys.platform.startswith("win"):
        os.system("")  # enables ANSI colours on older Windows consoles
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # block characters and symbols
        except (AttributeError, ValueError):
            pass

    argv, lang, no_anim = split_global_options(list(sys.argv[1:] if argv is None else argv))
    if lang and i18n.normalize(lang) is None:
        print(f"Unsupported language {lang!r}: use one of {', '.join(i18n.SUPPORTED)}.", file=sys.stderr)
        return 2
    i18n.init(lang)

    # Drag & drop / smart mode: a single path to an existing file
    dropped = Path(argv[0]) if len(argv) == 1 and argv[0] not in COMMANDS and not argv[0].startswith("-") else None
    if dropped is not None and not dropped.is_file():
        dropped = None
    args = None if dropped else build_parser().parse_args(argv)

    json_mode = bool(getattr(args, "json", False))
    if not ensure_deps(skip=("rich",) if json_mode else ()):
        if os.name == "nt":
            input(f"\n{t('cli.press_enter')}")
        return 1
    try:
        if json_mode:
            return run_json(args)
        if dropped is not None or args.cmd is None:
            from phantompixel import ui
            ui.interactive(start=dropped, no_anim=no_anim)
        else:
            run_cli(args)
        return 0
    except Exception as exc:  # noqa: BLE001
        # Do not import phantompixel modules here: the original error may be an import error.
        known = type(exc).__module__.startswith("phantompixel")
        print(f"\n{t('cli.error', error=exc)}" if known else f"\n{t('cli.unexpected', error=repr(exc))}", file=sys.stderr)
        if getattr(sys, "frozen", False):  # keep the .exe window open so the message can be read
            input(f"\n{t('cli.press_enter')}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
