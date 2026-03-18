"""
Pydantic schemas for the Stratum REST API.

Architectural Intent:
    These models define the HTTP request/response contracts for the FastAPI
    presentation layer. They are separate from application DTOs to allow the
    API surface to evolve independently from internal data structures.

    Schemas here mirror — but do not import — application DTOs. The routers
    are responsible for mapping between the two.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class AnalysisScenario(str, Enum):
    ma_due_diligence = "ma_due_diligence"
    vendor_audit = "vendor_audit"
    post_merger = "post_merger"
    decommission = "decommission"
    cto_onboarding = "cto_onboarding"
    oss_assessment = "oss_assessment"


class AnalysisStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    status: str = Field(description="Service health status")
    version: str = Field(description="Application version")
    timestamp: str = Field(description="Current server time in ISO-8601")


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    email: str = Field(description="User email address")
    password: str = Field(description="User password")


class AuthToken(BaseModel):
    access_token: str = Field(description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(default=3600, description="Token TTL in seconds")


class UserInfo(BaseModel):
    user_id: str = Field(description="Unique user identifier")
    email: str = Field(description="User email address")
    name: str = Field(description="Display name")
    role: str = Field(default="analyst", description="User role")


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------

class ProjectCreate(BaseModel):
    name: str = Field(
        min_length=1,
        max_length=200,
        description="Human-readable project name",
    )
    description: str = Field(
        default="",
        max_length=2000,
        description="Optional project description",
    )
    scenario: AnalysisScenario = Field(
        default=AnalysisScenario.cto_onboarding,
        description="Analysis scenario determining report framing",
    )


class ProjectResponse(BaseModel):
    project_id: str = Field(description="Unique project identifier")
    name: str = Field(description="Project name")
    description: str = Field(description="Project description")
    scenario: AnalysisScenario = Field(description="Analysis scenario")
    created_at: str = Field(description="Creation timestamp ISO-8601")
    updated_at: str = Field(description="Last update timestamp ISO-8601")
    analysis_status: AnalysisStatus = Field(
        default=AnalysisStatus.pending,
        description="Current analysis status",
    )
    overall_health_score: float | None = Field(
        default=None,
        description="Latest health score (null if no analysis run yet)",
    )


class ProjectList(BaseModel):
    projects: list[ProjectResponse] = Field(description="List of projects")
    total: int = Field(description="Total number of projects")


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

class AnalysisResponse(BaseModel):
    project_id: str = Field(description="Project that was analysed")
    status: AnalysisStatus = Field(description="Analysis run status")
    message: str = Field(default="", description="Status message or error detail")
    started_at: str | None = Field(default=None, description="Analysis start time")
    completed_at: str | None = Field(default=None, description="Analysis completion time")


class RiskScoreResponse(BaseModel):
    value: float = Field(ge=0, le=10, description="Risk score 0-10")
    severity: str = Field(description="Severity label: minimal/low/medium/high/critical")
    label: str = Field(description="Human-readable dimension label")
    evidence: str = Field(description="Evidence summary for this score")


class DimensionScoresResponse(BaseModel):
    project_id: str = Field(description="Project identifier")
    overall_health_score: float = Field(description="Inverse-risk health score 0-10")
    dimensions: dict[str, RiskScoreResponse] = Field(
        description="Score per quality dimension",
    )


class ComponentRiskResponse(BaseModel):
    component_name: str = Field(description="Component/module name")
    composite_score: float = Field(description="Average risk across dimensions")
    systemic_risk: bool = Field(description="True if 3+ dimensions score above 7")
    dimension_scores: dict[str, RiskScoreResponse] = Field(
        default_factory=dict,
        description="Per-dimension scores for this component",
    )


class ComponentRiskListResponse(BaseModel):
    project_id: str = Field(description="Project identifier")
    components: list[ComponentRiskResponse] = Field(
        description="Components sorted by composite risk",
    )


class FileHotspotResponse(BaseModel):
    file_path: str = Field(description="Path of the high-risk file")
    composite_risk_score: float = Field(description="Composite risk score")
    risk_indicators: dict[str, float] = Field(
        default_factory=dict,
        description="Individual risk indicator values",
    )
    refactoring_recommendation: str = Field(
        default="",
        description="Suggested refactoring action",
    )
    effort_estimate: str = Field(
        default="medium",
        description="Estimated effort: small/medium/large",
    )


class FileHotspotListResponse(BaseModel):
    project_id: str = Field(description="Project identifier")
    hotspots: list[FileHotspotResponse] = Field(
        description="Files sorted by composite risk",
    )


class TopRiskResponse(BaseModel):
    dimension: str = Field(description="Risk dimension name")
    value: float = Field(description="Risk score value")
    severity: str = Field(description="Severity label")
    label: str = Field(description="Human-readable label")
    evidence: str = Field(description="Evidence summary")


class TrendDataPoint(BaseModel):
    period: str = Field(description="Time period label (e.g. '2024-W03')")
    features: int = Field(default=0, description="Feature commit count")
    bugs: int = Field(default=0, description="Bug-fix commit count")
    refactors: int = Field(default=0, description="Refactoring commit count")
    bug_fix_ratio: float = Field(default=0.0, description="Ratio of bug fixes to total commits")
    total_commits: int = Field(default=0, description="Total commits in period")


class TrendResponse(BaseModel):
    project_id: str = Field(description="Project identifier")
    trends: list[TrendDataPoint] = Field(
        description="Time-series trend data points",
    )


class FullReportResponse(BaseModel):
    project_id: str = Field(description="Project identifier")
    project_name: str = Field(description="Project name")
    scenario: str = Field(description="Analysis scenario")
    analysis_timestamp: str = Field(description="When the analysis was run")
    overall_health_score: float = Field(description="Health score 0-10")
    dimension_scores: dict[str, RiskScoreResponse] = Field(
        description="All dimension scores",
    )
    top_risks: list[TopRiskResponse] = Field(description="Top 5 risk dimensions")
    component_risks: list[ComponentRiskResponse] = Field(
        description="Worst components by risk",
    )
    file_hotspots: list[FileHotspotResponse] = Field(
        description="Riskiest files",
    )
    ai_narrative: str = Field(default="", description="AI-generated executive summary")
    pdf_output_path: str = Field(default="", description="Path to generated PDF report")
