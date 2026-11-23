import hashlib
import secrets


def generate_reset_token() -> str:
    """Return a new random, URL-safe password reset token (256 bits)."""
    return secrets.token_urlsafe(32)


def hash_reset_token(token: str) -> str:
    """Hash a reset token for storage/lookup.

    The token is already high-entropy random data, so a fast hash is enough;
    storing only the hash means a leaked database can't be used to reset passwords.
    """
    return hashlib.sha256(token.encode()).hexdigest()
