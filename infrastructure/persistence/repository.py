"""
Repository implementations for Stratum persistence.

Architectural Intent:
    Repositories encapsulate all database access behind a clean async
    interface.  They accept and return plain ``dict`` objects so that the
    presentation layer stays decoupled from SQLAlchemy model classes.

    Each repository takes an ``AsyncSession`` at construction time, allowing
    the caller (typically a FastAPI dependency) to control transaction scope.
"""

from __future__ import annotations

import json
from datetime import datetime, UTC

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.persistence.models import AnalysisResultModel, ProjectModel


class ProjectRepository:
    """Async CRUD operations for ``ProjectModel``."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # -- helpers ----------------------------------------------------------

    @staticmethod
    def _to_dict(model: ProjectModel) -> dict:
        """Convert a ``ProjectModel`` instance to a plain dict."""
        return {
            "id": model.id,
            "project_id": model.project_id,
            "name": model.name,
            "description": model.description,
            "scenario": model.scenario,
            "analysis_status": model.analysis_status,
            "overall_health_score": model.overall_health_score,
            "owner_id": model.owner_id,
            "created_at": model.created_at.isoformat() if model.created_at else None,
            "updated_at": model.updated_at.isoformat() if model.updated_at else None,
        }

    # -- public API -------------------------------------------------------

    async def create(self, data: dict) -> dict:
        """Insert a new project and return it as a dict."""
        model = ProjectModel(**data)
        self._session.add(model)
        await self._session.commit()
        await self._session.refresh(model)
        return self._to_dict(model)

    async def get_by_id(self, project_id: str) -> dict | None:
        """Fetch a single project by its ``project_id``, or ``None``."""
        stmt = select(ProjectModel).where(ProjectModel.project_id == project_id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return self._to_dict(model)

    async def list_all(self, owner_id: str | None = None) -> list[dict]:
        """Return all projects, optionally filtered by owner, newest first."""
        stmt = select(ProjectModel).order_by(ProjectModel.updated_at.desc())
        if owner_id is not None:
            stmt = stmt.where(ProjectModel.owner_id == owner_id)
        result = await self._session.execute(stmt)
        return [self._to_dict(m) for m in result.scalars().all()]

    async def update(self, project_id: str, data: dict) -> dict | None:
        """Update fields on an existing project; return updated dict or ``None``."""
        stmt = select(ProjectModel).where(ProjectModel.project_id == project_id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        for key, value in data.items():
            if hasattr(model, key):
                setattr(model, key, value)
        model.updated_at = datetime.now(UTC)
        await self._session.commit()
        await self._session.refresh(model)
        return self._to_dict(model)

    async def delete(self, project_id: str) -> bool:
        """Delete a project by ``project_id``; return ``True`` if it existed."""
        stmt = select(ProjectModel).where(ProjectModel.project_id == project_id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return False
        await self._session.delete(model)
        await self._session.commit()
        return True


class AnalysisResultRepository:
    """Async operations for ``AnalysisResultModel``."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # -- helpers ----------------------------------------------------------

    @staticmethod
    def _to_dict(model: AnalysisResultModel) -> dict:
        """Convert an ``AnalysisResultModel`` instance to a plain dict."""
        return {
            "id": model.id,
            "project_id": model.project_id,
            "report_json": model.report_json,
            "created_at": model.created_at.isoformat() if model.created_at else None,
        }

    # -- public API -------------------------------------------------------

    async def save_result(self, project_id: str, report: dict) -> dict:
        """Persist a new analysis result (serialised as JSON)."""
        model = AnalysisResultModel(
            project_id=project_id,
            report_json=json.dumps(report),
        )
        self._session.add(model)
        await self._session.commit()
        await self._session.refresh(model)
        return self._to_dict(model)

    async def get_latest(self, project_id: str) -> dict | None:
        """Return the most recent analysis result for a project, or ``None``."""
        stmt = (
            select(AnalysisResultModel)
            .where(AnalysisResultModel.project_id == project_id)
            .order_by(AnalysisResultModel.created_at.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return self._to_dict(model)

    async def list_for_project(self, project_id: str) -> list[dict]:
        """Return all analysis results for a project, newest first."""
        stmt = (
            select(AnalysisResultModel)
            .where(AnalysisResultModel.project_id == project_id)
            .order_by(AnalysisResultModel.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return [self._to_dict(m) for m in result.scalars().all()]
