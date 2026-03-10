"""
Analysis DTOs — Data Transfer Objects for analysis input and output.

Architectural Intent:
- Decouple the application boundary from domain internals
- Provide JSON-serializable representations of analysis results
- AnalysisRequest captures all inputs needed to launch a full analysis
- AnalysisResultDTO captures the complete output suitable for API responses,
  persistence, or forwarding to report generators
- DTOs are plain dataclasses with no domain logic — they are anemic by design
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


# ---------------------------------------------------------------------------
# Request DTO
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AnalysisRequest:
    """Immutable input specification for a repository analysis run."""

    git_log_source: str
    project_name: str
    scenario: str  # M&A, vendor_audit, post_merger, decommission, cto_onboarding, oss_assessment
    output_path: str
    manifest_paths: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Result DTOs — nested structures mirroring the domain risk report
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RiskScoreDTO:
    """Serializable representation of a single risk dimension score."""

    value: float
    severity: str
    label: str
    evidence: str

    def to_dict(self) -> dict:
        return {
            "value": self.value,
            "severity": self.severity,
            "label": self.label,
            "evidence": self.evidence,
        }


@dataclass(frozen=True)
class ComponentRiskDTO:
    """Serializable representation of a component's risk profile."""

    component_name: str
    composite_score: float
    systemic_risk: bool
    dimension_scores: dict[str, RiskScoreDTO] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "component_name": self.component_name,
            "composite_score": self.composite_score,
            "systemic_risk": self.systemic_risk,
            "dimensions": {
                dim: score.to_dict()
                for dim, score in self.dimension_scores.items()
            },
        }


@dataclass(frozen=True)
class FileHotspotDTO:
    """Serializable representation of a high-risk file."""

    file_path: str
    composite_risk_score: float
    risk_indicators: dict[str, float] = field(default_factory=dict)
    refactoring_recommendation: str = ""
    effort_estimate: str = "medium"

    def to_dict(self) -> dict:
        return {
            "file_path": self.file_path,
            "composite_risk_score": self.composite_risk_score,
            "risk_indicators": self.risk_indicators,
            "refactoring_recommendation": self.refactoring_recommendation,
            "effort_estimate": self.effort_estimate,
        }


@dataclass(frozen=True)
class AnalysisResultDTO:
    """
    Complete analysis output — the top-level DTO returned by AnalyzeRepositoryCommand.

    Designed for JSON serialization.  Every field is a primitive, a string,
    or a nested DTO that itself implements ``to_dict()``.
    """

    project_name: str
    scenario: str
    analysis_timestamp: str  # ISO-8601 string
    overall_health_score: float
    dimension_scores: dict[str, RiskScoreDTO] = field(default_factory=dict)
    top_risks: list[dict] = field(default_factory=list)
    component_risks: list[ComponentRiskDTO] = field(default_factory=list)
    file_hotspots: list[FileHotspotDTO] = field(default_factory=list)
    ai_narrative: str = ""
    pdf_output_path: str = ""

    def to_dict(self) -> dict:
        """Full JSON-serializable dictionary representation."""
        return {
            "project_name": self.project_name,
            "scenario": self.scenario,
            "analysis_timestamp": self.analysis_timestamp,
            "overall_health_score": self.overall_health_score,
            "dimension_scores": {
                dim: score.to_dict()
                for dim, score in self.dimension_scores.items()
            },
            "top_risks": self.top_risks,
            "component_risks": [cr.to_dict() for cr in self.component_risks],
            "file_hotspots": [fh.to_dict() for fh in self.file_hotspots],
            "ai_narrative": self.ai_narrative,
            "pdf_output_path": self.pdf_output_path,
        }


# ---------------------------------------------------------------------------
# Factory — convert domain RiskReport to DTO
# ---------------------------------------------------------------------------

def risk_report_to_dto(
    report: object,
    pdf_output_path: str = "",
) -> AnalysisResultDTO:
    """
    Map a domain ``RiskReport`` to an ``AnalysisResultDTO``.

    Accepts ``object`` to avoid a hard import of the domain entity at the
    module level; the caller is expected to pass a ``RiskReport`` instance.
    We access attributes duck-typed to keep the DTO module free of domain
    coupling beyond the structural contract.
    """
    from domain.entities.risk_report import RiskReport  # deferred to keep module-level clean
    assert isinstance(report, RiskReport)

    dimension_scores = {
        dim: RiskScoreDTO(
            value=score.value,
            severity=score.severity,
            label=score.label,
            evidence=score.evidence,
        )
        for dim, score in report.dimension_scores.items()
    }

    top_risks = [
        {"dimension": dim, "value": score.value, "severity": score.severity,
         "label": score.label, "evidence": score.evidence}
        for dim, score in report.top_risks
    ]

    component_risks = [
        ComponentRiskDTO(
            component_name=cr.component_name,
            composite_score=cr.composite_score,
            systemic_risk=cr.systemic_risk,
            dimension_scores={
                d: RiskScoreDTO(
                    value=s.value,
                    severity=s.severity,
                    label=s.label,
                    evidence=s.evidence,
                )
                for d, s in cr.dimension_scores.items()
            },
        )
        for cr in report.worst_components
    ]

    file_hotspots = [
        FileHotspotDTO(
            file_path=fh.file_path,
            composite_risk_score=fh.composite_risk_score,
            risk_indicators=fh.risk_indicators,
            refactoring_recommendation=fh.refactoring_recommendation,
            effort_estimate=fh.effort_estimate,
        )
        for fh in report.file_hotspots[:25]
    ]

    return AnalysisResultDTO(
        project_name=report.project_name,
        scenario=report.scenario,
        analysis_timestamp=report.analysis_timestamp.isoformat(),
        overall_health_score=report.overall_health_score,
        dimension_scores=dimension_scores,
        top_risks=top_risks,
        component_risks=component_risks,
        file_hotspots=file_hotspots,
        ai_narrative=report.ai_narrative,
        pdf_output_path=pdf_output_path,
    )
