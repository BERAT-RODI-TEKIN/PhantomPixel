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

from . import demo, engine, i18n, picker, splash, workflows
from .config import APP_NAME, DARK_RED, GREY, RED, VERSION
from .errors import StegoError, WrongPasswordError
from .i18n import t
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


def banner(animate: bool = False, no_anim: bool = False) -> None:
    """Prints the banner. With animate=True it plays the start-up animation when the terminal allows it."""
    words = ["PHANTOMPIXEL"] if console.width >= 100 else ["PHANTOM", "PIXEL"]
    lines = [line for w in words for line in _render(w)]
    console.print()
    if animate and splash.should_animate(console, no_anim) and splash.play(
            console, lines, _GRADIENT, t("app.tagline"), VERSION, GREY):
        return
    for i, line in enumerate(lines):
        console.print(Align.center(f"[{_GRADIENT[i % 6]}]{line}[/]"))
    console.print(Align.center(f"[{GREY}]{t('app.tagline')}  •  v{VERSION}[/]"), highlight=False)
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
    console.print(f"[{GREY}]{t('ui.tip_back')}[/]")
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
    console.print(Panel(escape(msg), title=f"[bold]{t('ui.error_title')}[/]", border_style="red", box=box.ROUNDED))


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
            hint = t("ui.file_hint_keep", name=current.name)
        elif optional:
            hint = t("ui.file_hint_skip")
        else:
            hint = t("ui.file_hint")
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
                console.print(f"[{GREY}]{t('ui.no_dialog')}[/]")
                continue
            if picked is None:
                console.print(f"[{GREY}]{t('ui.no_file')}[/]")
                continue
            return picked

        path = Path(raw).expanduser()
        if path.is_file():
            return path
        console.print(f"[{GREY}]{t('ui.file_not_found', path=escape(raw))}[/]")


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
    console.print(f"\n{keys + '   ' if keys else ''}[bold {RED}]Enter[/] {t('ui.enter_back')}")
    while True:
        raw = Prompt.ask(f"[bold {RED}]›[/]", default="", show_default=False).strip().lower()
        if raw in ("", "<"):
            return
        if raw in options:
            options[raw][1]()
        else:
            console.print(f"[{GREY}]{t('ui.press_key')}[/]")


# --------------------------------------------------------------------------
# HIDE wizard
# --------------------------------------------------------------------------
def _hide_cover(c: dict) -> None:
    c["cover"] = _take(c, "cover") or ask_image(t("hide.cover"), c.get("cover"))
    w, h = engine.image_size(c["cover"])
    console.print(f"[green]✓[/] {escape(c['cover'].name)}  [{GREY}]"
                  f"{t('hide.cover_ok', w=w, h=h, cap=human_size(engine.capacity_for(w, h)), cap_pw=human_size(engine.capacity_for(w, h, True)))}[/]")


def _hide_secret(c: dict) -> None:
    w, h = engine.image_size(c["cover"])
    cap = engine.body_capacity_for(w, h)
    while True:
        raw = ask(t("hide.secret"), hint=t("hide.secret_hint"))
        if raw:
            payload = workflows.make_payload(text=raw)
            c["text"], c["file"] = raw, None
            c["what"] = t("hide.what_message", n=len(payload.data))
        else:
            try:
                picked = picker.pick("any", t("hide.pick_title"))
            except picker.PickerUnavailable:
                picked = ask_file(t("hide.file_label"), "any")
            if picked is None:
                console.print(f"[{GREY}]{t('ui.no_file')}[/]")
                continue
            payload = workflows.make_payload(file=picked)
            c["text"], c["file"] = None, picked
            c["what"] = t("hide.what_file", name=picked.name, size=human_size(picked.stat().st_size))

        stored = engine.stored_size(payload)   # after compression: text and documents shrink
        if stored > cap:
            _error(t("hide.too_big", size=human_size(stored), cap=human_size(cap)))
            continue
        c["payload"], c["stored"] = payload, stored
        console.print(f"[green]✓[/] {escape(c['what'])}  [{GREY}]{t('hide.usage_ok', pct=f'{stored / cap * 100:.1f}')}[/]")
        return


def _hide_password(c: dict) -> None:
    while True:
        pw = ask(t("common.password"), secret=True, hint=t("hide.pw_hint"))
        if not pw:
            c["password"] = None
            return
        if ask(t("hide.pw_repeat"), secret=True) == pw:
            c["password"] = pw
            return
        console.print(f"[{GREY}]{t('hide.pw_mismatch')}[/]")


def _hide_review(c: dict) -> None:
    encrypted = bool(c["password"])
    w, h = engine.image_size(c["cover"])
    cap = engine.body_capacity_for(w, h)
    stored = engine.stored_size(c["payload"], encrypted)
    if stored > cap:
        _error(t("hide.pw_too_big", size=human_size(stored), cap=human_size(cap)))
        raise GoTo(1)
    console.print(Panel(_kv([
        (t("hide.row_cover"), escape(c["cover"].name)),
        (t("hide.row_secret"), escape(c["what"])),
        (t("hide.row_protection"), t("hide.prot_on") if encrypted else t("hide.prot_off")),
        (t("hide.row_usage"), f"{bar(stored / cap)} {stored / cap * 100:.1f}%"),
    ]), title=f"[bold {RED}]{t('hide.ready')}[/]", border_style=DARK_RED, box=box.ROUNDED))
    ask(t("hide.confirm"), hint=t("hide.confirm_hint"))


def _hide_run(c: dict) -> None:
    with console.status(f"[{RED}]{t('hide.running')}[/]", spinner="dots"):
        res = workflows.hide(c["cover"], text=c.get("text"), file=c.get("file"), password=c["password"])
    hidden = (t("hide.hidden_compressed", size=human_size(res.stored_bytes), orig=human_size(res.original_bytes))
              if res.compressed else human_size(res.stored_bytes))
    console.print(Panel(_kv([
        (t("hide.row_saved"), f"[bold]{escape(str(res.output))}[/]"),
        (t("hide.row_hidden"), hidden),
        (t("hide.row_verified"), f"[green]{t('hide.verified_yes')}[/]" if res.verified else t("common.skipped")),
        (t("hide.row_note"), t("hide.note_png")),
    ]), title=f"[bold green]{t('hide.done')}[/]", border_style="green", box=box.ROUNDED))

    def card() -> None:
        path = workflows.make_card(c["cover"], res.output)
        console.print(f"[green]✓[/] {t('common.card_done', path=f'[bold]{escape(str(path))}[/]')}")
        workflows.open_file(path)

    _actions({"c": (t("hide.act_card"), card), "o": (t("common.folder"), lambda: workflows.reveal(res.output))})


HIDE = [_hide_cover, _hide_secret, _hide_password, _hide_review, _hide_run]


# --------------------------------------------------------------------------
# EXTRACT wizard
# --------------------------------------------------------------------------
def _kind(info: dict) -> str:
    return t("common.with_password") if info["encrypted"] else t("common.no_password")


def _x_image(c: dict) -> None:
    preset = _take(c, "stego")
    while True:
        path = preset or ask_image(t("x.image"), c.get("stego"))
        preset = None
        info = engine.inspect(path)   # raises NewerVersionError for images made by a newer version
        if info:
            break
        msg = t("x.no_data")
        if is_lossy(path):
            msg += t("x.jpeg")
        _error(msg)
        c.pop("stego", None)
    c["stego"], c["info"] = path, info
    console.print(f"[green]✓[/] {t('x.found', size=human_size(info['stored_bytes']), kind=_kind(info))}")


def _x_password(c: dict) -> None:
    if not c["info"]["encrypted"]:
        c["password"] = None
        return
    while True:
        pw = ask(t("common.password"), secret=True)
        if pw:
            c["password"] = pw
            return


def _x_run(c: dict) -> None:
    try:
        with console.status(f"[{RED}]{t('x.running')}[/]", spinner="dots"):
            res = workflows.extract(c["stego"], c.get("password"))
    except WrongPasswordError as exc:
        _error(str(exc))
        raise GoTo(1)  # ask for the password again

    if res.text is not None:
        console.print(Panel(escape(res.text), title=f"[bold {RED}]{t('x.msg_title')}[/]", border_style=RED, box=box.DOUBLE))

        def save() -> None:
            path = workflows.save_text(res.text, c["stego"])
            console.print(f"[green]✓[/] {t('common.saved', path=f'[bold]{escape(str(path))}[/]')}")
            workflows.reveal(path)

        _actions({"s": (t("x.act_save"), save)})
    else:
        console.print(Panel(t("x.file_saved", path=f"[bold]{escape(str(res.saved))}[/]"),
                            title=f"[bold green]{t('x.file_title')}[/]", border_style="green", box=box.ROUNDED))
        _actions({"o": (t("common.folder"), lambda: workflows.reveal(res.saved))})


EXTRACT = [_x_image, _x_password, _x_run]


# --------------------------------------------------------------------------
# INSPECT wizard
# --------------------------------------------------------------------------
def _i_image(c: dict) -> None:
    c["stego"] = _take(c, "stego") or ask_image(t("i.image"), c.get("stego"))


def _i_original(c: dict) -> None:
    if _has_preset(c, "original"):
        c["original"] = _take(c, "original")
        return
    c["original"] = ask_image(t("i.original"), c.get("original"), optional=True)


def _i_run(c: dict) -> None:
    with console.status(f"[{RED}]{t('i.running')}[/]", spinner="dots"):
        r = workflows.inspect(c["stego"], c.get("original"))

    if r.signature:
        sig = t("i.found", size=human_size(r.signature["stored_bytes"]), kind=_kind(r.signature),
                version=r.signature["version"])
    else:
        sig = t("i.none")
    rows = [
        (t("i.row_sig"), sig),
        (t("i.row_stat"), f"{bar(r.detection.suspicion)} {r.detection.suspicion * 100:.0f}%  {r.detection.verdict}"),
    ]
    if r.comparison:
        psnr = "∞" if r.comparison.psnr == float("inf") else f"{r.comparison.psnr:.1f} dB"
        rows += [(t("i.row_psnr"), psnr), (t("i.row_changed"), f"{r.comparison.changed_pixels_pct:.4f}%")]
    console.print(Panel(_kv(rows), title=f"[bold {RED}]{t('i.title')}[/]", border_style=RED, box=box.ROUNDED))
    console.print(f"[{GREY}]{t('i.note')}[/]")

    def lsb() -> None:
        path = workflows.save_lsb_plane(c["stego"])
        console.print(f"[green]✓[/] {t('i.lsb_done', path=f'[bold]{escape(str(path))}[/]')}")
        workflows.open_file(path)

    options: dict[str, tuple[str, Callable[[], None]]] = {}
    if r.signature:
        options["e"] = (t("i.act_extract"), lambda: run_wizard(EXTRACT, {"preset": {"stego": c["stego"]}}))
    options["l"] = (t("i.act_lsb"), lsb)
    _actions(options)


INSPECT = [_i_image, _i_original, _i_run]


# --------------------------------------------------------------------------
# CARD wizard
# --------------------------------------------------------------------------
def _c_original(c: dict) -> None:
    c["original"] = ask_image(t("c.original"), c.get("original"))


def _c_stego(c: dict) -> None:
    c["stego"] = ask_image(t("x.image"), c.get("stego"))


def _c_run(c: dict) -> None:
    with console.status(f"[{RED}]{t('c.running')}[/]", spinner="dots"):
        card = workflows.make_card(c["original"], c["stego"])
    console.print(f"[green]✓[/] {t('common.card_done', path=f'[bold]{escape(str(card))}[/]')}")
    workflows.open_file(card)
    _actions({"o": (t("common.folder"), lambda: workflows.reveal(card))})


CARD = [_c_original, _c_stego, _c_run]


# --------------------------------------------------------------------------
# CAPACITY wizard
# --------------------------------------------------------------------------
def _cap_image(c: dict) -> None:
    c["image"] = ask_image(t("cap.image"), c.get("image"))


def _cap_show(c: dict) -> None:
    info = workflows.capacity_info(c["image"])
    console.print(Panel(_kv([
        (t("cap.row_size"), t("cap.size_value", w=info["width"], h=info["height"])),
        (t("cap.row_cap"), human_size(info["capacity_bytes"])),
        (t("cap.row_cap_pw"), human_size(info["capacity_bytes_with_password"])),
        (t("cap.row_tip"), t("cap.tip")),
    ]), title=f"[bold {RED}]{t('cap.title')}[/]", border_style=RED, box=box.ROUNDED))
    _actions({})


CAPACITY = [_cap_image, _cap_show]


# --------------------------------------------------------------------------
# Demo
# --------------------------------------------------------------------------
def flow_demo(interactive: bool = True) -> None:
    steps: list[str] = []
    with console.status(f"[{RED}]{t('demo.starting')}[/]", spinner="dots") as status:
        def on_step(s: str) -> None:
            steps.append(s)
            status.update(f"[{RED}]{s}...[/]")
        r = demo.run(on_step=on_step)

    for s in steps:
        console.print(f"[green]✓[/] {s}")
    ok = r.recovered == r.message
    console.print(Panel(escape(r.recovered), title=f"[bold {RED}]{t('demo.recovered')}[/]",
                        border_style=RED, box=box.DOUBLE))
    console.print(Panel(_kv([
        (t("demo.row_check"), t("demo.check_ok") if ok else t("demo.check_bad")),
        (t("demo.row_protection"), t("demo.prot", pw=r.password) if r.password else t("demo.prot_none")),
        (t("demo.row_quality"), t("demo.quality", psnr=f"{r.comparison.psnr:.1f}")),
        (t("demo.row_changed"), t("demo.changed", pct=f"{r.comparison.changed_pixels_pct:.3f}", max=r.comparison.max_diff)),
        (t("demo.row_files"), escape(str(r.folder))),
    ]), title=f"[bold {RED}]{t('demo.title')}[/]", border_style=DARK_RED, box=box.ROUNDED))
    console.print(f"[{GREY}]{t('demo.opening')}[/]")
    workflows.open_file(r.card)
    if not interactive:  # command-line use: never wait for input
        return

    _actions({
        "i": (t("demo.act_inspect"),
              lambda: run_wizard(INSPECT, {"preset": {"stego": r.stego, "original": r.cover}})),
        "o": (t("common.folder"), lambda: workflows.reveal(r.card)),
    })


# --------------------------------------------------------------------------
# Language
# --------------------------------------------------------------------------
def flow_language() -> None:
    codes = list(i18n.SUPPORTED)
    current = i18n.get_language()
    options = "   ".join(f"[bold {RED}]{i}[/] {i18n.NAMES[code]}{' ✓' if code == current else ''}"
                        for i, code in enumerate(codes, 1))
    console.print(Panel(options, title=f"[bold {RED}]{t('lang.title')}[/]", border_style=DARK_RED, box=box.ROUNDED))
    raw = Prompt.ask(f"[bold {RED}]{t('lang.prompt')}[/]", default="", show_default=False).strip().lower()
    if raw in ("", "<"):
        return
    code = codes[int(raw) - 1] if raw.isdigit() and 1 <= int(raw) <= len(codes) else i18n.normalize(raw)
    if code is None:
        return
    i18n.set_language(code, persist=True)
    console.print(f"[green]✓[/] {t('lang.changed', name=i18n.NAMES[code])}")


# --------------------------------------------------------------------------
# Menu
# --------------------------------------------------------------------------
def _menu_items() -> list[tuple[str, str, str, Callable[[], None] | None]]:
    """(key, name, description, handler); built on every call so a language change shows at once."""
    return [
        ("1", t("menu.1"), t("menu.1.d"), flow_demo),
        ("2", t("menu.2"), t("menu.2.d"), lambda: run_wizard(HIDE, {})),
        ("3", t("menu.3"), t("menu.3.d"), lambda: run_wizard(EXTRACT, {})),
        ("4", t("menu.4"), t("menu.4.d"), lambda: run_wizard(INSPECT, {})),
        ("5", t("menu.5"), t("menu.5.d"), lambda: run_wizard(CARD, {})),
        ("6", t("menu.6"), t("menu.6.d"), lambda: run_wizard(CAPACITY, {})),
        ("7", t("menu.7"), t("menu.7.d"), flow_language),
        ("0", t("menu.0"), "", None),
    ]


def _menu() -> None:
    tbl = Table.grid(padding=(0, 2))
    tbl.add_column(style=f"bold {RED}", justify="right")
    tbl.add_column(style="bold")
    tbl.add_column(style=GREY)
    for key, name, desc, _ in _menu_items():
        tbl.add_row(f"[{key}]", name, desc)
    console.print(Panel(tbl, title=f"[bold {RED}]{APP_NAME}[/]", border_style=DARK_RED, box=box.ROUNDED))


def _guard(fn: Callable[[], None]) -> None:
    """Runs a flow; any error returns to the menu instead of crashing the program."""
    try:
        fn()
    except StegoError as exc:
        _error(str(exc))
    except KeyboardInterrupt:
        console.print(f"\n[grey70]{t('ui.cancelled')}[/]")
    except EOFError:
        return
    except Exception as exc:  # noqa: BLE001
        _error(t("ui.unexpected", error=exc))


def smart(path: Path) -> None:
    """Drag & drop entry: extract if the image holds PhantomPixel data, otherwise start hiding."""
    if engine.inspect(path):
        console.print(f"[green]✓[/] {t('smart.found', name=escape(path.name))}")
        run_wizard(EXTRACT, {"preset": {"stego": path}})
    else:
        console.print(t("smart.hide", name=f"[bold]{escape(path.name)}[/]"))
        run_wizard(HIDE, {"preset": {"cover": path}})


def interactive(start: Path | None = None, animate: bool = True, no_anim: bool = False) -> None:
    banner(animate=animate, no_anim=no_anim)
    if start is not None:
        _guard(lambda: smart(start))
    while True:
        _menu()
        handlers = {key: fn for key, _, _, fn in _menu_items() if fn}
        try:
            choice = Prompt.ask(f"[bold {RED}]{t('ui.prompt')}[/]", choices=[*handlers, "0", "q"], show_choices=False)
        except (KeyboardInterrupt, EOFError):
            return
        if choice in ("0", "q"):
            console.print(f"[{GREY}]{t('ui.bye')}[/]")
            return
        console.print()
        _guard(handlers[choice])
        console.print()
