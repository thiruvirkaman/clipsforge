"""Tests for the auth module: register, login, /me, refresh, logout."""
from app.models.refresh_token import RefreshToken


def test_login_never_stores_raw_refresh_token(client, db, test_user):
    """A DB read leak must not hand over a directly reusable refresh token."""
    response = client.post(
        "/api/v1/auth/login",
        data={"username": test_user.email, "password": "password123"},
    )
    raw_refresh_token = response.json()["refresh_token"]

    stored = db.query(RefreshToken).filter(RefreshToken.user_id == test_user.id).first()
    assert stored is not None
    assert stored.token != raw_refresh_token
    assert len(stored.token) == 64  # sha256 hex digest, not a JWT


def test_register_success(client):
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "new@example.com", "password": "password123", "full_name": "New User"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "new@example.com"
    assert body["full_name"] == "New User"
    assert body["is_active"] is True
    assert body["is_verified"] is False
    assert "hashed_password" not in body


def test_register_duplicate_email(client, test_user):
    response = client.post(
        "/api/v1/auth/register",
        json={"email": test_user.email, "password": "anotherpassword"},
    )
    assert response.status_code == 409
    assert response.json()["code"] == "CONFLICT"


def test_login_success(client, test_user):
    response = client.post(
        "/api/v1/auth/login",
        data={"username": test_user.email, "password": "password123"},
    )
    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert "refresh_token" in body
    assert body["token_type"] == "bearer"


def test_login_wrong_password(client, test_user):
    response = client.post(
        "/api/v1/auth/login",
        data={"username": test_user.email, "password": "wrongpassword"},
    )
    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHORIZED"


def test_login_unknown_email(client):
    response = client.post(
        "/api/v1/auth/login",
        data={"username": "nobody@example.com", "password": "password123"},
    )
    assert response.status_code == 401


def test_me_unauthorized(client):
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401


def test_me_authorized(client, auth_headers, test_user):
    response = client.get("/api/v1/auth/me", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == test_user.email
    assert body["id"] == test_user.id


def test_refresh_flow(client, test_user):
    login_response = client.post(
        "/api/v1/auth/login",
        data={"username": test_user.email, "password": "password123"},
    )
    refresh_token = login_response.json()["refresh_token"]

    refresh_response = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": refresh_token}
    )
    assert refresh_response.status_code == 200
    new_tokens = refresh_response.json()
    assert "access_token" in new_tokens
    assert "refresh_token" in new_tokens
    assert new_tokens["refresh_token"] != refresh_token

    # The new access token should work against /me.
    me_response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {new_tokens['access_token']}"},
    )
    assert me_response.status_code == 200


def test_refresh_rejects_reused_token(client, test_user):
    login_response = client.post(
        "/api/v1/auth/login",
        data={"username": test_user.email, "password": "password123"},
    )
    refresh_token = login_response.json()["refresh_token"]

    first = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert first.status_code == 200

    # Reusing the same (now-rotated/revoked) refresh token should fail.
    second = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert second.status_code == 401


def test_refresh_invalid_token(client):
    response = client.post("/api/v1/auth/refresh", json={"refresh_token": "not-a-real-token"})
    assert response.status_code == 401


def test_logout_revokes_refresh_token(client, test_user, auth_headers):
    login_response = client.post(
        "/api/v1/auth/login",
        data={"username": test_user.email, "password": "password123"},
    )
    refresh_token = login_response.json()["refresh_token"]

    logout_response = client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": refresh_token},
        headers=auth_headers,
    )
    assert logout_response.status_code == 204

    # The revoked refresh token can no longer be exchanged for a new pair.
    refresh_response = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": refresh_token}
    )
    assert refresh_response.status_code == 401


def test_logout_requires_auth(client, test_user):
    login_response = client.post(
        "/api/v1/auth/login",
        data={"username": test_user.email, "password": "password123"},
    )
    refresh_token = login_response.json()["refresh_token"]

    response = client.post("/api/v1/auth/logout", json={"refresh_token": refresh_token})
    assert response.status_code == 401
