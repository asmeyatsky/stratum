"""
Commit Entity

Architectural Intent:
- Core aggregate for git history analysis across P1, P2, P6
- Immutable — captures a point-in-time snapshot from version control
- Rich domain methods for commit quality and classification (P2)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime

from domain.entities.file_change import FileChange


_BUG_FIX_KEYWORDS = frozenset({
    "fix", "bug", "defect", "issue", "patch", "hotfix",
    "resolve", "repair", "correct", "crash", "error",
})

_REFACTOR_KEYWORDS = frozenset({
    "refactor", "restructure", "cleanup", "clean up",
    "reorganize", "simplify", "extract", "rename",
})

_JIRA_PATTERN = re.compile(r"[A-Z][A-Z0-9]+-\d+")


@dataclass(frozen=True)
class Commit:
    hash: str
    author_email: str
    author_name: str
    timestamp: datetime
    message: str
    file_changes: tuple[FileChange, ...] = field(default=())

    # --- Classification (P2) ---

    @property
    def is_bug_fix(self) -> bool:
        msg_lower = self.message.lower()
        return any(kw in msg_lower for kw in _BUG_FIX_KEYWORDS)

    @property
    def is_refactor(self) -> bool:
        msg_lower = self.message.lower()
        return any(kw in msg_lower for kw in _REFACTOR_KEYWORDS)

    @property
    def is_feature(self) -> bool:
        return not self.is_bug_fix and not self.is_refactor

    @property
    def commit_type(self) -> str:
        if self.is_bug_fix:
            return "bug_fix"
        if self.is_refactor:
            return "refactor"
        return "feature"

    # --- Quality indicators (P2) ---

    @property
    def jira_references(self) -> tuple[str, ...]:
        return tuple(_JIRA_PATTERN.findall(self.message))

    @property
    def has_jira_reference(self) -> bool:
        return len(self.jira_references) > 0

    @property
    def is_mega_commit(self) -> bool:
        """Commits changing >50 files are flagged for risk review."""
        return len(self.file_changes) > 50

    @property
    def modules_touched(self) -> frozenset[str]:
        return frozenset(fc.module for fc in self.file_changes)

    @property
    def scatter_score(self) -> int:
        """Number of distinct modules touched — high scatter = low cohesion."""
        return len(self.modules_touched)

    @property
    def is_scattered(self) -> bool:
        """Commits touching >3 unrelated modules simultaneously."""
        return self.scatter_score > 3

    @property
    def has_empty_message(self) -> bool:
        return len(self.message.strip()) == 0

    @property
    def total_churn(self) -> int:
        return sum(fc.churn for fc in self.file_changes)

    @property
    def files_changed_count(self) -> int:
        return len(self.file_changes)
