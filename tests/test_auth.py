import sqlite3
import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_db
from app.core.security.jwt import create_access_token
from app.main import app


@pytest.fixture
def test_db():
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    with conn:
        conn.execute(
            """
            CREATE TABLE users (
                id TEXT PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                hashed_password TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            );
            """
        )
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


def test_register_user_success(client: TestClient, test_db: sqlite3.Connection):
    response = client.post(
        "/auth/register",
        json={"email": "alice@example.com", "password": "SecurePassword123!"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "alice@example.com"
    assert data["is_active"] is True
    assert "id" in data
    assert "created_at" in data
    assert "password" not in data

    # Verify that password stored in DB is hashed using Argon2id
    cursor = test_db.execute(
        "SELECT hashed_password FROM users WHERE email = ?",
        ("alice@example.com",),
    )
    row = cursor.fetchone()
    assert row is not None
    assert row["hashed_password"].startswith("$argon2id$")


def test_register_duplicate_email(client: TestClient):
    client.post(
        "/auth/register",
        json={"email": "duplicate@example.com", "password": "Password123!"},
    )
    response = client.post(
        "/auth/register",
        json={"email": "duplicate@example.com", "password": "AnotherPassword123!"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Email already registered"


def test_register_password_too_short(client: TestClient):
    response = client.post(
        "/auth/register",
        json={"email": "short@example.com", "password": "short"},
    )
    assert response.status_code == 422


def test_login_json_success(client: TestClient):
    # Register first
    client.post(
        "/auth/register",
        json={"email": "bob@example.com", "password": "MySuperSecretPassword1"},
    )

    # Login
    response = client.post(
        "/auth/login",
        json={"email": "bob@example.com", "password": "MySuperSecretPassword1"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_json_wrong_password(client: TestClient):
    client.post(
        "/auth/register",
        json={"email": "charlie@example.com", "password": "CorrectPassword1"},
    )
    response = client.post(
        "/auth/login",
        json={"email": "charlie@example.com", "password": "WrongPassword2"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect email or password"


def test_login_json_nonexistent_user(client: TestClient):
    response = client.post(
        "/auth/login",
        json={"email": "nobody@example.com", "password": "Password123"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect email or password"


def test_login_oauth2_form_token(client: TestClient):
    client.post(
        "/auth/register",
        json={"email": "oauth@example.com", "password": "OAuthPassword123"},
    )

    response = client.post(
        "/auth/token",
        data={"username": "oauth@example.com", "password": "OAuthPassword123"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_oauth2_form_invalid_credentials(client: TestClient):
    response = client.post(
        "/auth/token",
        data={"username": "wrong@example.com", "password": "wrongpassword"},
    )
    assert response.status_code == 401


def test_auth_me_protected_route(client: TestClient):
    reg = client.post(
        "/auth/register",
        json={"email": "me@example.com", "password": "MyPassword123!"},
    )
    user_id = reg.json()["id"]

    login_res = client.post(
        "/auth/login",
        json={"email": "me@example.com", "password": "MyPassword123!"},
    )
    token = login_res.json()["access_token"]

    # Valid token
    me_res = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_res.status_code == 200
    data = me_res.json()
    assert data["id"] == user_id
    assert data["email"] == "me@example.com"
    assert data["is_active"] is True


def test_auth_me_missing_token(client: TestClient):
    response = client.get("/auth/me")
    assert response.status_code == 401


def test_auth_me_invalid_token(client: TestClient):
    response = client.get(
        "/auth/me",
        headers={"Authorization": "Bearer invalid.token.value"},
    )
    assert response.status_code == 401


def test_inactive_user_cannot_login(client: TestClient, test_db: sqlite3.Connection):
    client.post(
        "/auth/register",
        json={"email": "inactive@example.com", "password": "Password123!"},
    )
    with test_db:
        test_db.execute(
            "UPDATE users SET is_active = 0 WHERE email = ?",
            ("inactive@example.com",),
        )

    response = client.post(
        "/auth/login",
        json={"email": "inactive@example.com", "password": "Password123!"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Inactive user"


def test_inactive_user_cannot_access_me(client: TestClient, test_db: sqlite3.Connection):
    reg = client.post(
        "/auth/register",
        json={"email": "inactive_token@example.com", "password": "Password123!"},
    )
    user_id = reg.json()["id"]
    token = create_access_token(subject=user_id)

    with test_db:
        test_db.execute(
            "UPDATE users SET is_active = 0 WHERE id = ?",
            (user_id,),
        )

    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Inactive user"
