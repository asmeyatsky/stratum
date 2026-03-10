"""Integration tests for /api/projects endpoints."""

import pytest


class TestCreateProject:
    """Tests for POST /api/projects."""

    async def test_create_project_returns_201(self, client, auth_headers):
        """POST /api/projects with valid body returns 201."""
        resp = await client.post(
            "/api/projects",
            json={"name": "Test Project"},
            headers=auth_headers,
        )
        assert resp.status_code == 201

    async def test_create_project_returns_project_id(self, client, auth_headers):
        """Created project response contains a project_id."""
        resp = await client.post(
            "/api/projects",
            json={"name": "Test Project"},
            headers=auth_headers,
        )
        data = resp.json()
        assert "project_id" in data
        assert data["project_id"].startswith("prj_")

    async def test_create_project_returns_name(self, client, auth_headers):
        """Created project response echoes the provided name."""
        resp = await client.post(
            "/api/projects",
            json={"name": "My Analysis", "description": "A description"},
            headers=auth_headers,
        )
        data = resp.json()
        assert data["name"] == "My Analysis"
        assert data["description"] == "A description"

    async def test_create_project_default_scenario(self, client, auth_headers):
        """Created project defaults to cto_onboarding scenario."""
        resp = await client.post(
            "/api/projects",
            json={"name": "Test Project"},
            headers=auth_headers,
        )
        data = resp.json()
        assert data["scenario"] == "cto_onboarding"

    async def test_create_project_empty_name_returns_422(self, client, auth_headers):
        """POST /api/projects with empty name returns 422."""
        resp = await client.post(
            "/api/projects",
            json={"name": ""},
            headers=auth_headers,
        )
        assert resp.status_code == 422


class TestListProjects:
    """Tests for GET /api/projects."""

    async def test_list_projects_empty(self, client, auth_headers):
        """GET /api/projects returns empty list when no projects exist."""
        resp = await client.get("/api/projects", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["projects"] == []
        assert data["total"] == 0

    async def test_list_projects_returns_created_projects(self, client, auth_headers):
        """GET /api/projects returns previously created projects."""
        await client.post(
            "/api/projects",
            json={"name": "Project A"},
            headers=auth_headers,
        )
        await client.post(
            "/api/projects",
            json={"name": "Project B"},
            headers=auth_headers,
        )

        resp = await client.get("/api/projects", headers=auth_headers)
        data = resp.json()
        assert data["total"] == 2
        assert len(data["projects"]) == 2


class TestGetProject:
    """Tests for GET /api/projects/{project_id}."""

    async def test_get_project_returns_correct_project(self, client, auth_headers):
        """GET /api/projects/{id} returns the correct project."""
        create_resp = await client.post(
            "/api/projects",
            json={"name": "Lookup Test"},
            headers=auth_headers,
        )
        project_id = create_resp.json()["project_id"]

        resp = await client.get(f"/api/projects/{project_id}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["project_id"] == project_id
        assert data["name"] == "Lookup Test"

    async def test_get_project_bad_id_returns_404(self, client, auth_headers):
        """GET /api/projects/{bad_id} returns 404."""
        resp = await client.get("/api/projects/prj_nonexistent", headers=auth_headers)
        assert resp.status_code == 404


class TestDeleteProject:
    """Tests for DELETE /api/projects/{project_id}."""

    async def test_delete_project_returns_204(self, client, auth_headers):
        """DELETE /api/projects/{id} returns 204 on success."""
        create_resp = await client.post(
            "/api/projects",
            json={"name": "Delete Me"},
            headers=auth_headers,
        )
        project_id = create_resp.json()["project_id"]

        resp = await client.delete(f"/api/projects/{project_id}", headers=auth_headers)
        assert resp.status_code == 204

    async def test_delete_project_bad_id_returns_404(self, client, auth_headers):
        """DELETE /api/projects/{bad_id} returns 404."""
        resp = await client.delete("/api/projects/prj_nonexistent", headers=auth_headers)
        assert resp.status_code == 404


class TestProjectCrudLifecycle:
    """Full CRUD lifecycle test."""

    async def test_full_crud_lifecycle(self, client, auth_headers):
        """Create -> Get -> List -> Delete -> verify 404."""
        # Create
        create_resp = await client.post(
            "/api/projects",
            json={"name": "Lifecycle Test", "description": "End-to-end"},
            headers=auth_headers,
        )
        assert create_resp.status_code == 201
        project_id = create_resp.json()["project_id"]

        # Get
        get_resp = await client.get(
            f"/api/projects/{project_id}", headers=auth_headers
        )
        assert get_resp.status_code == 200
        assert get_resp.json()["name"] == "Lifecycle Test"

        # List (should contain our project)
        list_resp = await client.get("/api/projects", headers=auth_headers)
        assert list_resp.status_code == 200
        assert list_resp.json()["total"] >= 1
        ids = [p["project_id"] for p in list_resp.json()["projects"]]
        assert project_id in ids

        # Delete
        del_resp = await client.delete(
            f"/api/projects/{project_id}", headers=auth_headers
        )
        assert del_resp.status_code == 204

        # Verify 404 after deletion
        get_after_del = await client.get(
            f"/api/projects/{project_id}", headers=auth_headers
        )
        assert get_after_del.status_code == 404
