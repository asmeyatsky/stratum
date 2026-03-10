"""Integration tests for /api/auth endpoints."""

import pytest


class TestAuthLogin:
    """Tests for POST /api/auth/login."""

    async def test_login_returns_access_token(self, client):
        """POST /api/auth/login with valid credentials returns an access token."""
        resp = await client.post(
            "/api/auth/login",
            json={"email": "test@example.com", "password": "secret"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert isinstance(data["access_token"], str)
        assert len(data["access_token"]) > 0
        assert data["token_type"] == "bearer"
        assert data["expires_in"] > 0

    async def test_login_empty_body_returns_422(self, client):
        """POST /api/auth/login with empty body returns 422 validation error."""
        resp = await client.post("/api/auth/login", json={})
        assert resp.status_code == 422

    async def test_login_missing_password_returns_422(self, client):
        """POST /api/auth/login with missing password returns 422."""
        resp = await client.post(
            "/api/auth/login",
            json={"email": "test@example.com"},
        )
        assert resp.status_code == 422

    async def test_login_missing_email_returns_422(self, client):
        """POST /api/auth/login with missing email returns 422."""
        resp = await client.post(
            "/api/auth/login",
            json={"password": "secret"},
        )
        assert resp.status_code == 422


class TestAuthMe:
    """Tests for GET /api/auth/me."""

    async def test_me_returns_user_info_dev_mode(self, client, auth_headers):
        """GET /api/auth/me returns user info in dev mode (no API key required)."""
        resp = await client.get("/api/auth/me", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "user_id" in data
        assert "email" in data
        assert "name" in data
        assert "role" in data
        assert isinstance(data["user_id"], str)
        assert isinstance(data["email"], str)
