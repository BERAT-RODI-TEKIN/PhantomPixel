"""Terminal UI (rich): banner, menu and step-by-step wizards with back navigation.

Every prompt accepts "<" to go back one step; on the first step it returns to the menu.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable

from rich import box
from rich.align import Align
from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from . import demo, engine, picker, workflows
from .config import APP_NAME, DARK_RED, GREY, RED, TAGLINE, VERSION
from .errors import StegoError, WrongPasswordError
from .utils import bar, human_size, is_lossy

console = Console()
BACK_TOKENS = {"<", "/back", "/b"}

# --------------------------------------------------------------------------
# Banner
# --------------------------------------------------------------------------
_GLYPHS = {
    "P": ["██████╗ ", "██╔══██╗", "██████╔╝", "██╔═══╝ ", "██║     ", "╚═╝     "],
    "H": ["██╗  ██╗", "██║  ██║", "███████║", "██╔══██║", "██║  ██║", "╚═╝  ╚═╝"],
    "A": [" █████╗ ", "██╔══██╗", "███████║", "██╔══██║", "██║  ██║", "╚═╝  ╚═╝"],
    "N": ["███╗   ██╗", "████╗  ██║", "██╔██╗ ██║", "██║╚██╗██║", "██║ ╚████║", "╚═╝  ╚═══╝"],
    "T": ["████████╗", "╚══██╔══╝", "   ██║   ", "   ██║   ", "   ██║   ", "   ╚═╝   "],
    "O": [" ██████╗ ", "██╔═══██╗", "██║   ██║", "██║   ██║", "╚██████╔╝", " ╚═════╝ "],
    "M": ["███╗   ███╗", "████╗ ████║", "██╔████╔██║", "██║╚██╔╝██║", "██║ ╚═╝ ██║", "╚═╝     ╚═╝"],
    "I": ["██╗", "██║", "██║", "██║", "██║", "╚═╝"],
    "X": ["██╗  ██╗", "╚██╗██╔╝", " ╚███╔╝ ", " ██╔██╗ ", "██╔╝ ██╗", "╚═╝  ╚═╝"],
    "E": ["███████╗", "██╔════╝", "█████╗  ", "██╔══╝  ", "███████╗", "╚══════╝"],
    "L": ["██╗     ", "██║     ", "██║     ", "██║     ", "███████╗", "╚══════╝"],
}
_GRADIENT = ["#ff8a80", "#ff5252", "#ff1744", "#e0123c", "#c4102f", "#8e0b22"]


def _render(word: str) -> list[str]:
    return ["".join(_GLYPHS[c][r] for c in word) for r in range(6)]


def banner() -> None:
    words = ["PHANTOMPIXEL"] if console.width >= 100 else ["PHANTOM", "PIXEL"]
    console.print()
    for w in words:
        for row, line in enumerate(_render(w)):
            console.print(Align.center(f"[{_GRADIENT[row]}]{line}[/]"))
    console.print(Align.center(f"[{GREY}]{TAGLINE}  •  v{VERSION}[/]"))
    console.print()


# --------------------------------------------------------------------------
# Wizard framework: every flow is a list of steps; "<" goes back one step
# --------------------------------------------------------------------------
class GoBack(Exception):
    """The user typed '<' at a prompt."""


class GoTo(Exception):
    """Jump to a specific step of the running wizard."""

    def __init__(self, index: int):
        super().__init__(index)
        self.index = index


def run_wizard(steps: list[Callable[[dict], None]], ctx: dict) -> None:
    console.print(f"[{GREY}]Tip: type [bold]<[/bold] at any prompt to go back one step.[/]")
    i = 0
    while i < len(steps):
        try:
            steps[i](ctx)
            i += 1
        except GoBack:
            if i == 0:  # back from the first step = back to the menu
                return
            i -= 1
        except GoTo as jump:
            i = jump.index


# --------------------------------------------------------------------------
# Prompt helpers
# --------------------------------------------------------------------------
def _error(msg: str) -> None:
    console.print(Panel(escape(msg), title="[bold]Error[/]", border_style="red", box=box.ROUNDED))


def _kv(rows: list[tuple[str, str]]) -> Table:
    t = Table.grid(padding=(0, 2))
    t.add_column(style=GREY)
    t.add_column()
    for k, v in rows:
        t.add_row(k, v)
    return t


def ask(label: str, *, default: str = "", secret: bool = False, back: bool = True, hint: str = "") -> str:
    """Prompts for text. '<' raises GoBack (unless back=False)."""
    tail = f" [{GREY}]{escape(hint)}[/]" if hint else ""
    raw = Prompt.ask(f"[bold {RED}]{label}[/]{tail}", password=secret, default=default,
                     show_default=bool(default) and not secret)
    value = raw if secret else raw.strip()
    if back and value in BACK_TOKENS:
        raise GoBack
    return value


def ask_file(label: str, kind: str = "image", current: Path | None = None, optional: bool = False) -> Path | None:
    """Asks for a file: drag & drop it, paste a path, or press Enter / type ? to browse."""
    while True:
        if current:
            hint = f"(Enter = keep {current.name}, ? = browse, or drop a file here)"
        elif optional:
            hint = "(Enter = skip, ? = browse, or drop a file here)"
        else:
            hint = "(drop a file here, paste a path, or press Enter to browse)"
        raw = ask(label, hint=hint).strip('"').strip("'")

        if raw == "":
            if current:
                return current
            if optional:
                return None
            raw = "?"
        if raw == "?":
            try:
                picked = picker.pick(kind, label)
            except picker.PickerUnavailable:
                console.print(f"[{GREY}]No file dialog available here: drop a file onto this window or paste its path.[/]")
                continue
            if picked is None:
                console.print(f"[{GREY}]No file selected.[/]")
                continue
            return picked

        path = Path(raw).expanduser()
        if path.is_file():
            return path
        console.print(f"[{GREY}]File not found: {escape(raw)}[/]")


def ask_image(label: str, current: Path | None = None, optional: bool = False) -> Path | None:
    """Like ask_file, but keeps asking until the file really is a readable image."""
    while True:
        path = ask_file(label, "image", current, optional)
        if path is None:
            return None
        try:
            engine.image_size(path)
            return path
        except StegoError as exc:
            _error(str(exc))
            current = None


def _has_preset(c: dict, key: str) -> bool:
    return key in c.get("preset", {})


def _take(c: dict, key: str):
    return c.get("preset", {}).pop(key, None)


def _actions(options: dict[str, tuple[str, Callable[[], None]]]) -> None:
    """Shows one-key follow-up actions; Enter returns to the menu."""
    keys = "   ".join(f"[bold {RED}]{k}[/] {label}" for k, (label, _) in options.items())
    console.print(f"\n{keys + '   ' if keys else ''}[bold {RED}]Enter[/] back to menu")
    while True:
        raw = Prompt.ask(f"[bold {RED}]›[/]", default="", show_default=False).strip().lower()
        if raw in ("", "<"):
            return
        if raw in options:
            options[raw][1]()
        else:
            console.print(f"[{GREY}]Press one of the keys above, or Enter.[/]")


# --------------------------------------------------------------------------
# HIDE wizard
# --------------------------------------------------------------------------
def _hide_cover(c: dict) -> None:
    c["cover"] = _take(c, "cover") or ask_image("Cover image", c.get("cover"))
    w, h = engine.image_size(c["cover"])
    console.print(f"[green]✓[/] {escape(c['cover'].name)}  [{GREY}]{w}×{h} px · fits up to "
                  f"{human_size(engine.capacity_for(w, h))} ({human_size(engine.capacity_for(w, h, True))} with a password)[/]")


def _hide_secret(c: dict) -> None:
    cap = engine.capacity(c["cover"])
    while True:
        raw = ask("Secret", hint="(type a message, or press Enter to choose a file)")
        if raw:
            c["text"], c["file"] = raw, None
            c["size"] = len(raw.encode("utf-8"))
            c["what"] = f"message, {c['size']} bytes"
        else:
            try:
                picked = picker.pick("any", "Choose the file to hide")
            except picker.PickerUnavailable:
                picked = ask_file("File to hide", "any")
            if picked is None:
                console.print(f"[{GREY}]No file selected.[/]")
                continue
            c["text"], c["file"] = None, picked
            c["size"] = picked.stat().st_size + len(picked.name.encode("utf-8"))  # the name is stored too
            c["what"] = f"file {picked.name} ({human_size(picked.stat().st_size)})"

        if c["size"] > cap:
            _error(f"Too big: {human_size(c['size'])}, but this image holds about {human_size(cap)}. "
                   "Type < to pick a larger image, or choose a smaller secret.")
            continue
        console.print(f"[green]✓[/] {escape(c['what'])}  [{GREY}]({c['size'] / cap * 100:.1f}% of this image)[/]")
        return


def _hide_password(c: dict) -> None:
    while True:
        pw = ask("Password", secret=True, hint="(optional, Enter = no password; there is no recovery if you forget it)")
        if not pw:
            c["password"] = None
            return
        if ask("Repeat password", secret=True) == pw:
            c["password"] = pw
            return
        console.print(f"[{GREY}]The passwords do not match, try again.[/]")


def _hide_review(c: dict) -> None:
    encrypted = bool(c["password"])
    cap = engine.capacity(c["cover"], encrypted)
    if c["size"] > cap:
        _error(f"With a password the limit is {human_size(cap)} for this image. Choose a smaller secret.")
        raise GoTo(1)
    console.print(Panel(_kv([
        ("Cover", escape(c["cover"].name)),
        ("Secret", escape(c["what"])),
        ("Protection", "AES-256-GCM + password-keyed scattering" if encrypted else "none (anyone with this tool can read it)"),
        ("Image usage", f"{bar(c['size'] / cap)} {c['size'] / cap * 100:.1f}%"),
    ]), title=f"[bold {RED}]Ready[/]", border_style=DARK_RED, box=box.ROUNDED))
    ask("Hide it now?", hint="(Enter = yes, < = go back)")


def _hide_run(c: dict) -> None:
    with console.status(f"[{RED}]Hiding and verifying...[/]", spinner="dots"):
        res = workflows.hide(c["cover"], text=c.get("text"), file=c.get("file"), password=c["password"])
    console.print(Panel(_kv([
        ("Saved as", f"[bold]{escape(str(res.output))}[/]"),
        ("Hidden", human_size(res.stored_bytes)),
        ("Verified", "[green]✓ read back from the file and compared[/]" if res.verified else "skipped"),
        ("Note", "Share this file as a PNG file. JPEG / social media recompression destroys the data."),
    ]), title="[bold green]Done[/]", border_style="green", box=box.ROUNDED))

    def card() -> None:
        path = workflows.make_card(c["cover"], res.output)
        console.print(f"[green]✓[/] Card: [bold]{escape(str(path))}[/]")
        workflows.open_file(path)

    _actions({"c": ("make share card", card), "o": ("open folder", lambda: workflows.reveal(res.output))})


HIDE = [_hide_cover, _hide_secret, _hide_password, _hide_review, _hide_run]


# --------------------------------------------------------------------------
# EXTRACT wizard
# --------------------------------------------------------------------------
def _x_image(c: dict) -> None:
    preset = _take(c, "stego")
    while True:
        path = preset or ask_image("Image with hidden data", c.get("stego"))
        preset = None
        info = engine.inspect(path)
        if info:
            break
        msg = "No PhantomPixel data found in this image."
        if is_lossy(path):
            msg += " This is a JPEG: its compression destroys hidden data. You need the original PNG file."
        _error(msg)
        c.pop("stego", None)
    c["stego"], c["info"] = path, info
    kind = "password-protected" if info["encrypted"] else "no password"
    console.print(f"[green]✓[/] Hidden data found: {human_size(info['stored_bytes'])}, {kind}")


def _x_password(c: dict) -> None:
    if not c["info"]["encrypted"]:
        c["password"] = None
        return
    while True:
        pw = ask("Password", secret=True)
        if pw:
            c["password"] = pw
            return


def _x_run(c: dict) -> None:
    try:
        with console.status(f"[{RED}]Extracting...[/]", spinner="dots"):
            res = workflows.extract(c["stego"], c.get("password"))
    except WrongPasswordError as exc:
        _error(str(exc))
        raise GoTo(1)  # ask for the password again

    if res.text is not None:
        console.print(Panel(escape(res.text), title=f"[bold {RED}]Hidden message[/]", border_style=RED, box=box.DOUBLE))

        def save() -> None:
            path = workflows.save_text(res.text, c["stego"])
            console.print(f"[green]✓[/] Saved: [bold]{escape(str(path))}[/]")
            workflows.reveal(path)

        _actions({"s": ("save as .txt", save)})
    else:
        console.print(Panel(f"Saved as [bold]{escape(str(res.saved))}[/]", title="[bold green]File extracted[/]",
                            border_style="green", box=box.ROUNDED))
        _actions({"o": ("open folder", lambda: workflows.reveal(res.saved))})


EXTRACT = [_x_image, _x_password, _x_run]


# --------------------------------------------------------------------------
# INSPECT wizard
# --------------------------------------------------------------------------
def _i_image(c: dict) -> None:
    c["stego"] = _take(c, "stego") or ask_image("Image to inspect", c.get("stego"))


def _i_original(c: dict) -> None:
    if _has_preset(c, "original"):
        c["original"] = _take(c, "original")
        return
    c["original"] = ask_image("Original image (optional, adds a comparison)", c.get("original"), optional=True)


def _i_run(c: dict) -> None:
    with console.status(f"[{RED}]Analysing...[/]", spinner="dots"):
        r = workflows.inspect(c["stego"], c.get("original"))

    if r.signature:
        kind = "password-protected" if r.signature["encrypted"] else "no password"
        sig = f"[bold green]✔ FOUND[/]  {human_size(r.signature['stored_bytes'])}, {kind}"
    else:
        sig = "[bold yellow]✘ none found[/]"
    rows = [
        ("PhantomPixel signature", sig),
        ("Statistical test", f"{bar(r.detection.suspicion)} {r.detection.suspicion * 100:.0f}%  {r.detection.verdict}"),
    ]
    if r.comparison:
        psnr = "∞" if r.comparison.psnr == float("inf") else f"{r.comparison.psnr:.1f} dB"
        rows += [("PSNR vs original", psnr), ("Changed pixels", f"{r.comparison.changed_pixels_pct:.4f}%")]
    console.print(Panel(_kv(rows), title=f"[bold {RED}]Inspection[/]", border_style=RED, box=box.ROUNDED))
    console.print(f"[{GREY}]The signature check is exact but only recognises images made by PhantomPixel. "
                  f"The statistical test is a heuristic: a low score does not prove an image is clean.[/]")

    def lsb() -> None:
        path = workflows.save_lsb_plane(c["stego"])
        console.print(f"[green]✓[/] LSB plane: [bold]{escape(str(path))}[/]")
        workflows.open_file(path)

    options: dict[str, tuple[str, Callable[[], None]]] = {}
    if r.signature:
        options["e"] = ("extract it now", lambda: run_wizard(EXTRACT, {"preset": {"stego": c["stego"]}}))
    options["l"] = ("save LSB plane", lsb)
    _actions(options)


INSPECT = [_i_image, _i_original, _i_run]


# --------------------------------------------------------------------------
# CARD wizard
# --------------------------------------------------------------------------
def _c_original(c: dict) -> None:
    c["original"] = ask_image("Original image (without hidden data)", c.get("original"))


def _c_stego(c: dict) -> None:
    c["stego"] = ask_image("Image with hidden data", c.get("stego"))


def _c_run(c: dict) -> None:
    with console.status(f"[{RED}]Building card...[/]", spinner="dots"):
        card = workflows.make_card(c["original"], c["stego"])
    console.print(f"[green]✓[/] Card: [bold]{escape(str(card))}[/]")
    workflows.open_file(card)
    _actions({"o": ("open folder", lambda: workflows.reveal(card))})


CARD = [_c_original, _c_stego, _c_run]


# --------------------------------------------------------------------------
# CAPACITY wizard
# --------------------------------------------------------------------------
def _cap_image(c: dict) -> None:
    c["image"] = ask_image("Image", c.get("image"))


def _cap_show(c: dict) -> None:
    w, h = engine.image_size(c["image"])
    console.print(Panel(_kv([
        ("Size", f"{w} × {h} pixels"),
        ("Capacity", human_size(engine.capacity_for(w, h))),
        ("With password", human_size(engine.capacity_for(w, h, True))),
        ("Tip", "The less you fill, the less trace you leave."),
    ]), title=f"[bold {RED}]Capacity[/]", border_style=RED, box=box.ROUNDED))
    _actions({})


CAPACITY = [_cap_image, _cap_show]


# --------------------------------------------------------------------------
# Demo
# --------------------------------------------------------------------------
def flow_demo(interactive: bool = True) -> None:
    steps: list[str] = []
    with console.status(f"[{RED}]Starting demo...[/]", spinner="dots") as status:
        def on_step(s: str) -> None:
            steps.append(s)
            status.update(f"[{RED}]{s}...[/]")
        r = demo.run(on_step=on_step)

    for s in steps:
        console.print(f"[green]✓[/] {s}")
    ok = r.recovered == r.message
    console.print(Panel(escape(r.recovered), title=f"[bold {RED}]Text extracted from the image[/]",
                        border_style=RED, box=box.DOUBLE))
    console.print(Panel(_kv([
        ("Check", "[green]hidden and extracted text are identical[/]" if ok else "[red]MISMATCH![/]"),
        ("Protection", f"AES-256-GCM · password: [bold]{r.password}[/]" if r.password else "none"),
        ("Image quality", f"PSNR {r.comparison.psnr:.1f} dB (above 40 dB is invisible to the eye)"),
        ("Changed pixels", f"{r.comparison.changed_pixels_pct:.3f}% · largest colour change: {r.comparison.max_diff}/255"),
        ("Files", escape(str(r.folder))),
    ]), title=f"[bold {RED}]Demo result[/]", border_style=DARK_RED, box=box.ROUNDED))
    console.print(f"[{GREY}]Opening the comparison card...[/]")
    workflows.open_file(r.card)
    if not interactive:  # command-line use: never wait for input
        return

    _actions({
        "i": ("inspect the hidden image",
              lambda: run_wizard(INSPECT, {"preset": {"stego": r.stego, "original": r.cover}})),
        "o": ("open folder", lambda: workflows.reveal(r.card)),
    })


# --------------------------------------------------------------------------
# Menu
# --------------------------------------------------------------------------
_MENU = [
    ("1", "Quick demo", "One key: hide, extract and show the comparison card", flow_demo),
    ("2", "Hide", "Hide a message or any file inside an image", lambda: run_wizard(HIDE, {})),
    ("3", "Extract", "Read hidden data back out of an image", lambda: run_wizard(EXTRACT, {})),
    ("4", "Inspect", "Detect hidden data, compare images, view the LSB plane", lambda: run_wizard(INSPECT, {})),
    ("5", "Share card", "Original | hidden | difference map, ready to post", lambda: run_wizard(CARD, {})),
    ("6", "Capacity", "How much data fits into an image?", lambda: run_wizard(CAPACITY, {})),
    ("0", "Exit", "", None),
]


def _menu() -> None:
    t = Table.grid(padding=(0, 2))
    t.add_column(style=f"bold {RED}", justify="right")
    t.add_column(style="bold")
    t.add_column(style=GREY)
    for key, name, desc, _ in _MENU:
        t.add_row(f"[{key}]", name, desc)
    console.print(Panel(t, title=f"[bold {RED}]{APP_NAME}[/]", border_style=DARK_RED, box=box.ROUNDED))


def _guard(fn: Callable[[], None]) -> None:
    """Runs a flow; any error returns to the menu instead of crashing the program."""
    try:
        fn()
    except StegoError as exc:
        _error(str(exc))
    except KeyboardInterrupt:
        console.print("\n[grey70]Cancelled.[/]")
    except EOFError:
        return
    except Exception as exc:  # noqa: BLE001
        _error(f"Unexpected error: {exc}")


def smart(path: Path) -> None:
    """Drag & drop entry: extract if the image holds PhantomPixel data, otherwise start hiding."""
    if engine.inspect(path):
        console.print(f"[green]✓[/] {escape(path.name)} contains hidden data. Let's extract it.")
        run_wizard(EXTRACT, {"preset": {"stego": path}})
    else:
        console.print(f"Let's hide something in [bold]{escape(path.name)}[/].")
        run_wizard(HIDE, {"preset": {"cover": path}})


def interactive(start: Path | None = None) -> None:
    banner()
    if start is not None:
        _guard(lambda: smart(start))
    handlers = {key: fn for key, _, _, fn in _MENU if fn}
    while True:
        _menu()
        try:
            choice = Prompt.ask(f"[bold {RED}]phantom ›[/]", choices=[*handlers, "0", "q"], show_choices=False)
        except (KeyboardInterrupt, EOFError):
            return
        if choice in ("0", "q"):
            console.print(f"[{GREY}]Bye.[/]")
            return
        console.print()
        _guard(handlers[choice])
        console.print()
