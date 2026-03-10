"""
JiraAdapter — Infrastructure adapter implementing JiraPort.

Architectural Intent:
    Queries the Jira Cloud REST API v3 to retrieve project issues, issue
    types, and sprint data. Translates Jira API responses into domain-
    compatible data structures and JiraIssue entities for P2 task
    correlation analysis.

    This adapter handles only HTTP transport, response parsing, rate
    limiting, and pagination. No business logic or risk scoring belongs
    here — that is the domain's responsibility.

Design Decisions:
    - Uses httpx async client for non-blocking HTTP.
    - Authentication via API token (Basic auth with email:token).
    - Pagination via startAt/maxResults (Jira's standard mechanism).
    - Issue type taxonomy mapping (bug/feature/chore) is done at the
      entity level, not here.
    - Rate limit handling via Retry-After header inspection.
    - Failed requests are retried up to 3 times with exponential backoff.
    - Sprint data comes from the Jira Agile REST API (/rest/agile/1.0/).
"""

from __future__ import annotations

import asyncio
import base64
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

import httpx

from domain.entities.jira_issue import JiraIssue
from domain.ports.jira_port import JiraProjectInfo, JiraSprintInfo

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3
_RETRY_BACKOFF_BASE = 2.0
_DEFAULT_PAGE_SIZE = 50  # Jira default maxResults


@dataclass
class JiraAdapter:
    """Queries the Jira Cloud REST API v3 for project and issue data.

    Implements :class:`domain.ports.JiraPort`.

    Args:
        base_url: Jira Cloud instance URL (e.g. ``https://yourorg.atlassian.net``).
        email: User email address for API authentication.
        api_token: Jira API token (generated from id.atlassian.com).
        timeout: HTTP request timeout in seconds.
    """

    base_url: str
    email: str
    api_token: str
    timeout: float = 30.0
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False, repr=False)

    def __post_init__(self) -> None:
        # Normalise base URL — strip trailing slash
        self.base_url = self.base_url.rstrip("/")

    # ------------------------------------------------------------------
    # Port implementation
    # ------------------------------------------------------------------

    async def get_project_issues(
        self,
        project_key: str,
        *,
        max_results: int = 1000,
        jql_filter: str | None = None,
    ) -> list[dict]:
        """Retrieve issues from a Jira project using JQL search.

        Returns a list of dictionaries with normalised keys suitable for
        constructing JiraIssue entities.
        """
        jql = f"project = {project_key} ORDER BY created DESC"
        if jql_filter:
            jql = f"project = {project_key} AND ({jql_filter}) ORDER BY created DESC"

        issues: list[dict] = []
        start_at = 0

        while start_at < max_results:
            page_size = min(_DEFAULT_PAGE_SIZE, max_results - start_at)
            url = f"{self.base_url}/rest/api/3/search"
            params = {
                "jql": jql,
                "startAt": start_at,
                "maxResults": page_size,
                "fields": (
                    "summary,issuetype,status,created,resolutiondate,"
                    "assignee,story_points,customfield_10016,"  # story points (common field IDs)
                    "sprint,customfield_10020,"  # sprint (common field ID)
                    "labels"
                ),
            }

            data = await self._request("GET", url, params=params)
            if data is None:
                break

            raw_issues = data.get("issues", [])
            if not raw_issues:
                break

            for raw in raw_issues:
                parsed = _parse_issue(raw)
                if parsed is not None:
                    issues.append(parsed)

            total = data.get("total", 0)
            start_at += len(raw_issues)

            if start_at >= total:
                break

        logger.info(
            "Retrieved %d issues from Jira project %s", len(issues), project_key
        )
        return issues

    async def get_issue_types(self, project_key: str) -> list[dict]:
        """Retrieve issue type definitions for a project."""
        url = f"{self.base_url}/rest/api/3/project/{project_key}"
        data = await self._request("GET", url)
        if data is None:
            return []

        issue_types = []
        for it in data.get("issueTypes", []):
            issue_types.append({
                "id": it.get("id", ""),
                "name": it.get("name", ""),
                "description": it.get("description", ""),
                "subtask": it.get("subtask", False),
            })

        logger.info(
            "Retrieved %d issue types for Jira project %s",
            len(issue_types), project_key,
        )
        return issue_types

    async def get_sprints(self, board_id: int) -> list[JiraSprintInfo]:
        """Retrieve sprints from a Jira Agile board."""
        sprints: list[JiraSprintInfo] = []
        start_at = 0
        is_last = False

        while not is_last:
            url = f"{self.base_url}/rest/agile/1.0/board/{board_id}/sprint"
            params = {"startAt": start_at, "maxResults": _DEFAULT_PAGE_SIZE}

            data = await self._request("GET", url, params=params)
            if data is None:
                break

            is_last = data.get("isLast", True)

            for item in data.get("values", []):
                sprints.append(
                    JiraSprintInfo(
                        sprint_id=item.get("id", 0),
                        name=item.get("name", ""),
                        state=item.get("state", "unknown"),
                        start_date=item.get("startDate"),
                        end_date=item.get("endDate"),
                        complete_date=item.get("completeDate"),
                    )
                )

            start_at += len(data.get("values", []))

        logger.info(
            "Retrieved %d sprints from Jira board %d", len(sprints), board_id
        )
        return sprints

    # ------------------------------------------------------------------
    # Connection validation (used by connect endpoint)
    # ------------------------------------------------------------------

    async def validate_connection(self) -> dict:
        """Validate the configured credentials and return server info.

        Returns:
            Dictionary with ``baseUrl``, ``version``, ``serverTitle`` keys.

        Raises:
            ValueError: If the credentials are invalid or the server is unreachable.
        """
        url = f"{self.base_url}/rest/api/3/serverInfo"
        data = await self._request("GET", url)
        if data is None:
            raise ValueError(
                "Jira connection validation failed — check URL and credentials"
            )
        return {
            "base_url": data.get("baseUrl", self.base_url),
            "version": data.get("version", "unknown"),
            "server_title": data.get("serverTitle", ""),
        }

    async def get_projects(self) -> list[JiraProjectInfo]:
        """List all accessible Jira projects."""
        projects: list[JiraProjectInfo] = []
        start_at = 0

        while True:
            url = f"{self.base_url}/rest/api/3/project/search"
            params = {"startAt": start_at, "maxResults": _DEFAULT_PAGE_SIZE}

            data = await self._request("GET", url, params=params)
            if data is None:
                break

            raw_projects = data.get("values", [])
            if not raw_projects:
                break

            for p in raw_projects:
                lead = p.get("lead", {})
                projects.append(
                    JiraProjectInfo(
                        key=p.get("key", ""),
                        name=p.get("name", ""),
                        project_type=p.get("projectTypeKey", ""),
                        lead=lead.get("displayName") if lead else None,
                    )
                )

            total = data.get("total", 0)
            start_at += len(raw_projects)
            if start_at >= total:
                break

        logger.info("Retrieved %d Jira projects", len(projects))
        return projects

    # ------------------------------------------------------------------
    # HTTP transport
    # ------------------------------------------------------------------

    def _build_headers(self) -> dict[str, str]:
        """Build request headers with Basic auth (email:api_token)."""
        credentials = base64.b64encode(
            f"{self.email}:{self.api_token}".encode()
        ).decode()
        return {
            "Authorization": f"Basic {credentials}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "Stratum/1.0 (code-intelligence-platform)",
        }

    async def _request(
        self,
        method: str,
        url: str,
        *,
        params: dict | None = None,
        json_body: dict | None = None,
    ) -> dict | None:
        """Execute a Jira REST API request with retry and rate limit handling."""
        headers = self._build_headers()

        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.request(
                        method,
                        url,
                        params=params,
                        json=json_body,
                        headers=headers,
                    )

                if response.status_code in (200, 201):
                    return response.json()

                if response.status_code == 401:
                    raise ValueError(
                        "Jira authentication failed — check email and API token"
                    )

                if response.status_code == 403:
                    raise ValueError(
                        "Jira access forbidden — check API token permissions"
                    )

                if response.status_code == 404:
                    logger.info("Jira REST returned 404 for %s", url)
                    return None

                if response.status_code == 429:
                    # Rate limited — respect Retry-After header
                    retry_after = response.headers.get("Retry-After", "10")
                    try:
                        wait = min(float(retry_after), 60.0)
                    except ValueError:
                        wait = 10.0
                    logger.warning(
                        "Jira rate limit hit (429). Waiting %.1f seconds. "
                        "Attempt %d/%d.",
                        wait, attempt, _MAX_RETRIES,
                    )
                    await asyncio.sleep(wait)
                    continue

                logger.warning(
                    "Jira REST returned %d on attempt %d/%d: %s",
                    response.status_code, attempt, _MAX_RETRIES,
                    response.text[:300],
                )

            except httpx.TimeoutException:
                logger.warning(
                    "Jira REST request timed out on attempt %d/%d",
                    attempt, _MAX_RETRIES,
                )
            except (ValueError, httpx.HTTPError):
                raise
            except Exception as exc:
                logger.warning(
                    "Jira REST HTTP error on attempt %d/%d: %s",
                    attempt, _MAX_RETRIES, exc,
                )

            if attempt < _MAX_RETRIES:
                backoff = _RETRY_BACKOFF_BASE ** attempt
                logger.info("Retrying Jira request in %.1f seconds...", backoff)
                await asyncio.sleep(backoff)

        logger.error(
            "Jira REST request failed after %d attempts for %s",
            _MAX_RETRIES, url,
        )
        return None


# ---------------------------------------------------------------------------
# Response parsing helpers
# ---------------------------------------------------------------------------


def _parse_issue(raw: dict) -> dict | None:
    """Parse a raw Jira issue JSON object into a normalised dictionary.

    The dictionary keys match JiraIssue constructor parameters for easy
    entity construction.
    """
    key = raw.get("key")
    if not key:
        return None

    fields = raw.get("fields", {})

    # Issue type
    issue_type_data = fields.get("issuetype", {})
    issue_type = issue_type_data.get("name", "Task")

    # Status
    status_data = fields.get("status", {})
    status = status_data.get("name", "Unknown")

    # Summary
    summary = fields.get("summary", "")

    # Timestamps
    created_at = _parse_jira_timestamp(fields.get("created"))
    resolved_at = _parse_jira_timestamp(fields.get("resolutiondate"))

    # Assignee
    assignee_data = fields.get("assignee")
    assignee = assignee_data.get("displayName") if assignee_data else None

    # Story points — try common custom field IDs
    story_points = (
        fields.get("story_points")
        or fields.get("customfield_10016")  # Jira Cloud default
        or fields.get("customfield_10028")  # alternative
    )
    if story_points is not None:
        try:
            story_points = float(story_points)
        except (ValueError, TypeError):
            story_points = None

    # Sprint — try the sprint field and common custom field
    sprint_data = fields.get("sprint") or fields.get("customfield_10020")
    sprint_name: str | None = None
    if isinstance(sprint_data, dict):
        sprint_name = sprint_data.get("name")
    elif isinstance(sprint_data, list) and sprint_data:
        # customfield_10020 returns a list of sprint objects
        latest = sprint_data[-1]
        if isinstance(latest, dict):
            sprint_name = latest.get("name")
        elif isinstance(latest, str):
            sprint_name = latest

    # Labels
    labels = tuple(fields.get("labels", []))

    return {
        "key": key,
        "issue_type": issue_type,
        "status": status,
        "summary": summary,
        "created_at": created_at,
        "resolved_at": resolved_at,
        "assignee": assignee,
        "story_points": story_points,
        "sprint": sprint_name,
        "labels": labels,
    }


def _parse_jira_timestamp(value: str | None) -> datetime | None:
    """Parse a Jira timestamp string into a timezone-aware datetime.

    Jira uses ISO-8601 format: ``2024-01-15T14:30:00.000+0100``
    """
    if not value:
        return None

    try:
        return datetime.fromisoformat(value)
    except ValueError:
        pass

    # Try stripping milliseconds and parsing
    try:
        # Handle format like "2024-01-15T14:30:00.000+0100"
        if "." in value:
            base, rest = value.rsplit(".", 1)
            # Find timezone offset in the rest
            for sep in ("+", "-"):
                if sep in rest[1:]:  # skip first char in case of negative
                    tz_idx = rest.index(sep, 1)
                    tz_part = rest[tz_idx:]
                    clean = f"{base}{tz_part}"
                    return datetime.fromisoformat(clean)
            # No timezone found — treat as UTC
            return datetime.fromisoformat(base).replace(tzinfo=timezone.utc)
        return datetime.fromisoformat(value)
    except (ValueError, IndexError):
        logger.debug("Unparseable Jira timestamp: %s", value)
        return None
