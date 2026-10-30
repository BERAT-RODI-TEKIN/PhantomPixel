"""Constants, container formats and theme."""
from dataclasses import dataclass
from pathlib import Path

APP_NAME = "PhantomPixel"
VERSION = "2.1.0"

# --- Container formats --------------------------------------------------------
# Every PhantomPixel version writes its own format and can read its own format
# plus all OLDER ones. Older versions do not know newer magics, so they simply
# report "no data" for images made by a newer version (one-way compatibility):
#
#   v2.0  ->  PPX2   (read by v2.0, v2.1, ...)
#   v2.1  ->  PPX3   (read by v2.1, ...; NOT by v2.0)
#   v2.2  ->  PPX4   (planned: read by v2.2, ...; NOT by v2.1)
#
# Header, written sequentially into the first bits of the image (29 bytes):
#   MAGIC 4B | FLAGS 1B | SALT 16B | LENGTH 4B | CRC32 4B
# The body (optionally compressed, then optionally AES-256-GCM encrypted) is
# scattered over the remaining bits.
SALT_LEN = 16
HEADER_BYTES = 4 + 1 + SALT_LEN + 4 + 4
HEADER_BITS = HEADER_BYTES * 8
MAGIC_PREFIX = b"PPX"

FLAG_ENCRYPTED = 0b01
FLAG_COMPRESSED = 0b10   # PPX3 and newer

PAYLOAD_OVERHEAD = 3     # kind (1B) + name length (2B)
CRYPTO_OVERHEAD = 28     # AES-GCM nonce (12B) + tag (16B)

MAX_PAYLOAD_BYTES = 512 * 1024 * 1024   # also guards against decompression bombs


@dataclass(frozen=True)
class FormatSpec:
    magic: bytes
    app_version: str      # first PhantomPixel version that wrote this format
    kdf_n: int            # scrypt cost
    scatter_tag: bytes    # domain separation for the public (password-less) scatter seed
    bind_header: bool     # header (all but the CRC) is AES-GCM associated data
    compression: bool     # zlib compression supported


FMT_V20 = FormatSpec(b"PPX2", "2.0", 2 ** 14, b"PhantomPixel/scatter/v2", False, False)
FMT_V21 = FormatSpec(b"PPX3", "2.1", 2 ** 15, b"PhantomPixel/scatter/v3", True, True)

WRITE_FORMAT = FMT_V21                                   # what this version writes
READ_FORMATS = {f.magic: f for f in (FMT_V20, FMT_V21)}  # what this version can read

KDF_R = 8
KDF_P = 1

# --- Paths -------------------------------------------------------------------
WORKSPACE = Path.home() / "PhantomPixel"      # demo files and settings live here
SETTINGS_FILE = WORKSPACE / "settings.json"
LOSSY_EXTENSIONS = (".jpg", ".jpeg")

# --- Theme -------------------------------------------------------------------
RED = "#ff1744"
DARK_RED = "#b71c1c"
GREY = "#9e9e9e"
RED_RGB = (255, 23, 68)
BG_RGB = (10, 10, 12)
PANEL_RGB = (22, 22, 26)
