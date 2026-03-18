"""Integration tests for /api/partner endpoints."""

import pytest

from presentation.api.routers import partner as partner_module


@pytest.fixture(autouse=True)
def _clear_partner_stores():
    """Clear the in-memory partner stores before each test."""
    partner_module._assessments.clear()
    partner_module._webhooks.clear()
    yield
    partner_module._assessments.clear()
    partner_module._webhooks.clear()


class TestCreateAssessment:
    """Tests for POST /api/partner/assessments."""

    async def test_create_assessment_returns_201(self, client):
        """POST /api/partner/assessments creates an assessment."""
        resp = await client.post(
            "/api/partner/assessments",
            json={
                "partner_id": "partner_acme",
                "project_name": "Widget App",
                "repository_url": "https://github.com/acme/widget",
            },
        )
        assert resp.status_code == 201

    async def test_create_assessment_returns_correct_fields(self, client):
        """Created assessment response has all required fields."""
        resp = await client.post(
            "/api/partner/assessments",
            json={
                "partner_id": "partner_acme",
                "project_name": "Widget App",
                "repository_url": "https://github.com/acme/widget",
                "scenario": "ma_due_diligence",
            },
        )
        data = resp.json()
        assert data["partner_id"] == "partner_acme"
        assert data["project_name"] == "Widget App"
        assert data["repository_url"] == "https://github.com/acme/widget"
        assert data["scenario"] == "ma_due_diligence"
        assert data["status"] == "pending"
        assert data["assessment_id"].startswith("asmt_")
        assert "created_at" in data
        assert "updated_at" in data

    async def test_create_assessment_default_scenario(self, client):
        """Assessment defaults to cto_onboarding scenario."""
        resp = await client.post(
            "/api/partner/assessments",
            json={
                "partner_id": "partner_acme",
                "project_name": "Widget App",
                "repository_url": "https://github.com/acme/widget",
            },
        )
        data = resp.json()
        assert data["scenario"] == "cto_onboarding"

    async def test_create_assessment_missing_fields_returns_422(self, client):
        """POST /api/partner/assessments with missing required fields returns 422."""
        resp = await client.post(
            "/api/partner/assessments",
            json={"partner_id": "partner_acme"},
        )
        assert resp.status_code == 422


class TestListAssessments:
    """Tests for GET /api/partner/assessments."""

    async def test_list_assessments_empty(self, client):
        """GET /api/partner/assessments returns empty list when none exist."""
        resp = await client.get("/api/partner/assessments")
        assert resp.status_code == 200
        data = resp.json()
        assert data["assessments"] == []
        assert data["total"] == 0

    async def test_list_assessments_returns_created(self, client):
        """GET /api/partner/assessments returns previously created assessments."""
        await client.post(
            "/api/partner/assessments",
            json={
                "partner_id": "partner_acme",
                "project_name": "App A",
                "repository_url": "https://github.com/acme/app-a",
            },
        )
        await client.post(
            "/api/partner/assessments",
            json={
                "partner_id": "partner_acme",
                "project_name": "App B",
                "repository_url": "https://github.com/acme/app-b",
            },
        )

        resp = await client.get("/api/partner/assessments")
        data = resp.json()
        assert data["total"] == 2
        assert len(data["assessments"]) == 2

    async def test_list_assessments_filtered_by_partner_id(self, client):
        """GET /api/partner/assessments?partner_id=X filters correctly."""
        await client.post(
            "/api/partner/assessments",
            json={
                "partner_id": "partner_alpha",
                "project_name": "Alpha App",
                "repository_url": "https://github.com/alpha/app",
            },
        )
        await client.post(
            "/api/partner/assessments",
            json={
                "partner_id": "partner_beta",
                "project_name": "Beta App",
                "repository_url": "https://github.com/beta/app",
            },
        )

        resp = await client.get("/api/partner/assessments?partner_id=partner_alpha")
        data = resp.json()
        assert data["total"] == 1
        assert data["assessments"][0]["partner_id"] == "partner_alpha"


class TestRegisterWebhook:
    """Tests for POST /api/partner/webhooks."""

    async def test_register_webhook_returns_201(self, client):
        """POST /api/partner/webhooks registers a webhook."""
        resp = await client.post(
            "/api/partner/webhooks",
            json={
                "partner_id": "partner_acme",
                "url": "https://acme.com/hooks/stratum",
                "events": ["assessment.completed"],
            },
        )
        assert resp.status_code == 201

    async def test_register_webhook_returns_correct_fields(self, client):
        """Registered webhook response has all required fields."""
        resp = await client.post(
            "/api/partner/webhooks",
            json={
                "partner_id": "partner_acme",
                "url": "https://acme.com/hooks/stratum",
                "events": ["assessment.started", "assessment.completed"],
            },
        )
        data = resp.json()
        assert data["webhook_id"].startswith("whk_")
        assert data["partner_id"] == "partner_acme"
        assert data["url"] == "https://acme.com/hooks/stratum"
        assert "assessment.started" in data["events"]
        assert "assessment.completed" in data["events"]
        assert "created_at" in data


class TestListWebhooks:
    """Tests for GET /api/partner/webhooks."""

    async def test_list_webhooks_empty(self, client):
        """GET /api/partner/webhooks returns empty list when none exist."""
        resp = await client.get("/api/partner/webhooks")
        assert resp.status_code == 200
        data = resp.json()
        assert data["webhooks"] == []
        assert data["total"] == 0

    async def test_list_webhooks_returns_registered(self, client):
        """GET /api/partner/webhooks returns previously registered webhooks."""
        await client.post(
            "/api/partner/webhooks",
            json={
                "partner_id": "partner_acme",
                "url": "https://acme.com/hooks/stratum",
                "events": ["assessment.completed"],
            },
        )

        resp = await client.get("/api/partner/webhooks")
        data = resp.json()
        assert data["total"] == 1
        assert len(data["webhooks"]) == 1
        assert data["webhooks"][0]["url"] == "https://acme.com/hooks/stratum"
