"""
JiraPort — Port for Jira project and issue data retrieval.

Adapters: Jira Cloud REST API v3 client.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class JiraProjectInfo:
    """Lightweight Jira project metadata."""

    key: str
    name: str
    project_type: str
    lead: str | None


@dataclass(frozen=True)
class JiraSprintInfo:
    """Jira sprint metadata."""

    sprint_id: int
    name: str
    state: str  # active, closed, future
    start_date: str | None
    end_date: str | None
    complete_date: str | None


class JiraPort(Protocol):
    """Port for interacting with Jira project management data.

    Implementations must be fully async and return structured data
    suitable for P2 task correlation analysis.
    """

    async def get_project_issues(
        self,
        project_key: str,
        *,
        max_results: int = 1000,
        jql_filter: str | None = None,
    ) -> list[dict]:
        """Retrieve issues from a Jira project.

        Returns a list of dictionaries with keys: key, issue_type, status,
        summary, created_at, resolved_at, assignee, story_points, sprint, labels.

        Args:
            project_key: Jira project key (e.g. ``"PLAT"``).
            max_results: Maximum number of issues to retrieve.
            jql_filter: Optional additional JQL filter clause.
        """
        ...

    async def get_issue_types(self, project_key: str) -> list[dict]:
        """Retrieve issue type definitions for a project.

        Returns a list of dictionaries with keys: id, name, description, subtask.
        """
        ...

    async def get_sprints(self, board_id: int) -> list[JiraSprintInfo]:
        """Retrieve sprints from a Jira board.

        Args:
            board_id: Jira board ID (Scrum or Kanban).
        """
        ...
