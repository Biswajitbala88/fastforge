import sqlite3
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_db
from app.core.config import settings
from app.core.security.reset_token import hash_reset_token
from app.db.database import create_tables
from app.main import app

EMAIL = "reset@example.com"
OLD_PASSWORD = "OldPassword123!"
NEW_PASSWORD = "NewPassword456!"


@pytest.fixture
def test_db():
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    create_tables(conn)
    yield conn
    conn.close()


@pytest.fixture
def client(test_db):
    def override_get_db():
        yield test_db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def debug_mode(monkeypatch):
    monkeypatch.setattr(settings, "debug", True)


@pytest.fixture
def registered_user(client):
    response = client.post(
        "/auth/register", json={"email": EMAIL, "password": OLD_PASSWORD}
    )
    assert response.status_code == 201
    return response.json()


def _request_token(client) -> str:
    response = client.post("/auth/forgot-password", json={"email": EMAIL})
    assert response.status_code == 200
    return response.json()["reset_token"]


def _login(client, password):
    return client.post("/auth/login", json={"email": EMAIL, "password": password})


def test_full_reset_flow(client, registered_user, debug_mode):
    token = _request_token(client)

    response = client.post(
        "/auth/reset-password", json={"token": token, "new_password": NEW_PASSWORD}
    )
    assert response.status_code == 200
    assert response.json()["message"] == "Password has been reset successfully."

    assert _login(client, OLD_PASSWORD).status_code == 401
    assert _login(client, NEW_PASSWORD).status_code == 200


def test_forgot_password_same_response_for_unknown_email(client, registered_user):
    known = client.post("/auth/forgot-password", json={"email": EMAIL})
    unknown = client.post("/auth/forgot-password", json={"email": "nobody@example.com"})
    assert known.status_code == unknown.status_code == 200
    assert known.json() == unknown.json()


def test_token_not_returned_when_debug_off(client, registered_user, monkeypatch):
    monkeypatch.setattr(settings, "debug", False)
    response = client.post("/auth/forgot-password", json={"email": EMAIL})
    assert response.status_code == 200
    assert "reset_token" not in response.json()


def test_reset_link_is_logged(client, registered_user, debug_mode, caplog):
    with caplog.at_level("WARNING", logger="app.email"):
        token = _request_token(client)
    assert f"{settings.password_reset_url}?token={token}" in caplog.text


def test_only_token_hash_is_stored(client, registered_user, debug_mode, test_db):
    token = _request_token(client)
    rows = test_db.execute("SELECT token_hash FROM password_reset_tokens").fetchall()
    assert [r["token_hash"] for r in rows] == [hash_reset_token(token)]


def test_token_cannot_be_reused(client, registered_user, debug_mode):
    token = _request_token(client)
    first = client.post(
        "/auth/reset-password", json={"token": token, "new_password": NEW_PASSWORD}
    )
    second = client.post(
        "/auth/reset-password", json={"token": token, "new_password": "Another789!"}
    )
    assert first.status_code == 200
    assert second.status_code == 400
    assert second.json()["detail"] == "Invalid or expired reset token"
    assert _login(client, NEW_PASSWORD).status_code == 200


def test_new_request_invalidates_previous_token(client, registered_user, debug_mode):
    old_token = _request_token(client)
    new_token = _request_token(client)

    response = client.post(
        "/auth/reset-password", json={"token": old_token, "new_password": NEW_PASSWORD}
    )
    assert response.status_code == 400

    response = client.post(
        "/auth/reset-password", json={"token": new_token, "new_password": NEW_PASSWORD}
    )
    assert response.status_code == 200


def test_expired_token_rejected(client, registered_user, debug_mode, test_db):
    token = _request_token(client)
    past = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    with test_db:
        test_db.execute("UPDATE password_reset_tokens SET expires_at = ?", (past,))

    response = client.post(
        "/auth/reset-password", json={"token": token, "new_password": NEW_PASSWORD}
    )
    assert response.status_code == 400
    assert _login(client, OLD_PASSWORD).status_code == 200


def test_invalid_token_rejected(client, registered_user):
    response = client.post(
        "/auth/reset-password",
        json={"token": "not-a-real-token", "new_password": NEW_PASSWORD},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid or expired reset token"


def test_new_password_too_short(client, registered_user, debug_mode):
    token = _request_token(client)
    response = client.post(
        "/auth/reset-password", json={"token": token, "new_password": "short"}
    )
    assert response.status_code == 422


def test_inactive_user_gets_no_token(client, registered_user, debug_mode, test_db):
    with test_db:
        test_db.execute("UPDATE users SET is_active = 0 WHERE email = ?", (EMAIL,))
    response = client.post("/auth/forgot-password", json={"email": EMAIL})
    assert response.status_code == 200
    assert "reset_token" not in response.json()
    count = test_db.execute("SELECT COUNT(*) FROM password_reset_tokens").fetchone()[0]
    assert count == 0
