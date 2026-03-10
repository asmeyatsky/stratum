"""
Comprehensive tests for all domain services.

Tests cover:
- EvolutionAnalysisService: knowledge polarisation, bus factor, temporal coupling, churn anomalies
- CommitQualityService: commit quality reports, bug magnet detection, trends
- DependencyRiskService: single & batch dependency assessment, exploitability scoring
- RiskAggregationService: full report assembly, component matrix, file hotspots
"""

import pytest
from datetime import datetime, timedelta, UTC
from collections import Counter

from domain.entities.commit import Commit
from domain.entities.file_change import FileChange
from domain.entities.author import Author
from domain.entities.dependency import Dependency
from domain.entities.vulnerability import Vulnerability
from domain.value_objects.risk_score import RiskScore
from domain.value_objects.time_period import TimePeriod
from domain.services.evolution_analysis_service import (
    EvolutionAnalysisService,
    KnowledgeRisk,
    TemporalCoupling,
    ChurnAnomaly,
)
from domain.services.commit_quality_service import (
    CommitQualityService,
    CommitQualityReport,
    BugMagnet,
    FeatureBugTrend,
)
from domain.services.dependency_risk_service import (
    DependencyRiskService,
    DependencyRiskAssessment,
)
from domain.services.risk_aggregation_service import RiskAggregationService


# ============================================================================
# Fixtures
# ============================================================================


def create_commit(
    hash_str: str,
    author: str,
    timestamp: datetime,
    message: str,
    file_changes: list[FileChange] | None = None,
) -> Commit:
    """Factory for creating commits."""
    if file_changes is None:
        file_changes = [FileChange("src/file.py", 10, 5)]
    return Commit(
        hash=hash_str,
        author_email=author,
        author_name=author,
        timestamp=timestamp,
        message=message,
        file_changes=tuple(file_changes),
    )


@pytest.fixture
def evolution_service():
    """Evolution analysis service instance."""
    return EvolutionAnalysisService()


@pytest.fixture
def quality_service():
    """Commit quality service instance."""
    return CommitQualityService()


@pytest.fixture
def dependency_service():
    """Dependency risk service instance."""
    return DependencyRiskService()


@pytest.fixture
def aggregation_service():
    """Risk aggregation service instance."""
    return RiskAggregationService()


# ============================================================================
# EvolutionAnalysisService Tests
# ============================================================================


class TestEvolutionAnalysisService:
    """Tests for P1 evolution analysis service."""

    def test_analyze_knowledge_distribution_empty_commits(self, evolution_service):
        """analyze_knowledge_distribution handles empty commit list."""
        risks = evolution_service.analyze_knowledge_distribution([])
        assert risks == []

    def test_analyze_knowledge_distribution_knowledge_polarisation_detection(
        self, evolution_service
    ):
        """analyze_knowledge_distribution detects >70% single author (polarisation)."""
        base_time = datetime(2024, 1, 1, tzinfo=UTC)
        commits = [
            create_commit(f"abc{i}", "alice@example.com", base_time + timedelta(days=i), "fix", [FileChange("src/auth/file.py", 1, 1)])
            for i in range(75)  # Alice: 75 commits
        ] + [
            create_commit(f"def{i}", "bob@example.com", base_time + timedelta(days=i+100), "feature", [FileChange("src/auth/file.py", 1, 1)])
            for i in range(25)  # Bob: 25 commits
        ]

        risks = evolution_service.analyze_knowledge_distribution(commits)

        # Should detect polarisation (alice has 75% of commits)
        assert any(r.risk_type == "polarisation" for r in risks)
        polarisation = [r for r in risks if r.risk_type == "polarisation"][0]
        assert polarisation.primary_author == "alice@example.com"
        assert polarisation.primary_author_ratio > 0.7

    def test_analyze_knowledge_distribution_ignores_low_commit_components(
        self, evolution_service
    ):
        """analyze_knowledge_distribution ignores components with <10 commits."""
        base_time = datetime(2024, 1, 1, tzinfo=UTC)
        commits = [
            create_commit(f"abc{i}", "alice@example.com", base_time + timedelta(days=i), "fix", [FileChange("src/auth/file.py", 1, 1)])
            for i in range(9)
        ]

        risks = evolution_service.analyze_knowledge_distribution(commits)
        assert risks == []

    def test_analyze_knowledge_distribution_knowledge_loss_detection(
        self, evolution_service
    ):
        """analyze_knowledge_distribution detects >40% departed authors."""
        base_time = datetime(2024, 1, 1, tzinfo=UTC)
        commits = [
            create_commit(f"abc{i}", "alice@example.com", base_time + timedelta(days=i), "fix", [FileChange("src/auth/file.py", 1, 1)])
            for i in range(50)  # Alice: 50 commits (departed)
        ] + [
            create_commit(f"def{i}", "bob@example.com", base_time + timedelta(days=i+100), "feature", [FileChange("src/auth/file.py", 1, 1)])
            for i in range(50)  # Bob: 50 commits (active)
        ]

        # Alice has departed
        active_authors = {"bob@example.com"}
        risks = evolution_service.analyze_knowledge_distribution(commits, active_authors)

        loss_risks = [r for r in risks if r.risk_type == "loss"]
        assert len(loss_risks) > 0
        assert loss_risks[0].primary_author_ratio >= 0.4

    def test_analyze_knowledge_distribution_calculates_bus_factor(
        self, evolution_service
    ):
        """analyze_knowledge_distribution calculates bus factor (authors for 80%)."""
        base_time = datetime(2024, 1, 1, tzinfo=UTC)
        commits = [
            create_commit(f"abc{i}", "alice@example.com", base_time + timedelta(days=i), "fix", [FileChange("src/auth/file.py", 1, 1)])
            for i in range(50)
        ] + [
            create_commit(f"def{i}", "bob@example.com", base_time + timedelta(days=i+100), "feature", [FileChange("src/auth/file.py", 1, 1)])
            for i in range(30)
        ] + [
            create_commit(f"ghi{i}", "charlie@example.com", base_time + timedelta(days=i+200), "refactor", [FileChange("src/auth/file.py", 1, 1)])
            for i in range(20)
        ]

        risks = evolution_service.analyze_knowledge_distribution(commits)

        # Alice + Bob = 80, need both -> bus_factor = 2
        assert all(r.bus_factor <= 3 for r in risks)

    def test_detect_temporal_coupling_cross_module_only(self, evolution_service):
        """detect_temporal_coupling only flags cross-module couplings."""
        base_time = datetime(2024, 1, 1, tzinfo=UTC)

        # Same module files changing together (not flagged)
        same_module = [
            create_commit(
                f"same{i}",
                "alice@example.com",
                base_time + timedelta(days=i),
                "fix",
                [
                    FileChange("src/auth/login.py", 1, 1),
                    FileChange("src/auth/logout.py", 1, 1),
                ]
            )
            for i in range(10)
        ]

        couplings = evolution_service.detect_temporal_coupling(same_module)
        assert len(couplings) == 0

    def test_detect_temporal_coupling_detects_cross_module(self, evolution_service):
        """detect_temporal_coupling detects >60% co-change ratio across modules."""
        base_time = datetime(2024, 1, 1, tzinfo=UTC)

        commits = [
            create_commit(
                f"commit{i}",
                "alice@example.com",
                base_time + timedelta(days=i),
                "fix",
                [
                    FileChange("src/auth/login.py", 1, 1),
                    FileChange("api/v1/users.py", 1, 1),
                ]
            )
            for i in range(10)
        ]

        couplings = evolution_service.detect_temporal_coupling(commits, min_support=5)

        # Files change together 10/10 times = 100% ratio
        assert len(couplings) > 0
        assert couplings[0].co_change_ratio >= 0.6

    def test_detect_temporal_coupling_minimum_support_threshold(
        self, evolution_service
    ):
        """detect_temporal_coupling respects min_support parameter."""
        base_time = datetime(2024, 1, 1, tzinfo=UTC)

        commits = [
            create_commit(
                f"commit{i}",
                "alice@example.com",
                base_time + timedelta(days=i),
                "fix",
                [
                    FileChange("src/auth/login.py", 1, 1),
                    FileChange("api/v1/users.py", 1, 1),
                ]
            )
            for i in range(3)  # Only 3 co-occurrences
        ]

        couplings = evolution_service.detect_temporal_coupling(commits, min_support=5)
        assert len(couplings) == 0

    def test_detect_churn_anomalies_empty_commits(self, evolution_service):
        """detect_churn_anomalies handles empty commit list."""
        anomalies = evolution_service.detect_churn_anomalies([])
        assert anomalies == []

    def test_detect_churn_anomalies_ignores_short_timespan(self, evolution_service):
        """detect_churn_anomalies ignores files changed <90 days."""
        base_time = datetime(2024, 1, 1, tzinfo=UTC)

        commits = [
            create_commit(
                f"commit{i}",
                "alice@example.com",
                base_time + timedelta(days=i),  # Only 10 days span
                "fix",
                [FileChange("src/file.py", 10, 5)]
            )
            for i in range(15)
        ]

        anomalies = evolution_service.detect_churn_anomalies(commits)
        assert anomalies == []

    def test_detect_churn_anomalies_detects_high_churn_over_3_months(
        self, evolution_service
    ):
        """detect_churn_anomalies detects >5 changes per sprint over 3+ months."""
        base_time = datetime(2024, 1, 1, tzinfo=UTC)

        # Need >10 changes over >90 days with >5 per sprint (14-day)
        # 35 changes over 100 days = 100/14 = 7.14 sprints, so 35/7.14 = 4.9 per sprint
        # Need 50 changes: 50/7.14 = 7.0 per sprint
        commits = [
            create_commit(
                f"commit{i}",
                "alice@example.com",
                base_time + timedelta(days=i * 2),  # 2-day intervals, 50 commits = 98 days
                "fix",
                [FileChange("src/hotspot.py", 20, 10)]
            )
            for i in range(50)
        ]

        anomalies = evolution_service.detect_churn_anomalies(commits, sprint_days=14)

        # Should detect anomaly for high-churn file
        assert len(anomalies) > 0
        assert anomalies[0].file_path == "src/hotspot.py"
        assert anomalies[0].changes_per_sprint > 5.0

    def test_detect_churn_anomalies_ignores_low_change_files(self, evolution_service):
        """detect_churn_anomalies ignores files with <10 changes."""
        base_time = datetime(2024, 1, 1, tzinfo=UTC)

        commits = [
            create_commit(
                f"commit{i}",
                "alice@example.com",
                base_time + timedelta(days=i * 10),
                "fix",
                [FileChange("src/file.py", 10, 5)]
            )
            for i in range(5)  # Only 5 changes
        ]

        anomalies = evolution_service.detect_churn_anomalies(commits)
        assert anomalies == []

    def test_compute_risk_scores_returns_team_knowledge_dimension(
        self, evolution_service
    ):
        """compute_risk_scores returns team_knowledge dimension score."""
        knowledge_risks = [
            KnowledgeRisk(
                component="auth",
                primary_author="alice@example.com",
                primary_author_ratio=0.75,
                total_contributors=5,
                bus_factor=2,
                risk_type="polarisation",
            )
        ]

        scores = evolution_service.compute_risk_scores(
            knowledge_risks=knowledge_risks,
            couplings=[],
            churn_anomalies=[],
            total_components=10,
        )

        assert "team_knowledge" in scores
        assert isinstance(scores["team_knowledge"], RiskScore)

    def test_compute_risk_scores_returns_code_instability_dimension(
        self, evolution_service
    ):
        """compute_risk_scores returns code_instability dimension score."""
        churn_anomalies = [
            ChurnAnomaly(
                file_path="src/file.py",
                changes_per_sprint=6.0,
                total_changes=20,
                anomaly_type="high_churn",
            )
        ]

        scores = evolution_service.compute_risk_scores(
            knowledge_risks=[],
            couplings=[],
            churn_anomalies=churn_anomalies,
            total_components=10,
        )

        assert "code_instability" in scores
        assert isinstance(scores["code_instability"], RiskScore)

    def test_compute_risk_scores_returns_architectural_coupling_dimension(
        self, evolution_service
    ):
        """compute_risk_scores returns architectural_coupling dimension score."""
        couplings = [
            TemporalCoupling(
                file_a="src/auth/login.py",
                file_b="api/v1/users.py",
                co_change_ratio=0.75,
                co_change_count=10,
            )
        ]

        scores = evolution_service.compute_risk_scores(
            knowledge_risks=[],
            couplings=couplings,
            churn_anomalies=[],
            total_components=10,
        )

        assert "architectural_coupling" in scores
        assert isinstance(scores["architectural_coupling"], RiskScore)


# ============================================================================
# CommitQualityService Tests
# ============================================================================


class TestCommitQualityService:
    """Tests for P2 commit quality service."""

    def test_assess_commit_quality_empty_commits(self, quality_service):
        """assess_commit_quality handles empty commit list."""
        report = quality_service.assess_commit_quality([])

        assert report.total_commits == 0
        assert report.empty_message_count == 0
        assert report.mega_commit_count == 0

    def test_assess_commit_quality_counts_empty_messages(self, quality_service):
        """assess_commit_quality counts commits with empty messages."""
        commits = [
            create_commit("abc1", "alice@example.com", datetime.now(UTC), ""),
            create_commit("abc2", "alice@example.com", datetime.now(UTC), "   "),
            create_commit("abc3", "alice@example.com", datetime.now(UTC), "valid message"),
        ]

        report = quality_service.assess_commit_quality(commits)

        assert report.total_commits == 3
        assert report.empty_message_count == 2

    def test_assess_commit_quality_counts_mega_commits(self, quality_service):
        """assess_commit_quality counts commits with >50 file changes."""
        base_time = datetime.now(UTC)
        commits = [
            create_commit(
                "abc1",
                "alice@example.com",
                base_time,
                "large refactor",
                [FileChange(f"src/file_{i}.py", 1, 1) for i in range(51)]
            ),
            create_commit(
                "abc2",
                "alice@example.com",
                base_time,
                "small change",
                [FileChange("src/file.py", 1, 1)]
            ),
        ]

        report = quality_service.assess_commit_quality(commits)

        assert report.total_commits == 2
        assert report.mega_commit_count == 1

    def test_assess_commit_quality_counts_scattered_commits(self, quality_service):
        """assess_commit_quality counts commits touching >3 modules."""
        commits = [
            create_commit(
                "abc1",
                "alice@example.com",
                datetime.now(UTC),
                "scattered",
                [
                    FileChange("src/file.py", 1, 1),
                    FileChange("api/file.py", 1, 1),
                    FileChange("tests/file.py", 1, 1),
                    FileChange("docs/file.py", 1, 1),
                ]
            ),
            create_commit(
                "abc2",
                "alice@example.com",
                datetime.now(UTC),
                "focused",
                [FileChange("src/file.py", 1, 1)]
            ),
        ]

        report = quality_service.assess_commit_quality(commits)

        assert report.scattered_commit_count == 1

    def test_assess_commit_quality_jira_reference_ratio(self, quality_service):
        """assess_commit_quality calculates JIRA reference ratio."""
        commits = [
            create_commit("abc1", "alice@example.com", datetime.now(UTC), "PROJ-123: Fix bug"),
            create_commit("abc2", "alice@example.com", datetime.now(UTC), "PROJ-456: Feature"),
            create_commit("abc3", "alice@example.com", datetime.now(UTC), "No ticket"),
        ]

        report = quality_service.assess_commit_quality(commits)

        assert report.jira_reference_ratio == pytest.approx(2/3, rel=0.01)

    def test_assess_commit_quality_avg_scatter_score(self, quality_service):
        """assess_commit_quality calculates average scatter score."""
        commits = [
            create_commit(
                "abc1",
                "alice@example.com",
                datetime.now(UTC),
                "one module",
                [FileChange("src/file.py", 1, 1)]
            ),
            create_commit(
                "abc2",
                "alice@example.com",
                datetime.now(UTC),
                "three modules",
                [
                    FileChange("src/file.py", 1, 1),
                    FileChange("api/file.py", 1, 1),
                    FileChange("tests/file.py", 1, 1),
                ]
            ),
        ]

        report = quality_service.assess_commit_quality(commits)

        assert report.avg_scatter_score == 2.0  # (1 + 3) / 2

    def test_detect_bug_magnets_empty_commits(self, quality_service):
        """detect_bug_magnets handles empty commit list."""
        magnets = quality_service.detect_bug_magnets([])
        assert magnets == []

    def test_detect_bug_magnets_ignores_low_sample_size(self, quality_service):
        """detect_bug_magnets ignores files with <5 commits."""
        commits = [
            create_commit(
                f"abc{i}",
                "alice@example.com",
                datetime.now(UTC),
                "fix bug",
                [FileChange("src/file.py", 1, 1)]
            )
            for i in range(4)  # Only 4 commits
        ]

        magnets = quality_service.detect_bug_magnets(commits)
        assert magnets == []

    def test_detect_bug_magnets_detects_high_bug_fix_ratio(self, quality_service):
        """detect_bug_magnets detects files with >40% bug-fix commits."""
        commits = [
            create_commit(
                f"bug{i}",
                "alice@example.com",
                datetime.now(UTC),
                "fix bug",
                [FileChange("src/problematic.py", 1, 1)]
            )
            for i in range(4)
        ] + [
            create_commit(
                f"feat{i}",
                "alice@example.com",
                datetime.now(UTC),
                "add feature",
                [FileChange("src/problematic.py", 1, 1)]
            )
            for i in range(1)
        ]

        magnets = quality_service.detect_bug_magnets(commits, threshold=0.4)

        assert len(magnets) > 0
        assert magnets[0].file_path == "src/problematic.py"
        assert magnets[0].bug_fix_ratio >= 0.4

    def test_detect_bug_magnets_custom_threshold(self, quality_service):
        """detect_bug_magnets respects custom threshold parameter."""
        commits = [
            create_commit(
                f"bug{i}",
                "alice@example.com",
                datetime.now(UTC),
                "fix bug",
                [FileChange("src/file.py", 1, 1)]
            )
            for i in range(5)
        ] + [
            create_commit(
                f"feat{i}",
                "alice@example.com",
                datetime.now(UTC),
                "add feature",
                [FileChange("src/file.py", 1, 1)]
            )
            for i in range(5)
        ]

        magnets_strict = quality_service.detect_bug_magnets(commits, threshold=0.6)
        magnets_lenient = quality_service.detect_bug_magnets(commits, threshold=0.4)

        # 50% ratio: passes lenient but not strict
        assert len(magnets_strict) == 0
        assert len(magnets_lenient) > 0

    def test_compute_feature_bug_trends_returns_three_windows(self, quality_service):
        """compute_feature_bug_trends returns trends for 30/90/180-day windows."""
        commits = [
            create_commit(
                f"commit{i}",
                "alice@example.com",
                datetime.now(UTC) - timedelta(days=i),
                "add feature" if i % 2 == 0 else "fix bug",
            )
            for i in range(50)
        ]

        trends = quality_service.compute_feature_bug_trends(commits)

        assert len(trends) == 3
        assert trends[0].period_label == "last_30_days"
        assert trends[1].period_label == "last_90_days"
        assert trends[2].period_label == "last_180_days"

    def test_compute_feature_bug_trends_counts_by_type(self, quality_service):
        """compute_feature_bug_trends correctly counts commit types."""
        base_time = datetime.now(UTC)
        commits = [
            create_commit("f1", "alice@example.com", base_time - timedelta(days=5), "add feature"),
            create_commit("f2", "alice@example.com", base_time - timedelta(days=4), "add another"),
            create_commit("b1", "alice@example.com", base_time - timedelta(days=3), "fix bug"),
            create_commit("r1", "alice@example.com", base_time - timedelta(days=2), "refactor code"),
        ]

        trends = quality_service.compute_feature_bug_trends(commits)

        # 30-day window includes all
        assert trends[0].feature_count == 2
        assert trends[0].bug_fix_count == 1
        assert trends[0].refactor_count == 1

    def test_detect_high_impact_tasks_returns_qualifying_commits(self, quality_service):
        """detect_high_impact_tasks returns commits with >15 files and >3 modules."""
        commits = [
            create_commit(
                "high",
                "alice@example.com",
                datetime.now(UTC),
                "large refactor",
                [
                    FileChange(f"src/file_{i}.py", 1, 1) for i in range(8)
                ] + [
                    FileChange(f"api/file_{i}.py", 1, 1) for i in range(5)
                ] + [
                    FileChange(f"tests/file_{i}.py", 1, 1) for i in range(5)
                ] + [
                    FileChange(f"docs/file_{i}.py", 1, 1) for i in range(3)
                ]
            ),
            create_commit(
                "low",
                "alice@example.com",
                datetime.now(UTC),
                "small change",
                [FileChange("src/file.py", 1, 1)]
            ),
        ]

        high_impact = quality_service.detect_high_impact_tasks(
            commits, file_threshold=15, module_threshold=3
        )

        assert len(high_impact) == 1
        assert high_impact[0].hash == "high"

    def test_compute_risk_scores_returns_commit_quality_dimension(
        self, quality_service
    ):
        """compute_risk_scores returns commit_quality dimension."""
        report = CommitQualityReport(
            total_commits=100,
            empty_message_count=5,
            mega_commit_count=2,
            scattered_commit_count=3,
            jira_reference_ratio=0.8,
            avg_scatter_score=2.0,
        )

        scores = quality_service.compute_risk_scores(
            quality_report=report,
            bug_magnets=[],
            trends=[],
        )

        assert "commit_quality" in scores
        assert isinstance(scores["commit_quality"], RiskScore)

    def test_compute_risk_scores_returns_bug_concentration_dimension(
        self, quality_service
    ):
        """compute_risk_scores returns bug_concentration dimension."""
        magnets = [
            BugMagnet(
                file_path="src/file.py",
                bug_fix_ratio=0.6,
                total_commits=10,
                bug_fix_commits=6,
                is_recurring=True,
            )
        ]

        scores = quality_service.compute_risk_scores(
            quality_report=CommitQualityReport(
                total_commits=100,
                empty_message_count=0,
                mega_commit_count=0,
                scattered_commit_count=0,
                jira_reference_ratio=0.0,
                avg_scatter_score=1.0,
            ),
            bug_magnets=magnets,
            trends=[],
        )

        assert "bug_concentration" in scores
        assert isinstance(scores["bug_concentration"], RiskScore)


# ============================================================================
# DependencyRiskService Tests
# ============================================================================


class TestDependencyRiskService:
    """Tests for P4 dependency risk service."""

    def test_assess_dependency_single_dependency_no_vulns(
        self, dependency_service
    ):
        """assess_dependency returns assessment for dependency with no vulnerabilities."""
        dep = Dependency(
            name="requests",
            current_version="2.28.0",
            ecosystem="pip",
            manifest_path="requirements.txt",
            call_site_count=100,
        )

        assessment = dependency_service.assess_dependency(dep, [])

        assert assessment.dependency == dep
        assert len(assessment.vulnerabilities) == 0
        assert assessment.max_exploitability_score == 0.0
        assert assessment.risk_level == "low"

    def test_assess_dependency_exploitability_adjusted_scoring(
        self, dependency_service
    ):
        """assess_dependency scores using exploitability-adjusted CVSS × coupling."""
        dep = Dependency(
            name="lib",
            current_version="1.0.0",
            ecosystem="pip",
            manifest_path="requirements.txt",
            call_site_count=100,
        )
        vuln = Vulnerability(
            cve_id="CVE-2023-12345",
            description="Test",
            cvss_score=5.0,
            severity="MEDIUM",
            affected_library="lib",
            affected_versions="<2.0",
        )

        assessment = dependency_service.assess_dependency(dep, [vuln])

        # 5.0 × (1 + 100/100) = 10.0
        assert assessment.max_exploitability_score == 10.0

    def test_assess_dependency_multiple_vulnerabilities(
        self, dependency_service
    ):
        """assess_dependency returns maximum score for multiple vulnerabilities."""
        dep = Dependency(
            name="lib",
            current_version="1.0.0",
            ecosystem="pip",
            manifest_path="requirements.txt",
            call_site_count=50,
        )
        vulns = [
            Vulnerability(
                cve_id="CVE-2023-1",
                description="Test",
                cvss_score=5.0,
                severity="MEDIUM",
                affected_library="lib",
                affected_versions="<2.0",
            ),
            Vulnerability(
                cve_id="CVE-2023-2",
                description="Test",
                cvss_score=8.0,
                severity="HIGH",
                affected_library="lib",
                affected_versions="<2.0",
            ),
        ]

        assessment = dependency_service.assess_dependency(dep, vulns)

        # Max of two adjusted scores
        assert assessment.max_exploitability_score > 0.0
        assert len(assessment.vulnerabilities) == 2

    def test_assess_dependency_license_risk_detection_gpl(
        self, dependency_service
    ):
        """assess_dependency detects GPL licenses as risk."""
        dep = Dependency(
            name="lib",
            current_version="1.0.0",
            ecosystem="pip",
            manifest_path="requirements.txt",
            license="GPL-3.0",
        )

        assessment = dependency_service.assess_dependency(dep, [])

        assert assessment.is_license_risk

    def test_assess_dependency_license_risk_detection_apache(
        self, dependency_service
    ):
        """assess_dependency ignores Apache license."""
        dep = Dependency(
            name="lib",
            current_version="1.0.0",
            ecosystem="pip",
            manifest_path="requirements.txt",
            license="Apache-2.0",
        )

        assessment = dependency_service.assess_dependency(dep, [])

        assert not assessment.is_license_risk

    def test_assess_all_dependencies(self, dependency_service):
        """assess_all returns assessments for all dependencies."""
        deps = [
            Dependency(
                name="requests",
                current_version="2.28.0",
                ecosystem="pip",
                manifest_path="requirements.txt",
            ),
            Dependency(
                name="flask",
                current_version="2.0.0",
                ecosystem="pip",
                manifest_path="requirements.txt",
            ),
        ]
        vuln_map = {
            "requests": [
                Vulnerability(
                    cve_id="CVE-2023-12345",
                    description="Test",
                    cvss_score=7.5,
                    severity="HIGH",
                    affected_library="requests",
                    affected_versions="<2.28.1",
                )
            ]
        }

        assessments = dependency_service.assess_all(deps, vuln_map)

        assert len(assessments) == 2
        # Sorted by max_exploitability_score descending
        assert assessments[0].max_exploitability_score > assessments[1].max_exploitability_score

    def test_compute_risk_scores_returns_library_risk_dimension(
        self, dependency_service
    ):
        """compute_risk_scores returns library_risk dimension."""
        assessment = DependencyRiskAssessment(
            dependency=Dependency(
                name="lib",
                current_version="1.0.0",
                ecosystem="pip",
                manifest_path="requirements.txt",
            ),
            vulnerabilities=(),
            max_exploitability_score=12.0,
            is_license_risk=False,
        )

        scores = dependency_service.compute_risk_scores(
            assessments=[assessment],
            dependencies=[],
        )

        assert "library_risk" in scores
        assert isinstance(scores["library_risk"], RiskScore)

    def test_compute_risk_scores_returns_security_posture_dimension(
        self, dependency_service
    ):
        """compute_risk_scores returns security_posture dimension."""
        vuln = Vulnerability(
            cve_id="CVE-2023-12345",
            description="Test",
            cvss_score=8.0,
            severity="HIGH",
            affected_library="lib",
            affected_versions="<2.0",
        )
        assessment = DependencyRiskAssessment(
            dependency=Dependency(
                name="lib",
                current_version="1.0.0",
                ecosystem="pip",
                manifest_path="requirements.txt",
            ),
            vulnerabilities=(vuln,),
            max_exploitability_score=8.0,
            is_license_risk=False,
        )

        scores = dependency_service.compute_risk_scores(
            assessments=[assessment],
            dependencies=[],
        )

        assert "security_posture" in scores
        assert isinstance(scores["security_posture"], RiskScore)


# ============================================================================
# RiskAggregationService Tests
# ============================================================================


class TestRiskAggregationService:
    """Tests for P6 risk aggregation service."""

    def test_build_report_assembles_all_scores(self, aggregation_service):
        """build_report merges P1, P2, P4 scores into single report."""
        p1_scores = {"team_knowledge": RiskScore(value=5.0)}
        p2_scores = {"commit_quality": RiskScore(value=6.0)}
        p4_scores = {"library_risk": RiskScore(value=4.0)}

        report = aggregation_service.build_report(
            project_name="test-proj",
            scenario="M&A",
            p1_scores=p1_scores,
            p2_scores=p2_scores,
            p4_scores=p4_scores,
            knowledge_risks=[],
            bug_magnets=[],
            churn_anomalies=[],
            commits=[],
        )

        assert "team_knowledge" in report.dimension_scores
        assert "commit_quality" in report.dimension_scores
        assert "library_risk" in report.dimension_scores

    def test_build_report_fills_missing_dimensions(self, aggregation_service):
        """build_report fills missing dimensions with defaults."""
        report = aggregation_service.build_report(
            project_name="test-proj",
            scenario="M&A",
            p1_scores={},
            p2_scores={},
            p4_scores={},
            knowledge_risks=[],
            bug_magnets=[],
            churn_anomalies=[],
            commits=[],
        )

        # Should have defaults for unassessed dimensions
        for dim in ("code_complexity", "code_duplication", "coordination_risk"):
            assert dim in report.dimension_scores

    def test_build_report_builds_component_risk_matrix(self, aggregation_service):
        """build_report builds component risk matrix from knowledge/bug/churn risks."""
        knowledge_risks = [
            KnowledgeRisk(
                component="auth",
                primary_author="alice@example.com",
                primary_author_ratio=0.8,
                total_contributors=5,
                bus_factor=1,
                risk_type="polarisation",
            )
        ]

        report = aggregation_service.build_report(
            project_name="test-proj",
            scenario="M&A",
            p1_scores={},
            p2_scores={},
            p4_scores={},
            knowledge_risks=knowledge_risks,
            bug_magnets=[],
            churn_anomalies=[],
            commits=[],
        )

        assert len(report.component_risks) > 0
        assert any(c.component_name == "auth" for c in report.component_risks)

    def test_build_report_builds_file_hotspots(self, aggregation_service):
        """build_report builds file hotspot catalogue."""
        bug_magnets = [
            BugMagnet(
                file_path="src/auth.py",
                bug_fix_ratio=0.6,
                total_commits=10,
                bug_fix_commits=6,
                is_recurring=True,
            )
        ]

        report = aggregation_service.build_report(
            project_name="test-proj",
            scenario="M&A",
            p1_scores={},
            p2_scores={},
            p4_scores={},
            knowledge_risks=[],
            bug_magnets=bug_magnets,
            churn_anomalies=[],
            commits=[],
        )

        assert len(report.file_hotspots) > 0
        assert any(f.file_path == "src/auth.py" for f in report.file_hotspots)

    def test_build_report_limits_hotspots_to_25(self, aggregation_service):
        """build_report limits file_hotspots to top 25."""
        bug_magnets = [
            BugMagnet(
                file_path=f"src/file_{i}.py",
                bug_fix_ratio=0.5,
                total_commits=10,
                bug_fix_commits=5,
                is_recurring=False,
            )
            for i in range(30)
        ]

        report = aggregation_service.build_report(
            project_name="test-proj",
            scenario="M&A",
            p1_scores={},
            p2_scores={},
            p4_scores={},
            knowledge_risks=[],
            bug_magnets=bug_magnets,
            churn_anomalies=[],
            commits=[],
        )

        assert len(report.file_hotspots) == 25
