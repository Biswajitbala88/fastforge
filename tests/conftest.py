"""Shared test fixtures: an isolated in-memory database and API client."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_current_user
from app.core.database import Base, get_db
from app.core.security import hash_password
from app.main import app
from app.models.user import User


@pytest.fixture()
def db_session():
    """A fresh in-memory SQLite database for each test."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(db_session):
    """TestClient whose get_db dependency is bound to the test database."""

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def _make_user(db_session, *, email, password="password123", is_admin=False):
    user = User(
        name="Seed User",
        email=email,
        hashed_password=hash_password(password),
        role="admin" if is_admin else "user",
        is_admin=is_admin,
        is_superuser=False,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def admin_user(db_session):
    return _make_user(db_session, email="admin@example.com", is_admin=True)


def _auth_headers(client, email, password="password123"):
    resp = client.post(
        "/auth/login", data={"username": email, "password": password}
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.fixture()
def auth_headers_for(client):
    """Factory returning auth headers for a given email/password."""
    return lambda email, password="password123": _auth_headers(
        client, email, password
    )
