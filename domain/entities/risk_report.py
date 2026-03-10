"""
RiskReport Aggregate

Architectural Intent:
- P6 integrated risk model aggregate — the flagship output
- Aggregates findings from P1, P2, P4 into 15 quality dimensions
- Scored on 1-10 severity scale per dimension
- Immutable — built progressively via domain methods
- Domain events emitted on report completion
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, UTC

from domain.value_objects.risk_score import RiskScore
from domain.events.analysis_events import ReportGeneratedEvent


QUALITY_DIMENSIONS = (
    "code_complexity",
    "code_duplication",
    "bug_concentration",
    "commit_quality",
    "code_instability",
    "team_knowledge",
    "coordination_risk",
    "dependency_coupling",
    "library_risk",
    "security_posture",
    "technology_actuality",
    "refactoring_debt",
    "architectural_coupling",
    "testability",
    "traceability",
)


@dataclass(frozen=True)
class ComponentRisk:
    component_name: str
    dimension_scores: dict[str, RiskScore] = field(default_factory=dict)

    @property
    def composite_score(self) -> float:
        if not self.dimension_scores:
            return 0.0
        scores = [s.value for s in self.dimension_scores.values()]
        return round(sum(scores) / len(scores), 2)

    @property
    def systemic_risk(self) -> bool:
        """Components scoring >7 across 3+ dimensions = systemic risk."""
        high_dims = sum(1 for s in self.dimension_scores.values() if s.value >= 7)
        return high_dims >= 3


@dataclass(frozen=True)
class FileHotspot:
    file_path: str
    composite_risk_score: float
    risk_indicators: dict[str, float] = field(default_factory=dict)
    refactoring_recommendation: str = ""
    effort_estimate: str = "medium"  # small / medium / large

    @property
    def is_critical(self) -> bool:
        return self.composite_risk_score >= 7.0


@dataclass(frozen=True)
class RiskReport:
    project_name: str
    analysis_timestamp: datetime
    scenario: str  # M&A, vendor_audit, post_merger, decommission, cto_onboarding, oss_assessment
    dimension_scores: dict[str, RiskScore] = field(default_factory=dict)
    component_risks: tuple[ComponentRisk, ...] = field(default=())
    file_hotspots: tuple[FileHotspot, ...] = field(default=())
    ai_narrative: str = ""
    domain_events: tuple = field(default=())

    @property
    def overall_health_score(self) -> float:
        """Inverse of average risk — 10 = perfect, 1 = critical."""
        if not self.dimension_scores:
            return 10.0
        avg_risk = sum(s.value for s in self.dimension_scores.values()) / len(
            self.dimension_scores
        )
        return round(10.0 - avg_risk, 2)

    @property
    def top_risks(self) -> list[tuple[str, RiskScore]]:
        """Top 5 risk dimensions sorted by severity."""
        sorted_dims = sorted(
            self.dimension_scores.items(), key=lambda x: x[1].value, reverse=True
        )
        return sorted_dims[:5]

    @property
    def worst_components(self) -> tuple[ComponentRisk, ...]:
        """Worst 5 components by composite risk score."""
        sorted_comps = sorted(
            self.component_risks, key=lambda c: c.composite_score, reverse=True
        )
        return tuple(sorted_comps[:5])

    def with_dimension_score(self, dimension: str, score: RiskScore) -> RiskReport:
        new_scores = dict(self.dimension_scores)
        new_scores[dimension] = score
        return replace(self, dimension_scores=new_scores)

    def with_component_risks(self, risks: tuple[ComponentRisk, ...]) -> RiskReport:
        return replace(self, component_risks=risks)

    def with_file_hotspots(self, hotspots: tuple[FileHotspot, ...]) -> RiskReport:
        return replace(self, file_hotspots=hotspots)

    def with_ai_narrative(self, narrative: str) -> RiskReport:
        return replace(
            self,
            ai_narrative=narrative,
            domain_events=self.domain_events + (
                ReportGeneratedEvent(
                    aggregate_id=self.project_name,
                    scenario=self.scenario,
                    overall_health=self.overall_health_score,
                ),
            ),
        )

    def to_dict(self) -> dict:
        return {
            "project_name": self.project_name,
            "analysis_timestamp": self.analysis_timestamp.isoformat(),
            "scenario": self.scenario,
            "overall_health_score": self.overall_health_score,
            "dimension_scores": {
                dim: score.to_dict()
                for dim, score in self.dimension_scores.items()
            },
            "top_risks": [
                {"dimension": dim, **score.to_dict()}
                for dim, score in self.top_risks
            ],
            "component_risks": [
                {
                    "component": cr.component_name,
                    "composite_score": cr.composite_score,
                    "systemic_risk": cr.systemic_risk,
                    "dimensions": {
                        d: s.to_dict() for d, s in cr.dimension_scores.items()
                    },
                }
                for cr in self.worst_components
            ],
            "file_hotspots": [
                {
                    "file": fh.file_path,
                    "score": fh.composite_risk_score,
                    "indicators": fh.risk_indicators,
                    "recommendation": fh.refactoring_recommendation,
                    "effort": fh.effort_estimate,
                }
                for fh in self.file_hotspots[:25]
            ],
            "ai_narrative": self.ai_narrative,
        }
