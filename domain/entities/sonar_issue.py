"""
SonarIssue Entity

Architectural Intent:
- Represents a single issue reported by SonarQube/SonarCloud (Phase 3)
- Carries rule key, severity, and effort metadata for P6 enrichment
- Immutable — imported from SonarQube, never modified in Stratum
- Type classification (BUG, VULNERABILITY, CODE_SMELL) enables
  dimension-specific scoring in the risk model
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SonarIssue:
    rule_key: str  # e.g., "java:S1192", "python:S107"
    severity: str  # BLOCKER, CRITICAL, MAJOR, MINOR, INFO
    component: str  # file path within the SonarQube project
    message: str  # human-readable issue description
    effort: str  # estimated remediation effort, e.g., "15min", "2h"
    type: str  # BUG, VULNERABILITY, CODE_SMELL
    line: int | None = None  # source line number (None if file-level)
    status: str = "OPEN"  # OPEN, CONFIRMED, REOPENED, RESOLVED, CLOSED

    @property
    def is_bug(self) -> bool:
        return self.type == "BUG"

    @property
    def is_vulnerability(self) -> bool:
        return self.type == "VULNERABILITY"

    @property
    def is_code_smell(self) -> bool:
        return self.type == "CODE_SMELL"

    @property
    def is_critical_or_blocker(self) -> bool:
        return self.severity in ("CRITICAL", "BLOCKER")

    @property
    def effort_minutes(self) -> int:
        """Parse the effort string into total minutes.

        SonarQube effort strings use formats like ``"15min"``, ``"2h"``,
        ``"1h30min"``, ``"3d"``. Returns 0 if parsing fails.
        """
        if not self.effort:
            return 0

        total = 0
        remaining = self.effort.lower().strip()

        # Days (SonarQube assumes 8h/day)
        if "d" in remaining:
            parts = remaining.split("d", 1)
            try:
                total += int(parts[0].strip()) * 480
            except ValueError:
                return 0
            remaining = parts[1]

        # Hours
        if "h" in remaining:
            parts = remaining.split("h", 1)
            try:
                total += int(parts[0].strip()) * 60
            except ValueError:
                pass
            remaining = parts[1]

        # Minutes
        if "min" in remaining:
            parts = remaining.split("min", 1)
            try:
                total += int(parts[0].strip())
            except ValueError:
                pass

        return total
