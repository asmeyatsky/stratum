"""Integration tests for the /api/health endpoint."""

import pytest


class TestHealthEndpoint:
    """Tests for GET /api/health."""

    async def test_health_returns_200(self, client):
        """GET /api/health returns 200 OK."""
        resp = await client.get("/api/health")
        assert resp.status_code == 200

    async def test_health_has_status_healthy(self, client):
        """Health response contains status='healthy'."""
        resp = await client.get("/api/health")
        data = resp.json()
        assert data["status"] == "healthy"

    async def test_health_has_version(self, client):
        """Health response contains a version string."""
        resp = await client.get("/api/health")
        data = resp.json()
        assert "version" in data
        assert isinstance(data["version"], str)
        assert len(data["version"]) > 0

    async def test_health_has_timestamp(self, client):
        """Health response contains an ISO-8601 timestamp."""
        resp = await client.get("/api/health")
        data = resp.json()
        assert "timestamp" in data
        assert isinstance(data["timestamp"], str)
        # Basic ISO-8601 format check
        assert "T" in data["timestamp"] or "-" in data["timestamp"]
