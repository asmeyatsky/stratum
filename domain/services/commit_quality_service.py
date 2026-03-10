"""
P2 — Tasks & Commit Quality Analysis Service

Architectural Intent:
- Pure domain service — classifies commits and detects quality patterns
- Bug magnet detection via keyword-based classification (MVP, no Jira required)
- Commit quality scoring: cohesion, message quality, smart commit adherence
- Feature vs bug ratio trending across rolling windows

Key Design Decisions:
1. Bug-fix classification: keyword detection in commit messages (MVP fallback)
2. Scatter score threshold: >3 modules = scattered commit
3. Bug magnet threshold: >40% bug-fix commits over analysis window
4. Mega commit threshold: >50 files changed
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass

from domain.entities.commit import Commit
from domain.value_objects.risk_score import RiskScore
from domain.value_objects.time_period import TimePeriod


@dataclass(frozen=True)
class CommitQualityReport:
    total_commits: int
    empty_message_count: int
    mega_commit_count: int
    scattered_commit_count: int
    jira_reference_ratio: float
    avg_scatter_score: float

    @property
    def empty_message_ratio(self) -> float:
        return self.empty_message_count / self.total_commits if self.total_commits > 0 else 0.0

    @property
    def mega_commit_ratio(self) -> float:
        return self.mega_commit_count / self.total_commits if self.total_commits > 0 else 0.0


@dataclass(frozen=True)
class BugMagnet:
    file_path: str
    bug_fix_ratio: float
    total_commits: int
    bug_fix_commits: int
    is_recurring: bool  # bug magnet across multiple quarters


@dataclass(frozen=True)
class FeatureBugTrend:
    period_label: str
    feature_count: int
    bug_fix_count: int
    refactor_count: int

    @property
    def bug_fix_ratio(self) -> float:
        total = self.feature_count + self.bug_fix_count + self.refactor_count
        return self.bug_fix_count / total if total > 0 else 0.0


class CommitQualityService:
    """P2 domain service — commit quality analysis and bug magnet detection."""

    def assess_commit_quality(self, commits: list[Commit]) -> CommitQualityReport:
        """P2.1 — Assess overall commit quality across the history."""
        if not commits:
            return CommitQualityReport(
                total_commits=0,
                empty_message_count=0,
                mega_commit_count=0,
                scattered_commit_count=0,
                jira_reference_ratio=0.0,
                avg_scatter_score=0.0,
            )

        empty = sum(1 for c in commits if c.has_empty_message)
        mega = sum(1 for c in commits if c.is_mega_commit)
        scattered = sum(1 for c in commits if c.is_scattered)
        jira = sum(1 for c in commits if c.has_jira_reference)
        avg_scatter = sum(c.scatter_score for c in commits) / len(commits)

        return CommitQualityReport(
            total_commits=len(commits),
            empty_message_count=empty,
            mega_commit_count=mega,
            scattered_commit_count=scattered,
            jira_reference_ratio=round(jira / len(commits), 3),
            avg_scatter_score=round(avg_scatter, 2),
        )

    def detect_bug_magnets(
        self, commits: list[Commit], threshold: float = 0.4
    ) -> list[BugMagnet]:
        """
        P2.4 — Files changed in bug-fix commits >40% of the time.
        """
        file_total: Counter[str] = Counter()
        file_bugfix: Counter[str] = Counter()

        for commit in commits:
            for fc in commit.file_changes:
                file_total[fc.file_path] += 1
                if commit.is_bug_fix:
                    file_bugfix[fc.file_path] += 1

        magnets: list[BugMagnet] = []
        for file_path, total in file_total.items():
            if total < 5:  # Minimum sample size
                continue
            bug_count = file_bugfix.get(file_path, 0)
            ratio = bug_count / total
            if ratio >= threshold:
                magnets.append(
                    BugMagnet(
                        file_path=file_path,
                        bug_fix_ratio=round(ratio, 3),
                        total_commits=total,
                        bug_fix_commits=bug_count,
                        is_recurring=self._is_recurring_magnet(
                            file_path, commits, threshold
                        ),
                    )
                )

        return sorted(magnets, key=lambda m: m.bug_fix_ratio, reverse=True)

    def compute_feature_bug_trends(
        self, commits: list[Commit]
    ) -> list[FeatureBugTrend]:
        """P2.2 — Rolling 30/90/180-day breakdown of commit types."""
        trends: list[FeatureBugTrend] = []
        for period in TimePeriod.rolling_windows():
            period_commits = [c for c in commits if period.contains(c.timestamp)]
            features = sum(1 for c in period_commits if c.is_feature)
            bugs = sum(1 for c in period_commits if c.is_bug_fix)
            refactors = sum(1 for c in period_commits if c.is_refactor)
            trends.append(
                FeatureBugTrend(
                    period_label=f"last_{period.days}_days",
                    feature_count=features,
                    bug_fix_count=bugs,
                    refactor_count=refactors,
                )
            )
        return trends

    def detect_high_impact_tasks(
        self, commits: list[Commit], file_threshold: int = 15, module_threshold: int = 3
    ) -> list[Commit]:
        """P2.3 — Tasks requiring changes across >15 files and >3 modules."""
        return [
            c for c in commits
            if c.files_changed_count > file_threshold and c.scatter_score > module_threshold
        ]

    def compute_risk_scores(
        self,
        quality_report: CommitQualityReport,
        bug_magnets: list[BugMagnet],
        trends: list[FeatureBugTrend],
    ) -> dict[str, RiskScore]:
        """Compute P2-related quality dimension scores for P6."""
        scores: dict[str, RiskScore] = {}

        # Commit Quality (dimension 4)
        quality_score = 0.0
        quality_score += quality_report.empty_message_ratio * 3
        quality_score += quality_report.mega_commit_ratio * 4
        quality_score += min(quality_report.avg_scatter_score / 2, 3.0)
        scores["commit_quality"] = RiskScore(
            value=round(min(quality_score, 10.0), 1),
            label="Commit Quality",
            evidence=(
                f"{quality_report.empty_message_count} empty messages, "
                f"{quality_report.mega_commit_count} mega-commits, "
                f"avg scatter {quality_report.avg_scatter_score}"
            ),
        )

        # Bug Concentration (dimension 3)
        bug_score = min(len(bug_magnets) * 0.8, 10.0)
        scores["bug_concentration"] = RiskScore(
            value=round(bug_score, 1),
            label="Bug Concentration",
            evidence=f"{len(bug_magnets)} bug magnet files detected",
        )

        # Refactoring Debt (dimension 12) — derived from bug/feature trend
        if trends:
            latest = trends[0]  # 30-day window
            refactor_debt = latest.bug_fix_ratio * 10
        else:
            refactor_debt = 0.0
        scores["refactoring_debt"] = RiskScore(
            value=round(min(refactor_debt, 10.0), 1),
            label="Refactoring Debt",
            evidence=f"Bug-fix ratio in last 30 days: {trends[0].bug_fix_ratio:.1%}" if trends else "No trend data",
        )

        return scores

    def _is_recurring_magnet(
        self, file_path: str, commits: list[Commit], threshold: float
    ) -> bool:
        """Check if file is a bug magnet across multiple quarters."""
        if not commits:
            return False

        sorted_commits = sorted(commits, key=lambda c: c.timestamp)
        # Split into quarters (rough: 90-day windows)
        quarters_as_magnet = 0
        for period in TimePeriod.rolling_windows():
            period_commits = [c for c in sorted_commits if period.contains(c.timestamp)]
            relevant = [c for c in period_commits if any(fc.file_path == file_path for fc in c.file_changes)]
            if len(relevant) < 3:
                continue
            bug_ratio = sum(1 for c in relevant if c.is_bug_fix) / len(relevant)
            if bug_ratio >= threshold:
                quarters_as_magnet += 1

        return quarters_as_magnet >= 2
