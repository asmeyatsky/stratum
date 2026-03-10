"""
Jira connector router — connect, browse projects, and import issues.

Architectural Intent:
    Thin HTTP adapter for the Jira connector. Accepts Jira Cloud credentials,
    validates connectivity, lists accessible projects, and imports issues
    for P2 task correlation analysis.

    No business logic lives here — all data retrieval is delegated to the
    JiraAdapter (which implements the JiraPort) and domain layers.
"""

from __future__ import annotations

import logging
from datetime import datetime, UTC
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from domain.entities.jira_issue import JiraIssue
from infrastructure.config.dependency_injection import Container
from presentation.api.dependencies import get_container, get_current_user
from presentation.api.schemas import UserInfo

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/connectors/jira", tags=["jira"])


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class JiraConnectRequest(BaseModel):
    base_url: str = Field(
        description="Jira Cloud instance URL (e.g. https://yourorg.atlassian.net)"
    )
    email: str = Field(description="Jira user email address")
    api_token: str = Field(description="Jira API token (from id.atlassian.com)")


class JiraConnectResponse(BaseModel):
    connected: bool = Field(description="Whether the connection succeeded")
    base_url: str = Field(default="", description="Confirmed Jira instance URL")
    version: str = Field(default="", description="Jira server version")
    server_title: str = Field(default="", description="Jira server title")
    message: str = Field(default="", description="Status message")


class JiraProjectResponse(BaseModel):
    key: str = Field(description="Project key (e.g. PLAT)")
    name: str = Field(description="Project name")
    project_type: str = Field(default="", description="Project type key")
    lead: str | None = Field(default=None, description="Project lead name")


class JiraProjectListResponse(BaseModel):
    projects: list[JiraProjectResponse] = Field(description="List of Jira projects")
    total: int = Field(description="Total count")


class JiraIssueResponse(BaseModel):
    key: str = Field(description="Issue key (e.g. PLAT-123)")
    issue_type: str = Field(description="Issue type name")
    taxonomy: str = Field(description="Stratum taxonomy: bug/feature/chore")
    status: str = Field(description="Issue status")
    summary: str = Field(description="Issue summary")
    created_at: str | None = Field(default=None, description="Creation timestamp")
    resolved_at: str | None = Field(default=None, description="Resolution timestamp")
    assignee: str | None = Field(default=None, description="Assignee name")
    story_points: float | None = Field(default=None, description="Story point estimate")
    sprint: str | None = Field(default=None, description="Sprint name")
    labels: list[str] = Field(default_factory=list, description="Issue labels")
    resolution_days: float | None = Field(
        default=None, description="Days to resolution (null if unresolved)"
    )


class JiraImportRequest(BaseModel):
    jql_filter: str | None = Field(
        default=None,
        description="Optional JQL filter to narrow imported issues",
    )
    max_results: int = Field(
        default=1000,
        ge=1,
        le=10000,
        description="Maximum number of issues to import",
    )


class JiraImportResponse(BaseModel):
    project_key: str = Field(description="Jira project key")
    issues_imported: int = Field(description="Number of issues imported")
    bugs: int = Field(default=0, description="Number of bug-type issues")
    features: int = Field(default=0, description="Number of feature-type issues")
    chores: int = Field(default=0, description="Number of chore-type issues")
    message: str = Field(default="", description="Status message")


# ---------------------------------------------------------------------------
# In-memory credential store (MVP — Phase 3 will use encrypted storage)
# ---------------------------------------------------------------------------

_jira_credentials: dict[str, dict] = {}  # user_id -> {base_url, email, api_token}


def _get_adapter(container: Container, user_id: str):
    """Retrieve a JiraAdapter for the authenticated user.

    Uses credentials stored from a prior /connect call if no adapter is
    pre-configured on the container.
    """
    # Prefer container-level adapter (set via env vars)
    adapter = getattr(container, "jira_adapter", None)
    if adapter is not None:
        return adapter

    # Fall back to user-stored credentials
    creds = _jira_credentials.get(user_id)
    if creds is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Jira not connected. Call POST /api/connectors/jira/connect "
                "with valid credentials first."
            ),
        )

    from infrastructure.adapters.jira_adapter import JiraAdapter
    return JiraAdapter(
        base_url=creds["base_url"],
        email=creds["email"],
        api_token=creds["api_token"],
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/connect",
    response_model=JiraConnectResponse,
    summary="Connect Jira instance",
    description="Validate Jira Cloud credentials and store them for subsequent API calls.",
)
async def connect_jira(
    body: JiraConnectRequest,
    container: Annotated[Container, Depends(get_container)],
    current_user: Annotated[UserInfo, Depends(get_current_user)],
) -> JiraConnectResponse:
    """Accept Jira credentials, validate connectivity, and store for the session."""
    from infrastructure.adapters.jira_adapter import JiraAdapter

    adapter = JiraAdapter(
        base_url=body.base_url,
        email=body.email,
        api_token=body.api_token,
    )

    try:
        server_info = await adapter.validate_connection()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        )
    except Exception as exc:
        logger.exception("Jira connect failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to connect to Jira: {exc}",
        )

    # Store credentials for subsequent requests
    _jira_credentials[current_user.user_id] = {
        "base_url": body.base_url,
        "email": body.email,
        "api_token": body.api_token,
    }

    logger.info(
        "Jira connected: user=%s instance=%s",
        current_user.user_id, body.base_url,
    )

    return JiraConnectResponse(
        connected=True,
        base_url=server_info.get("base_url", body.base_url),
        version=server_info.get("version", ""),
        server_title=server_info.get("server_title", ""),
        message="Jira connected successfully.",
    )


@router.get(
    "/projects",
    response_model=JiraProjectListResponse,
    summary="List Jira projects",
    description="List all Jira projects accessible to the connected user.",
)
async def list_projects(
    container: Annotated[Container, Depends(get_container)],
    current_user: Annotated[UserInfo, Depends(get_current_user)],
) -> JiraProjectListResponse:
    """List all accessible Jira projects."""
    adapter = _get_adapter(container, current_user.user_id)

    try:
        project_infos = await adapter.get_projects()

        projects = [
            JiraProjectResponse(
                key=p.key,
                name=p.name,
                project_type=p.project_type,
                lead=p.lead,
            )
            for p in project_infos
        ]

        return JiraProjectListResponse(
            projects=projects, total=len(projects)
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        )
    except Exception as exc:
        logger.exception("Failed to list Jira projects")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to retrieve Jira projects: {exc}",
        )


@router.post(
    "/projects/{project_key}/import",
    response_model=JiraImportResponse,
    summary="Import Jira issues",
    description=(
        "Import issues from a Jira project for P2 task correlation analysis. "
        "Maps issue types to bug/feature/chore taxonomy and calculates "
        "resolution metrics."
    ),
)
async def import_project_issues(
    project_key: str,
    body: JiraImportRequest | None = None,
    container: Annotated[Container, Depends(get_container)] = None,
    current_user: Annotated[UserInfo, Depends(get_current_user)] = None,
) -> JiraImportResponse:
    """Import issues from a Jira project and convert to JiraIssue entities."""
    adapter = _get_adapter(container, current_user.user_id)

    jql_filter = body.jql_filter if body else None
    max_results = body.max_results if body else 1000

    try:
        raw_issues = await adapter.get_project_issues(
            project_key,
            max_results=max_results,
            jql_filter=jql_filter,
        )

        # Convert raw dicts to JiraIssue domain entities for taxonomy classification
        jira_issues: list[JiraIssue] = []
        for raw in raw_issues:
            try:
                issue = JiraIssue(
                    key=raw["key"],
                    issue_type=raw["issue_type"],
                    status=raw["status"],
                    summary=raw["summary"],
                    created_at=raw["created_at"] or datetime.now(UTC),
                    resolved_at=raw.get("resolved_at"),
                    assignee=raw.get("assignee"),
                    story_points=raw.get("story_points"),
                    sprint=raw.get("sprint"),
                    labels=raw.get("labels", ()),
                )
                jira_issues.append(issue)
            except (KeyError, TypeError) as exc:
                logger.warning("Skipping malformed Jira issue: %s", exc)
                continue

        bugs = sum(1 for i in jira_issues if i.is_bug)
        features = sum(1 for i in jira_issues if i.is_feature)
        chores = sum(1 for i in jira_issues if i.is_chore)

        logger.info(
            "Imported %d issues from Jira project %s (bugs=%d, features=%d, chores=%d)",
            len(jira_issues), project_key, bugs, features, chores,
        )

        return JiraImportResponse(
            project_key=project_key,
            issues_imported=len(jira_issues),
            bugs=bugs,
            features=features,
            chores=chores,
            message=(
                f"Successfully imported {len(jira_issues)} issues from {project_key}. "
                f"Taxonomy: {bugs} bugs, {features} features, {chores} chores."
            ),
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        )
    except Exception as exc:
        logger.exception("Jira import failed for project %s", project_key)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Import failed: {exc}",
        )
