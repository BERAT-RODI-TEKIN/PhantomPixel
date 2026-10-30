"""Crypto layer: scrypt key derivation + AES-256-GCM."""
import hashlib
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .config import KDF_N, KDF_P, KDF_R
from .errors import WrongPasswordError


def derive(password: str, salt: bytes) -> tuple[bytes, bytes]:
    """Derive two independent values from a password: an AES key and a scatter seed (32B each)."""
    raw = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=KDF_N,
        r=KDF_R,
        p=KDF_P,
        maxmem=64 * 1024 * 1024,
        dklen=64,
    )
    return raw[:32], raw[32:]


def encrypt(plaintext: bytes, key: bytes) -> bytes:
    """Returns nonce (12B) + ciphertext + authentication tag (16B)."""
    nonce = os.urandom(12)
    return nonce + AESGCM(key).encrypt(nonce, plaintext, None)


def decrypt(blob: bytes, key: bytes) -> bytes:
    try:
        return AESGCM(key).decrypt(blob[:12], blob[12:], None)
    except InvalidTag as exc:
        raise WrongPasswordError("Wrong password, or the data was modified.") from exc
