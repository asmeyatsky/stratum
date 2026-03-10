"""
GitHubAdapter — Infrastructure adapter implementing GitHubPort.

Architectural Intent:
    Queries the GitHub GraphQL API (api.github.com/graphql) to retrieve
    repository metadata, commit history, contributor stats, and pull
    request data. Translates GitHub API responses into domain entities
    and port-defined data structures.

    This adapter handles only HTTP transport, GraphQL query construction,
    response parsing, rate limiting, and pagination. No business logic
    or risk scoring belongs here — that is the domain's responsibility.

Design Decisions:
    - Uses httpx async client for non-blocking HTTP.
    - GraphQL API preferred over REST for efficient bulk data retrieval
      (fewer round-trips, field-level selection).
    - Authentication via OAuth / GitHub App token (Bearer token).
    - Rate limit handling checks X-RateLimit-Remaining headers and
      pauses proactively when approaching limits.
    - Cursor-based pagination for large result sets (commits, PRs).
    - Failed requests are retried up to 3 times with exponential backoff.
    - Contributor stats fall back to REST API v3 (GraphQL lacks this).
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

import httpx

from domain.entities.commit import Commit
from domain.entities.file_change import FileChange
from domain.ports.github_port import (
    ContributorInfo,
    PullRequestInfo,
    RepositoryInfo,
)

logger = logging.getLogger(__name__)

_GRAPHQL_URL = "https://api.github.com/graphql"
_REST_BASE_URL = "https://api.github.com"

_MAX_RETRIES = 3
_RETRY_BACKOFF_BASE = 2.0
_RATE_LIMIT_THRESHOLD = 50  # pause when remaining requests drop below this
_PAGE_SIZE = 100  # GitHub GraphQL max nodes per page


# ---------------------------------------------------------------------------
# GraphQL query templates
# ---------------------------------------------------------------------------

_REPO_INFO_QUERY = """
query($owner: String!, $name: String!) {
  repository(owner: $owner, name: $name) {
    owner { login }
    name
    nameWithOwner
    description
    defaultBranchRef { name }
    primaryLanguage { name }
    stargazerCount
    forkCount
    issues(states: OPEN) { totalCount }
    isPrivate
    createdAt
    updatedAt
  }
}
"""

_COMMIT_HISTORY_QUERY = """
query($owner: String!, $name: String!, $after: String, $since: GitTimestamp, $until: GitTimestamp) {
  repository(owner: $owner, name: $name) {
    defaultBranchRef {
      target {
        ... on Commit {
          history(first: 100, after: $after, since: $since, until: $until) {
            pageInfo {
              hasNextPage
              endCursor
            }
            nodes {
              oid
              message
              authoredDate
              author {
                email
                name
              }
              additions
              deletions
              changedFilesIfAvailable
            }
          }
        }
      }
    }
  }
}
"""

_PULL_REQUESTS_QUERY = """
query($owner: String!, $name: String!, $states: [PullRequestState!], $after: String, $first: Int!) {
  repository(owner: $owner, name: $name) {
    pullRequests(first: $first, after: $after, states: $states, orderBy: {field: CREATED_AT, direction: DESC}) {
      pageInfo {
        hasNextPage
        endCursor
      }
      nodes {
        number
        title
        state
        author { login }
        createdAt
        mergedAt
        additions
        deletions
        changedFiles
        labels(first: 10) {
          nodes { name }
        }
      }
    }
  }
}
"""

_ORG_REPOS_QUERY = """
query($org: String!, $after: String) {
  organization(login: $org) {
    repositories(first: 100, after: $after, orderBy: {field: UPDATED_AT, direction: DESC}) {
      pageInfo {
        hasNextPage
        endCursor
      }
      nodes {
        owner { login }
        name
        nameWithOwner
        description
        defaultBranchRef { name }
        primaryLanguage { name }
        stargazerCount
        forkCount
        issues(states: OPEN) { totalCount }
        isPrivate
        createdAt
        updatedAt
      }
    }
  }
}
"""


@dataclass
class GitHubAdapter:
    """Queries the GitHub GraphQL API for repository data.

    Implements :class:`domain.ports.GitHubPort`.

    Args:
        token: GitHub personal access token, OAuth token, or GitHub App
            installation token.
        timeout: HTTP request timeout in seconds.
    """

    token: str
    timeout: float = 30.0
    _last_request_time: float = field(default=0.0, init=False, repr=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False, repr=False)

    # ------------------------------------------------------------------
    # Port implementation
    # ------------------------------------------------------------------

    async def get_repository_info(self, owner: str, repo: str) -> RepositoryInfo:
        """Retrieve metadata for a single repository via GraphQL."""
        variables = {"owner": owner, "name": repo}
        data = await self._graphql_request(_REPO_INFO_QUERY, variables)

        repo_data = data.get("data", {}).get("repository")
        if repo_data is None:
            raise ValueError(f"Repository not found: {owner}/{repo}")

        return _parse_repository_info(repo_data)

    async def get_commit_history(
        self,
        owner: str,
        repo: str,
        *,
        since: str | None = None,
        until: str | None = None,
    ) -> list[Commit]:
        """Retrieve commit history via GraphQL with cursor-based pagination.

        Returns chronologically ordered Commit entities (oldest first).
        """
        commits: list[Commit] = []
        cursor: str | None = None
        has_next = True

        while has_next:
            variables: dict = {"owner": owner, "name": repo, "after": cursor}
            if since:
                variables["since"] = since
            if until:
                variables["until"] = until

            data = await self._graphql_request(_COMMIT_HISTORY_QUERY, variables)

            history = (
                data.get("data", {})
                .get("repository", {})
                .get("defaultBranchRef", {})
                .get("target", {})
                .get("history", {})
            )

            if not history:
                break

            page_info = history.get("pageInfo", {})
            has_next = page_info.get("hasNextPage", False)
            cursor = page_info.get("endCursor")

            for node in history.get("nodes", []):
                commit = _parse_commit_node(node)
                if commit is not None:
                    commits.append(commit)

        # Return oldest first for chronological analysis
        commits.sort(key=lambda c: c.timestamp)
        logger.info(
            "Retrieved %d commits from GitHub for %s/%s", len(commits), owner, repo
        )
        return commits

    async def get_contributors(self, owner: str, repo: str) -> list[ContributorInfo]:
        """Retrieve contributor statistics via REST API v3.

        The GraphQL API does not expose contributor stats, so this
        method uses the REST endpoint ``GET /repos/{owner}/{repo}/contributors``.
        """
        contributors: list[ContributorInfo] = []
        page = 1

        while True:
            url = f"{_REST_BASE_URL}/repos/{owner}/{repo}/contributors"
            params = {"per_page": 100, "page": page}

            response = await self._rest_request("GET", url, params=params)
            if response is None:
                break

            if not isinstance(response, list) or len(response) == 0:
                break

            for item in response:
                contributors.append(
                    ContributorInfo(
                        login=item.get("login", ""),
                        name=None,  # REST contributors endpoint omits name
                        email=None,
                        commit_count=item.get("contributions", 0),
                        additions=0,
                        deletions=0,
                    )
                )

            if len(response) < 100:
                break
            page += 1

        logger.info(
            "Retrieved %d contributors from GitHub for %s/%s",
            len(contributors), owner, repo,
        )
        return contributors

    async def get_pull_requests(
        self,
        owner: str,
        repo: str,
        *,
        state: str = "all",
        limit: int = 100,
    ) -> list[PullRequestInfo]:
        """Retrieve pull request metadata via GraphQL."""
        state_map = {
            "open": ["OPEN"],
            "closed": ["CLOSED"],
            "merged": ["MERGED"],
            "all": ["OPEN", "CLOSED", "MERGED"],
        }
        states = state_map.get(state.lower(), ["OPEN", "CLOSED", "MERGED"])

        pull_requests: list[PullRequestInfo] = []
        cursor: str | None = None
        has_next = True

        while has_next and len(pull_requests) < limit:
            page_size = min(_PAGE_SIZE, limit - len(pull_requests))
            variables: dict = {
                "owner": owner,
                "name": repo,
                "states": states,
                "after": cursor,
                "first": page_size,
            }

            data = await self._graphql_request(_PULL_REQUESTS_QUERY, variables)

            prs_data = (
                data.get("data", {})
                .get("repository", {})
                .get("pullRequests", {})
            )
            if not prs_data:
                break

            page_info = prs_data.get("pageInfo", {})
            has_next = page_info.get("hasNextPage", False)
            cursor = page_info.get("endCursor")

            for node in prs_data.get("nodes", []):
                pr = _parse_pull_request_node(node)
                if pr is not None:
                    pull_requests.append(pr)

        logger.info(
            "Retrieved %d pull requests from GitHub for %s/%s",
            len(pull_requests), owner, repo,
        )
        return pull_requests[:limit]

    async def get_org_repositories(self, org: str) -> list[RepositoryInfo]:
        """List all repositories in a GitHub organisation via GraphQL."""
        repositories: list[RepositoryInfo] = []
        cursor: str | None = None
        has_next = True

        while has_next:
            variables: dict = {"org": org, "after": cursor}
            data = await self._graphql_request(_ORG_REPOS_QUERY, variables)

            org_data = data.get("data", {}).get("organization", {}).get("repositories", {})
            if not org_data:
                break

            page_info = org_data.get("pageInfo", {})
            has_next = page_info.get("hasNextPage", False)
            cursor = page_info.get("endCursor")

            for node in org_data.get("nodes", []):
                repo_info = _parse_repository_info(node)
                repositories.append(repo_info)

        logger.info(
            "Retrieved %d repositories from GitHub org %s", len(repositories), org
        )
        return repositories

    # ------------------------------------------------------------------
    # Token validation (used by connect endpoint)
    # ------------------------------------------------------------------

    async def validate_token(self) -> dict:
        """Validate the configured token and return user/app information.

        Returns:
            Dictionary with ``login``, ``name``, and ``scopes`` keys.

        Raises:
            ValueError: If the token is invalid or expired.
        """
        url = f"{_REST_BASE_URL}/user"
        response = await self._rest_request("GET", url)
        if response is None:
            raise ValueError("GitHub token validation failed — invalid or expired token")
        return {
            "login": response.get("login", ""),
            "name": response.get("name", ""),
            "avatar_url": response.get("avatar_url", ""),
        }

    # ------------------------------------------------------------------
    # HTTP transport — GraphQL
    # ------------------------------------------------------------------

    async def _graphql_request(
        self, query: str, variables: dict
    ) -> dict:
        """Execute a GraphQL request with retry and rate limit handling."""
        headers = self._build_headers()
        payload = {"query": query, "variables": variables}

        for attempt in range(1, _MAX_RETRIES + 1):
            await self._check_rate_limit_pause()

            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        _GRAPHQL_URL,
                        json=payload,
                        headers=headers,
                    )

                self._update_rate_limit_state(response)

                if response.status_code == 200:
                    data = response.json()
                    errors = data.get("errors")
                    if errors:
                        error_messages = "; ".join(
                            e.get("message", "Unknown error") for e in errors
                        )
                        logger.warning("GitHub GraphQL errors: %s", error_messages)
                        if any(e.get("type") == "NOT_FOUND" for e in errors):
                            raise ValueError(f"GitHub resource not found: {error_messages}")
                    return data

                if response.status_code == 401:
                    raise ValueError(
                        "GitHub authentication failed — check token validity"
                    )

                if response.status_code == 403:
                    logger.warning(
                        "GitHub API rate limit or permission error (403). "
                        "Attempt %d/%d.",
                        attempt, _MAX_RETRIES,
                    )
                else:
                    logger.warning(
                        "GitHub GraphQL returned %d on attempt %d/%d: %s",
                        response.status_code, attempt, _MAX_RETRIES,
                        response.text[:300],
                    )

            except httpx.TimeoutException:
                logger.warning(
                    "GitHub GraphQL request timed out on attempt %d/%d",
                    attempt, _MAX_RETRIES,
                )
            except (ValueError, httpx.HTTPError):
                raise
            except Exception as exc:
                logger.warning(
                    "GitHub GraphQL HTTP error on attempt %d/%d: %s",
                    attempt, _MAX_RETRIES, exc,
                )

            if attempt < _MAX_RETRIES:
                backoff = _RETRY_BACKOFF_BASE ** attempt
                logger.info("Retrying GitHub request in %.1f seconds...", backoff)
                await asyncio.sleep(backoff)

        raise ConnectionError(
            f"GitHub GraphQL request failed after {_MAX_RETRIES} attempts"
        )

    # ------------------------------------------------------------------
    # HTTP transport — REST
    # ------------------------------------------------------------------

    async def _rest_request(
        self,
        method: str,
        url: str,
        *,
        params: dict | None = None,
        json_body: dict | None = None,
    ) -> dict | list | None:
        """Execute a REST API request with retry and rate limit handling."""
        headers = self._build_headers()

        for attempt in range(1, _MAX_RETRIES + 1):
            await self._check_rate_limit_pause()

            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.request(
                        method,
                        url,
                        params=params,
                        json=json_body,
                        headers=headers,
                    )

                self._update_rate_limit_state(response)

                if response.status_code in (200, 201):
                    return response.json()

                if response.status_code == 401:
                    raise ValueError(
                        "GitHub authentication failed — check token validity"
                    )

                if response.status_code == 404:
                    logger.info("GitHub REST returned 404 for %s", url)
                    return None

                if response.status_code == 403:
                    logger.warning(
                        "GitHub REST rate limit or permission error (403). "
                        "Attempt %d/%d.",
                        attempt, _MAX_RETRIES,
                    )
                else:
                    logger.warning(
                        "GitHub REST returned %d on attempt %d/%d: %s",
                        response.status_code, attempt, _MAX_RETRIES,
                        response.text[:300],
                    )

            except httpx.TimeoutException:
                logger.warning(
                    "GitHub REST request timed out on attempt %d/%d",
                    attempt, _MAX_RETRIES,
                )
            except (ValueError, httpx.HTTPError):
                raise
            except Exception as exc:
                logger.warning(
                    "GitHub REST HTTP error on attempt %d/%d: %s",
                    attempt, _MAX_RETRIES, exc,
                )

            if attempt < _MAX_RETRIES:
                backoff = _RETRY_BACKOFF_BASE ** attempt
                await asyncio.sleep(backoff)

        logger.error("GitHub REST request failed after %d attempts for %s", _MAX_RETRIES, url)
        return None

    # ------------------------------------------------------------------
    # Rate limiting
    # ------------------------------------------------------------------

    _rate_limit_remaining: int = field(default=5000, init=False, repr=False)
    _rate_limit_reset: float = field(default=0.0, init=False, repr=False)

    def _build_headers(self) -> dict[str, str]:
        """Build request headers with Bearer token authentication."""
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
            "User-Agent": "Stratum/1.0 (code-intelligence-platform)",
        }

    def _update_rate_limit_state(self, response: httpx.Response) -> None:
        """Update rate limit tracking from response headers."""
        remaining = response.headers.get("X-RateLimit-Remaining")
        if remaining is not None:
            try:
                self._rate_limit_remaining = int(remaining)
            except ValueError:
                pass

        reset = response.headers.get("X-RateLimit-Reset")
        if reset is not None:
            try:
                self._rate_limit_reset = float(reset)
            except ValueError:
                pass

        if self._rate_limit_remaining < _RATE_LIMIT_THRESHOLD:
            logger.warning(
                "GitHub API rate limit low: %d remaining (resets at %s)",
                self._rate_limit_remaining,
                datetime.fromtimestamp(self._rate_limit_reset, tz=timezone.utc).isoformat()
                if self._rate_limit_reset
                else "unknown",
            )

    async def _check_rate_limit_pause(self) -> None:
        """Pause if we are close to exhausting the rate limit."""
        async with self._lock:
            if self._rate_limit_remaining < _RATE_LIMIT_THRESHOLD:
                now = time.time()
                if self._rate_limit_reset > now:
                    wait = min(self._rate_limit_reset - now, 60.0)  # cap wait at 60s
                    logger.info(
                        "Rate limit approaching — pausing %.1f seconds", wait
                    )
                    await asyncio.sleep(wait)


# ---------------------------------------------------------------------------
# Response parsing helpers
# ---------------------------------------------------------------------------


def _parse_repository_info(node: dict) -> RepositoryInfo:
    """Parse a GraphQL repository node into a RepositoryInfo."""
    owner_data = node.get("owner", {})
    default_branch = node.get("defaultBranchRef") or {}
    language_data = node.get("primaryLanguage") or {}
    issues_data = node.get("issues", {})

    return RepositoryInfo(
        owner=owner_data.get("login", ""),
        name=node.get("name", ""),
        full_name=node.get("nameWithOwner", ""),
        description=node.get("description") or "",
        default_branch=default_branch.get("name", "main"),
        language=language_data.get("name"),
        stars=node.get("stargazerCount", 0),
        forks=node.get("forkCount", 0),
        open_issues=issues_data.get("totalCount", 0),
        is_private=node.get("isPrivate", False),
        created_at=node.get("createdAt", ""),
        updated_at=node.get("updatedAt", ""),
    )


def _parse_commit_node(node: dict) -> Commit | None:
    """Parse a GraphQL commit node into a domain Commit entity."""
    oid = node.get("oid", "")
    if not oid:
        return None

    author_data = node.get("author") or {}
    authored_date = node.get("authoredDate", "")

    try:
        timestamp = datetime.fromisoformat(authored_date.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        logger.warning("Skipping commit %s — unparseable timestamp: %s", oid[:8], authored_date)
        return None

    # GitHub GraphQL provides aggregate additions/deletions but not per-file
    # numstat. We create a single synthetic FileChange to preserve churn data.
    additions = node.get("additions", 0)
    deletions = node.get("deletions", 0)
    file_changes: tuple[FileChange, ...] = ()

    if additions > 0 or deletions > 0:
        file_changes = (
            FileChange(
                file_path="(aggregate)",
                lines_added=additions,
                lines_deleted=deletions,
            ),
        )

    return Commit(
        hash=oid,
        author_email=author_data.get("email", ""),
        author_name=author_data.get("name", ""),
        timestamp=timestamp,
        message=node.get("message", "").split("\n")[0],  # first line only
        file_changes=file_changes,
    )


def _parse_pull_request_node(node: dict) -> PullRequestInfo | None:
    """Parse a GraphQL pull request node into a PullRequestInfo."""
    number = node.get("number")
    if number is None:
        return None

    author_data = node.get("author") or {}
    labels_data = node.get("labels", {}).get("nodes", [])

    return PullRequestInfo(
        number=number,
        title=node.get("title", ""),
        state=node.get("state", "OPEN"),
        author=author_data.get("login", "unknown"),
        created_at=node.get("createdAt", ""),
        merged_at=node.get("mergedAt"),
        additions=node.get("additions", 0),
        deletions=node.get("deletions", 0),
        changed_files=node.get("changedFiles", 0),
        labels=tuple(label.get("name", "") for label in labels_data),
    )
