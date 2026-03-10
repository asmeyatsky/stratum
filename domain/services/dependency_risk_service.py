"""
P4 — Library Dependency Risk Analysis Service

Architectural Intent:
- Pure domain service — no infrastructure dependencies
- Assesses dependency health, version currency, and CVE exposure
- Unique insight: exploitability-adjusted risk = CVSS × coupling strength
- License risk detection for commercial codebases

Key Design Decisions:
1. High migration cost: >200 call sites
2. End of life: no upstream releases in >24 months
3. Exploitability-adjusted score: CVSS × (1 + call_sites/100, capped at 3x)
4. GPL/AGPL flagged as license risk in commercial context
"""

from __future__ import annotations

from dataclasses import dataclass

from domain.entities.dependency import Dependency
from domain.entities.vulnerability import Vulnerability
from domain.value_objects.risk_score import RiskScore


_COPYLEFT_LICENSES = frozenset({
    "GPL-2.0", "GPL-3.0", "AGPL-3.0", "LGPL-2.1", "LGPL-3.0",
    "GPL-2.0-only", "GPL-3.0-only", "AGPL-3.0-only",
})


@dataclass(frozen=True)
class DependencyRiskAssessment:
    dependency: Dependency
    vulnerabilities: tuple[Vulnerability, ...]
    max_exploitability_score: float
    is_license_risk: bool

    @property
    def highest_severity_cve(self) -> Vulnerability | None:
        if not self.vulnerabilities:
            return None
        return max(self.vulnerabilities, key=lambda v: v.cvss_score)

    @property
    def risk_level(self) -> str:
        if self.max_exploitability_score >= 15:
            return "critical"
        if self.max_exploitability_score >= 10:
            return "high"
        if self.max_exploitability_score >= 5:
            return "medium"
        return "low"


class DependencyRiskService:
    """P4 domain service — dependency risk analysis logic."""

    def assess_dependency(
        self,
        dependency: Dependency,
        vulnerabilities: list[Vulnerability],
    ) -> DependencyRiskAssessment:
        """Compute risk assessment for a single dependency."""
        adjusted_scores = [
            vuln.exploitability_adjusted_score(dependency.call_site_count)
            for vuln in vulnerabilities
        ]
        max_score = max(adjusted_scores) if adjusted_scores else 0.0

        is_license_risk = (
            dependency.license is not None
            and dependency.license.upper() in (lic.upper() for lic in _COPYLEFT_LICENSES)
        )

        return DependencyRiskAssessment(
            dependency=dependency,
            vulnerabilities=tuple(vulnerabilities),
            max_exploitability_score=max_score,
            is_license_risk=is_license_risk,
        )

    def assess_all(
        self,
        dependencies: list[Dependency],
        vulnerability_map: dict[str, list[Vulnerability]],
    ) -> list[DependencyRiskAssessment]:
        """Assess all dependencies. vulnerability_map keyed by library name."""
        assessments = []
        for dep in dependencies:
            vulns = vulnerability_map.get(dep.name, [])
            assessments.append(self.assess_dependency(dep, vulns))
        return sorted(
            assessments, key=lambda a: a.max_exploitability_score, reverse=True
        )

    def compute_risk_scores(
        self,
        assessments: list[DependencyRiskAssessment],
        dependencies: list[Dependency],
    ) -> dict[str, RiskScore]:
        """Compute P4-related quality dimension scores for P6."""
        scores: dict[str, RiskScore] = {}

        # Library Risk (dimension 9)
        critical_deps = [a for a in assessments if a.risk_level in ("critical", "high")]
        lib_score = min(len(critical_deps) * 2.0, 10.0)
        scores["library_risk"] = RiskScore(
            value=round(lib_score, 1),
            label="Library Risk",
            evidence=f"{len(critical_deps)} high/critical risk dependencies",
        )

        # Security Posture (dimension 10)
        total_vulns = sum(len(a.vulnerabilities) for a in assessments)
        critical_vulns = sum(
            1 for a in assessments
            for v in a.vulnerabilities if v.cvss_score >= 7.0
        )
        sec_score = min(critical_vulns * 2.5, 10.0)
        scores["security_posture"] = RiskScore(
            value=round(sec_score, 1),
            label="Security Posture",
            evidence=f"{total_vulns} total CVEs, {critical_vulns} critical (CVSS >= 7.0)",
        )

        # Technology Actuality (dimension 11)
        outdated = [d for d in dependencies if d.is_outdated]
        eol = [d for d in dependencies if d.is_end_of_life]
        actuality_score = min(len(outdated) * 0.5 + len(eol) * 3, 10.0)
        scores["technology_actuality"] = RiskScore(
            value=round(actuality_score, 1),
            label="Technology Actuality",
            evidence=f"{len(outdated)} outdated, {len(eol)} end-of-life dependencies",
        )

        # Dependency Coupling (dimension 8)
        high_coupling = [d for d in dependencies if d.coupling_strength == "high"]
        coupling_score = min(len(high_coupling) * 2.0, 10.0)
        scores["dependency_coupling"] = RiskScore(
            value=round(coupling_score, 1),
            label="Dependency Coupling",
            evidence=f"{len(high_coupling)} high-coupling dependencies (>200 call sites)",
        )

        return scores
