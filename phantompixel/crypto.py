"""Crypto layer: scrypt key derivation + AES-256-GCM."""
import hashlib
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from . import i18n
from .config import KDF_P, KDF_R
from .errors import WrongPasswordError


def derive(password: str, salt: bytes, n: int) -> tuple[bytes, bytes]:
    """Derive two independent values from a password: an AES key and a scatter seed (32B each)."""
    raw = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=n,
        r=KDF_R,
        p=KDF_P,
        maxmem=128 * 1024 * 1024,
        dklen=64,
    )
    return raw[:32], raw[32:]


def encrypt(plaintext: bytes, key: bytes, aad: bytes | None = None) -> bytes:
    """Returns nonce (12B) + ciphertext + authentication tag (16B).

    `aad` is authenticated but not encrypted (PPX3 binds the header to the data with it).
    """
    nonce = os.urandom(12)
    return nonce + AESGCM(key).encrypt(nonce, plaintext, aad)


def decrypt(blob: bytes, key: bytes, aad: bytes | None = None) -> bytes:
    try:
        return AESGCM(key).decrypt(blob[:12], blob[12:], aad)
    except InvalidTag as exc:
        raise WrongPasswordError(i18n.t("err.gcm")) from exc
