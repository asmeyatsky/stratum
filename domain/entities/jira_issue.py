"""
JiraIssue Entity

Architectural Intent:
- Represents a Jira issue for P2 task correlation analysis
- Maps issue types to bug/feature/chore taxonomy for commit cross-referencing
- Immutable — captures a point-in-time snapshot from Jira
- Calculates resolution metrics for engineering velocity analysis
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


_BUG_TYPES = frozenset({"bug", "defect", "incident", "problem"})
_FEATURE_TYPES = frozenset({"story", "feature", "enhancement", "new feature", "epic"})


@dataclass(frozen=True)
class JiraIssue:
    """Immutable representation of a Jira issue for P2 task correlation."""

    key: str
    issue_type: str
    status: str
    summary: str
    created_at: datetime
    resolved_at: datetime | None = None
    assignee: str | None = None
    story_points: float | None = None
    sprint: str | None = None
    labels: tuple[str, ...] = field(default=())

    # --- Taxonomy classification ---

    @property
    def is_bug(self) -> bool:
        """True if this issue type maps to the bug taxonomy."""
        return self.issue_type.lower() in _BUG_TYPES

    @property
    def is_feature(self) -> bool:
        """True if this issue type maps to the feature taxonomy."""
        return self.issue_type.lower() in _FEATURE_TYPES

    @property
    def is_chore(self) -> bool:
        """True if this issue type does not map to bug or feature (task, subtask, etc.)."""
        return not self.is_bug and not self.is_feature

    @property
    def taxonomy(self) -> str:
        """Classify into bug/feature/chore for P2 correlation."""
        if self.is_bug:
            return "bug"
        if self.is_feature:
            return "feature"
        return "chore"

    # --- Resolution metrics ---

    @property
    def resolution_days(self) -> float | None:
        """Days between creation and resolution. None if unresolved."""
        if self.resolved_at is None:
            return None
        delta = self.resolved_at - self.created_at
        return round(delta.total_seconds() / 86400, 2)

    @property
    def is_resolved(self) -> bool:
        return self.resolved_at is not None
