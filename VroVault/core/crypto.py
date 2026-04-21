"""
VroVault - Cryptographic Engine
AES-256-GCM authenticated encryption + Argon2id key derivation.
Zero plaintext persistence.
"""

import os
import base64
import secrets
import string
from typing import Tuple, Optional

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
from argon2.low_level import hash_secret_raw, Type

KEY_LEN            = 32
NONCE_LEN          = 12
SALT_LEN           = 32
TAG_LEN            = 16
ARGON2_TIME_COST   = 3
ARGON2_MEMORY_COST = 65536
ARGON2_PARALLELISM = 4
ARGON2_HASH_LEN    = KEY_LEN
ARGON2_TYPE        = Type.ID
VERIFY_MAGIC       = b"VROVAULT_OK_v1"


def derive_key(master_password: str, salt: bytes) -> bytes:
    """Derives 256-bit key from master password using Argon2id."""
    if not isinstance(master_password, str) or not master_password:
        raise ValueError("Master password must be a non-empty string.")
    if len(salt) != SALT_LEN:
        raise ValueError(f"Salt must be {SALT_LEN} bytes.")
    return hash_secret_raw(
        secret=master_password.encode("utf-8"),
        salt=salt,
        time_cost=ARGON2_TIME_COST,
        memory_cost=ARGON2_MEMORY_COST,
        parallelism=ARGON2_PARALLELISM,
        hash_len=ARGON2_HASH_LEN,
        type=ARGON2_TYPE,
    )


def generate_salt() -> bytes:
    return secrets.token_bytes(SALT_LEN)


def encrypt(plaintext: bytes, key: bytes) -> bytes:
    """AES-256-GCM encryption. Returns nonce||ciphertext+tag."""
    nonce  = secrets.token_bytes(NONCE_LEN)
    aesgcm = AESGCM(key)
    return nonce + aesgcm.encrypt(nonce, plaintext, None)


def decrypt(blob: bytes, key: bytes) -> bytes:
    """AES-256-GCM decryption. Raises InvalidTag on wrong key/tampering."""
    if len(blob) < NONCE_LEN + TAG_LEN:
        raise ValueError("Blob too short.")
    nonce  = blob[:NONCE_LEN]
    ct     = blob[NONCE_LEN:]
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ct, None)


def encrypt_str(plaintext: str, key: bytes) -> str:
    return base64.b64encode(encrypt(plaintext.encode("utf-8"), key)).decode("ascii")


def decrypt_str(b64_blob: str, key: bytes) -> str:
    return decrypt(base64.b64decode(b64_blob.encode("ascii")), key).decode("utf-8")


def create_verification_token(key: bytes) -> str:
    return base64.b64encode(encrypt(VERIFY_MAGIC, key)).decode("ascii")


def verify_key(key: bytes, token: str) -> bool:
    try:
        blob = base64.b64decode(token.encode("ascii"))
        return decrypt(blob, key) == VERIFY_MAGIC
    except Exception:
        return False


def hash_pin(pin: str, salt: bytes) -> str:
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt,
                      iterations=260_000, backend=default_backend())
    return base64.b64encode(kdf.derive(pin.encode("utf-8"))).decode("ascii")


def verify_pin(pin: str, salt: bytes, stored_hash: str) -> bool:
    try:
        return hash_pin(pin, salt) == stored_hash
    except Exception:
        return False


def generate_secure_password(
    length: int = 20,
    use_upper: bool = True,
    use_lower: bool = True,
    use_digits: bool = True,
    use_symbols: bool = True,
    exclude_ambiguous: bool = False,
) -> str:
    """Cryptographically secure password generator with guaranteed class coverage."""
    if length < 8:
        raise ValueError("Password length must be at least 8.")

    upper_chars  = "ABCDEFGHJKLMNPQRSTUVWXYZ" if exclude_ambiguous else string.ascii_uppercase
    lower_chars  = "abcdefghjkmnpqrstuvwxyz"  if exclude_ambiguous else string.ascii_lowercase
    digit_chars  = "23456789"                  if exclude_ambiguous else string.digits
    symbol_chars = "!@#$%^&*()-_=+[]{}|;:,.<>?"

    charset  = ""
    required = []
    for enabled, chars in [(use_upper, upper_chars), (use_lower, lower_chars),
                            (use_digits, digit_chars), (use_symbols, symbol_chars)]:
        if enabled:
            charset += chars
            required.append(secrets.choice(chars))

    if not charset:
        raise ValueError("At least one character class must be enabled.")

    pool  = required + [secrets.choice(charset) for _ in range(length - len(required))]
    for i in range(len(pool) - 1, 0, -1):
        j = secrets.randbelow(i + 1)
        pool[i], pool[j] = pool[j], pool[i]
    return "".join(pool)
