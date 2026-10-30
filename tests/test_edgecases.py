"""Image-format edge cases and the v2.1 header binding (AES-GCM associated data)."""
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from phantompixel import engine, i18n, workflows  # noqa: E402
from phantompixel.errors import CapacityError, WrongPasswordError  # noqa: E402


def setUpModule():
    i18n.set_language("en")


class ImageModes(unittest.TestCase):
    """Every kind of input image must survive hide -> extract, and keep its look."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.rng = np.random.default_rng(5)
        self.rgb = self.rng.integers(0, 256, (60, 80, 3), dtype=np.uint8)

    def roundtrip(self, name: str, img: Image.Image, password=None) -> tuple[Path, np.ndarray]:
        src = self.tmp / f"{name}.png"
        img.save(src)
        res = workflows.hide(src, text=f"edge case {name}", password=password)
        self.assertEqual(workflows.extract(res.output, password).text, f"edge case {name}")
        return res.output, engine.load_array(src)

    def test_rgb(self):
        self.roundtrip("rgb", Image.fromarray(self.rgb))

    def test_rgba_alpha_is_kept(self):
        alpha = self.rng.integers(0, 256, (60, 80), dtype=np.uint8)
        out, _ = self.roundtrip("rgba", Image.fromarray(np.dstack([self.rgb, alpha])))
        self.assertTrue((engine.load_array(out)[..., 3] == alpha).all())

    def test_grayscale(self):
        out, _ = self.roundtrip("gray", Image.fromarray(self.rgb[..., 0]))
        with Image.open(out) as im:
            self.assertEqual(im.mode, "RGB")

    def test_grayscale_with_alpha(self):
        alpha = self.rng.integers(0, 256, (60, 80), dtype=np.uint8)
        out, _ = self.roundtrip("la", Image.fromarray(np.dstack([self.rgb[..., 0], alpha]), "LA"))
        self.assertTrue((engine.load_array(out)[..., 3] == alpha).all())

    def test_palette_image(self):
        self.roundtrip("palette", Image.fromarray(self.rgb).quantize(64))

    def test_palette_transparency_is_not_lost(self):
        """v2.0 silently turned transparent palette pixels opaque."""
        pal = Image.fromarray(self.rgb).quantize(64)
        pal.info["transparency"] = 0
        pal.save(self.tmp / "t.png", transparency=0)
        res = workflows.hide(self.tmp / "t.png", text="keep the holes")
        out = engine.load_array(res.output)
        self.assertEqual(out.shape[2], 4)
        self.assertTrue((out[..., 3] == 0).any(), "transparent pixels must stay transparent")
        self.assertEqual(workflows.extract(res.output).text, "keep the holes")

    def test_16_bit_grayscale_is_scaled_not_clipped(self):
        """v2.0 clipped 16-bit values to 255 and produced a nearly white image."""
        g16 = np.linspace(0, 65535, 60 * 80).reshape(60, 80).astype(np.uint16)
        src = self.tmp / "g16.png"
        Image.fromarray(g16).save(src)
        loaded = engine.load_array(src)
        self.assertLess(loaded.mean(), 160)               # a clipped image would be ~250
        self.assertGreater(int(loaded.max()) - int(loaded.min()), 200)
        res = workflows.hide(src, text="16 bit")
        self.assertEqual(workflows.extract(res.output).text, "16 bit")

    def test_16_bit_rgb(self):
        import zlib, struct
        w, h = 40, 30
        data = self.rng.integers(0, 65536, (h, w, 3), dtype=np.uint16).astype(">u2")
        raw = b"".join(b"\x00" + data[y].tobytes() for y in range(h))
        def chunk(tag, body):
            return struct.pack(">I", len(body)) + tag + body + struct.pack(">I", zlib.crc32(tag + body) & 0xFFFFFFFF)
        png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 16, 2, 0, 0, 0))
               + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))
        src = self.tmp / "rgb16.png"
        src.write_bytes(png)
        res = workflows.hide(src, text="deep colour")
        self.assertEqual(workflows.extract(res.output).text, "deep colour")

    def test_exif_orientation_is_applied(self):
        img = Image.fromarray(self.rng.integers(0, 256, (60, 80, 3), dtype=np.uint8))   # landscape 80x60
        exif = Image.Exif()
        exif[0x0112] = 6                                                                  # rotate 90 degrees
        src = self.tmp / "rot.jpg"
        img.save(src, quality=95, exif=exif)
        res = workflows.hide(src, text="rotated")
        with Image.open(res.output) as im:
            self.assertEqual(im.size, (60, 80))                                           # now portrait
        self.assertEqual(workflows.extract(res.output).text, "rotated")

    def test_tiny_image_reports_capacity_error(self):
        src = self.tmp / "tiny.png"
        Image.fromarray(self.rgb[:4, :4]).save(src)
        with self.assertRaises(CapacityError):
            workflows.hide(src, text="hi")
        self.assertEqual(engine.capacity(src), 0)

    def test_not_an_image(self):
        bad = self.tmp / "bad.png"
        bad.write_bytes(b"this is not a png")
        with self.assertRaises(engine.StegoError):
            engine.load_array(bad)


class HeaderBinding(unittest.TestCase):
    """PPX3 passes the header (magic, flags, salt, length) to AES-GCM as associated data."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        rng = np.random.default_rng(9)
        arr = rng.integers(0, 256, (80, 80, 3), dtype=np.uint8)
        self.cover = self.tmp / "c.png"
        Image.fromarray(arr).save(self.cover)

    def _flip_header_bit(self, image: Path, bit_index: int) -> Path:
        arr = engine.load_array(image)
        arr[..., :3].reshape(-1)[bit_index] ^= 1
        out = self.tmp / "flipped.png"
        Image.fromarray(arr).save(out)
        return out

    def test_flipping_the_compression_flag_is_caught_by_the_tag(self):
        payload = engine.Payload("text", "", os.urandom(200))      # incompressible -> compressed flag is 0
        res = engine.hide(self.cover, payload, self.tmp / "p.png", "pw")
        self.assertFalse(res.compressed)
        flags_bit_for_compressed = 32 + 6                          # FLAGS byte starts at bit 32; 0b10 is bit 6 of it
        tampered = self._flip_header_bit(res.output, flags_bit_for_compressed)
        self.assertTrue(engine.inspect(tampered)["compressed"])    # the header now claims "compressed"
        # Without header binding the password would still decrypt and zlib would fail later.
        # With binding, the authentication tag rejects it before anything is decompressed.
        with self.assertRaises(WrongPasswordError):
            engine.extract(tampered, "pw")

    def test_unmodified_image_still_opens(self):
        payload = engine.Payload("text", "", os.urandom(200))
        res = engine.hide(self.cover, payload, self.tmp / "p.png", "pw")
        self.assertEqual(engine.extract(res.output, "pw").data, payload.data)


if __name__ == "__main__":
    unittest.main()
