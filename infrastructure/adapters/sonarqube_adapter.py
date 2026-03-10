"""
SonarQubeAdapter — Infrastructure adapter implementing SonarQubePort.

Architectural Intent:
    Queries SonarQube (self-hosted) or SonarCloud REST APIs to retrieve
    issues, metrics, and quality gate status. Translates JSON responses
    into domain SonarIssue entities.

    This adapter handles only HTTP transport, response parsing, and
    authentication. No risk scoring or business logic belongs here —
    that is the domain's responsibility.

Design Decisions:
    - Uses httpx async client for non-blocking HTTP.
    - Authentication via user token (SonarQube) or bearer token (SonarCloud).
    - SonarCloud uses a different base URL (sonarcloud.io) and requires
      an ``organization`` parameter on most endpoints.
    - Pagination support for issues endpoint (SonarQube uses 1-based pages
      with configurable page size, max 500 per page).
    - Failed requests are retried up to 3 times with exponential backoff.
    - Partial failures are logged and return empty results rather than
      raising exceptions, allowing the analysis pipeline to proceed.

API References:
    - SonarQube Web API: https://<host>/api
    - SonarCloud API:    https://sonarcloud.io/api
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

import httpx

from domain.entities.sonar_issue import SonarIssue

logger = logging.getLogger(__name__)

_SONARQUBE_DEFAULT_URL = "http://localhost:9000"
_SONARCLOUD_URL = "https://sonarcloud.io"

_MAX_RETRIES = 3
_RETRY_BACKOFF_BASE = 2.0  # seconds
_PAGE_SIZE = 100  # max items per page for issues endpoint (SonarQube max: 500)


@dataclass
class SonarQubeAdapter:
    """Queries SonarQube/SonarCloud APIs for static analysis data.

    Implements :class:`domain.ports.SonarQubePort`.

    Args:
        token: User token (SonarQube) or bearer token (SonarCloud).
        base_url: SonarQube server URL. Defaults to ``http://localhost:9000``.
            Use ``https://sonarcloud.io`` for SonarCloud.
        organization: SonarCloud organization key. Required for SonarCloud,
            ignored for self-hosted SonarQube.
        timeout: HTTP request timeout in seconds.
    """

    token: str
    base_url: str = _SONARQUBE_DEFAULT_URL
    organization: str | None = None
    timeout: float = 30.0
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False, repr=False)

    @property
    def _is_sonarcloud(self) -> bool:
        return "sonarcloud.io" in self.base_url

    # ------------------------------------------------------------------
    # Port implementation
    # ------------------------------------------------------------------

    async def get_issues(
        self, project_key: str, *, severities: str | None = None, page: int = 1
    ) -> list[SonarIssue]:
        """Retrieve issues for a SonarQube/SonarCloud project.

        Args:
            project_key: SonarQube project key.
            severities: Comma-separated severity filter (e.g., ``"CRITICAL,MAJOR"``).
            page: 1-based page number.

        Returns:
            List of :class:`SonarIssue` entities for the requested page.
        """
        params: dict[str, str | int] = {
            "componentKeys": project_key,
            "ps": _PAGE_SIZE,
            "p": page,
        }
        if severities:
            params["severities"] = severities
        if self.organization:
            params["organization"] = self.organization

        data = await self._request("api/issues/search", params)
        if data is None:
            return []

        return self._parse_issues(data)

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
        params: dict[str, str] = {
            "component": project_key,
            "metricKeys": ",".join(metric_keys),
        }
        if self.organization:
            params["organization"] = self.organization

        data = await self._request("api/measures/component", params)
        if data is None:
            return {}

        return self._parse_metrics(data)

    async def get_quality_gate_status(self, project_key: str) -> dict[str, str]:
        """Retrieve the quality gate status for a project.

        Args:
            project_key: SonarQube project key.

        Returns:
            Dict with ``"status"`` (``"OK"``, ``"WARN"``, ``"ERROR"``),
            and ``"conditions"`` detail entries.
        """
        params: dict[str, str] = {"projectKey": project_key}
        if self.organization:
            params["organization"] = self.organization

        data = await self._request("api/qualitygates/project_status", params)
        if data is None:
            return {"status": "UNKNOWN"}

        return self._parse_quality_gate(data)

    # ------------------------------------------------------------------
    # HTTP transport
    # ------------------------------------------------------------------

    def _build_headers(self) -> dict[str, str]:
        """Build request headers with token-based authentication.

        SonarQube user tokens use HTTP Basic auth with the token as the
        username and an empty password. SonarCloud uses the same scheme.
        """
        return {
            "Accept": "application/json",
            "User-Agent": "Stratum/1.0 (code-intelligence-platform)",
        }

    def _build_auth(self) -> httpx.BasicAuth:
        """SonarQube/SonarCloud tokens use Basic auth (token as username, blank password)."""
        return httpx.BasicAuth(username=self.token, password="")

    async def _request(
        self, endpoint: str, params: dict[str, str | int]
    ) -> dict | None:
        """Execute an API request with retry logic."""
        url = f"{self.base_url.rstrip('/')}/{endpoint}"
        headers = self._build_headers()
        auth = self._build_auth()

        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.get(
                        url,
                        params=params,
                        headers=headers,
                        auth=auth,
                    )

                if response.status_code == 200:
                    return response.json()

                if response.status_code == 401:
                    logger.error(
                        "SonarQube authentication failed (401). Check token validity."
                    )
                    return None

                if response.status_code == 404:
                    logger.info(
                        "SonarQube returned 404 for %s with params %s",
                        endpoint,
                        params,
                    )
                    return None

                logger.warning(
                    "SonarQube API returned %d on attempt %d/%d for %s: %s",
                    response.status_code,
                    attempt,
                    _MAX_RETRIES,
                    endpoint,
                    response.text[:200],
                )

            except httpx.TimeoutException:
                logger.warning(
                    "SonarQube request timed out on attempt %d/%d for %s",
                    attempt,
                    _MAX_RETRIES,
                    endpoint,
                )
            except httpx.HTTPError as exc:
                logger.warning(
                    "SonarQube HTTP error on attempt %d/%d for %s: %s",
                    attempt,
                    _MAX_RETRIES,
                    endpoint,
                    exc,
                )

            if attempt < _MAX_RETRIES:
                backoff = _RETRY_BACKOFF_BASE ** attempt
                logger.info("Retrying SonarQube request in %.1f seconds...", backoff)
                await asyncio.sleep(backoff)

        logger.error(
            "SonarQube request failed after %d attempts for %s",
            _MAX_RETRIES,
            endpoint,
        )
        return None

    # ------------------------------------------------------------------
    # Response parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_issues(data: dict) -> list[SonarIssue]:
        """Parse the ``api/issues/search`` JSON response into SonarIssue entities."""
        issues: list[SonarIssue] = []

        for item in data.get("issues", []):
            try:
                issue = SonarIssue(
                    rule_key=item.get("rule", ""),
                    severity=item.get("severity", "INFO"),
                    component=item.get("component", ""),
                    message=item.get("message", ""),
                    effort=item.get("effort", item.get("debt", "")),
                    type=item.get("type", "CODE_SMELL"),
                    line=item.get("line"),
                    status=item.get("status", "OPEN"),
                )
                issues.append(issue)
            except (KeyError, TypeError) as exc:
                logger.warning("Failed to parse SonarQube issue: %s — %s", item, exc)

        logger.info(
            "Parsed %d issues from SonarQube response (total: %s)",
            len(issues),
            data.get("total", "?"),
        )
        return issues

    @staticmethod
    def _parse_metrics(data: dict) -> dict[str, float]:
        """Parse the ``api/measures/component`` JSON response into a metric dict."""
        metrics: dict[str, float] = {}

        component = data.get("component", {})
        for measure in component.get("measures", []):
            key = measure.get("metric", "")
            value = measure.get("value")
            if key and value is not None:
                try:
                    metrics[key] = float(value)
                except (ValueError, TypeError):
                    logger.warning(
                        "Non-numeric metric value for %s: %s", key, value
                    )

        logger.info("Parsed %d metrics from SonarQube response", len(metrics))
        return metrics

    @staticmethod
    def _parse_quality_gate(data: dict) -> dict[str, str]:
        """Parse the ``api/qualitygates/project_status`` JSON response."""
        project_status = data.get("projectStatus", {})
        status = project_status.get("status", "UNKNOWN")

        result: dict[str, str] = {"status": status}

        # Include individual condition results for detailed reporting
        for i, condition in enumerate(project_status.get("conditions", [])):
            metric = condition.get("metricKey", f"metric_{i}")
            cond_status = condition.get("status", "UNKNOWN")
            actual = condition.get("actualValue", "N/A")
            threshold = condition.get("errorThreshold", "N/A")
            result[f"condition_{metric}"] = (
                f"{cond_status} (actual: {actual}, threshold: {threshold})"
            )

        logger.info("Quality gate status: %s", status)
        return result
