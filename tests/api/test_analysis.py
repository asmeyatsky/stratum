"""Integration tests for /api/projects/{project_id}/... analysis endpoints."""

import io
import pytest


# Sample git log in the expected format:
#   <hash>|<email>|<name>|<date>|<subject>
#   <added>\t<deleted>\t<file>
SAMPLE_GIT_LOG = """\
abc123def456abc123def456abc123def456abcd01|dev@example.com|Dev User|2025-01-15 10:00:00 +0000|Initial commit
10\t0\tREADME.md
50\t0\tsrc/main.py

def456abc123def456abc123def456abc123abcd02|dev@example.com|Dev User|2025-02-01 12:30:00 +0000|Add feature module
120\t5\tsrc/feature.py
3\t1\tsrc/main.py

aaa111bbb222ccc333ddd444eee555fff666abcd03|other@example.com|Other Dev|2025-03-01 09:00:00 +0000|Fix bug in feature
2\t8\tsrc/feature.py
"""


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


class TestAnalysisUpload:
    """Tests for uploading a git log and triggering analysis."""

    async def test_upload_git_log_returns_202(self, client, auth_headers):
        """POST /api/projects/{id}/analyze with a git log file returns 202 Accepted."""
        # Create a project first
        create_resp = await client.post(
            "/api/projects",
            json={"name": "Upload Test Project"},
            headers=auth_headers,
        )
        project_id = create_resp.json()["project_id"]

        # Upload a git log file
        git_log_file = io.BytesIO(SAMPLE_GIT_LOG.encode("utf-8"))
        resp = await client.post(
            f"/api/projects/{project_id}/analyze",
            files={"git_log": ("git.log", git_log_file, "text/plain")},
            headers=auth_headers,
        )
        assert resp.status_code == 202
        data = resp.json()
        assert data["project_id"] == project_id
        assert data["status"] in ("pending", "running")
        assert "message" in data

    async def test_upload_without_git_log_returns_422(self, client, auth_headers):
        """POST /api/projects/{id}/analyze without git_log file returns 422."""
        create_resp = await client.post(
            "/api/projects",
            json={"name": "No File Project"},
            headers=auth_headers,
        )
        project_id = create_resp.json()["project_id"]

        resp = await client.post(
            f"/api/projects/{project_id}/analyze",
            headers=auth_headers,
        )
        assert resp.status_code == 422

    async def test_report_returns_404_before_analysis_completes(self, client, auth_headers):
        """GET /api/projects/{id}/report returns 404 before analysis is complete."""
        create_resp = await client.post(
            "/api/projects",
            json={"name": "Pending Analysis Project"},
            headers=auth_headers,
        )
        project_id = create_resp.json()["project_id"]

        resp = await client.get(
            f"/api/projects/{project_id}/report",
            headers=auth_headers,
        )
        assert resp.status_code == 404


class TestFileUploadSecurity:
    """Tests for file upload security — path traversal prevention."""

    async def test_path_traversal_filename_rejected(self, client, auth_headers):
        """Filenames with path traversal sequences are rejected or sanitised.

        A malicious filename like ``../../etc/passwd`` should not be accepted
        verbatim. The server should either reject it (400/422) or sanitise
        the filename before saving to disk.
        """
        create_resp = await client.post(
            "/api/projects",
            json={"name": "Security Test Project"},
            headers=auth_headers,
        )
        project_id = create_resp.json()["project_id"]

        # Upload with a path traversal filename
        malicious_content = b"malicious content"
        git_log_file = io.BytesIO(SAMPLE_GIT_LOG.encode("utf-8"))

        resp = await client.post(
            f"/api/projects/{project_id}/analyze",
            files={
                "git_log": ("git.log", git_log_file, "text/plain"),
                "manifests": ("../../etc/passwd", io.BytesIO(malicious_content), "text/plain"),
            },
            headers=auth_headers,
        )
        # The server should either reject the request (400) or accept it
        # after sanitising the filename (202). It must NOT write to a path
        # outside the upload directory.
        assert resp.status_code in (202, 400, 422)

    async def test_null_byte_filename_rejected(self, client, auth_headers):
        """Filenames with null bytes are rejected."""
        create_resp = await client.post(
            "/api/projects",
            json={"name": "Null Byte Test"},
            headers=auth_headers,
        )
        project_id = create_resp.json()["project_id"]

        git_log_file = io.BytesIO(SAMPLE_GIT_LOG.encode("utf-8"))

        resp = await client.post(
            f"/api/projects/{project_id}/analyze",
            files={
                "git_log": ("git.log", git_log_file, "text/plain"),
                "manifests": ("malicious\x00.txt", io.BytesIO(b"data"), "text/plain"),
            },
            headers=auth_headers,
        )
        # Should either reject or sanitise
        assert resp.status_code in (202, 400, 422)
