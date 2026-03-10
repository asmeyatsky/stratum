"""
GitLogParser — Infrastructure adapter implementing GitLogPort.

Architectural Intent:
    Translates raw git log output into domain Commit entities. This adapter
    handles only parsing and data translation — no business logic resides here.
    The expected input format is produced by:

        git log --all --numstat --format='%H|%ae|%an|%ai|%s'

    Each commit block consists of:
        <hash>|<email>|<name>|<date>|<subject>
        <lines_added>\t<lines_deleted>\t<file_path>
        ...
        (blank line separates commits)

    Binary files use '-' for added/deleted counts and are recorded as 0/0.

Design Decisions:
    - Async interface for consistency, even though file I/O is synchronous
      (enables future streaming or remote source support).
    - Lenient parsing: malformed lines are skipped with warnings logged,
      ensuring partial logs still yield usable results.
    - File is read once into memory — acceptable for git logs up to several
      hundred MB.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from domain.entities.commit import Commit
from domain.entities.file_change import FileChange

logger = logging.getLogger(__name__)


class GitLogParser:
    """Parses ``git log --all --numstat`` output files into domain Commit entities.

    Implements :class:`domain.ports.GitLogPort`.
    """

    async def parse(self, source: str) -> list[Commit]:
        """Parse commits from a git log file.

        Args:
            source: Filesystem path to a git log output file.

        Returns:
            Chronologically ordered list of :class:`Commit` entities (oldest first).

        Raises:
            FileNotFoundError: If *source* does not exist.
            PermissionError: If *source* is not readable.
        """
        path = Path(source)
        if not path.exists():
            raise FileNotFoundError(f"Git log file not found: {source}")
        if not path.is_file():
            raise ValueError(f"Source is not a file: {source}")

        raw = path.read_text(encoding="utf-8", errors="replace")
        return self._parse_log(raw)

    # ------------------------------------------------------------------
    # Internal parsing
    # ------------------------------------------------------------------

    def _parse_log(self, raw: str) -> list[Commit]:
        """Parse the full log text into Commit entities."""
        commits: list[Commit] = []
        blocks = self._split_into_blocks(raw)

        for block in blocks:
            commit = self._parse_block(block)
            if commit is not None:
                commits.append(commit)

        # Return oldest-first for chronological analysis
        commits.sort(key=lambda c: c.timestamp)
        logger.info("Parsed %d commits from git log", len(commits))
        return commits

    @staticmethod
    def _split_into_blocks(raw: str) -> list[list[str]]:
        """Split raw log text into per-commit line groups.

        Commits are separated by one or more blank lines. The first non-blank
        line of each block is the header; subsequent non-blank lines are
        numstat entries.
        """
        blocks: list[list[str]] = []
        current: list[str] = []

        for line in raw.splitlines():
            stripped = line.strip()
            if stripped == "":
                if current:
                    blocks.append(current)
                    current = []
            else:
                current.append(stripped)

        # Flush the last block (file may not end with a blank line)
        if current:
            blocks.append(current)

        return blocks

    def _parse_block(self, lines: list[str]) -> Commit | None:
        """Parse a single commit block (header + numstat lines)."""
        if not lines:
            return None

        header = lines[0]
        header_parts = header.split("|", maxsplit=4)

        if len(header_parts) < 5:
            logger.warning("Skipping malformed commit header: %s", header[:120])
            return None

        commit_hash, author_email, author_name, date_str, message = header_parts

        timestamp = self._parse_timestamp(date_str.strip())
        if timestamp is None:
            logger.warning(
                "Skipping commit %s — unparseable timestamp: %s",
                commit_hash[:8],
                date_str,
            )
            return None

        file_changes: list[FileChange] = []
        for numstat_line in lines[1:]:
            fc = self._parse_numstat_line(numstat_line)
            if fc is not None:
                file_changes.append(fc)

        return Commit(
            hash=commit_hash.strip(),
            author_email=author_email.strip(),
            author_name=author_name.strip(),
            timestamp=timestamp,
            message=message.strip(),
            file_changes=tuple(file_changes),
        )

    @staticmethod
    def _parse_numstat_line(line: str) -> FileChange | None:
        """Parse a single numstat line: ``<added>\\t<deleted>\\t<filepath>``.

        Binary files report ``-\\t-\\tpath`` and are recorded with 0/0 counts.
        Rename paths (``old => new``) use the new path.
        """
        parts = line.split("\t", maxsplit=2)
        if len(parts) != 3:
            logger.debug("Skipping non-numstat line: %s", line[:80])
            return None

        added_str, deleted_str, file_path = parts
        file_path = file_path.strip()

        if not file_path:
            return None

        # Handle rename notation: {old => new}/path or old/path => new/path
        if " => " in file_path:
            # Use the destination (new) path
            file_path = _resolve_rename_path(file_path)

        # Binary files use '-' for counts
        try:
            lines_added = int(added_str) if added_str != "-" else 0
        except ValueError:
            lines_added = 0

        try:
            lines_deleted = int(deleted_str) if deleted_str != "-" else 0
        except ValueError:
            lines_deleted = 0

        return FileChange(
            file_path=file_path,
            lines_added=lines_added,
            lines_deleted=lines_deleted,
        )

    @staticmethod
    def _parse_timestamp(date_str: str) -> datetime | None:
        """Parse git author date (ISO-like with timezone offset).

        Git ``%ai`` format example: ``2024-01-15 14:30:00 +0100``
        """
        # Try the standard git %ai format first
        for fmt in (
            "%Y-%m-%d %H:%M:%S %z",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%d %H:%M:%S",
        ):
            try:
                dt = datetime.strptime(date_str, fmt)
                # Ensure timezone-aware (default to UTC if missing)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except ValueError:
                continue

        return None


def _resolve_rename_path(path: str) -> str:
    """Resolve git rename notation to the destination path.

    Handles two forms:
        1. ``src/{old.py => new.py}``  ->  ``src/new.py``
        2. ``old/path.py => new/path.py``  ->  ``new/path.py``
    """
    # Form 1: curly-brace rename inside a directory
    if "{" in path and "}" in path:
        prefix = path[: path.index("{")]
        brace_content = path[path.index("{") + 1 : path.index("}")]
        suffix = path[path.index("}") + 1 :]

        if " => " in brace_content:
            _, new_part = brace_content.split(" => ", maxsplit=1)
            resolved = prefix + new_part + suffix
            # Clean up double slashes
            while "//" in resolved:
                resolved = resolved.replace("//", "/")
            return resolved

    # Form 2: plain arrow rename
    if " => " in path:
        _, new_path = path.split(" => ", maxsplit=1)
        return new_path.strip()

    return path
