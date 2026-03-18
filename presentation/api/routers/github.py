"""
GitHub connector router — connect, browse, and import from GitHub.

Architectural Intent:
    Thin HTTP adapter for the GitHub connector. Accepts GitHub tokens,
    validates them, lists accessible repositories and organisations, and
    triggers commit history import via the GitHubAdapter (which implements
    the GitHubPort).

    No business logic lives here — all data retrieval is delegated to the
    adapter and domain layers.
"""

from __future__ import annotations

import logging
from datetime import datetime, UTC
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from infrastructure.config.dependency_injection import Container
from presentation.api.dependencies import get_container, get_current_user
from presentation.api.schemas import UserInfo

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/connectors/github", tags=["github"])


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class GitHubConnectRequest(BaseModel):
    token: str = Field(description="GitHub personal access token or OAuth token")


class GitHubConnectResponse(BaseModel):
    connected: bool = Field(description="Whether the connection succeeded")
    login: str = Field(default="", description="Authenticated GitHub user login")
    name: str = Field(default="", description="Authenticated GitHub user display name")
    avatar_url: str = Field(default="", description="User avatar URL")
    message: str = Field(default="", description="Status message")


class GitHubRepoResponse(BaseModel):
    owner: str = Field(description="Repository owner")
    name: str = Field(description="Repository name")
    full_name: str = Field(description="Full owner/name")
    description: str = Field(default="", description="Repository description")
    default_branch: str = Field(default="main", description="Default branch")
    language: str | None = Field(default=None, description="Primary language")
    stars: int = Field(default=0, description="Star count")
    forks: int = Field(default=0, description="Fork count")
    open_issues: int = Field(default=0, description="Open issue count")
    is_private: bool = Field(default=False, description="Private repository flag")
    created_at: str = Field(default="", description="Creation timestamp")
    updated_at: str = Field(default="", description="Last update timestamp")


class GitHubRepoListResponse(BaseModel):
    repositories: list[GitHubRepoResponse] = Field(description="List of repositories")
    total: int = Field(description="Total count")


class GitHubImportRequest(BaseModel):
    since: str | None = Field(
        default=None, description="Import commits after this ISO-8601 timestamp"
    )
    until: str | None = Field(
        default=None, description="Import commits before this ISO-8601 timestamp"
    )


class GitHubImportResponse(BaseModel):
    owner: str = Field(description="Repository owner")
    repo: str = Field(description="Repository name")
    commits_imported: int = Field(description="Number of commits imported")
    message: str = Field(default="", description="Status message")


class GitHubPRResponse(BaseModel):
    number: int = Field(description="PR number")
    title: str = Field(description="PR title")
    state: str = Field(description="PR state")
    author: str = Field(description="PR author")
    created_at: str = Field(description="Creation timestamp")
    merged_at: str | None = Field(default=None, description="Merge timestamp")
    additions: int = Field(default=0)
    deletions: int = Field(default=0)
    changed_files: int = Field(default=0)
    labels: list[str] = Field(default_factory=list)


class GitHubContributorResponse(BaseModel):
    login: str = Field(description="GitHub login")
    name: str | None = Field(default=None, description="Display name")
    commit_count: int = Field(default=0, description="Number of commits")


# ---------------------------------------------------------------------------
# In-memory token store (MVP — Phase 3 will use encrypted storage)
# ---------------------------------------------------------------------------

_github_tokens: dict[str, str] = {}  # user_id -> token


def _get_adapter(container: Container, user_id: str):
    """Retrieve a GitHubAdapter for the authenticated user.

    Uses the token stored from a prior /connect call if no adapter is
    pre-configured on the container.
    """
    # Prefer container-level adapter (set via env var)
    adapter = getattr(container, "github_adapter", None)
    if adapter is not None:
        return adapter

    # Fall back to user-stored token
    token = _github_tokens.get(user_id)
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "GitHub not connected. Call POST /api/connectors/github/connect "
                "with a valid token first."
            ),
        )

    from infrastructure.adapters.github_adapter import GitHubAdapter
    return GitHubAdapter(token=token)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/connect",
    response_model=GitHubConnectResponse,
    summary="Connect GitHub account",
    description="Validate a GitHub token and store it for subsequent API calls.",
)
async def connect_github(
    body: GitHubConnectRequest,
    container: Annotated[Container, Depends(get_container)],
    current_user: Annotated[UserInfo, Depends(get_current_user)],
) -> GitHubConnectResponse:
    """Accept a GitHub token, validate it, and store for the session."""
    from infrastructure.adapters.github_adapter import GitHubAdapter

    adapter = GitHubAdapter(token=body.token)

    try:
        user_info = await adapter.validate_token()
    except ValueError as exc:
        logger.exception("GitHub connect failed — invalid credentials")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="GitHub authentication failed. Check your token.",
        )
    except Exception as exc:
        logger.exception("GitHub connect failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to connect to GitHub. Check server logs for details.",
        )

    # Store token for subsequent requests
    _github_tokens[current_user.user_id] = body.token

    logger.info(
        "GitHub connected: user=%s github_login=%s",
        current_user.user_id, user_info.get("login"),
    )

    return GitHubConnectResponse(
        connected=True,
        login=user_info.get("login", ""),
        name=user_info.get("name", ""),
        avatar_url=user_info.get("avatar_url", ""),
        message="GitHub connected successfully.",
    )


@router.get(
    "/repos",
    response_model=GitHubRepoListResponse,
    summary="List accessible repositories",
    description="List repositories accessible to the connected GitHub token.",
)
async def list_repos(
    container: Annotated[Container, Depends(get_container)],
    current_user: Annotated[UserInfo, Depends(get_current_user)],
) -> GitHubRepoListResponse:
    """List repositories the authenticated GitHub user can access."""
    adapter = _get_adapter(container, current_user.user_id)

    try:
        # Use REST API to list user repos (GraphQL viewer query)
        user_info = await adapter.validate_token()
        login = user_info.get("login", "")
        if not login:
            raise ValueError("Could not determine GitHub login")

        # Fetch user's repositories via REST
        repos_data = await adapter._rest_request(
            "GET",
            f"https://api.github.com/user/repos",
            params={"per_page": 100, "sort": "updated", "type": "all"},
        )

        if repos_data is None or not isinstance(repos_data, list):
            return GitHubRepoListResponse(repositories=[], total=0)

        repositories = []
        for r in repos_data:
            owner_data = r.get("owner", {})
            repositories.append(
                GitHubRepoResponse(
                    owner=owner_data.get("login", ""),
                    name=r.get("name", ""),
                    full_name=r.get("full_name", ""),
                    description=r.get("description") or "",
                    default_branch=r.get("default_branch", "main"),
                    language=r.get("language"),
                    stars=r.get("stargazers_count", 0),
                    forks=r.get("forks_count", 0),
                    open_issues=r.get("open_issues_count", 0),
                    is_private=r.get("private", False),
                    created_at=r.get("created_at", ""),
                    updated_at=r.get("updated_at", ""),
                )
            )

        return GitHubRepoListResponse(
            repositories=repositories, total=len(repositories)
        )

    except HTTPException:
        raise
    except ValueError as exc:
        logger.exception("Failed to list GitHub repos — invalid credentials")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="GitHub authentication failed. Check your token.",
        )
    except Exception as exc:
        logger.exception("Failed to list GitHub repos")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to retrieve repositories from GitHub. Check server logs for details.",
        )


@router.post(
    "/repos/{owner}/{repo}/import",
    response_model=GitHubImportResponse,
    summary="Import git history from GitHub",
    description=(
        "Import commit history from a GitHub repository. Creates domain "
        "Commit entities via the GitHub API instead of requiring a git log file."
    ),
)
async def import_repo(
    owner: str,
    repo: str,
    body: GitHubImportRequest | None = None,
    container: Annotated[Container, Depends(get_container)] = None,
    current_user: Annotated[UserInfo, Depends(get_current_user)] = None,
) -> GitHubImportResponse:
    """Import git history from GitHub using the GraphQL API."""
    adapter = _get_adapter(container, current_user.user_id)

    since = body.since if body else None
    until = body.until if body else None

    try:
        commits = await adapter.get_commit_history(
            owner, repo, since=since, until=until
        )

        logger.info(
            "Imported %d commits from GitHub %s/%s", len(commits), owner, repo
        )

        return GitHubImportResponse(
            owner=owner,
            repo=repo,
            commits_imported=len(commits),
            message=f"Successfully imported {len(commits)} commits from {owner}/{repo}.",
        )

    except ValueError as exc:
        logger.exception("GitHub import failed — value error for %s/%s", owner, repo)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository not found or inaccessible.",
        )
    except ConnectionError as exc:
        logger.exception("GitHub import failed — connection error for %s/%s", owner, repo)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to connect to GitHub. Check server logs for details.",
        )
    except Exception as exc:
        logger.exception("GitHub import failed for %s/%s", owner, repo)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Import failed. Check server logs for details.",
        )


@router.get(
    "/orgs/{org}/repos",
    response_model=GitHubRepoListResponse,
    summary="List organisation repositories",
    description=(
        "List all repositories in a GitHub organisation. Useful for CTO "
        "onboarding scenarios where the full technology landscape needs scanning."
    ),
)
async def list_org_repos(
    org: str,
    container: Annotated[Container, Depends(get_container)],
    current_user: Annotated[UserInfo, Depends(get_current_user)],
) -> GitHubRepoListResponse:
    """List all repositories in a GitHub organisation via GraphQL."""
    adapter = _get_adapter(container, current_user.user_id)

    try:
        repo_infos = await adapter.get_org_repositories(org)

        repositories = [
            GitHubRepoResponse(
                owner=ri.owner,
                name=ri.name,
                full_name=ri.full_name,
                description=ri.description,
                default_branch=ri.default_branch,
                language=ri.language,
                stars=ri.stars,
                forks=ri.forks,
                open_issues=ri.open_issues,
                is_private=ri.is_private,
                created_at=ri.created_at,
                updated_at=ri.updated_at,
            )
            for ri in repo_infos
        ]

        return GitHubRepoListResponse(
            repositories=repositories, total=len(repositories)
        )

    except ValueError as exc:
        logger.exception("Failed to list repos for org %s — not found", org)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organisation not found or inaccessible.",
        )
    except Exception as exc:
        logger.exception("Failed to list repos for org %s", org)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to retrieve organisation repositories. Check server logs for details.",
        )
