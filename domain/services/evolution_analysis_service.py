"""
P1 — Code & Team Evolution Analysis Service

Architectural Intent:
- Pure domain service — no infrastructure dependencies
- Analyses commit history to surface knowledge risks, temporal coupling, and churn anomalies
- All methods operate on immutable domain entities and return value objects

Key Design Decisions:
1. Knowledge polarisation threshold: >70% of commits from single developer
2. Knowledge loss: developers with >40% contribution have left
3. Temporal coupling: files co-changing >60% of the time
4. Churn anomaly: >5 changes per sprint (2 weeks) over 3+ months
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from itertools import combinations

from domain.entities.commit import Commit
from domain.value_objects.risk_score import RiskScore


@dataclass(frozen=True)
class KnowledgeRisk:
    component: str
    primary_author: str
    primary_author_ratio: float
    total_contributors: int
    bus_factor: int
    risk_type: str  # polarisation, loss, churn

    @property
    def is_critical(self) -> bool:
        return self.primary_author_ratio > 0.7 and self.bus_factor <= 1


@dataclass(frozen=True)
class TemporalCoupling:
    file_a: str
    file_b: str
    co_change_ratio: float
    co_change_count: int

    @property
    def is_significant(self) -> bool:
        return self.co_change_ratio >= 0.6 and self.co_change_count >= 5


@dataclass(frozen=True)
class ChurnAnomaly:
    file_path: str
    changes_per_sprint: float
    total_changes: int
    anomaly_type: str  # high_churn, growth_spike, stale_critical


class EvolutionAnalysisService:
    """P1 domain service — pure analysis logic over commit history."""

    def analyze_knowledge_distribution(
        self, commits: list[Commit], active_authors: set[str] | None = None
    ) -> list[KnowledgeRisk]:
        """
        P1.2 — Detect knowledge polarisation, loss, and developer churn per component.

        Args:
            commits: Full commit history
            active_authors: Set of currently active author emails (if None, all are considered active)
        """
        # Group commits by module/component
        component_authors: dict[str, Counter[str]] = defaultdict(Counter)
        for commit in commits:
            for fc in commit.file_changes:
                component_authors[fc.module][commit.author_email] += 1

        risks: list[KnowledgeRisk] = []
        for component, author_counts in component_authors.items():
            total_commits = sum(author_counts.values())
            if total_commits < 10:
                continue

            top_author, top_count = author_counts.most_common(1)[0]
            ratio = top_count / total_commits

            # Bus factor: how many authors account for 80% of commits
            bus_factor = self._calculate_bus_factor(author_counts)

            # Knowledge polarisation
            if ratio > 0.7:
                risks.append(
                    KnowledgeRisk(
                        component=component,
                        primary_author=top_author,
                        primary_author_ratio=round(ratio, 3),
                        total_contributors=len(author_counts),
                        bus_factor=bus_factor,
                        risk_type="polarisation",
                    )
                )

            # Knowledge loss — check if dominant authors have left
            if active_authors is not None:
                departed_ratio = sum(
                    count for author, count in author_counts.items()
                    if author not in active_authors
                ) / total_commits
                if departed_ratio > 0.4:
                    risks.append(
                        KnowledgeRisk(
                            component=component,
                            primary_author=top_author,
                            primary_author_ratio=round(departed_ratio, 3),
                            total_contributors=len(author_counts),
                            bus_factor=bus_factor,
                            risk_type="loss",
                        )
                    )

        return risks

    def detect_temporal_coupling(
        self, commits: list[Commit], min_support: int = 5
    ) -> list[TemporalCoupling]:
        """
        P1.3 — Find files that change together >60% of the time despite being in different modules.
        """
        # Count how often each file appears in commits
        file_commit_count: Counter[str] = Counter()
        # Count co-occurrences
        co_change_count: Counter[tuple[str, str]] = Counter()

        for commit in commits:
            files = [fc.file_path for fc in commit.file_changes]
            for f in files:
                file_commit_count[f] += 1
            for a, b in combinations(sorted(set(files)), 2):
                co_change_count[(a, b)] += 1

        couplings: list[TemporalCoupling] = []
        for (file_a, file_b), count in co_change_count.items():
            if count < min_support:
                continue
            # Ratio relative to the less-frequently-changed file
            min_changes = min(file_commit_count[file_a], file_commit_count[file_b])
            ratio = count / min_changes if min_changes > 0 else 0

            if ratio >= 0.6:
                # Only flag cross-module coupling
                module_a = file_a.split("/")[0] if "/" in file_a else "(root)"
                module_b = file_b.split("/")[0] if "/" in file_b else "(root)"
                if module_a != module_b:
                    couplings.append(
                        TemporalCoupling(
                            file_a=file_a,
                            file_b=file_b,
                            co_change_ratio=round(ratio, 3),
                            co_change_count=count,
                        )
                    )

        return sorted(couplings, key=lambda c: c.co_change_ratio, reverse=True)

    def detect_churn_anomalies(
        self, commits: list[Commit], sprint_days: int = 14
    ) -> list[ChurnAnomaly]:
        """
        P1.1 — Files with abnormally high churn rate (changed >5 times per sprint over 3+ months).
        """
        if not commits:
            return []

        file_timestamps: dict[str, list] = defaultdict(list)
        for commit in commits:
            for fc in commit.file_changes:
                file_timestamps[fc.file_path].append(commit.timestamp)

        anomalies: list[ChurnAnomaly] = []
        for file_path, timestamps in file_timestamps.items():
            if len(timestamps) < 10:
                continue

            sorted_ts = sorted(timestamps)
            span_days = (sorted_ts[-1] - sorted_ts[0]).days
            if span_days < 90:  # Need 3+ months
                continue

            sprints = max(span_days / sprint_days, 1)
            changes_per_sprint = len(timestamps) / sprints

            if changes_per_sprint > 5:
                anomalies.append(
                    ChurnAnomaly(
                        file_path=file_path,
                        changes_per_sprint=round(changes_per_sprint, 2),
                        total_changes=len(timestamps),
                        anomaly_type="high_churn",
                    )
                )

        return sorted(anomalies, key=lambda a: a.changes_per_sprint, reverse=True)

    def compute_risk_scores(
        self,
        knowledge_risks: list[KnowledgeRisk],
        couplings: list[TemporalCoupling],
        churn_anomalies: list[ChurnAnomaly],
        total_components: int,
    ) -> dict[str, RiskScore]:
        """Compute P1-related quality dimension scores for P6."""
        scores: dict[str, RiskScore] = {}

        # Team Knowledge (dimension 6)
        if total_components > 0:
            polarised_ratio = len([k for k in knowledge_risks if k.risk_type == "polarisation"]) / total_components
            knowledge_score = min(polarised_ratio * 15, 10.0)
        else:
            knowledge_score = 0.0
        scores["team_knowledge"] = RiskScore(
            value=round(knowledge_score, 1),
            label="Team Knowledge Risk",
            evidence=f"{len(knowledge_risks)} components with knowledge concentration issues",
        )

        # Code Instability (dimension 5)
        churn_score = min(len(churn_anomalies) * 1.5, 10.0)
        scores["code_instability"] = RiskScore(
            value=round(churn_score, 1),
            label="Code Instability",
            evidence=f"{len(churn_anomalies)} files with abnormal churn patterns",
        )

        # Architectural Coupling (dimension 13)
        coupling_score = min(len(couplings) * 1.0, 10.0)
        scores["architectural_coupling"] = RiskScore(
            value=round(coupling_score, 1),
            label="Architectural Coupling",
            evidence=f"{len(couplings)} cross-module temporal couplings detected",
        )

        return scores

    @staticmethod
    def _calculate_bus_factor(author_counts: Counter[str]) -> int:
        """Minimum authors accounting for 80% of commits."""
        total = sum(author_counts.values())
        target = total * 0.8
        accumulated = 0
        for i, (_, count) in enumerate(author_counts.most_common(), 1):
            accumulated += count
            if accumulated >= target:
                return i
        return len(author_counts)
