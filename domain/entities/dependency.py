"""
Dependency Entity

Architectural Intent:
- Represents a third-party library dependency (P4)
- Tracks version currency, coupling strength, and ecosystem metadata
- Immutable — enriched versions produced via domain methods
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime


@dataclass(frozen=True)
class Dependency:
    name: str
    current_version: str
    ecosystem: str  # npm, pip, maven, cargo
    manifest_path: str
    latest_version: str | None = None
    call_site_count: int = 0
    last_upstream_release: datetime | None = None
    license: str | None = None

    @property
    def is_outdated(self) -> bool:
        if self.latest_version is None:
            return False
        return self.current_version != self.latest_version

    @property
    def is_end_of_life(self) -> bool:
        """No upstream releases in >24 months."""
        if self.last_upstream_release is None:
            return False
        from datetime import timezone
        delta = datetime.now(timezone.utc) - self.last_upstream_release
        return delta.days > 730

    @property
    def is_high_migration_cost(self) -> bool:
        """Libraries with >200 call sites are high-migration-cost."""
        return self.call_site_count > 200

    @property
    def coupling_strength(self) -> str:
        if self.call_site_count > 200:
            return "high"
        if self.call_site_count > 50:
            return "medium"
        return "low"

    def with_latest_version(self, version: str) -> Dependency:
        return replace(self, latest_version=version)

    def with_call_sites(self, count: int) -> Dependency:
        return replace(self, call_site_count=count)
