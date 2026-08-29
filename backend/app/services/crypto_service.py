"""Symmetric encryption helpers for at-rest secrets (OAuth access/refresh tokens).

Uses Fernet (AES-128-CBC + HMAC) from the `cryptography` package. The Fernet
key is derived from `settings.SECRET_KEY` via SHA-256 + base64url-encoding.
This is a pragmatic derivation reusing the app's existing JWT signing secret
so no new secret needs to be provisioned for this pass -- it is NOT a
dedicated encryption key. If this module ever needs independent key
rotation, introduce a separate `ENCRYPTION_KEY` setting instead.
"""
import base64
import hashlib
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from app.config import settings
from app.exceptions import AppException


class TokenDecryptionError(AppException):
    """Raised when a stored token cannot be decrypted (corrupt or wrong key)."""

    def __init__(self) -> None:
        super().__init__("Failed to decrypt stored token", "DECRYPTION_ERROR", 500)


@lru_cache(maxsize=1)
def _get_fernet() -> Fernet:
    """Build (and cache) the Fernet cipher from the derived key material."""
    digest = hashlib.sha256(settings.SECRET_KEY.encode("utf-8")).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def encrypt_token(plain: str) -> str:
    """Encrypt a plaintext token (e.g. an OAuth access/refresh token) for storage."""
    return _get_fernet().encrypt(plain.encode("utf-8")).decode("utf-8")


def decrypt_token(token: str) -> str:
    """Decrypt a token previously produced by `encrypt_token`.

    Raises:
        TokenDecryptionError: If the ciphertext is invalid or was encrypted
            with a different key.
    """
    try:
        return _get_fernet().decrypt(token.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise TokenDecryptionError() from exc
