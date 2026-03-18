"""Integration tests for API middleware (correlation ID and rate limiting)."""

import os

import pytest

from presentation.api.routers import partner as partner_module


class TestCorrelationIdMiddleware:
    """Tests for the CorrelationIdMiddleware."""

    async def test_response_has_x_request_id(self, client):
        """Every response includes an X-Request-Id header."""
        resp = await client.get("/api/health")
        assert resp.status_code == 200
        assert "x-request-id" in resp.headers
        assert len(resp.headers["x-request-id"]) > 0

    async def test_preserves_incoming_request_id(self, client):
        """Middleware preserves an incoming X-Request-Id header."""
        custom_id = "test-correlation-12345"
        resp = await client.get(
            "/api/health",
            headers={"X-Request-Id": custom_id},
        )
        assert resp.status_code == 200
        assert resp.headers["x-request-id"] == custom_id

    async def test_generates_unique_ids(self, client):
        """Each request without an incoming X-Request-Id gets a unique ID."""
        resp1 = await client.get("/api/health")
        resp2 = await client.get("/api/health")
        id1 = resp1.headers["x-request-id"]
        id2 = resp2.headers["x-request-id"]
        assert id1 != id2


class TestRateLimitMiddleware:
    """Tests for the RateLimitMiddleware.

    The conftest sets RATE_LIMIT_RPM=100000 and RATE_LIMIT_BURST=10000 to
    prevent rate limiting during normal tests. This test class creates a
    separate client with low limits to test the 429 behaviour.
    """

    async def test_rate_limit_returns_429(self):
        """Middleware returns 429 after exceeding the burst limit."""
        from httpx import AsyncClient, ASGITransport
        from presentation.api.middleware.rate_limit import RateLimitMiddleware, _TokenBucket

        # Create a minimal FastAPI app with a very low rate limit
        from fastapi import FastAPI

        test_app = FastAPI()

        @test_app.get("/api/test")
        async def test_endpoint():
            return {"ok": True}

        @test_app.get("/api/health")
        async def health():
            return {"status": "healthy"}

        # Add rate limit middleware with a burst of 2
        middleware = RateLimitMiddleware(test_app)
        middleware._rpm = 60
        middleware._burst = 2
        middleware._refill_rate = 1.0  # 1 token/sec

        transport = ASGITransport(app=middleware)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            # First 2 requests should succeed (burst = 2)
            resp1 = await ac.get("/api/test")
            assert resp1.status_code == 200

            resp2 = await ac.get("/api/test")
            assert resp2.status_code == 200

            # Third request should be rate-limited
            resp3 = await ac.get("/api/test")
            assert resp3.status_code == 429
            assert "retry-after" in resp3.headers

    async def test_health_endpoint_exempt_from_rate_limit(self):
        """The /api/health endpoint is exempt from rate limiting."""
        from httpx import AsyncClient, ASGITransport
        from presentation.api.middleware.rate_limit import RateLimitMiddleware

        from fastapi import FastAPI

        test_app = FastAPI()

        @test_app.get("/api/health")
        async def health():
            return {"status": "healthy"}

        @test_app.get("/api/test")
        async def test_endpoint():
            return {"ok": True}

        middleware = RateLimitMiddleware(test_app)
        middleware._rpm = 60
        middleware._burst = 1
        middleware._refill_rate = 1.0

        transport = ASGITransport(app=middleware)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            # Use up the single burst token
            resp = await ac.get("/api/test")
            assert resp.status_code == 200

            # Health endpoint should still work even though rate limit is exhausted
            for _ in range(5):
                resp = await ac.get("/api/health")
                assert resp.status_code == 200
