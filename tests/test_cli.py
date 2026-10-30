"""Command line: --json output, capacity command, --lang / --no-anim handling, start-up animation."""
import contextlib
import io
import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import main as cli  # noqa: E402
from phantompixel import i18n  # noqa: E402


def run(*argv: str, env: dict | None = None) -> tuple[int, str, str]:
    """Runs main.main() in-process and returns (exit code, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    with mock.patch.dict(os.environ, env or {}), contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli.main(list(argv))
    return code, out.getvalue(), err.getvalue()


class JsonMode(unittest.TestCase):
    def setUp(self):
        i18n.set_language("en")
        self.addCleanup(i18n.set_language, "en")
        self.tmp = Path(tempfile.mkdtemp())
        rng = np.random.default_rng(2)
        self.cover = self.tmp / "cover.png"
        Image.fromarray(rng.integers(0, 256, (100, 120, 3), dtype=np.uint8)).save(self.cover)
        self.env = {"PHANTOMPIXEL_LANG": "en", "PHANTOMPIXEL_PASSWORD": "pw-cli"}

    def j(self, *argv, env=None):
        code, out, err = run(*argv, env=env or self.env)
        self.assertEqual(err, "", err)
        return code, json.loads(out)          # stdout must be exactly one JSON document

    def test_capacity(self):
        code, data = self.j("capacity", str(self.cover), "--json")
        self.assertEqual(code, 0)
        self.assertEqual((data["ok"], data["width"], data["height"]), (True, 120, 100))
        self.assertGreater(data["capacity_bytes"], data["capacity_bytes_with_password"])

    def test_hide_extract_inspect_roundtrip(self):
        out_png = self.tmp / "out.png"
        code, hidden = self.j("hide", str(self.cover), "-m", "json says hi " * 20, "-p", "-o", str(out_png), "--json")
        self.assertEqual(code, 0)
        self.assertTrue(hidden["ok"] and hidden["encrypted"] and hidden["verified"] and hidden["compressed"])
        self.assertLess(hidden["stored_bytes"], hidden["original_bytes"])

        code, info = self.j("inspect", str(out_png), "--original", str(self.cover), "--json")
        self.assertEqual(info["signature"]["version"], "2.1")
        self.assertIn(info["detection"]["level"], ("low", "medium", "high"))
        self.assertEqual(info["comparison"]["max_diff"], 1)

        code, got = self.j("extract", str(out_png), "-p", "--json")
        self.assertEqual((code, got["kind"], got["text"]), (0, "text", "json says hi " * 20))

    def test_file_extract_reports_where_it_was_saved(self):
        secret = self.tmp / "s.bin"
        secret.write_bytes(os.urandom(300))
        out_png = self.tmp / "f.png"
        self.j("hide", str(self.cover), "-f", str(secret), "-o", str(out_png), "--json")
        code, got = self.j("extract", str(out_png), "--json")
        self.assertEqual((got["kind"], got["name"], got["size"]), ("file", "s.bin", 300 + 0))
        self.assertEqual(Path(got["saved"]).read_bytes(), secret.read_bytes())

    def test_errors_are_json_with_a_stable_code_and_exit_status_1(self):
        out_png = self.tmp / "o.png"
        self.j("hide", str(self.cover), "-m", "x", "-p", "-o", str(out_png), "--json")
        code, data = self.j("extract", str(out_png), "-p", "--json", env={**self.env, "PHANTOMPIXEL_PASSWORD": "nope"})
        self.assertEqual(code, 1)
        self.assertEqual((data["ok"], data["code"]), (False, "WrongPasswordError"))
        code, data = self.j("extract", str(self.cover), "--json")
        self.assertEqual((code, data["code"]), (1, "NoDataError"))

    def test_error_text_follows_the_language_but_code_does_not(self):
        _, data = self.j("extract", str(self.cover), "--json", "--lang", "tr")
        self.assertIn("bulunamadı", data["error"])
        self.assertEqual(data["code"], "NoDataError")

    def test_v20_images_work_through_the_cli(self):
        fixtures = ROOT / "tests" / "fixtures"
        code, got = self.j("extract", str(fixtures / "v20_text.png"), "--json")
        self.assertIn("made by v2.0", got["text"])
        _, info = self.j("inspect", str(fixtures / "v20_encrypted.png"), "--json")
        self.assertEqual(info["signature"]["version"], "2.0")

    def test_json_mode_does_not_need_rich(self):
        with mock.patch.object(cli, "_missing_deps", wraps=cli._missing_deps) as spy:
            self.j("capacity", str(self.cover), "--json")
        spy.assert_called_with(("rich",))


class Options(unittest.TestCase):
    def test_global_options_are_split_out_anywhere(self):
        self.assertEqual(cli.split_global_options(["--lang", "ru", "hide", "a.png", "--no-anim"]),
                         (["hide", "a.png"], "ru", True))
        self.assertEqual(cli.split_global_options(["capacity", "a.png", "--lang=tr"]), (["capacity", "a.png"], "tr", False))
        self.assertEqual(cli.split_global_options(["photo.png"]), (["photo.png"], None, False))

    def test_a_message_that_looks_like_an_option_is_kept(self):
        self.assertEqual(cli.split_global_options(["hide", "a.png", "-m", "--lang"])[0], ["hide", "a.png", "-m", "--lang"])

    def test_unsupported_language_is_reported(self):
        code, _, err = run("--lang", "de", "capacity", "x.png")
        self.assertEqual(code, 2)
        self.assertIn("de", err)

    def test_help_is_translated(self):
        for lang, word in (("tr", "gizle"), ("ru", "Прячьте")):
            i18n.init(lang)
            self.addCleanup(i18n.set_language, "en")
            text = cli.build_parser().format_help()
            self.assertIn(word, text)
            self.assertIn("capacity", text)
            self.assertIn("--no-anim", text)


class Splash(unittest.TestCase):
    LINES = ["██████╗ ██╗  ██╗", "██╔══██╗██║  ██║", "██████╔╝███████║", "██╔═══╝ ██╔══██║", "██║     ██║  ██║",
             "╚═╝     ╚═╝  ╚═╝"]
    GRADIENT = ["#ff8a80", "#ff5252", "#ff1744", "#e0123c", "#c4102f", "#8e0b22"]

    def console(self, **kw):
        from rich.console import Console
        buf = io.StringIO()
        return Console(file=buf, force_terminal=kw.pop("force_terminal", True), width=kw.pop("width", 100),
                       height=kw.pop("height", 40), color_system="truecolor", **kw), buf

    def test_it_plays_and_ends_on_the_banner(self):
        from phantompixel import splash
        con, buf = self.console()
        self.assertTrue(splash.play(con, self.LINES, self.GRADIENT, "Tagline here", "2.1.0",
                                    sleep=lambda s: None, seed=3))
        plain = re.sub(r"\x1b\[[0-9;?]*[A-Za-z]", "", buf.getvalue())
        last_frame = plain.split("\r")[-1]
        for line in self.LINES:
            self.assertIn(line, last_frame)
        self.assertIn("Tagline here  •  v2.1.0", last_frame)
        self.assertNotIn("░", last_frame)                                  # no noise left in the final picture

    def test_it_uses_every_frame_and_the_requested_pauses(self):
        from phantompixel import splash
        con, _ = self.console()
        pauses = []
        splash.play(con, self.LINES, self.GRADIENT, "abc", "2.1.0", frames=5, delay=0.5, type_delay=0.25,
                    sleep=pauses.append, seed=1)
        self.assertEqual(pauses.count(0.5), 6)
        self.assertEqual(pauses.count(0.25), 4)

    def test_skipped_when_output_is_not_a_terminal(self):
        from phantompixel import splash
        con, _ = self.console(force_terminal=False)
        self.assertFalse(splash.should_animate(con))

    def test_skipped_by_flag_and_by_environment(self):
        from phantompixel import splash
        con, _ = self.console()
        self.assertTrue(splash.should_animate(con))
        self.assertFalse(splash.should_animate(con, disabled=True))
        with mock.patch.dict(os.environ, {"PHANTOMPIXEL_NO_ANIM": "1"}):
            self.assertFalse(splash.should_animate(con))

    def test_skipped_when_the_window_is_too_small(self):
        from phantompixel import splash
        con, buf = self.console(width=10)
        self.assertFalse(splash.play(con, self.LINES, self.GRADIENT, "t", "1", sleep=lambda s: None))
        self.assertEqual(buf.getvalue(), "")
        con, buf = self.console(height=6)
        self.assertFalse(splash.play(con, self.LINES, self.GRADIENT, "t", "1", sleep=lambda s: None))

    def test_ctrl_c_skips_the_show_instead_of_crashing(self):
        from phantompixel import splash
        con, buf = self.console()
        def boom(_):
            raise KeyboardInterrupt
        self.assertTrue(splash.play(con, self.LINES, self.GRADIENT, "Skip me", "2.1.0", sleep=boom, seed=1))
        self.assertIn("Skip me", re.sub(r"\x1b\[[0-9;?]*[A-Za-z]", "", buf.getvalue()))

    def test_the_banner_function_falls_back_to_the_plain_banner(self):
        from phantompixel import ui
        con, buf = self.console(force_terminal=False, width=120)
        with mock.patch.object(ui, "console", con):
            ui.banner(animate=True)                                          # not a terminal -> static banner
        text = re.sub(r"\x1b\[[0-9;?]*[A-Za-z]", "", buf.getvalue())
        self.assertIn("██████╗", text)
        self.assertIn(f"v{ui.VERSION}", text)


if __name__ == "__main__":
    unittest.main()
