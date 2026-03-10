from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, UTC


@dataclass(frozen=True)
class DomainEvent:
    aggregate_id: str
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
