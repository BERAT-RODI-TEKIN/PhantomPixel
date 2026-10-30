"""LSB steganography core.

The least significant bit (LSB) of every colour channel (R, G, B) carries data.
Changing it moves a colour by at most 1/255, which the eye cannot see.

Layout (see config.py): a 29-byte header is written sequentially at the start,
the body is scattered over the rest of the image by a keyed permutation.
  * With a password: the body is AES-256-GCM encrypted and the permutation is
    keyed by the password, so the data is both unreadable and unlocatable.
  * Without a password: the permutation is keyed by the public salt, which
    spreads the data evenly instead of leaving a stripe at the top.
"""
from __future__ import annotations

import hashlib
import os
import struct
import zlib
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

from . import crypto
from .config import (
    CRYPTO_OVERHEAD,
    FLAG_ENCRYPTED,
    HEADER_BITS,
    HEADER_BYTES,
    MAGIC,
    PAYLOAD_OVERHEAD,
    SALT_LEN,
)
from .errors import (
    CapacityError,
    CorruptedDataError,
    NoDataError,
    PasswordRequiredError,
    StegoError,
    WrongPasswordError,
)

__all__ = ["Payload", "HideResult", "hide", "extract", "inspect", "capacity", "capacity_for",
           "image_size", "load_array", "StegoError"]


@dataclass
class Payload:
    kind: str  # "text" | "file"
    name: str
    data: bytes


@dataclass
class HideResult:
    output: Path
    stored_bytes: int
    capacity_bytes: int
    encrypted: bool
    verified: bool

    @property
    def usage(self) -> float:
        return self.stored_bytes / self.capacity_bytes if self.capacity_bytes else 1.0


@dataclass
class _Header:
    flags: int
    salt: bytes
    length: int
    crc: int


# --------------------------------------------------------------------------
# Payload packing
# --------------------------------------------------------------------------
def _pack(p: Payload) -> bytes:
    name = p.name.encode("utf-8")[:65535]
    return bytes([1 if p.kind == "file" else 0]) + struct.pack(">H", len(name)) + name + p.data


def _unpack(raw: bytes) -> Payload:
    if len(raw) < PAYLOAD_OVERHEAD:
        raise CorruptedDataError("The hidden data is damaged.")
    n = struct.unpack(">H", raw[1:3])[0]
    return Payload("file" if raw[0] else "text", raw[3:3 + n].decode("utf-8", "replace"), raw[3 + n:])


# --------------------------------------------------------------------------
# Image helpers
# --------------------------------------------------------------------------
def image_size(path: str | Path) -> tuple[int, int]:
    """Width and height without decoding the whole image (fast)."""
    try:
        with Image.open(path) as im:
            return im.size
    except Exception as exc:  # noqa: BLE001
        raise StegoError(f"Could not open the image: {exc}") from exc


def load_array(path: str | Path) -> np.ndarray:
    """Loads an image as an RGB / RGBA array (alpha is preserved, EXIF rotation applied)."""
    try:
        img = Image.open(path)
        img.load()
    except Exception as exc:  # noqa: BLE001
        raise StegoError(f"Could not open the image: {exc}") from exc
    try:
        img = ImageOps.exif_transpose(img)
    except Exception:  # noqa: BLE001
        pass
    return np.array(img.convert("RGBA" if "A" in img.getbands() else "RGB"))


def capacity_for(width: int, height: int, encrypted: bool = False) -> int:
    """Maximum bytes of user data that fit into an image of this size."""
    cap = (width * height * 3 - HEADER_BITS) // 8 - PAYLOAD_OVERHEAD
    return max(0, cap - (CRYPTO_OVERHEAD if encrypted else 0))


def capacity(path: str | Path, encrypted: bool = False) -> int:
    return capacity_for(*image_size(path), encrypted)


# --------------------------------------------------------------------------
# Keyed permutation (memory-light, platform independent)
# --------------------------------------------------------------------------
# A Feistel network over the smallest even-bit domain that covers the image,
# plus "cycle walking" to stay inside the exact domain. It needs O(n) memory for
# n hidden bits (a full np.random.permutation would need 8 bytes per image bit)
# and uses only integer maths, so results are identical on every platform.
_C1 = np.uint64(0x9E3779B97F4A7C15)
_C2 = np.uint64(0xBF58476D1CE4E5B9)
_ROUNDS = 8


def _round_keys(seed: bytes) -> list[np.uint64]:
    base = [int.from_bytes(seed[i:i + 8], "little") for i in range(0, 32, 8)]
    return [np.uint64((base[i % 4] + i * 0x9E3779B97F4A7C15) & 0xFFFFFFFFFFFFFFFF) for i in range(_ROUNDS)]


def _feistel(x: np.ndarray, half: int, keys: list[np.uint64]) -> np.ndarray:
    h = np.uint64(half)
    mask = np.uint64((1 << half) - 1)
    left, right = x >> h, x & mask
    for k in keys:
        t = (right + k) * _C1
        t ^= t >> np.uint64(29)
        t = t * _C2
        t ^= t >> np.uint64(32)
        left, right = right, left ^ (t & mask)
    return (left << h) | right


def _permute(indices: np.ndarray, domain: int, seed: bytes) -> np.ndarray:
    """Maps indices 0..n-1 to distinct positions inside 0..domain-1."""
    bits = max(2, (domain - 1).bit_length())
    half = (bits + bits % 2) // 2
    keys = _round_keys(seed)
    with np.errstate(over="ignore"):
        x = _feistel(indices.astype(np.uint64), half, keys)
        todo = np.flatnonzero(x >= domain)
        while todo.size:  # cycle walking: re-encrypt values that fell outside the domain
            x[todo] = _feistel(x[todo], half, keys)
            todo = todo[x[todo] >= domain]
    return x.astype(np.int64)


def _public_seed(salt: bytes) -> bytes:
    return hashlib.sha256(b"PhantomPixel/scatter/v2" + salt).digest()


def _positions(total_bits: int, n_bits: int, seed: bytes) -> np.ndarray:
    """Bit positions of the body (everything after the header)."""
    return HEADER_BITS + _permute(np.arange(n_bits, dtype=np.uint64), total_bits - HEADER_BITS, seed)


def _read_header(flat: np.ndarray) -> _Header:
    if flat.size < HEADER_BITS:
        raise NoDataError("The image is too small to contain data.")
    raw = np.packbits(flat[:HEADER_BITS] & 1).tobytes()
    if raw[:4] != MAGIC:
        raise NoDataError("No PhantomPixel data found in this image.")
    length, crc = struct.unpack(">II", raw[5 + SALT_LEN:HEADER_BYTES])
    return _Header(raw[4], raw[5:5 + SALT_LEN], length, crc)


# --------------------------------------------------------------------------
# Public operations
# --------------------------------------------------------------------------
def hide(cover: str | Path, payload: Payload, output: str | Path,
         password: str | None = None, verify: bool = True) -> HideResult:
    out = Path(output)
    if out.exists() and out.resolve() == Path(cover).resolve():
        raise StegoError("The output file would overwrite the cover image. Choose a different name.")

    arr = load_array(cover)
    rgb = arr[..., :3].copy()
    flat = rgb.reshape(-1)  # rgb is C-contiguous, so this is a view: writing to flat changes rgb

    body = _pack(payload)
    salt = os.urandom(SALT_LEN)
    flags = 0
    if password:
        key, seed = crypto.derive(password, salt)
        body = crypto.encrypt(body, key)
        flags |= FLAG_ENCRYPTED
    else:
        seed = _public_seed(salt)

    body_bits = len(body) * 8
    if HEADER_BITS + body_bits > flat.size:
        h, w = arr.shape[:2]
        raise CapacityError(
            f"The secret does not fit: it needs {len(body):,} bytes but this image holds about "
            f"{capacity_for(w, h, bool(password)):,}. Use a larger image or a smaller secret."
        )

    header = MAGIC + bytes([flags]) + salt + struct.pack(">II", len(body), zlib.crc32(body))
    flat[:HEADER_BITS] = (flat[:HEADER_BITS] & 0xFE) | np.unpackbits(np.frombuffer(header, np.uint8))
    pos = _positions(flat.size, body_bits, seed)
    flat[pos] = (flat[pos] & 0xFE) | np.unpackbits(np.frombuffer(body, np.uint8))
    arr[..., :3] = rgb

    out.parent.mkdir(parents=True, exist_ok=True)
    part = out.with_name(out.name + ".part")
    try:
        # PNG is lossless; JPEG would destroy the hidden bits.
        Image.fromarray(arr).save(part, format="PNG", compress_level=3)
        os.replace(part, out)
    finally:
        part.unlink(missing_ok=True)

    if verify:  # read the written file back and compare: never report success blindly
        try:
            check = extract(out, password)
            ok = check.kind == payload.kind and check.data == payload.data
        except StegoError as exc:
            out.unlink(missing_ok=True)
            raise StegoError(f"Self-check failed ({exc}). Nothing was saved.") from exc
        if not ok:
            out.unlink(missing_ok=True)
            raise StegoError("Self-check failed: the data read back did not match. Nothing was saved.")

    h, w = arr.shape[:2]
    return HideResult(out, len(body), capacity_for(w, h, bool(password)), bool(password), verify)


def extract(stego: str | Path, password: str | None = None) -> Payload:
    flat = load_array(stego)[..., :3].reshape(-1)
    head = _read_header(flat)
    if head.length * 8 > flat.size - HEADER_BITS:
        raise CorruptedDataError("The header is damaged: the image was probably modified after hiding.")

    encrypted = bool(head.flags & FLAG_ENCRYPTED)
    if encrypted:
        if not password:
            raise PasswordRequiredError("This data is protected by a password.")
        key, seed = crypto.derive(password, head.salt)
    else:
        seed = _public_seed(head.salt)

    pos = _positions(flat.size, head.length * 8, seed)
    body = np.packbits(flat[pos] & 1).tobytes()

    if zlib.crc32(body) != head.crc:
        if encrypted:
            raise WrongPasswordError(
                "Wrong password, or the image was modified after hiding "
                "(JPEG conversion, resizing, screenshot, editing)."
            )
        raise CorruptedDataError(
            "The hidden data is damaged: the image was modified after hiding "
            "(JPEG conversion, resizing, screenshot, editing). Use the original PNG file."
        )
    if encrypted:
        body = crypto.decrypt(body, key)
    return _unpack(body)


def inspect(path: str | Path) -> dict | None:
    """Reads the header without a password. Returns None when there is no PhantomPixel data."""
    try:
        head = _read_header(load_array(path)[..., :3].reshape(-1))
    except NoDataError:
        return None
    return {"encrypted": bool(head.flags & FLAG_ENCRYPTED), "stored_bytes": head.length}
