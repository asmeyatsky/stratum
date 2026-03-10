"""
GitHubPort — Port for GitHub repository data retrieval.

Adapters: GitHub GraphQL API client.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from domain.entities.commit import Commit


@dataclass(frozen=True)
class RepositoryInfo:
    """Lightweight repository metadata returned by the GitHub port."""

    owner: str
    name: str
    full_name: str
    description: str
    default_branch: str
    language: str | None
    stars: int
    forks: int
    open_issues: int
    is_private: bool
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class PullRequestInfo:
    """Pull request summary returned by the GitHub port."""

    number: int
    title: str
    state: str  # OPEN, CLOSED, MERGED
    author: str
    created_at: str
    merged_at: str | None
    additions: int
    deletions: int
    changed_files: int
    labels: tuple[str, ...]


@dataclass(frozen=True)
class ContributorInfo:
    """Contributor statistics returned by the GitHub port."""

    login: str
    name: str | None
    email: str | None
    commit_count: int
    additions: int
    deletions: int


class GitHubPort(Protocol):
    """Port for interacting with GitHub repository data.

    Implementations must be fully async and return domain-compatible
    data structures.
    """

    async def get_repository_info(self, owner: str, repo: str) -> RepositoryInfo:
        """Retrieve metadata for a single repository."""
        ...

    async def get_commit_history(
        self, owner: str, repo: str, *, since: str | None = None, until: str | None = None
    ) -> list[Commit]:
        """Retrieve commit history and convert to domain Commit entities.

        Args:
            owner: Repository owner (user or org).
            repo: Repository name.
            since: ISO-8601 timestamp — only return commits after this date.
            until: ISO-8601 timestamp — only return commits before this date.

        Returns:
            Chronologically ordered list of Commit entities (oldest first).
        """
        ...

    async def get_contributors(self, owner: str, repo: str) -> list[ContributorInfo]:
        """Retrieve contributor statistics for a repository."""
        ...

    async def get_pull_requests(
        self, owner: str, repo: str, *, state: str = "all", limit: int = 100
    ) -> list[PullRequestInfo]:
        """Retrieve pull request metadata.

        Args:
            owner: Repository owner.
            repo: Repository name.
            state: Filter by state — ``"open"``, ``"closed"``, ``"merged"``, or ``"all"``.
            limit: Maximum number of PRs to return.
        """
        ...

    async def get_org_repositories(self, org: str) -> list[RepositoryInfo]:
        """List all repositories in a GitHub organisation."""
        ...
