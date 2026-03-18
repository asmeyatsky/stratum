"""Integration tests for /api/billing endpoints."""

import pytest


class TestListPlans:
    """Tests for GET /api/billing/plans."""

    async def test_plans_returns_200(self, client):
        """GET /api/billing/plans returns 200."""
        resp = await client.get("/api/billing/plans")
        assert resp.status_code == 200

    async def test_plans_returns_list(self, client):
        """Response contains a 'plans' list."""
        resp = await client.get("/api/billing/plans")
        data = resp.json()
        assert "plans" in data
        assert isinstance(data["plans"], list)
        assert len(data["plans"]) > 0

    async def test_plans_have_correct_structure(self, client):
        """Each plan has required fields."""
        resp = await client.get("/api/billing/plans")
        plans = resp.json()["plans"]
        for plan in plans:
            assert "plan_id" in plan
            assert "name" in plan
            assert "price_cents" in plan
            assert "currency" in plan
            assert "billing_period" in plan
            assert "features" in plan
            assert "limits" in plan
            assert isinstance(plan["features"], list)
            assert isinstance(plan["limits"], dict)

    async def test_plans_include_expected_tiers(self, client):
        """Plans include assessment, pro, enterprise, and partner tiers."""
        resp = await client.get("/api/billing/plans")
        plan_ids = {p["plan_id"] for p in resp.json()["plans"]}
        assert "assessment" in plan_ids
        assert "pro" in plan_ids
        assert "enterprise" in plan_ids
        assert "partner" in plan_ids


class TestGetUsage:
    """Tests for GET /api/billing/usage."""

    async def test_usage_returns_200(self, client, auth_headers):
        """GET /api/billing/usage returns 200."""
        resp = await client.get("/api/billing/usage", headers=auth_headers)
        assert resp.status_code == 200

    async def test_usage_has_correct_structure(self, client, auth_headers):
        """Usage response contains all expected fields."""
        resp = await client.get("/api/billing/usage", headers=auth_headers)
        data = resp.json()
        assert "user_id" in data
        assert "plan_id" in data
        assert "billing_period_start" in data
        assert "billing_period_end" in data
        assert "repositories_used" in data
        assert "repositories_limit" in data
        assert "analyses_this_period" in data
        assert "analyses_limit" in data

    async def test_usage_has_valid_limits(self, client, auth_headers):
        """Usage limits are integers."""
        resp = await client.get("/api/billing/usage", headers=auth_headers)
        data = resp.json()
        assert isinstance(data["repositories_used"], int)
        assert isinstance(data["repositories_limit"], int)
        assert isinstance(data["analyses_this_period"], int)
        assert isinstance(data["analyses_limit"], int)


class TestSubscribe:
    """Tests for POST /api/billing/subscribe."""

    async def test_subscribe_with_valid_plan(self, client, auth_headers):
        """POST /api/billing/subscribe with a valid plan_id returns 200."""
        resp = await client.post(
            "/api/billing/subscribe",
            json={"plan_id": "pro"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["plan_id"] == "pro"
        assert "checkout_session_id" in data
        assert "checkout_url" in data
        assert "message" in data

    async def test_subscribe_with_invalid_plan_returns_400(self, client, auth_headers):
        """POST /api/billing/subscribe with invalid plan_id returns 400."""
        resp = await client.post(
            "/api/billing/subscribe",
            json={"plan_id": "nonexistent_plan"},
            headers=auth_headers,
        )
        assert resp.status_code == 400
        assert "invalid" in resp.json()["detail"].lower() or "plan_id" in resp.json()["detail"]

    async def test_subscribe_with_empty_body_returns_422(self, client, auth_headers):
        """POST /api/billing/subscribe with empty body returns 422."""
        resp = await client.post(
            "/api/billing/subscribe",
            json={},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    async def test_subscribe_checkout_url_contains_plan(self, client, auth_headers):
        """Checkout URL contains the plan identifier."""
        resp = await client.post(
            "/api/billing/subscribe",
            json={"plan_id": "enterprise"},
            headers=auth_headers,
        )
        data = resp.json()
        assert "enterprise" in data["checkout_url"]


class TestCancelSubscription:
    """Tests for POST /api/billing/cancel."""

    async def test_cancel_returns_200(self, client, auth_headers):
        """POST /api/billing/cancel returns 200."""
        resp = await client.post("/api/billing/cancel", headers=auth_headers)
        assert resp.status_code == 200

    async def test_cancel_returns_confirmation(self, client, auth_headers):
        """Cancel response contains cancellation confirmation."""
        resp = await client.post("/api/billing/cancel", headers=auth_headers)
        data = resp.json()
        assert data["cancelled"] is True
        assert "user_id" in data
        assert "effective_date" in data
        assert "message" in data
