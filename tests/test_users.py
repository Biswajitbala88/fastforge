"""Tests for registration, profile updates, and mass-assignment protection."""


def _signup(client, **overrides):
    payload = {
        "name": "John",
        "email": "john@example.com",
        "password": "password123",
    }
    payload.update(overrides)
    return client.post("/auth/signup", json=payload)


# --- Happy paths ------------------------------------------------------------


def test_signup_succeeds(client):
    resp = _signup(client)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["email"] == "john@example.com"
    assert body["role"] == "user"
    assert body["is_admin"] is False
    assert body["is_superuser"] is False
    assert "hashed_password" not in body
    assert "password" not in body


def test_profile_update_succeeds(client, auth_headers_for):
    _signup(client)
    headers = auth_headers_for("john@example.com")
    resp = client.patch(
        "/users/me", json={"name": "Johnny"}, headers=headers
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["name"] == "Johnny"


def test_password_change_allows_relogin(client, auth_headers_for):
    _signup(client)
    headers = auth_headers_for("john@example.com")
    resp = client.patch(
        "/users/me", json={"password": "newpassword456"}, headers=headers
    )
    assert resp.status_code == 200
    # Old password no longer works; new one does.
    assert (
        client.post(
            "/auth/login",
            data={"username": "john@example.com", "password": "password123"},
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/auth/login",
            data={"username": "john@example.com", "password": "newpassword456"},
        ).status_code
        == 200
    )


# --- Mass-assignment rejection at signup ------------------------------------


def test_signup_rejects_is_admin(client):
    resp = _signup(client, is_admin=True)
    assert resp.status_code == 422


def test_signup_rejects_role(client):
    resp = _signup(client, role="admin")
    assert resp.status_code == 422


def test_signup_rejects_permissions(client):
    resp = _signup(client, permissions=["all"])
    assert resp.status_code == 422


def test_signup_rejects_is_superuser(client):
    resp = _signup(client, is_superuser=True)
    assert resp.status_code == 422


def test_signup_rejects_unknown_field(client):
    resp = _signup(client, hacker="yes")
    assert resp.status_code == 422


# --- Privilege escalation is impossible even when fields are absent ---------


def test_profile_update_rejects_privileged_fields(client, auth_headers_for):
    _signup(client)
    headers = auth_headers_for("john@example.com")
    for field, value in [
        ("is_admin", True),
        ("role", "admin"),
        ("is_superuser", True),
        ("permissions", ["all"]),
    ]:
        resp = client.patch("/users/me", json={field: value}, headers=headers)
        assert resp.status_code == 422, f"{field} should be rejected"

    # And the record remains unprivileged.
    me = client.get("/users/me", headers=headers).json()
    assert me["is_admin"] is False
    assert me["role"] == "user"


# --- Authorization / ownership ----------------------------------------------


def test_unauthenticated_cannot_read_profile(client):
    assert client.get("/users/me").status_code == 401


def test_user_cannot_read_another_users_record(client, auth_headers_for):
    _signup(client)
    _signup(client, email="victim@example.com")
    headers = auth_headers_for("john@example.com")
    # victim is the second user created -> id 2; john is id 1.
    resp = client.get("/users/2", headers=headers)
    assert resp.status_code == 403


def test_user_cannot_use_admin_update_endpoint(client, auth_headers_for):
    _signup(client)
    headers = auth_headers_for("john@example.com")
    resp = client.patch(
        "/users/1", json={"is_admin": True}, headers=headers
    )
    assert resp.status_code == 403
    me = client.get("/users/me", headers=headers).json()
    assert me["is_admin"] is False


def test_user_cannot_list_users(client, auth_headers_for):
    _signup(client)
    headers = auth_headers_for("john@example.com")
    assert client.get("/users", headers=headers).status_code == 403


# --- Admin can perform permitted operations ---------------------------------


def test_admin_can_list_users(client, admin_user, auth_headers_for):
    _signup(client)
    headers = auth_headers_for("admin@example.com")
    resp = client.get("/users", headers=headers)
    assert resp.status_code == 200
    emails = {u["email"] for u in resp.json()}
    assert {"admin@example.com", "john@example.com"} <= emails


def test_admin_can_update_privileged_fields(client, admin_user, auth_headers_for):
    _signup(client)  # creates john as id 2 (admin is id 1)
    headers = auth_headers_for("admin@example.com")
    resp = client.patch(
        "/users/2",
        json={"is_admin": True, "role": "admin"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["is_admin"] is True
    assert body["role"] == "admin"


def test_admin_update_still_rejects_unknown_fields(
    client, admin_user, auth_headers_for
):
    _signup(client)
    headers = auth_headers_for("admin@example.com")
    resp = client.patch(
        "/users/2", json={"password": "hunter2000"}, headers=headers
    )
    # ``password`` is not an admin-editable field in AdminUserUpdate.
    assert resp.status_code == 422


# --- Concurrency: unique-email races ---------------------------------------
#
# Two simultaneous requests can both pass the "is this email taken?" lookup
# before either commits. These tests force that interleaving deterministically
# by making the pre-check miss, so the database's unique index is what catches
# the duplicate. The API must answer 409, never 500.


class _PreCheckMiss:
    """Stands in for ``db.query(User).filter(...)`` and always finds nothing."""

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return None


def _force_precheck_miss(monkeypatch, db_session):
    monkeypatch.setattr(db_session, "query", lambda *a, **k: _PreCheckMiss())


def test_signup_race_returns_409_not_500(client, db_session, monkeypatch):
    assert _signup(client).status_code == 201

    _force_precheck_miss(monkeypatch, db_session)
    resp = _signup(client)
    assert resp.status_code == 409, resp.text
    assert resp.json()["detail"] == "A user with this email already exists"

    # The failed transaction was rolled back; the session is still usable.
    monkeypatch.undo()
    assert _signup(client, email="next@example.com").status_code == 201


def test_profile_email_change_race_returns_409(
    client, db_session, monkeypatch, auth_headers_for
):
    _signup(client)
    _signup(client, email="taken@example.com")
    headers = auth_headers_for("john@example.com")

    _force_precheck_miss(monkeypatch, db_session)
    resp = client.patch(
        "/users/me", json={"email": "taken@example.com"}, headers=headers
    )
    assert resp.status_code == 409, resp.text


def test_admin_email_change_race_returns_409(
    client, db_session, monkeypatch, admin_user, auth_headers_for
):
    target = _signup(client).json()
    headers = auth_headers_for("admin@example.com")

    _force_precheck_miss(monkeypatch, db_session)
    resp = client.patch(
        f"/users/{target['id']}",
        json={"email": "admin@example.com"},
        headers=headers,
    )
    assert resp.status_code == 409, resp.text
