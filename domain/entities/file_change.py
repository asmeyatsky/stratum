"""
FileChange Entity

Architectural Intent:
- Represents a single file modification within a commit
- Carries lines-added/removed for churn and hotspot analysis
- Immutable value — no identity beyond its containing commit
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FileChange:
    file_path: str
    lines_added: int
    lines_deleted: int

    @property
    def churn(self) -> int:
        return self.lines_added + self.lines_deleted

    @property
    def is_binary(self) -> bool:
        return self.lines_added == 0 and self.lines_deleted == 0 and self.file_path != ""

    @property
    def module(self) -> str:
        """Extract top-level module/directory from file path."""
        parts = self.file_path.split("/")
        return parts[0] if len(parts) > 1 else "(root)"
