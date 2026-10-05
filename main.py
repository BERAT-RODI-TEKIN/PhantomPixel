#!/usr/bin/env python3
"""PhantomPixel - single entry point.

Run without arguments for the interactive menu (this is also what double-clicking
the .exe does). Drag an image onto the program and it figures out what to do:
it extracts if the image holds hidden data, otherwise it starts hiding.

Scripting:

    python main.py                                   # interactive menu
    python main.py photo.png                         # smart mode (same as drag & drop)
    python main.py demo                              # one-key demo
    python main.py hide cover.png -m "secret text"   # hide a message
    python main.py hide cover.png -f report.pdf -p   # hide a file, ask for a password
    python main.py extract hidden.png -p             # extract (asks for the password)
    python main.py inspect hidden.png --original cover.png
    python main.py card cover.png hidden.png         # shareable comparison card
"""
from __future__ import annotations

import argparse
import getpass
import os
import sys
from pathlib import Path

from phantompixel import __version__

COMMANDS = {"demo", "hide", "extract", "inspect", "card"}
REQUIRED = {"rich": "rich", "cryptography": "cryptography", "PIL": "pillow", "numpy": "numpy"}


def _missing_deps() -> list[str]:
    import importlib.util
    return [pkg for mod, pkg in REQUIRED.items() if importlib.util.find_spec(mod) is None]


def ensure_deps() -> bool:
    """Offers to install missing libraries (source runs only). Returns True when ready."""
    if getattr(sys, "frozen", False):  # inside the .exe everything is already bundled
        return True
    missing = _missing_deps()
    if not missing:
        return True

    import importlib
    import subprocess

    cmd = [sys.executable, "-m", "pip", "install", "-r", str(Path(__file__).with_name("requirements.txt"))]
    print(f"\nMissing libraries: {', '.join(missing)}")
    print(f"Python in use: {sys.executable}")
    try:
        answer = input("Install them now? (internet required) [Y/n]: ").strip().lower()
    except EOFError:
        answer = "n"
    if answer in ("", "y", "yes"):
        if subprocess.call(cmd) == 0:
            importlib.invalidate_caches()
            return not _missing_deps()
        print("\nInstallation failed. Check your internet connection and try again.")
    else:
        print("\nTo install them yourself, run:")
        print(f'    "{sys.executable}" -m pip install -r requirements.txt')
    return False


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="PhantomPixel", description="Hide data inside images.",
                                epilog="Tip: pass just an image path (or drag an image onto the program) for smart mode.")
    p.add_argument("--version", action="version", version=f"PhantomPixel {__version__}")
    sub = p.add_subparsers(dest="cmd")

    sub.add_parser("demo", help="one-key demo")

    h = sub.add_parser("hide", help="hide a message or file inside an image")
    h.add_argument("cover", help="cover image (any format; the result is always PNG)")
    g = h.add_mutually_exclusive_group(required=True)
    g.add_argument("-m", "--message", help="text to hide")
    g.add_argument("-f", "--file", help="file to hide")
    h.add_argument("-p", "--password", action="store_true", help="ask for a password (hidden input)")
    h.add_argument("-o", "--output", help="output path (default: next to the cover, *_phantom.png)")
    h.add_argument("--card", action="store_true", help="also create a share card")
    h.add_argument("--no-verify", action="store_true", help="skip the read-back self-check")

    e = sub.add_parser("extract", help="extract hidden data")
    e.add_argument("stego", help="image that contains hidden data")
    e.add_argument("-p", "--password", action="store_true", help="ask for the password (hidden input)")

    i = sub.add_parser("inspect", help="inspect an image")
    i.add_argument("stego")
    i.add_argument("--original", help="original image, for a comparison")

    c = sub.add_parser("card", help="create a share card")
    c.add_argument("original")
    c.add_argument("stego")
    return p


def _pw(flag: bool) -> str | None:
    return (getpass.getpass("Password: ") or None) if flag else None


def run_cli(args: argparse.Namespace) -> None:
    # Heavy modules are imported only when needed (keeps the .exe start fast)
    from phantompixel import ui, workflows

    c = ui.console
    if args.cmd == "demo":
        ui.banner()
        ui.flow_demo(interactive=False)
    elif args.cmd == "hide":
        res = workflows.hide(args.cover, text=args.message, file=args.file, password=_pw(args.password),
                             output=args.output, verify=not args.no_verify)
        c.print(f"[green]✓[/] Written: {res.output}  (image usage {res.usage * 100:.1f}%"
                f"{', verified' if res.verified else ''})", highlight=False)
        if args.card:
            c.print(f"[green]✓[/] Card: {workflows.make_card(args.cover, res.output)}", highlight=False)
    elif args.cmd == "extract":
        res = workflows.extract(args.stego, _pw(args.password))
        if res.text is not None:
            c.print(res.text, markup=False, highlight=False)
        else:
            c.print(f"[green]✓[/] File saved: {res.saved}", highlight=False)
    elif args.cmd == "inspect":
        r = workflows.inspect(args.stego, args.original)
        c.print(f"Signature: {r.signature or 'none found'}", highlight=False)
        c.print(f"Statistical suspicion: {r.detection.suspicion * 100:.0f}% - {r.detection.verdict}", highlight=False)
        if r.comparison:
            c.print(f"PSNR: {r.comparison.psnr:.1f} dB, changed pixels: {r.comparison.changed_pixels_pct:.4f}%",
                    highlight=False)
    elif args.cmd == "card":
        c.print(f"[green]✓[/] Card: {workflows.make_card(args.original, args.stego)}", highlight=False)


def main(argv: list[str] | None = None) -> int:
    if sys.platform.startswith("win"):
        os.system("")  # enables ANSI colours on older Windows consoles
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # block characters and symbols
        except (AttributeError, ValueError):
            pass

    argv = list(sys.argv[1:] if argv is None else argv)
    # Drag & drop / smart mode: a single path to an existing file
    dropped = Path(argv[0]) if len(argv) == 1 and argv[0] not in COMMANDS and not argv[0].startswith("-") else None
    if dropped is not None and not dropped.is_file():
        dropped = None
    args = None if dropped else build_parser().parse_args(argv)

    if not ensure_deps():
        if os.name == "nt":
            input("\nPress Enter to close...")
        return 1
    try:
        if dropped is not None or args.cmd is None:
            from phantompixel import ui
            ui.interactive(start=dropped)
        else:
            run_cli(args)
        return 0
    except Exception as exc:  # noqa: BLE001
        # Do not import phantompixel modules here: the original error may be an import error.
        known = type(exc).__module__.startswith("phantompixel")
        print(f"\nError: {exc}" if known else f"\nUnexpected error: {exc!r}", file=sys.stderr)
        if getattr(sys, "frozen", False):  # keep the .exe window open so the message can be read
            input("\nPress Enter to close...")
        return 1


if __name__ == "__main__":
    sys.exit(main())
