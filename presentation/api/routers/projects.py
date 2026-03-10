"""
Project management router — CRUD for analysis projects.

Architectural Intent:
    Thin HTTP adapter for project lifecycle operations. Projects are stored
    in-memory for the MVP; the data model is designed to migrate cleanly to
    BigQuery persistence in production.

    No domain logic lives here — the router validates input via Pydantic
    schemas, manages the in-memory store, and returns serialised responses.
"""

from __future__ import annotations

import uuid
from datetime import datetime, UTC
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from presentation.api.dependencies import get_current_user
from presentation.api.schemas import (
    AnalysisStatus,
    ProjectCreate,
    ProjectList,
    ProjectResponse,
    UserInfo,
)

router = APIRouter(prefix="/api/projects", tags=["projects"])

# ---------------------------------------------------------------------------
# In-memory project store (MVP — replaced by BigQuery in production)
# ---------------------------------------------------------------------------

_projects: dict[str, dict] = {}


def _project_to_response(data: dict) -> ProjectResponse:
    """Map internal dict to response schema."""
    return ProjectResponse(
        project_id=data["project_id"],
        name=data["name"],
        description=data["description"],
        scenario=data["scenario"],
        created_at=data["created_at"],
        updated_at=data["updated_at"],
        analysis_status=data.get("analysis_status", AnalysisStatus.pending),
        overall_health_score=data.get("overall_health_score"),
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new project",
    description="Register a new project for analysis. Returns the created project with its generated ID.",
)
async def create_project(
    body: ProjectCreate,
    current_user: Annotated[UserInfo, Depends(get_current_user)],
) -> ProjectResponse:
    """Create a new analysis project."""
    now = datetime.now(UTC).isoformat()
    project_id = f"prj_{uuid.uuid4().hex[:12]}"

    project_data = {
        "project_id": project_id,
        "name": body.name,
        "description": body.description,
        "scenario": body.scenario.value,
        "created_at": now,
        "updated_at": now,
        "analysis_status": AnalysisStatus.pending,
        "overall_health_score": None,
        "owner_id": current_user.user_id,
    }
    _projects[project_id] = project_data

    return _project_to_response(project_data)


@router.get(
    "",
    response_model=ProjectList,
    summary="List all projects",
    description="Retrieve all projects for the authenticated user.",
)
async def list_projects(
    current_user: Annotated[UserInfo, Depends(get_current_user)],
) -> ProjectList:
    """List all projects, most recently updated first."""
    sorted_projects = sorted(
        _projects.values(),
        key=lambda p: p["updated_at"],
        reverse=True,
    )
    return ProjectList(
        projects=[_project_to_response(p) for p in sorted_projects],
        total=len(sorted_projects),
    )


@router.get(
    "/{project_id}",
    response_model=ProjectResponse,
    summary="Get project details",
    description="Retrieve a single project by its ID.",
)
async def get_project(
    project_id: str,
    current_user: Annotated[UserInfo, Depends(get_current_user)],
) -> ProjectResponse:
    """Get a single project by ID."""
    project = _projects.get(project_id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found.",
        )
    return _project_to_response(project)


@router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a project",
    description="Permanently delete a project and its analysis results.",
)
async def delete_project(
    project_id: str,
    current_user: Annotated[UserInfo, Depends(get_current_user)],
) -> None:
    """Delete a project by ID."""
    if project_id not in _projects:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found.",
        )
    del _projects[project_id]
