"""
P6 — Integrated Risk & Quality Model Aggregation Service

Architectural Intent:
- Aggregates findings from P1, P2, P4 into unified risk model
- 15 quality dimensions scored on 1-10 severity scale
- Produces component risk matrix, file hotspot catalogue, and overall health score
- Pure domain service — receives pre-computed scores from analysis engines

Parallelization Notes:
- P1, P2, P4 score computation runs concurrently (no data dependency)
- Component risk matrix and file hotspots computed after all dimension scores are ready
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, UTC

from domain.entities.commit import Commit
from domain.entities.risk_report import (
    ComponentRisk,
    FileHotspot,
    RiskReport,
)
from domain.services.commit_quality_service import BugMagnet
from domain.services.evolution_analysis_service import ChurnAnomaly, KnowledgeRisk
from domain.value_objects.risk_score import RiskScore


class RiskAggregationService:
    """P6 domain service — assembles the integrated risk report."""

    def build_report(
        self,
        project_name: str,
        scenario: str,
        p1_scores: dict[str, RiskScore],
        p2_scores: dict[str, RiskScore],
        p4_scores: dict[str, RiskScore],
        knowledge_risks: list[KnowledgeRisk],
        bug_magnets: list[BugMagnet],
        churn_anomalies: list[ChurnAnomaly],
        commits: list[Commit],
        p3_scores: dict[str, RiskScore] | None = None,
    ) -> RiskReport:
        """Assemble the full P6 integrated risk report."""
        # Merge all dimension scores
        all_scores: dict[str, RiskScore] = {}
        all_scores.update(p1_scores)
        all_scores.update(p2_scores)
        all_scores.update(p4_scores)

        if p3_scores:
            for key, score in p3_scores.items():
                all_scores[key] = score

        # Fill remaining dimensions with defaults for MVP
        for dim in ("code_complexity", "code_duplication", "coordination_risk",
                     "testability", "traceability"):
            if dim not in all_scores:
                all_scores[dim] = RiskScore(
                    value=0.0,
                    label=dim.replace("_", " ").title(),
                    evidence="Not assessed in current analysis scope",
                )

        # Build component risk matrix
        component_risks = self._build_component_risks(
            knowledge_risks, bug_magnets, churn_anomalies, commits
        )

        # Build file hotspot catalogue
        file_hotspots = self._build_file_hotspots(
            bug_magnets, churn_anomalies, commits
        )

        return RiskReport(
            project_name=project_name,
            analysis_timestamp=datetime.now(UTC),
            scenario=scenario,
            dimension_scores=all_scores,
            component_risks=tuple(component_risks),
            file_hotspots=tuple(file_hotspots[:25]),
        )

    def _build_component_risks(
        self,
        knowledge_risks: list[KnowledgeRisk],
        bug_magnets: list[BugMagnet],
        churn_anomalies: list[ChurnAnomaly],
        commits: list[Commit],
    ) -> list[ComponentRisk]:
        """Build per-component risk matrix across available dimensions."""
        component_scores: dict[str, dict[str, RiskScore]] = defaultdict(dict)

        # Knowledge risk per component
        for kr in knowledge_risks:
            score = min(kr.primary_author_ratio * 10, 10.0)
            component_scores[kr.component]["team_knowledge"] = RiskScore(
                value=round(score, 1),
                label="Knowledge Risk",
                evidence=f"Primary author: {kr.primary_author} ({kr.primary_author_ratio:.0%})",
            )

        # Bug concentration per component
        component_bugs: dict[str, list[BugMagnet]] = defaultdict(list)
        for bm in bug_magnets:
            module = bm.file_path.split("/")[0] if "/" in bm.file_path else "(root)"
            component_bugs[module].append(bm)
        for component, magnets in component_bugs.items():
            avg_ratio = sum(m.bug_fix_ratio for m in magnets) / len(magnets)
            component_scores[component]["bug_concentration"] = RiskScore(
                value=round(min(avg_ratio * 12, 10.0), 1),
                label="Bug Concentration",
                evidence=f"{len(magnets)} bug magnet files",
            )

        # Churn per component
        component_churn: dict[str, list[ChurnAnomaly]] = defaultdict(list)
        for ca in churn_anomalies:
            module = ca.file_path.split("/")[0] if "/" in ca.file_path else "(root)"
            component_churn[module].append(ca)
        for component, anomalies in component_churn.items():
            avg_churn = sum(a.changes_per_sprint for a in anomalies) / len(anomalies)
            component_scores[component]["code_instability"] = RiskScore(
                value=round(min(avg_churn, 10.0), 1),
                label="Code Instability",
                evidence=f"{len(anomalies)} high-churn files, avg {avg_churn:.1f} changes/sprint",
            )

        return [
            ComponentRisk(component_name=comp, dimension_scores=scores)
            for comp, scores in component_scores.items()
        ]

    def _build_file_hotspots(
        self,
        bug_magnets: list[BugMagnet],
        churn_anomalies: list[ChurnAnomaly],
        commits: list[Commit],
    ) -> list[FileHotspot]:
        """Build top-25 most critical files ranked by composite risk score."""
        file_indicators: dict[str, dict[str, float]] = defaultdict(dict)

        for bm in bug_magnets:
            file_indicators[bm.file_path]["bug_fix_ratio"] = bm.bug_fix_ratio

        for ca in churn_anomalies:
            file_indicators[ca.file_path]["churn_per_sprint"] = ca.changes_per_sprint

        # Add commit count as an indicator
        file_commit_count: Counter[str] = Counter()
        for commit in commits:
            for fc in commit.file_changes:
                file_commit_count[fc.file_path] += 1

        hotspots: list[FileHotspot] = []
        for file_path, indicators in file_indicators.items():
            commit_count = file_commit_count.get(file_path, 0)
            indicators["total_commits"] = float(commit_count)

            # Composite score: weighted sum of normalised indicators
            composite = 0.0
            if "bug_fix_ratio" in indicators:
                composite += indicators["bug_fix_ratio"] * 5
            if "churn_per_sprint" in indicators:
                composite += min(indicators["churn_per_sprint"] / 2, 5.0)
            composite = round(min(composite, 10.0), 2)

            effort = "small" if composite < 4 else ("medium" if composite < 7 else "large")

            hotspots.append(
                FileHotspot(
                    file_path=file_path,
                    composite_risk_score=composite,
                    risk_indicators=indicators,
                    effort_estimate=effort,
                )
            )

        return sorted(hotspots, key=lambda h: h.composite_risk_score, reverse=True)
