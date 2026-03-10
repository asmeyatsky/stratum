"""
GitLogPort — Port for git history ingestion.

Adapters: local file parser, GitHub API client.
"""

from __future__ import annotations

from typing import Protocol

from domain.entities.commit import Commit


class GitLogPort(Protocol):
    async def parse(self, source: str) -> list[Commit]:
        """Parse commits from a source (file path, repo URL, etc.)."""
        ...
