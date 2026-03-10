"""
Project management router — CRUD for analysis projects.

Architectural Intent:
    Thin HTTP adapter for project lifecycle operations. Projects are persisted
    to the database via ``ProjectRepository``. No domain logic lives here —
    the router validates input via Pydantic schemas, delegates to the
    repository, and returns serialised responses.
"""

from __future__ import annotations

import uuid
from datetime import datetime, UTC
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.persistence.database import get_db_session
from infrastructure.persistence.repository import ProjectRepository
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
# Helpers
# ---------------------------------------------------------------------------


def _project_to_response(data: dict) -> ProjectResponse:
    """Map a repository dict to the API response schema."""
    return ProjectResponse(
        project_id=data["project_id"],
        name=data["name"],
        description=data["description"],
        scenario=data["scenario"],
        created_at=data["created_at"] if isinstance(data["created_at"], str) else data["created_at"].isoformat() if data["created_at"] else "",
        updated_at=data["updated_at"] if isinstance(data["updated_at"], str) else data["updated_at"].isoformat() if data["updated_at"] else "",
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
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ProjectResponse:
    """Create a new analysis project."""
    now = datetime.now(UTC)
    project_id = f"prj_{uuid.uuid4().hex[:12]}"

    repo = ProjectRepository(session)
    project_data = await repo.create({
        "project_id": project_id,
        "name": body.name,
        "description": body.description,
        "scenario": body.scenario.value,
        "analysis_status": AnalysisStatus.pending.value,
        "overall_health_score": None,
        "owner_id": current_user.user_id,
        "created_at": now,
        "updated_at": now,
    })

    return _project_to_response(project_data)


@router.get(
    "",
    response_model=ProjectList,
    summary="List all projects",
    description="Retrieve all projects for the authenticated user.",
)
async def list_projects(
    current_user: Annotated[UserInfo, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ProjectList:
    """List all projects, most recently updated first."""
    repo = ProjectRepository(session)
    projects = await repo.list_all()
    return ProjectList(
        projects=[_project_to_response(p) for p in projects],
        total=len(projects),
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
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ProjectResponse:
    """Get a single project by ID."""
    repo = ProjectRepository(session)
    project = await repo.get_by_id(project_id)
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
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> None:
    """Delete a project by ID."""
    repo = ProjectRepository(session)
    deleted = await repo.delete(project_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found.",
        )
