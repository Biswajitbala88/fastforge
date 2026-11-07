from datetime import timedelta
import jwt
import pytest

from app.core.config import settings
from app.core.security.jwt import create_access_token, decode_access_token
from app.core.security.password import (
    check_password_rehash,
    hash_password,
    verify_password,
)


def test_hash_password_uses_argon2id():
    password = "TestPassword@123"
    hashed = hash_password(password)

    # Argon2id hashes start with $argon2id$
    assert hashed.startswith("$argon2id$")
    assert hashed != password


def test_verify_password():
    password = "CorrectHorseBatteryStaple"
    hashed = hash_password(password)

    assert verify_password(password, hashed) is True
    assert verify_password("WrongPassword", hashed) is False
    assert verify_password("", hashed) is False


def test_check_password_rehash():
    password = "RehashCheckPassword"
    hashed = hash_password(password)

    # A newly created hash with current parameters should not need rehash
    assert check_password_rehash(hashed) is False


def test_jwt_create_and_decode():
    sub = "user-12345"
    token = create_access_token(subject=sub, expires_delta=timedelta(minutes=15))

    payload = decode_access_token(token)
    assert payload["sub"] == sub
    assert "exp" in payload
    assert "iat" in payload


def test_jwt_expired_token():
    token = create_access_token(subject="user-123", expires_delta=timedelta(seconds=-10))

    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(token)


def test_jwt_invalid_token():
    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token("not-a-valid-jwt-token")
