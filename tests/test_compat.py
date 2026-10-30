"""Format compatibility between PhantomPixel versions.

Rule (one-way): a version reads its own format and all OLDER ones, never newer ones.
    v2.1 opens images made by v2.0          (PPX2)
    v2.0 can NOT open images made by v2.1   (PPX3)  -> proven here with the REAL v2.0 code
    v2.1 can NOT open images made by v2.2   (PPX4)  -> refused with a clear message

Run with:  python -m unittest discover -s tests -v
"""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))   # the project
sys.path.insert(0, str(HERE))          # tests/legacy_v20

from phantompixel import engine, i18n, workflows  # noqa: E402
from phantompixel.errors import NewerVersionError, NoDataError, PasswordRequiredError, WrongPasswordError  # noqa: E402
from legacy_v20 import engine as v20_engine  # noqa: E402  (unmodified v2.0 code)
from legacy_v20 import errors as v20_errors  # noqa: E402

FIXTURES = HERE / "fixtures"
EXPECTED = json.loads((FIXTURES / "v20_expected.json").read_text(encoding="utf-8"))


def setUpModule():
    i18n.set_language("en")


class NewReadsOld(unittest.TestCase):
    """Images made by the real v2.0 program (stored in tests/fixtures) open in v2.1."""

    def test_v20_fixtures(self):
        for name, meta in EXPECTED.items():
            with self.subTest(name):
                got = engine.extract(FIXTURES / name, meta["password"])
                self.assertEqual(got.kind, meta["kind"])
                if meta["kind"] == "text":
                    self.assertEqual(got.data.decode("utf-8"), meta["text"])
                else:
                    self.assertEqual(got.name, meta["name"])
                    self.assertEqual(hashlib.sha256(got.data).hexdigest(), meta["sha256"])

    def test_v20_images_are_reported_as_v20(self):
        info = engine.inspect(FIXTURES / "v20_text.png")
        self.assertEqual(info["version"], "2.0")
        self.assertFalse(info["compressed"])
        self.assertTrue(engine.inspect(FIXTURES / "v20_encrypted.png")["encrypted"])

    def test_v20_password_rules_still_apply(self):
        with self.assertRaises(PasswordRequiredError):
            engine.extract(FIXTURES / "v20_encrypted.png")
        with self.assertRaises(WrongPasswordError):
            engine.extract(FIXTURES / "v20_encrypted.png", "wrong")

    def test_freshly_made_v20_images_open_too(self):
        """Not only the stored fixtures: whatever the real v2.0 code writes today."""
        out = Path(tempfile.mkdtemp()) / "fresh.png"
        v20_engine.hide(FIXTURES / "v20_cover.png", v20_engine.Payload("text", "", b"fresh v2.0"), out, "pw")
        self.assertEqual(engine.extract(out, "pw").data, b"fresh v2.0")

    def test_workflow_level_extract_of_v20_file(self):
        out = workflows.extract(FIXTURES / "v20_file.png", outdir=Path(tempfile.mkdtemp()))
        self.assertEqual(out.saved.name, "note.bin")
        self.assertEqual(len(out.saved.read_bytes()), EXPECTED["v20_file.png"]["size"])


class OldCannotReadNew(unittest.TestCase):
    """The real v2.0 code must not be able to open anything v2.1 writes."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.cover = FIXTURES / "v20_cover.png"

    def _make(self, password):
        res = engine.hide(self.cover, engine.Payload("text", "", b"made by v2.1 " * 20), self.tmp / "new.png", password)
        self.assertEqual(engine.inspect(res.output)["version"], "2.1")
        return res.output

    def test_v20_cannot_open_plain_v21_image(self):
        out = self._make(None)
        with self.assertRaises(v20_errors.NoDataError):
            v20_engine.extract(out)
        self.assertIsNone(v20_engine.inspect(out))

    def test_v20_cannot_open_password_protected_v21_image(self):
        out = self._make("secret")
        with self.assertRaises(v20_errors.NoDataError):
            v20_engine.extract(out, "secret")
        self.assertIsNone(v20_engine.inspect(out))

    def test_v21_still_opens_its_own_images(self):
        out = self._make("secret")
        self.assertEqual(engine.extract(out, "secret").data, b"made by v2.1 " * 20)

    def test_new_format_uses_a_new_magic(self):
        out = self._make(None)
        flat = engine.load_array(out)[..., :3].reshape(-1)
        self.assertEqual(np.packbits(flat[:32] & 1).tobytes(), b"PPX3")


class NewerImagesAreRefused(unittest.TestCase):
    """Preparing for v2.2: an image with a newer magic is recognised and refused, never misread."""

    def _image_with_magic(self, magic: bytes) -> Path:
        tmp = Path(tempfile.mkdtemp())
        res = engine.hide(FIXTURES / "v20_cover.png", engine.Payload("text", "", b"x"), tmp / "a.png")
        arr = engine.load_array(res.output)
        flat = arr[..., :3].reshape(-1)
        flat[:32] = (flat[:32] & 0xFE) | np.unpackbits(np.frombuffer(magic, np.uint8))
        out = tmp / "newer.png"
        Image.fromarray(arr).save(out)
        return out

    def test_ppx4_is_a_newer_version(self):
        out = self._image_with_magic(b"PPX4")
        with self.assertRaises(NewerVersionError) as ctx:
            engine.extract(out)
        self.assertIn("PPX4", str(ctx.exception))
        with self.assertRaises(NewerVersionError):
            engine.inspect(out)

    def test_later_magics_are_newer_too(self):
        for magic in (b"PPX9", b"PPXA"):
            with self.subTest(magic), self.assertRaises(NewerVersionError):
                engine.extract(self._image_with_magic(magic))

    def test_unrelated_or_older_unknown_magics_are_just_no_data(self):
        for magic in (b"PPX1", b"PPX0", b"ABCD", b"PPX\x00"):
            with self.subTest(magic), self.assertRaises(NoDataError):
                engine.extract(self._image_with_magic(magic))

    def test_message_is_translated(self):
        out = self._image_with_magic(b"PPX4")
        try:
            i18n.set_language("tr")
            with self.assertRaises(NewerVersionError) as ctx:
                engine.extract(out)
            self.assertIn("güncelleyin", str(ctx.exception))
        finally:
            i18n.set_language("en")


if __name__ == "__main__":
    unittest.main()
