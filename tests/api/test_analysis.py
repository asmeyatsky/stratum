"""Integration tests for /api/projects/{project_id}/... analysis endpoints."""

import pytest


class TestAnalysisEndpointExists:
    """Tests that analysis-related endpoints respond correctly."""

    async def test_analyze_returns_error_for_missing_project(self, client, auth_headers):
        """POST /api/projects/{bad_id}/analyze returns 404 or 422 for non-existent project.

        The endpoint requires a multipart file upload (git_log), so a plain
        POST without files may return 422 (validation) or 404 (not found),
        depending on evaluation order. Either is acceptable — the point is
        the endpoint exists and responds.
        """
        resp = await client.post(
            "/api/projects/prj_nonexistent/analyze",
            headers=auth_headers,
        )
        assert resp.status_code in (404, 422)


class TestReportEndpoints:
    """Tests that report endpoints return 404 for non-existent projects."""

    async def test_report_returns_404_for_missing_project(self, client, auth_headers):
        """GET /api/projects/{bad_id}/report returns 404."""
        resp = await client.get(
            "/api/projects/prj_nonexistent/report",
            headers=auth_headers,
        )
        assert resp.status_code == 404

    async def test_dimensions_returns_404_for_missing_project(self, client, auth_headers):
        """GET /api/projects/{bad_id}/report/dimensions returns 404."""
        resp = await client.get(
            "/api/projects/prj_nonexistent/report/dimensions",
            headers=auth_headers,
        )
        assert resp.status_code == 404

    async def test_components_returns_404_for_missing_project(self, client, auth_headers):
        """GET /api/projects/{bad_id}/report/components returns 404."""
        resp = await client.get(
            "/api/projects/prj_nonexistent/report/components",
            headers=auth_headers,
        )
        assert resp.status_code == 404

    async def test_hotspots_returns_404_for_missing_project(self, client, auth_headers):
        """GET /api/projects/{bad_id}/report/hotspots returns 404."""
        resp = await client.get(
            "/api/projects/prj_nonexistent/report/hotspots",
            headers=auth_headers,
        )
        assert resp.status_code == 404

    async def test_trends_returns_404_for_missing_project(self, client, auth_headers):
        """GET /api/projects/{bad_id}/report/trends returns 404."""
        resp = await client.get(
            "/api/projects/prj_nonexistent/report/trends",
            headers=auth_headers,
        )
        assert resp.status_code == 404

    async def test_report_returns_404_for_project_without_analysis(
        self, client, auth_headers
    ):
        """GET /api/projects/{id}/report returns 404 when no analysis has been run."""
        # Create a project first
        create_resp = await client.post(
            "/api/projects",
            json={"name": "No Analysis Project"},
            headers=auth_headers,
        )
        project_id = create_resp.json()["project_id"]

        resp = await client.get(
            f"/api/projects/{project_id}/report",
            headers=auth_headers,
        )
        assert resp.status_code == 404
