from __future__ import annotations

from dataclasses import dataclass

from domain.events.event_base import DomainEvent


@dataclass(frozen=True)
class AnalysisStartedEvent(DomainEvent):
    scenario: str = ""
    packages: tuple[str, ...] = ()


@dataclass(frozen=True)
class AnalysisCompletedEvent(DomainEvent):
    packages_completed: tuple[str, ...] = ()
    duration_seconds: float = 0.0


@dataclass(frozen=True)
class ReportGeneratedEvent(DomainEvent):
    scenario: str = ""
    overall_health: float = 0.0
