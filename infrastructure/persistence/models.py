"""
SQLAlchemy ORM models for Stratum persistence.

Architectural Intent:
    These models map the core Stratum entities to relational tables using
    SQLAlchemy 2.0 ``Mapped`` / ``mapped_column`` style.  They live in the
    infrastructure layer because they are implementation details of the
    persistence adapter — domain entities remain plain dataclasses.

Tables:
    - ``projects`` — analysis project metadata and status.
    - ``analysis_results`` — serialised JSON reports linked to projects.
"""

from __future__ import annotations

import uuid
from datetime import datetime, UTC

from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.persistence.database import Base


class ProjectModel(Base):
    """Persistent representation of an analysis project."""

    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    project_id: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(String(2000), default="")
    scenario: Mapped[str] = mapped_column(String(50), nullable=False)
    analysis_status: Mapped[str] = mapped_column(String(20), default="pending")
    overall_health_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    owner_id: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


class AnalysisResultModel(Base):
    """Serialised analysis report linked to a project."""

    __tablename__ = "analysis_results"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    project_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("projects.project_id"),
        nullable=False,
        index=True,
    )
    report_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )
