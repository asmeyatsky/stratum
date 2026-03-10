"""
Analysis router — trigger and retrieve code intelligence analysis.

Architectural Intent:
    Thin HTTP adapter that converts multipart file uploads into an
    ``AnalysisRequest``, delegates execution to ``AnalyzeRepositoryCommand``
    from the application layer, and maps the ``AnalysisResultDTO`` back
    to API response schemas.

    Long-running analysis is executed via FastAPI ``BackgroundTasks`` so
    the POST endpoint returns immediately with a 202 Accepted status.
    Clients poll the report endpoints to check for completion.
"""

from __future__ import annotations

import logging
import os
import tempfile
from datetime import datetime, UTC
from typing import Annotated

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    UploadFile,
    status,
)

from application.commands.analyze_repository import AnalyzeRepositoryCommand
from application.dtos.analysis_dto import AnalysisRequest, AnalysisResultDTO
from infrastructure.config.dependency_injection import Container
from presentation.api.dependencies import get_container, get_current_user
from presentation.api.schemas import (
    AnalysisResponse,
    AnalysisStatus,
    ComponentRiskListResponse,
    ComponentRiskResponse,
    DimensionScoresResponse,
    FileHotspotListResponse,
    FileHotspotResponse,
    FullReportResponse,
    RiskScoreResponse,
    TopRiskResponse,
    TrendDataPoint,
    TrendResponse,
    UserInfo,
)

# Projects store is shared with the projects router
from presentation.api.routers.projects import _projects

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/projects", tags=["analysis"])

# ---------------------------------------------------------------------------
# In-memory analysis results store (MVP)
# ---------------------------------------------------------------------------

_analysis_results: dict[str, AnalysisResultDTO] = {}
_analysis_status: dict[str, dict] = {}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _require_project(project_id: str) -> dict:
    """Raise 404 if project does not exist; return project data."""
    project = _projects.get(project_id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found.",
        )
    return project


def _dto_to_dimension_scores(dto: AnalysisResultDTO) -> dict[str, RiskScoreResponse]:
    """Convert DTO dimension scores to response schema."""
    return {
        dim: RiskScoreResponse(
            value=score.value,
            severity=score.severity,
            label=score.label,
            evidence=score.evidence,
        )
        for dim, score in dto.dimension_scores.items()
    }


def _dto_to_component_risks(dto: AnalysisResultDTO) -> list[ComponentRiskResponse]:
    """Convert DTO component risks to response schema."""
    return [
        ComponentRiskResponse(
            component_name=cr.component_name,
            composite_score=cr.composite_score,
            systemic_risk=cr.systemic_risk,
            dimension_scores={
                dim: RiskScoreResponse(
                    value=s.value,
                    severity=s.severity,
                    label=s.label,
                    evidence=s.evidence,
                )
                for dim, s in cr.dimension_scores.items()
            },
        )
        for cr in dto.component_risks
    ]


def _dto_to_file_hotspots(dto: AnalysisResultDTO) -> list[FileHotspotResponse]:
    """Convert DTO file hotspots to response schema."""
    return [
        FileHotspotResponse(
            file_path=fh.file_path,
            composite_risk_score=fh.composite_risk_score,
            risk_indicators=fh.risk_indicators,
            refactoring_recommendation=fh.refactoring_recommendation,
            effort_estimate=fh.effort_estimate,
        )
        for fh in dto.file_hotspots
    ]


def _dto_to_top_risks(dto: AnalysisResultDTO) -> list[TopRiskResponse]:
    """Convert DTO top risks to response schema."""
    return [
        TopRiskResponse(
            dimension=risk.get("dimension", ""),
            value=risk.get("value", 0.0),
            severity=risk.get("severity", ""),
            label=risk.get("label", ""),
            evidence=risk.get("evidence", ""),
        )
        for risk in dto.top_risks
    ]


# ---------------------------------------------------------------------------
# Background analysis runner
# ---------------------------------------------------------------------------


async def _run_analysis_background(
    project_id: str,
    git_log_path: str,
    manifest_paths: list[str],
    container: Container,
) -> None:
    """Execute analysis in the background and store results.

    This coroutine is scheduled via ``BackgroundTasks``. On completion it
    updates the project's status and stores the ``AnalysisResultDTO``.
    Temporary files are cleaned up after analysis completes.
    """
    project = _projects.get(project_id)
    if project is None:
        logger.error("Background analysis: project %s vanished", project_id)
        return

    project["analysis_status"] = AnalysisStatus.running
    _analysis_status[project_id] = {
        "status": AnalysisStatus.running,
        "started_at": datetime.now(UTC).isoformat(),
        "completed_at": None,
        "message": "Analysis in progress",
    }

    try:
        command = AnalyzeRepositoryCommand(
            git_log_port=container.git_log_parser,
            vulnerability_db_port=container.nvd_adapter,
            ai_narrative_port=container.narrative_adapter,
            report_generator_port=container.report_adapter,
        )

        output_dir = tempfile.mkdtemp(prefix="stratum_report_")
        output_path = os.path.join(output_dir, f"{project_id}_report.pdf")

        request = AnalysisRequest(
            git_log_source=git_log_path,
            project_name=project["name"],
            scenario=project["scenario"],
            output_path=output_path,
            manifest_paths=manifest_paths,
        )

        result = await command.execute(request)

        # Store result and update status
        _analysis_results[project_id] = result
        project["analysis_status"] = AnalysisStatus.completed
        project["overall_health_score"] = result.overall_health_score
        project["updated_at"] = datetime.now(UTC).isoformat()
        _analysis_status[project_id].update({
            "status": AnalysisStatus.completed,
            "completed_at": datetime.now(UTC).isoformat(),
            "message": f"Analysis complete. Health score: {result.overall_health_score}/10",
        })

        logger.info(
            "Background analysis complete: project=%s health=%.1f",
            project_id,
            result.overall_health_score,
        )

    except Exception as exc:
        logger.exception("Background analysis failed for project %s", project_id)
        project["analysis_status"] = AnalysisStatus.failed
        project["updated_at"] = datetime.now(UTC).isoformat()
        _analysis_status[project_id].update({
            "status": AnalysisStatus.failed,
            "completed_at": datetime.now(UTC).isoformat(),
            "message": f"Analysis failed: {exc}",
        })

    finally:
        # Clean up uploaded temp files
        for path in [git_log_path] + manifest_paths:
            try:
                if os.path.exists(path):
                    os.unlink(path)
            except OSError:
                pass


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/{project_id}/analyze",
    response_model=AnalysisResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger repository analysis",
    description=(
        "Upload a git log file and optional manifest files to trigger a full "
        "Stratum analysis. The analysis runs in the background; poll the report "
        "endpoints to check for completion."
    ),
)
async def trigger_analysis(
    project_id: str,
    background_tasks: BackgroundTasks,
    container: Annotated[Container, Depends(get_container)],
    current_user: Annotated[UserInfo, Depends(get_current_user)],
    git_log: UploadFile = File(
        ..., description="Git log file (git log --numstat --pretty=format:'%H|%ae|%an|%aI|%s')"
    ),
    manifests: list[UploadFile] = File(
        default=[],
        description="Package manifest files (package.json, requirements.txt, etc.)",
    ),
) -> AnalysisResponse:
    """Trigger a full code intelligence analysis for a project.

    The git log file and manifest files are uploaded as multipart form data.
    Analysis is executed asynchronously; the endpoint returns 202 immediately.
    """
    project = _require_project(project_id)

    # Persist uploaded files to temp directory
    upload_dir = tempfile.mkdtemp(prefix="stratum_upload_")

    git_log_path = os.path.join(upload_dir, "git.log")
    content = await git_log.read()
    with open(git_log_path, "wb") as f:
        f.write(content)

    manifest_paths: list[str] = []
    for manifest_file in manifests:
        if manifest_file.filename:
            manifest_path = os.path.join(upload_dir, manifest_file.filename)
            manifest_content = await manifest_file.read()
            with open(manifest_path, "wb") as f:
                f.write(manifest_content)
            manifest_paths.append(manifest_path)

    started_at = datetime.now(UTC).isoformat()

    # Schedule background execution
    background_tasks.add_task(
        _run_analysis_background,
        project_id,
        git_log_path,
        manifest_paths,
        container,
    )

    project["analysis_status"] = AnalysisStatus.pending
    project["updated_at"] = datetime.now(UTC).isoformat()
    _analysis_status[project_id] = {
        "status": AnalysisStatus.pending,
        "started_at": started_at,
        "completed_at": None,
        "message": "Analysis queued",
    }

    return AnalysisResponse(
        project_id=project_id,
        status=AnalysisStatus.pending,
        message="Analysis queued and will run in the background.",
        started_at=started_at,
    )


@router.get(
    "/{project_id}/report",
    response_model=FullReportResponse,
    summary="Get latest analysis report",
    description="Retrieve the full analysis report including all dimensions, components, and hotspots.",
)
async def get_report(
    project_id: str,
    current_user: Annotated[UserInfo, Depends(get_current_user)],
) -> FullReportResponse:
    """Return the complete analysis report for a project."""
    _require_project(project_id)

    dto = _analysis_results.get(project_id)
    if dto is None:
        status_info = _analysis_status.get(project_id, {})
        current_status = status_info.get("status", AnalysisStatus.pending)
        if current_status == AnalysisStatus.running:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Analysis is still running. Please try again shortly.",
            )
        if current_status == AnalysisStatus.failed:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Analysis failed: {status_info.get('message', 'Unknown error')}",
            )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No analysis report available. Trigger an analysis first.",
        )

    return FullReportResponse(
        project_id=project_id,
        project_name=dto.project_name,
        scenario=dto.scenario,
        analysis_timestamp=dto.analysis_timestamp,
        overall_health_score=dto.overall_health_score,
        dimension_scores=_dto_to_dimension_scores(dto),
        top_risks=_dto_to_top_risks(dto),
        component_risks=_dto_to_component_risks(dto),
        file_hotspots=_dto_to_file_hotspots(dto),
        ai_narrative=dto.ai_narrative,
        pdf_output_path=dto.pdf_output_path,
    )


@router.get(
    "/{project_id}/report/dimensions",
    response_model=DimensionScoresResponse,
    summary="Get dimension scores",
    description="Retrieve the 15 quality dimension scores for the latest analysis.",
)
async def get_dimensions(
    project_id: str,
    current_user: Annotated[UserInfo, Depends(get_current_user)],
) -> DimensionScoresResponse:
    """Return dimension scores for the latest analysis."""
    _require_project(project_id)

    dto = _analysis_results.get(project_id)
    if dto is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No analysis report available. Trigger an analysis first.",
        )

    return DimensionScoresResponse(
        project_id=project_id,
        overall_health_score=dto.overall_health_score,
        dimensions=_dto_to_dimension_scores(dto),
    )


@router.get(
    "/{project_id}/report/components",
    response_model=ComponentRiskListResponse,
    summary="Get component risk matrix",
    description="Retrieve the worst components ranked by composite risk score.",
)
async def get_components(
    project_id: str,
    current_user: Annotated[UserInfo, Depends(get_current_user)],
) -> ComponentRiskListResponse:
    """Return the component risk matrix for the latest analysis."""
    _require_project(project_id)

    dto = _analysis_results.get(project_id)
    if dto is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No analysis report available. Trigger an analysis first.",
        )

    return ComponentRiskListResponse(
        project_id=project_id,
        components=_dto_to_component_risks(dto),
    )


@router.get(
    "/{project_id}/report/hotspots",
    response_model=FileHotspotListResponse,
    summary="Get file hotspots",
    description="Retrieve files ranked by composite risk score — the riskiest files in the codebase.",
)
async def get_hotspots(
    project_id: str,
    current_user: Annotated[UserInfo, Depends(get_current_user)],
) -> FileHotspotListResponse:
    """Return file hotspots for the latest analysis."""
    _require_project(project_id)

    dto = _analysis_results.get(project_id)
    if dto is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No analysis report available. Trigger an analysis first.",
        )

    return FileHotspotListResponse(
        project_id=project_id,
        hotspots=_dto_to_file_hotspots(dto),
    )


@router.get(
    "/{project_id}/report/trends",
    response_model=TrendResponse,
    summary="Get feature/bug trends",
    description=(
        "Retrieve time-series trend data showing the balance of feature work, "
        "bug fixes, and refactoring commits over time."
    ),
)
async def get_trends(
    project_id: str,
    current_user: Annotated[UserInfo, Depends(get_current_user)],
) -> TrendResponse:
    """Return feature/bug/refactor trends for the latest analysis.

    Trend data is derived from the commit classification performed during
    P2 (commit quality) analysis. If no analysis has been run, or commit
    data is insufficient, an empty trends list is returned.
    """
    _require_project(project_id)

    dto = _analysis_results.get(project_id)
    if dto is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No analysis report available. Trigger an analysis first.",
        )

    # Trend data is not directly available on the DTO in Phase 1.
    # We derive a placeholder from the analysis timestamp to show the
    # API contract. In Phase 2, the commit quality service will emit
    # per-period breakdowns that feed this endpoint.
    #
    # For now, return the top_risks as a proxy indicator that the
    # analysis ran, and provide the structure the frontend expects.
    trends: list[TrendDataPoint] = []

    # If we have dimension scores, we at least know analysis ran —
    # return an empty trends list with the correct shape so the
    # frontend can render the chart (it will be empty until Phase 2
    # adds per-period commit classification).
    return TrendResponse(
        project_id=project_id,
        trends=trends,
    )
