"""Run with:  python -m unittest discover -s tests -v"""
import io
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from phantompixel import analyzer, engine, workflows  # noqa: E402
from phantompixel.errors import (  # noqa: E402
    CapacityError, CorruptedDataError, NoDataError, PasswordRequiredError, StegoError, WrongPasswordError,
)
from phantompixel.utils import unique_path  # noqa: E402


class StegoTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        rng = np.random.default_rng(1)
        base = np.linspace(0, 255, 200 * 300 * 3).reshape(200, 300, 3)
        arr = np.clip(base + rng.normal(0, 3, base.shape), 0, 255).astype(np.uint8)
        self.cover = self.tmp / "cover.png"
        Image.fromarray(arr).save(self.cover)

    # --- round trips -------------------------------------------------------
    def test_text_roundtrip(self):
        res = workflows.hide(self.cover, text="Hello world, ĞÜŞİÖÇ ✓")
        self.assertTrue(res.verified)
        self.assertEqual(workflows.extract(res.output).text, "Hello world, ĞÜŞİÖÇ ✓")

    def test_encrypted_roundtrip(self):
        res = workflows.hide(self.cover, text="secret", password="pass123")
        self.assertTrue(res.encrypted)
        self.assertEqual(workflows.extract(res.output, "pass123").text, "secret")

    def test_file_roundtrip(self):
        secret = self.tmp / "secret.bin"
        secret.write_bytes(bytes(range(256)) * 10)
        res = workflows.hide(self.cover, file=secret)
        out = workflows.extract(res.output)
        self.assertEqual(out.saved.read_bytes(), secret.read_bytes())

    def test_alpha_preserved(self):
        rgba = np.zeros((100, 100, 4), np.uint8)
        rgba[..., 3] = np.arange(100)[:, None] * 2
        src = self.tmp / "a.png"
        Image.fromarray(rgba).save(src)
        res = workflows.hide(src, text="alpha")
        self.assertTrue((engine.load_array(res.output)[..., 3] == rgba[..., 3]).all())
        self.assertEqual(workflows.extract(res.output).text, "alpha")

    def test_jpeg_cover_is_accepted(self):
        jpg = self.tmp / "cover.jpg"
        Image.open(self.cover).convert("RGB").save(jpg, quality=95)
        res = workflows.hide(jpg, text="from a jpeg cover")
        self.assertEqual(res.output.suffix, ".png")
        self.assertEqual(workflows.extract(res.output).text, "from a jpeg cover")

    # --- passwords ---------------------------------------------------------
    def test_wrong_and_missing_password(self):
        res = workflows.hide(self.cover, text="secret", password="right")
        with self.assertRaises(WrongPasswordError):
            workflows.extract(res.output, "wrong")
        with self.assertRaises(PasswordRequiredError):
            workflows.extract(res.output)

    # --- reliability -------------------------------------------------------
    def test_too_large(self):
        with self.assertRaises(CapacityError):
            workflows.hide(self.cover, text="x" * 100_000)

    def test_clean_image_has_no_data(self):
        self.assertIsNone(engine.inspect(self.cover))
        with self.assertRaises(NoDataError):
            engine.extract(self.cover)

    def test_jpeg_recompression_is_detected(self):
        res = workflows.hide(self.cover, text="fragile")
        jpg = self.tmp / "recompressed.jpg"
        Image.open(res.output).convert("RGB").save(jpg, quality=95)
        with self.assertRaises(StegoError):  # header is destroyed -> NoDataError
            engine.extract(jpg)

    def test_tampering_with_the_body_is_detected(self):
        res = workflows.hide(self.cover, text="x" * 3000)
        arr = engine.load_array(res.output)
        arr[100:, :, :3] ^= 1  # flip the LSB of most of the image (header rows untouched)
        tampered = self.tmp / "tampered.png"
        Image.fromarray(arr).save(tampered)
        with self.assertRaises(CorruptedDataError):
            engine.extract(tampered)

    def test_cannot_overwrite_cover(self):
        payload = engine.Payload("text", "m.txt", b"hi")
        with self.assertRaises(StegoError):
            engine.hide(self.cover, payload, self.cover)
        self.assertIsNone(engine.inspect(self.cover))  # untouched

    def test_default_output_never_overwrites(self):
        first = workflows.hide(self.cover, text="one").output
        second = workflows.hide(self.cover, text="two").output
        self.assertNotEqual(first, second)
        self.assertEqual(workflows.extract(first).text, "one")

    def test_malicious_file_name_cannot_escape_folder(self):
        engine.hide(self.cover, engine.Payload("file", "../../evil.txt", b"x"), self.tmp / "e.png")
        saved = workflows.extract(self.tmp / "e.png", outdir=self.tmp / "ex").saved
        self.assertEqual(saved.parent, self.tmp / "ex")

    def test_visual_change_is_tiny(self):
        res = workflows.hide(self.cover, text="a" * 500)
        cmp = analyzer.compare(self.cover, res.output)
        self.assertEqual(cmp.max_diff, 1)
        self.assertGreater(cmp.psnr, 50)

    def test_capacity_matches_reality(self):
        cap = engine.capacity(self.cover)
        workflows.hide(self.cover, text="x" * (cap - 0))  # exactly full must work
        with self.assertRaises(CapacityError):
            workflows.hide(self.cover, text="x" * (cap + 1))


class PermutationTests(unittest.TestCase):
    SEED = bytes(range(32))

    def test_is_a_bijection(self):
        for m in (1, 2, 3, 17, 1000, 4096, 5000, 65537):
            p = engine._permute(np.arange(m, dtype=np.uint64), m, self.SEED)
            self.assertTrue(np.array_equal(np.sort(p), np.arange(m)), m)

    def test_golden_values_guard_the_file_format(self):
        # If this fails, files made by older versions can no longer be read!
        p = engine._permute(np.arange(1000, dtype=np.uint64), 100000, self.SEED)
        self.assertEqual(p[:6].tolist(), [95839, 55023, 37000, 54426, 9374, 5545])

    def test_depends_on_seed(self):
        a = engine._permute(np.arange(100, dtype=np.uint64), 10000, self.SEED)
        b = engine._permute(np.arange(100, dtype=np.uint64), 10000, bytes(32))
        self.assertFalse(np.array_equal(a, b))


class UtilTests(unittest.TestCase):
    def test_unique_path(self):
        d = Path(tempfile.mkdtemp())
        (d / "a.png").write_bytes(b"")
        self.assertEqual(unique_path(d / "a.png"), d / "a (1).png")
        self.assertEqual(unique_path(d / "b.png"), d / "b.png")


if __name__ == "__main__":
    unittest.main()
