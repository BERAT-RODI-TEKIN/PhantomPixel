"""LSB steganography core.

The least significant bit (LSB) of every colour channel (R, G, B) carries data.
Changing it moves a colour by at most 1/255, which the eye cannot see.

Layout (see config.py): a 29-byte header is written sequentially at the start,
the body is scattered over the rest of the image by a keyed permutation.
  * The body is zlib-compressed when that makes it smaller (PPX3 and newer).
  * With a password: the body is AES-256-GCM encrypted (PPX3: the header is bound to it
    as associated data) and the permutation is keyed by the password, so the data is
    both unreadable and unlocatable.
  * Without a password: the permutation is keyed by the public salt, which
    spreads the data evenly instead of leaving a stripe at the top.

Versions: this file WRITES the newest format and READS every older one. Images made
by a newer program are recognised and refused with a clear message (never misread).
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
    FLAG_COMPRESSED,
    FLAG_ENCRYPTED,
    HEADER_BITS,
    HEADER_BYTES,
    MAGIC_PREFIX,
    MAX_PAYLOAD_BYTES,
    PAYLOAD_OVERHEAD,
    READ_FORMATS,
    SALT_LEN,
    WRITE_FORMAT,
    FormatSpec,
)
from .errors import (
    CapacityError,
    CorruptedDataError,
    NewerVersionError,
    NoDataError,
    PasswordRequiredError,
    StegoError,
    WrongPasswordError,
)
from .i18n import t
from .utils import human_size

__all__ = ["Payload", "HideResult", "hide", "extract", "inspect", "capacity", "capacity_for",
           "body_capacity_for", "stored_size", "image_size", "load_array", "StegoError"]


@dataclass
class Payload:
    kind: str  # "text" | "file"
    name: str
    data: bytes


@dataclass
class HideResult:
    output: Path
    stored_bytes: int      # bytes written into the image (after compression / encryption)
    capacity_bytes: int    # bytes the image can hold in total
    encrypted: bool
    verified: bool
    compressed: bool = False
    original_bytes: int = 0  # size of the secret before compression

    @property
    def usage(self) -> float:
        return self.stored_bytes / self.capacity_bytes if self.capacity_bytes else 1.0


@dataclass
class _Header:
    spec: FormatSpec
    flags: int
    salt: bytes
    length: int
    crc: int
    aad: bytes  # everything in the header except the CRC (authenticated by PPX3)


# --------------------------------------------------------------------------
# Payload packing
# --------------------------------------------------------------------------
def _pack(p: Payload) -> bytes:
    name = p.name.encode("utf-8")[:65535]
    return bytes([1 if p.kind == "file" else 0]) + struct.pack(">H", len(name)) + name + p.data


def _unpack(raw: bytes) -> Payload:
    if len(raw) < PAYLOAD_OVERHEAD:
        raise CorruptedDataError(t("err.payload_damaged"))
    n = struct.unpack(">H", raw[1:3])[0]
    return Payload("file" if raw[0] else "text", raw[3:3 + n].decode("utf-8", "replace"), raw[3 + n:])


def _compress(packed: bytes) -> tuple[bytes, int]:
    """Returns (body, flags): compressed only when that really saves space."""
    z = zlib.compress(packed, 9)
    return (z, FLAG_COMPRESSED) if len(z) < len(packed) else (packed, 0)


def _inflate(data: bytes) -> bytes:
    """Decompresses with a hard size limit: a tiny malicious image must not expand to gigabytes."""
    d = zlib.decompressobj()
    try:
        out = d.decompress(data, MAX_PAYLOAD_BYTES + 1)
    except zlib.error as exc:
        raise CorruptedDataError(t("err.decompress")) from exc
    if len(out) > MAX_PAYLOAD_BYTES:
        raise CorruptedDataError(t("err.decompress_big", limit=human_size(MAX_PAYLOAD_BYTES)))
    if not d.eof:
        raise CorruptedDataError(t("err.decompress"))
    return out


# --------------------------------------------------------------------------
# Image helpers
# --------------------------------------------------------------------------
def image_size(path: str | Path) -> tuple[int, int]:
    """Width and height without decoding the whole image (fast)."""
    try:
        with Image.open(path) as im:
            return im.size
    except Exception as exc:  # noqa: BLE001
        raise StegoError(t("err.cannot_open", error=exc)) from exc


def _to_rgb_image(img: Image.Image) -> Image.Image:
    """Any Pillow image -> 8-bit RGB / RGBA (transparency of palette and tRNS images is kept)."""
    if img.mode.startswith("I"):   # 16-bit (or 32-bit) greyscale: scale down, do not clip to white
        a = np.array(img).astype(np.int64)
        if img.mode.startswith("I;16") or a.max() > 255:
            a = a >> 8
        img = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "L")
    elif img.mode == "F":
        img = Image.fromarray(np.clip(np.array(img), 0, 255).astype(np.uint8), "L")
    has_alpha = "A" in img.getbands() or "transparency" in img.info
    return img.convert("RGBA" if has_alpha else "RGB")


def load_array(path: str | Path) -> np.ndarray:
    """Loads an image as an RGB / RGBA array (alpha is preserved, EXIF rotation applied)."""
    try:
        img = Image.open(path)
        img.load()
    except Exception as exc:  # noqa: BLE001
        raise StegoError(t("err.cannot_open", error=exc)) from exc
    try:
        img = ImageOps.exif_transpose(img)
    except Exception:  # noqa: BLE001
        pass
    try:
        return np.array(_to_rgb_image(img))
    except Exception as exc:  # noqa: BLE001
        raise StegoError(t("err.cannot_open", error=exc)) from exc


def body_capacity_for(width: int, height: int) -> int:
    """Raw bytes of body (after compression / encryption) that fit into an image of this size."""
    return max(0, (width * height * 3 - HEADER_BITS) // 8)


def capacity_for(width: int, height: int, encrypted: bool = False) -> int:
    """Maximum bytes of INCOMPRESSIBLE user data that fit into an image of this size.

    Compressible data (text, documents, bitmaps) fits more; see stored_size().
    """
    cap = body_capacity_for(width, height) - PAYLOAD_OVERHEAD
    return max(0, cap - (CRYPTO_OVERHEAD if encrypted else 0))


def capacity(path: str | Path, encrypted: bool = False) -> int:
    return capacity_for(*image_size(path), encrypted)


def stored_size(payload: Payload, encrypted: bool = False) -> int:
    """Bytes this secret will occupy inside an image (after compression and encryption)."""
    body, _ = _compress(_pack(payload))
    return len(body) + (CRYPTO_OVERHEAD if encrypted else 0)


# --------------------------------------------------------------------------
# Keyed permutation (memory-light, platform independent)
# --------------------------------------------------------------------------
# A Feistel network over the smallest even-bit domain that covers the image,
# plus "cycle walking" to stay inside the exact domain. It needs O(n) memory for
# n hidden bits (a full np.random.permutation would need 8 bytes per image bit)
# and uses only integer maths, so results are identical on every platform.
# NOTE: this construction is part of every file format. Never change it.
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
        tt = (right + k) * _C1
        tt ^= tt >> np.uint64(29)
        tt = tt * _C2
        tt ^= tt >> np.uint64(32)
        left, right = right, left ^ (tt & mask)
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


def _public_seed(spec: FormatSpec, salt: bytes) -> bytes:
    return hashlib.sha256(spec.scatter_tag + salt).digest()


def _positions(total_bits: int, n_bits: int, seed: bytes) -> np.ndarray:
    """Bit positions of the body (everything after the header)."""
    return HEADER_BITS + _permute(np.arange(n_bits, dtype=np.uint64), total_bits - HEADER_BITS, seed)


def _spec_for(magic: bytes) -> FormatSpec:
    """Maps a header magic to a format this version can read, or explains why it cannot."""
    spec = READ_FORMATS.get(magic)
    if spec is not None:
        return spec
    # PPX<c> with a character after the newest one we know = made by a newer PhantomPixel
    if magic[:3] == MAGIC_PREFIX and magic[3:4].isalnum() and magic[3] > WRITE_FORMAT.magic[3]:
        raise NewerVersionError(t("err.newer", magic=magic.decode("ascii")))
    raise NoDataError(t("err.no_data"))


def _read_header(flat: np.ndarray) -> _Header:
    if flat.size < HEADER_BITS:
        raise NoDataError(t("err.too_small"))
    raw = np.packbits(flat[:HEADER_BITS] & 1).tobytes()
    spec = _spec_for(raw[:4])
    length, crc = struct.unpack(">II", raw[5 + SALT_LEN:HEADER_BYTES])
    return _Header(spec, raw[4], raw[5:5 + SALT_LEN], length, crc, raw[:HEADER_BYTES - 4])


# --------------------------------------------------------------------------
# Public operations
# --------------------------------------------------------------------------
def hide(cover: str | Path, payload: Payload, output: str | Path,
         password: str | None = None, verify: bool = True) -> HideResult:
    out = Path(output)
    if out.exists() and out.resolve() == Path(cover).resolve():
        raise StegoError(t("err.overwrite_cover"))

    spec = WRITE_FORMAT
    arr = load_array(cover)
    rgb = arr[..., :3].copy()
    flat = rgb.reshape(-1)  # rgb is C-contiguous, so this is a view: writing to flat changes rgb

    packed = _pack(payload)
    if len(packed) > MAX_PAYLOAD_BYTES:
        raise CapacityError(t("err.payload_too_large", limit=human_size(MAX_PAYLOAD_BYTES)))
    body, flags = _compress(packed)
    compressed = bool(flags & FLAG_COMPRESSED)
    salt = os.urandom(SALT_LEN)
    if password:
        flags |= FLAG_ENCRYPTED
        stored_len = len(body) + CRYPTO_OVERHEAD
    else:
        stored_len = len(body)

    if HEADER_BITS + stored_len * 8 > flat.size:
        h, w = arr.shape[:2]
        raise CapacityError(t("err.capacity", need=f"{stored_len:,}",
                              cap=f"{capacity_for(w, h, bool(password)):,}"))

    head_no_crc = spec.magic + bytes([flags]) + salt + struct.pack(">I", stored_len)
    if password:
        key, seed = crypto.derive(password, salt, spec.kdf_n)
        body = crypto.encrypt(body, key, head_no_crc if spec.bind_header else None)
    else:
        seed = _public_seed(spec, salt)
    assert len(body) == stored_len

    header = head_no_crc + struct.pack(">I", zlib.crc32(body))
    flat[:HEADER_BITS] = (flat[:HEADER_BITS] & 0xFE) | np.unpackbits(np.frombuffer(header, np.uint8))
    pos = _positions(flat.size, len(body) * 8, seed)
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
            raise StegoError(t("err.selfcheck_fail", error=exc)) from exc
        if not ok:
            out.unlink(missing_ok=True)
            raise StegoError(t("err.selfcheck_mismatch"))

    h, w = arr.shape[:2]
    return HideResult(out, len(body), body_capacity_for(w, h), bool(password), verify,
                      compressed, len(packed))


def extract(stego: str | Path, password: str | None = None) -> Payload:
    flat = load_array(stego)[..., :3].reshape(-1)
    head = _read_header(flat)
    spec = head.spec
    if spec.compression and head.flags & ~(FLAG_ENCRYPTED | FLAG_COMPRESSED):
        raise CorruptedDataError(t("err.unknown_flags"))
    if head.length * 8 > flat.size - HEADER_BITS:
        raise CorruptedDataError(t("err.header_damaged"))

    encrypted = bool(head.flags & FLAG_ENCRYPTED)
    if encrypted:
        if not password:
            raise PasswordRequiredError(t("err.pw_required"))
        key, seed = crypto.derive(password, head.salt, spec.kdf_n)
    else:
        seed = _public_seed(spec, head.salt)

    pos = _positions(flat.size, head.length * 8, seed)
    body = np.packbits(flat[pos] & 1).tobytes()

    if zlib.crc32(body) != head.crc:
        raise (WrongPasswordError(t("err.wrong_pw")) if encrypted
               else CorruptedDataError(t("err.corrupted")))
    if encrypted:
        body = crypto.decrypt(body, key, head.aad if spec.bind_header else None)
    if spec.compression and head.flags & FLAG_COMPRESSED:
        body = _inflate(body)
    return _unpack(body)


def inspect(path: str | Path) -> dict | None:
    """Reads the header without a password. Returns None when there is no PhantomPixel data.

    Raises NewerVersionError when the image was made by a newer PhantomPixel.
    """
    try:
        head = _read_header(load_array(path)[..., :3].reshape(-1))
    except NoDataError:
        return None
    return {
        "encrypted": bool(head.flags & FLAG_ENCRYPTED),
        "compressed": bool(head.spec.compression and head.flags & FLAG_COMPRESSED),
        "stored_bytes": head.length,
        "version": head.spec.app_version,
    }
