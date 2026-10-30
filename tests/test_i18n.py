"""Language support: English, Turkish, Russian."""
import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from phantompixel import i18n  # noqa: E402
from phantompixel.locales import en, ru, tr  # noqa: E402

PKG = Path(__file__).resolve().parent.parent / "phantompixel"
PLACEHOLDER = re.compile(r"\{(\w+)\}")


class Tables(unittest.TestCase):
    def test_every_language_has_every_key(self):
        for name, table in (("tr", tr.S), ("ru", ru.S)):
            self.assertEqual(sorted(set(en.S) - set(table)), [], f"{name}: missing keys")
            self.assertEqual(sorted(set(table) - set(en.S)), [], f"{name}: keys that do not exist in English")

    def test_placeholders_match_english(self):
        for name, table in (("tr", tr.S), ("ru", ru.S)):
            for key, text in en.S.items():
                self.assertEqual(set(PLACEHOLDER.findall(text)), set(PLACEHOLDER.findall(table[key])), f"{name}:{key}")

    def test_no_empty_translations(self):
        for name, table in (("en", en.S), ("tr", tr.S), ("ru", ru.S)):
            for key, text in table.items():
                if key.endswith(".d") and key.startswith("menu.0"):
                    continue
                self.assertTrue(text.strip(), f"{name}:{key} is empty")

    def test_translated_text_really_differs_from_english(self):
        same = [k for k in en.S if tr.S[k] == en.S[k] and len(en.S[k]) > 12 and k != "menu.7.d"]
        self.assertEqual(same, [], "untranslated Turkish texts")
        same = [k for k in en.S if ru.S[k] == en.S[k] and len(en.S[k]) > 12 and k != "menu.7.d"]
        self.assertEqual(same, [], "untranslated Russian texts")

    def test_rich_markup_is_balanced(self):
        """A broken [tag] in a translation would crash or garble the terminal UI."""
        tag = re.compile(r"\[(/?)(?:bold|green|red|yellow|grey70)?[^\]]*\]")
        for name, table in (("en", en.S), ("tr", tr.S), ("ru", ru.S)):
            for key, text in table.items():
                opens = len(re.findall(r"\[(?!/)[a-z#][^\]]*\]", text))
                closes = len(re.findall(r"\[/[^\]]*\]", text))
                self.assertEqual(opens, closes, f"{name}:{key}: {text!r}")

    def test_every_key_used_in_code_exists(self):
        used = set()
        for path in list(PKG.glob("*.py")) + [PKG.parent / "main.py"]:
            used |= set(re.findall(r"""\bt\(\s*["']([a-z0-9_.]+)["']""", path.read_text(encoding="utf-8")))
            used |= set(re.findall(r"""_card_text\(\s*["']([a-z0-9_.]+)["']""", path.read_text(encoding="utf-8")))
        self.assertGreater(len(used), 80)
        self.assertEqual(sorted(k for k in used if k not in en.S), [])

    def test_every_english_key_is_used_somewhere(self):
        text = "\n".join(p.read_text(encoding="utf-8") for p in list(PKG.glob("*.py")) + [PKG.parent / "main.py"])
        dynamic = ("menu.", "detect.", "card.")          # keys built at run time (f"detect.{level}", t(f"menu.{n}") ...)
        unused = [k for k in en.S if k not in text and not k.startswith(dynamic)]
        self.assertEqual(unused, [])


class Switching(unittest.TestCase):
    def tearDown(self):
        i18n.set_language("en")

    def test_t_follows_the_current_language(self):
        i18n.set_language("tr")
        self.assertEqual(i18n.t("menu.2"), "Gizle")
        i18n.set_language("ru")
        self.assertEqual(i18n.t("menu.2"), "Спрятать")
        i18n.set_language("en")
        self.assertEqual(i18n.t("menu.2"), "Hide")

    def test_fallbacks_never_crash(self):
        self.assertEqual(i18n.t("no.such.key"), "no.such.key")
        i18n.set_language("tr")
        self.assertEqual(i18n.t("err.capacity", need=1, cap=2).count("1"), 1)
        self.assertIn("{need}", i18n.t("err.capacity"))        # missing placeholders: raw text, no exception

    def test_normalize(self):
        for given, expected in (("tr", "tr"), ("TR", "tr"), ("tr_TR.UTF-8", "tr"), ("ru-RU", "ru"), ("Türkçe", "tr"),
                                ("русский", "ru"), ("en_US", "en"), ("de", None), ("", None), (None, None)):
            self.assertEqual(i18n.normalize(given), expected, given)

    def test_unsupported_language_is_rejected(self):
        with self.assertRaises(ValueError):
            i18n.set_language("de")


class Remembering(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        patcher = mock.patch.object(i18n, "SETTINGS_FILE", self.tmp / "sub" / "settings.json")
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(i18n.set_language, "en")

    def test_choice_is_saved_and_used_next_time(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("PHANTOMPIXEL_LANG", None)
            i18n.set_language("ru", persist=True)
            self.assertEqual(json.loads(i18n.SETTINGS_FILE.read_text(encoding="utf-8"))["language"], "ru")
            self.assertEqual(i18n.resolve(), "ru")

    def test_order_of_precedence(self):
        i18n.save_setting("language", "ru")
        with mock.patch.dict(os.environ, {"PHANTOMPIXEL_LANG": "tr"}):
            self.assertEqual(i18n.resolve(), "tr")              # environment beats the saved choice
            self.assertEqual(i18n.resolve("en"), "en")          # --lang beats everything
            self.assertEqual(i18n.resolve("de"), "tr")          # an unsupported --lang is ignored

    def test_other_settings_survive(self):
        i18n.save_setting("something", 1)
        i18n.save_setting("language", "tr")
        data = json.loads(i18n.SETTINGS_FILE.read_text(encoding="utf-8"))
        self.assertEqual(data, {"something": 1, "language": "tr"})

    def test_unwritable_settings_never_break_the_program(self):
        with mock.patch.object(i18n, "SETTINGS_FILE", Path("/proc/definitely/not/writable/settings.json")):
            i18n.save_setting("language", "tr")                  # must simply do nothing
            self.assertEqual(i18n.load_settings(), {})

    def test_corrupt_settings_file_is_ignored(self):
        i18n.SETTINGS_FILE.parent.mkdir(parents=True)
        i18n.SETTINGS_FILE.write_text("{ not json", encoding="utf-8")
        self.assertEqual(i18n.load_settings(), {})

    def test_system_language_from_environment(self):
        with mock.patch.object(sys, "platform", "linux"):
            for env, expected in (({"LANG": "tr_TR.UTF-8"}, "tr"), ({"LC_ALL": "ru_RU.UTF-8"}, "ru"),
                                  ({"LANG": "en_US.UTF-8"}, "en"), ({"LANG": "de_DE.UTF-8"}, None)):
                with mock.patch.dict(os.environ, env, clear=True):
                    self.assertEqual(i18n.system_language(), expected, env)


class Output(unittest.TestCase):
    """The translations are really used by the program."""

    def tearDown(self):
        i18n.set_language("en")

    def test_detector_verdict_is_translated_but_level_is_stable(self):
        from phantompixel.analyzer import Detection
        d = Detection(1.0, 0.95, "high")
        i18n.set_language("tr")
        self.assertIn("Yüksek", d.verdict)
        i18n.set_language("ru")
        self.assertIn("Высокое", d.verdict)
        self.assertEqual(d.level, "high")

    def test_errors_follow_the_language(self):
        from phantompixel import engine
        from phantompixel.errors import NoDataError
        clean = Path(__file__).parent / "fixtures" / "v20_cover.png"      # an image without hidden data
        for lang, word in (("en", "No PhantomPixel"), ("tr", "bulunamadı"), ("ru", "нет данных")):
            i18n.set_language(lang)
            with self.assertRaises(NoDataError) as ctx:
                engine.extract(clean)
            self.assertIn(word, str(ctx.exception), lang)


if __name__ == "__main__":
    unittest.main()
