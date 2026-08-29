"""Shared pytest fixtures for ClipForge backend tests.

Sets required settings via environment variables (so `app.config.settings`
can be instantiated without a real `.env`) before any `app.*` module is
imported. Binds the real `app.main.app` singleton (all routers wired, same
as production) to an in-memory SQLite database (via a `get_db` override)
and exposes `db` / `test_user` / `other_user` / `auth_headers` /
`other_user_auth_headers` / `client` fixtures for use across test modules.
"""
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("ASR_SERVICE_BASE_URL", "")
os.environ.setdefault("ASR_SERVICE_API_KEY", "")
os.environ.setdefault("LLM_SERVICE_API_KEY", "")
os.environ.setdefault("MEDIA_STORAGE_PATH", "./test_media")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.jwt import create_access_token, hash_password
from app.database import Base, get_db
from app.main import app
from app.models import User

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _override_get_db():
    db_session = TestingSessionLocal()
    try:
        yield db_session
    finally:
        db_session.close()


app.dependency_overrides[get_db] = _override_get_db


@pytest.fixture()
def db():
    """A fresh in-memory SQLite session, tables created/dropped per test."""
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def test_user(db) -> User:
    user = User(
        email="test@example.com",
        hashed_password=hash_password("password123"),
        full_name="Test User",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture()
def other_user(db) -> User:
    user = User(
        email="other@example.com",
        hashed_password=hash_password("password123"),
        full_name="Other User",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture()
def auth_headers(test_user) -> dict[str, str]:
    token = create_access_token({"sub": str(test_user.id)})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def other_user_auth_headers(other_user) -> dict[str, str]:
    token = create_access_token({"sub": str(other_user.id)})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def client(db):
    """TestClient bound to the same in-memory DB as the `db` fixture.

    Depends on `db` (even when a test doesn't use it directly) so tables are
    always created before requests hit the app -- otherwise tests that only
    request `client` (no `test_user`) hit "no such table" errors.
    """
    with TestClient(app) as c:
        yield c
