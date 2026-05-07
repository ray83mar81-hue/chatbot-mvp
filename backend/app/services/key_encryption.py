"""Symmetric encryption for sensitive secrets stored in the database.

Currently used for tenant-supplied AI provider API keys (Business.ai_api_key).
Format of stored values:

    "enc:v1:<base64_fernet_token>"   → encrypted with the platform secret
    any other non-prefixed string    → legacy plaintext, returned as-is

If `AI_KEY_ENCRYPTION_SECRET` is empty in settings, both encrypt() and
decrypt() are pass-through — keeps dev/staging working out of the box.
Production should set the env var; the startup migration will then
automatically convert existing plaintext keys to the encrypted form.

The Fernet key is derived from the configured secret via SHA-256 + base64
so the operator can pass any string (no need to generate a 32-byte
base64 key by hand).
"""
import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.config import settings

PREFIX = "enc:v1:"


def _fernet() -> Fernet | None:
    secret = (settings.AI_KEY_ENCRYPTION_SECRET or "").strip()
    if not secret:
        return None
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def encrypt(plaintext: str | None) -> str:
    """Return the encrypted form (with prefix) or the input unchanged when
    no secret is configured. Empty input returns "".
    """
    if not plaintext:
        return ""
    if plaintext.startswith(PREFIX):
        return plaintext  # already encrypted — defensive idempotency
    f = _fernet()
    if f is None:
        return plaintext  # secret not configured → store plaintext
    token = f.encrypt(plaintext.encode("utf-8")).decode("ascii")
    return PREFIX + token


def decrypt(stored: str | None) -> str:
    """Resolve a stored value to its plaintext. Handles both encrypted
    (PREFIX + token) and legacy plaintext rows. On failure (corrupted
    token, missing secret for an encrypted value), returns the stored
    value unchanged — caller will see the prefix and detect the issue
    rather than silently using a wrong key.
    """
    if not stored:
        return ""
    if not stored.startswith(PREFIX):
        return stored  # legacy plaintext
    body = stored[len(PREFIX):]
    f = _fernet()
    if f is None:
        return stored  # encrypted but no secret loaded — surface the issue
    try:
        return f.decrypt(body.encode("ascii")).decode("utf-8")
    except InvalidToken:
        return stored  # corrupt token; preserve so admin can rotate
