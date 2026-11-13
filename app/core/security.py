"""Password hashing and stateless auth-token helpers (standard library only)."""

import hashlib
import hmac
import os
import time

from app.core.config import settings

# --- Password hashing -------------------------------------------------------
#
# Uses PBKDF2-HMAC-SHA256 from the standard library so no third-party crypto
# dependency is required. Stored format: ``pbkdf2_sha256$<iterations>$<salt_hex>$<hash_hex>``.

_ALGORITHM = "pbkdf2_sha256"
_ITERATIONS = 240_000
_SALT_BYTES = 16


def hash_password(password: str) -> str:
    """Return a salted PBKDF2 hash string for ``password``."""
    salt = os.urandom(_SALT_BYTES)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, _ITERATIONS
    )
    return f"{_ALGORITHM}${_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """Verify ``password`` against a previously stored hash string."""
    try:
        algorithm, iterations, salt_hex, hash_hex = stored.split("$")
    except ValueError:
        return False
    if algorithm != _ALGORITHM:
        return False
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(iterations)
    )
    return hmac.compare_digest(digest.hex(), hash_hex)


# --- Auth tokens ------------------------------------------------------------
#
# Stateless HMAC-signed tokens of the form ``<user_id>.<issued_at>.<signature>``.
# No JWT library needed; the signature binds the user id and issue time to the
# server secret.

_TOKEN_TTL_SECONDS = 60 * 60 * 24  # 24 hours


def _sign(message: str) -> str:
    return hmac.new(
        settings.secret_key.encode("utf-8"), message.encode("utf-8"), hashlib.sha256
    ).hexdigest()


def create_access_token(user_id: int) -> str:
    """Create a signed access token for ``user_id``."""
    issued_at = str(int(time.time()))
    message = f"{user_id}.{issued_at}"
    return f"{message}.{_sign(message)}"


def verify_access_token(token: str) -> int | None:
    """Return the user id encoded in ``token`` if valid and unexpired, else None."""
    try:
        user_id_str, issued_at_str, signature = token.split(".")
    except ValueError:
        return None
    message = f"{user_id_str}.{issued_at_str}"
    if not hmac.compare_digest(_sign(message), signature):
        return None
    try:
        issued_at = int(issued_at_str)
        user_id = int(user_id_str)
    except ValueError:
        return None
    if int(time.time()) - issued_at > _TOKEN_TTL_SECONDS:
        return None
    return user_id
