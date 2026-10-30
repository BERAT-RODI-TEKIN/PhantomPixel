"""Constants, format definition and theme."""
from pathlib import Path

APP_NAME = "PhantomPixel"
VERSION = "2.0.0"
TAGLINE = "Hide data inside images. Invisible to the eye."

# --- Container format (v2) ---------------------------------------------------
# Header, written sequentially into the first bits of the image (29 bytes):
#   MAGIC 4B | FLAGS 1B | SALT 16B | LENGTH 4B | CRC32 4B
# The body (optionally AES-256-GCM encrypted) is scattered over the remaining bits.
MAGIC = b"PPX2"
SALT_LEN = 16
HEADER_BYTES = len(MAGIC) + 1 + SALT_LEN + 4 + 4
HEADER_BITS = HEADER_BYTES * 8
FLAG_ENCRYPTED = 0b01

PAYLOAD_OVERHEAD = 3   # kind (1B) + name length (2B)
CRYPTO_OVERHEAD = 28   # AES-GCM nonce (12B) + tag (16B)

# --- Key derivation (scrypt) -------------------------------------------------
KDF_N = 2 ** 14
KDF_R = 8
KDF_P = 1

# --- Paths -------------------------------------------------------------------
WORKSPACE = Path.home() / "PhantomPixel"      # demo files live here
LOSSY_EXTENSIONS = (".jpg", ".jpeg")

# --- Theme -------------------------------------------------------------------
RED = "#ff1744"
DARK_RED = "#b71c1c"
GREY = "#9e9e9e"
RED_RGB = (255, 23, 68)
BG_RGB = (10, 10, 12)
PANEL_RGB = (22, 22, 26)
