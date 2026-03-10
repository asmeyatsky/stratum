"""
SonarQubePort — Port for SonarQube/SonarCloud static analysis data.

Architectural Intent:
    Provides access to SonarQube issues, metrics, and quality gate status
    for P6 enrichment. Adapters may connect to self-hosted SonarQube instances
    or SonarCloud.

Adapters: SonarQube Web API client (REST).
"""

from __future__ import annotations

from typing import Protocol

from domain.entities.sonar_issue import SonarIssue


class SonarQubePort(Protocol):
    async def get_issues(
        self, project_key: str, *, severities: str | None = None, page: int = 1
    ) -> list[SonarIssue]:
        """Retrieve issues for a SonarQube project.

        Args:
            project_key: SonarQube project key (e.g., ``my-org:my-repo``).
            severities: Comma-separated severity filter (e.g., ``"CRITICAL,MAJOR"``).
            page: Page number for paginated results (1-based).

        Returns:
            List of :class:`SonarIssue` entities for the requested page.
        """
        ...

    async def get_metrics(
        self,
        project_key: str,
        metric_keys: tuple[str, ...] = (
            "complexity",
            "duplicated_lines_density",
            "coverage",
            "ncloc",
            "sqale_index",
        ),
    ) -> dict[str, float]:
        """Retrieve project-level metrics from SonarQube.

        Args:
            project_key: SonarQube project key.
            metric_keys: Tuple of metric keys to fetch.

        Returns:
            Dict mapping metric key to its numeric value.
        """
        ...

    async def get_quality_gate_status(self, project_key: str) -> dict[str, str]:
        """Retrieve the quality gate status for a project.

        Args:
            project_key: SonarQube project key.

        Returns:
            Dict with at least ``"status"`` key (``"OK"``, ``"WARN"``, ``"ERROR"``),
            plus condition-level details.
        """
        ...
