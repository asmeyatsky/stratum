"""
Comprehensive tests for the DesignAntipatternService (P3).

Tests cover:
- God Class detection: large files, non-OOP files, empty commits
- Feature Envy detection: cross-module coupling, same-module coupling
- Shotgun Surgery detection: widespread co-changes, minimal co-changes
- Data Class detection: model files with high field estimates, regular code
- Risk score computation: no anti-patterns vs many anti-patterns
"""

import pytest
from datetime import datetime, UTC

from domain.entities.commit import Commit
from domain.entities.file_change import FileChange
from domain.services.design_antipattern_service import DesignAntipatternService
from domain.value_objects.risk_score import RiskScore


# ============================================================================
# Helpers
# ============================================================================


def create_commit(
    hash_str: str,
    author: str,
    message: str,
    file_changes: list[FileChange],
    timestamp: datetime | None = None,
) -> Commit:
    """Factory for creating test commits."""
    return Commit(
        hash=hash_str,
        author_email=author,
        author_name=author,
        timestamp=timestamp or datetime.now(UTC),
        message=message,
        file_changes=tuple(file_changes),
    )


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def service():
    """DesignAntipatternService instance."""
    return DesignAntipatternService()


# ============================================================================
# God Class Detection Tests
# ============================================================================


class TestDetectGodClasses:
    """Tests for detect_god_classes."""

    def test_detect_god_classes_with_large_files(self, service):
        """Files with >300 lines added should be detected as god class candidates.

        With 350 lines added: estimated_methods = 350 // 15 = 23 (> 20 threshold).
        """
        commits = [
            create_commit(
                "abc1",
                "alice@example.com",
                "add large service",
                [FileChange("src/service/BigService.java", 350, 0)],
            ),
        ]

        candidates = service.detect_god_classes(commits)

        assert len(candidates) > 0
        assert candidates[0].file_path == "src/service/BigService.java"
        assert candidates[0].estimated_methods > 20
        assert candidates[0].reason in ("excessive_methods", "both")

    def test_detect_god_classes_ignores_non_oop_files(self, service):
        """Non-OOP files (.json, .md) should not produce god class candidates."""
        commits = [
            create_commit(
                "abc1",
                "alice@example.com",
                "add config",
                [
                    FileChange("config/settings.json", 500, 0),
                    FileChange("docs/README.md", 400, 0),
                    FileChange("data/output.csv", 600, 0),
                ],
            ),
        ]

        candidates = service.detect_god_classes(commits)

        assert len(candidates) == 0

    def test_detect_god_classes_empty_commits(self, service):
        """Empty commit list should return no candidates."""
        candidates = service.detect_god_classes([])

        assert candidates == []

    def test_detect_god_classes_small_files_not_flagged(self, service):
        """Files with few lines added should not be flagged."""
        commits = [
            create_commit(
                "abc1",
                "alice@example.com",
                "small change",
                [FileChange("src/util/Helper.py", 30, 5)],
            ),
        ]

        candidates = service.detect_god_classes(commits)

        assert len(candidates) == 0

    def test_detect_god_classes_model_file_excessive_fields(self, service):
        """Model files with many lines should be flagged for excessive fields.

        A model file with 100 lines: estimated_fields = 100 // 2 = 50 (> 15).
        """
        commits = [
            create_commit(
                "abc1",
                "alice@example.com",
                "add user model",
                [FileChange("src/models/UserModel.py", 100, 0)],
            ),
        ]

        candidates = service.detect_god_classes(commits)

        assert len(candidates) > 0
        assert candidates[0].estimated_fields > 15

    def test_detect_god_classes_sorted_by_methods_descending(self, service):
        """Candidates should be sorted by estimated_methods in descending order."""
        commits = [
            create_commit(
                "abc1",
                "alice@example.com",
                "add services",
                [
                    FileChange("src/SmallService.py", 350, 0),
                    FileChange("src/BigService.py", 600, 0),
                ],
            ),
        ]

        candidates = service.detect_god_classes(commits)

        assert len(candidates) >= 2
        assert candidates[0].estimated_methods >= candidates[1].estimated_methods


# ============================================================================
# Feature Envy Detection Tests
# ============================================================================


class TestDetectFeatureEnvy:
    """Tests for detect_feature_envy."""

    def test_detect_feature_envy_cross_module(self, service):
        """Files co-changing mostly with files in other modules should be flagged."""
        # Create commits where src/auth/handler.py always changes with files
        # in api/, db/, and utils/ (external) but rarely with src/auth/ (own)
        commits = []
        for i in range(10):
            commits.append(
                create_commit(
                    f"commit_{i}",
                    "alice@example.com",
                    "cross-module change",
                    [
                        FileChange("src/auth/handler.py", 5, 2),
                        FileChange("api/routes/users.py", 3, 1),
                        FileChange("db/queries/auth.py", 2, 1),
                    ],
                )
            )

        candidates = service.detect_feature_envy(commits)

        # handler.py co-changes with 2 external files per commit (10 times)
        # external = 20, own = 0 => ratio = 1.0 > 0.6
        auth_candidates = [c for c in candidates if "handler.py" in c.file_path]
        assert len(auth_candidates) > 0
        assert auth_candidates[0].coupling_ratio > 0.6

    def test_detect_feature_envy_same_module(self, service):
        """Files co-changing only within same module should not be flagged."""
        commits = []
        for i in range(10):
            commits.append(
                create_commit(
                    f"commit_{i}",
                    "alice@example.com",
                    "same-module change",
                    [
                        FileChange("src/auth/handler.py", 5, 2),
                        FileChange("src/auth/validator.py", 3, 1),
                        FileChange("src/auth/middleware.py", 2, 1),
                    ],
                )
            )

        candidates = service.detect_feature_envy(commits)

        # All files are in src/auth — own-module co-changes only
        auth_candidates = [c for c in candidates if "handler.py" in c.file_path]
        assert len(auth_candidates) == 0

    def test_detect_feature_envy_ignores_non_oop_files(self, service):
        """Non-OOP files should not appear as feature envy candidates."""
        commits = []
        for i in range(10):
            commits.append(
                create_commit(
                    f"commit_{i}",
                    "alice@example.com",
                    "config change",
                    [
                        FileChange("config/app.json", 5, 2),
                        FileChange("api/routes.py", 3, 1),
                    ],
                )
            )

        candidates = service.detect_feature_envy(commits)

        json_candidates = [c for c in candidates if c.file_path.endswith(".json")]
        assert len(json_candidates) == 0

    def test_detect_feature_envy_requires_minimum_co_changes(self, service):
        """Files with fewer than 5 total co-changes should not be flagged."""
        commits = [
            create_commit(
                f"commit_{i}",
                "alice@example.com",
                "rare change",
                [
                    FileChange("src/auth/handler.py", 5, 2),
                    FileChange("api/routes.py", 3, 1),
                ],
            )
            for i in range(3)  # Only 3 co-changes, below threshold of 5
        ]

        candidates = service.detect_feature_envy(commits)

        auth_candidates = [c for c in candidates if "handler.py" in c.file_path]
        assert len(auth_candidates) == 0


# ============================================================================
# Shotgun Surgery Detection Tests
# ============================================================================


class TestDetectShotgunSurgery:
    """Tests for detect_shotgun_surgery."""

    def test_detect_shotgun_surgery_widespread(self, service):
        """File co-changing with many files across many modules should be flagged."""
        # Create commits where core/engine.py always changes alongside files
        # in 5+ different modules
        commits = []
        external_files = [
            "api/routes/main.py",
            "db/models/user.py",
            "auth/handler.py",
            "utils/helpers.py",
            "config/settings.py",
            "web/views.py",
        ]
        for i in range(5):
            commits.append(
                create_commit(
                    f"commit_{i}",
                    "alice@example.com",
                    "widespread change",
                    [FileChange("core/engine.py", 10, 5)]
                    + [FileChange(f, 2, 1) for f in external_files],
                )
            )

        candidates = service.detect_shotgun_surgery(commits, min_support=3)

        engine_candidates = [c for c in candidates if "engine.py" in c.file_path]
        assert len(engine_candidates) > 0
        assert engine_candidates[0].co_changing_modules_count >= 3
        assert engine_candidates[0].co_changing_files_count >= 5

    def test_detect_shotgun_surgery_minimal(self, service):
        """File with few co-changes should not be flagged."""
        commits = [
            create_commit(
                f"commit_{i}",
                "alice@example.com",
                "small change",
                [
                    FileChange("core/engine.py", 10, 5),
                    FileChange("core/utils.py", 2, 1),
                ],
            )
            for i in range(5)
        ]

        candidates = service.detect_shotgun_surgery(commits, min_support=3)

        # Only co-changes within same module and with 1 file
        engine_candidates = [c for c in candidates if "engine.py" in c.file_path]
        assert len(engine_candidates) == 0

    def test_detect_shotgun_surgery_respects_min_support(self, service):
        """Pairs with fewer co-changes than min_support should be ignored."""
        external_files = [
            "api/routes/main.py",
            "db/models/user.py",
            "auth/handler.py",
            "utils/helpers.py",
            "config/settings.py",
            "web/views.py",
        ]
        # Only 2 commits — below min_support=3
        commits = [
            create_commit(
                f"commit_{i}",
                "alice@example.com",
                "rare change",
                [FileChange("core/engine.py", 10, 5)]
                + [FileChange(f, 2, 1) for f in external_files],
            )
            for i in range(2)
        ]

        candidates = service.detect_shotgun_surgery(commits, min_support=3)

        assert len(candidates) == 0


# ============================================================================
# Data Class Detection Tests
# ============================================================================


class TestDetectDataClasses:
    """Tests for detect_data_classes."""

    def test_detect_data_classes_model_files(self, service):
        """Model-like paths with high field estimates should be detected.

        A model file with 60 lines: estimated_fields = 60 // 2 = 30 (>= 5),
        estimated_methods = 60 // 15 = 4, ratio = 4/30 = 0.133 (< 0.5).
        """
        commits = [
            create_commit(
                "abc1",
                "alice@example.com",
                "add user model",
                [FileChange("src/models/UserModel.py", 60, 0)],
            ),
        ]

        candidates = service.detect_data_classes(commits)

        assert len(candidates) > 0
        assert candidates[0].file_path == "src/models/UserModel.py"
        assert candidates[0].estimated_fields >= 5
        assert candidates[0].method_to_field_ratio < 0.5

    def test_detect_data_classes_regular_code(self, service):
        """Regular code files with normal method-to-field ratio should not be flagged.

        A regular file with 100 lines: estimated_fields = 100 // 10 = 10,
        estimated_methods = 100 // 15 = 6, ratio = 6/10 = 0.6 (>= 0.5).
        Since it's not a data-named path, 0.6 >= 0.5 means not flagged.
        """
        commits = [
            create_commit(
                "abc1",
                "alice@example.com",
                "add service",
                [FileChange("src/services/AuthService.py", 100, 0)],
            ),
        ]

        candidates = service.detect_data_classes(commits)

        service_candidates = [c for c in candidates if "AuthService" in c.file_path]
        assert len(service_candidates) == 0

    def test_detect_data_classes_dto_path(self, service):
        """Files with 'dto' in path and moderate lines should be flagged."""
        commits = [
            create_commit(
                "abc1",
                "alice@example.com",
                "add dto",
                [FileChange("src/dto/UserDTO.py", 40, 0)],
            ),
        ]

        candidates = service.detect_data_classes(commits)

        dto_candidates = [c for c in candidates if "UserDTO" in c.file_path]
        assert len(dto_candidates) > 0

    def test_detect_data_classes_empty_commits(self, service):
        """Empty commit list should return no candidates."""
        candidates = service.detect_data_classes([])
        assert candidates == []

    def test_detect_data_classes_sorted_by_ratio_ascending(self, service):
        """Candidates should be sorted by method_to_field_ratio in ascending order."""
        commits = [
            create_commit(
                "abc1",
                "alice@example.com",
                "add models",
                [
                    FileChange("src/models/SmallModel.py", 40, 0),
                    FileChange("src/models/LargeModel.py", 120, 0),
                ],
            ),
        ]

        candidates = service.detect_data_classes(commits)

        if len(candidates) >= 2:
            assert candidates[0].method_to_field_ratio <= candidates[1].method_to_field_ratio


# ============================================================================
# Risk Score Computation Tests
# ============================================================================


class TestComputeRiskScores:
    """Tests for compute_risk_scores."""

    def test_compute_risk_scores_no_antipatterns(self, service):
        """No anti-patterns should produce low scores."""
        scores = service.compute_risk_scores(
            god_classes=[],
            feature_envy=[],
            shotgun_surgery=[],
            data_classes=[],
        )

        assert "code_complexity" in scores
        assert "code_duplication" in scores
        assert isinstance(scores["code_complexity"], RiskScore)
        assert isinstance(scores["code_duplication"], RiskScore)
        assert scores["code_complexity"].value == 0.0
        assert scores["code_duplication"].value == 0.0

    def test_compute_risk_scores_many_antipatterns(self, service):
        """Many anti-patterns should produce high scores."""
        # Build enough commits to produce many anti-patterns
        commits = []

        # Add large files across multiple modules for god classes
        large_file_changes = [
            FileChange(f"src/module{m}/BigClass{i}.java", 500, 0)
            for m in range(4)
            for i in range(3)
        ]
        commits.append(
            create_commit("big1", "alice@example.com", "add big classes", large_file_changes)
        )

        god_classes = service.detect_god_classes(commits)
        feature_envy = service.detect_feature_envy(commits)
        shotgun_surgery = service.detect_shotgun_surgery(commits)
        data_classes = service.detect_data_classes(commits)

        scores = service.compute_risk_scores(
            god_classes=god_classes,
            feature_envy=feature_envy,
            shotgun_surgery=shotgun_surgery,
            data_classes=data_classes,
        )

        # With 12 god class candidates, complexity should be high
        assert scores["code_complexity"].value > 5.0

    def test_compute_risk_scores_returns_evidence(self, service):
        """Risk scores should include evidence strings."""
        commits = [
            create_commit(
                "abc1",
                "alice@example.com",
                "add large file",
                [FileChange("src/BigService.py", 500, 0)],
            ),
        ]

        god_classes = service.detect_god_classes(commits)

        scores = service.compute_risk_scores(
            god_classes=god_classes,
            feature_envy=[],
            shotgun_surgery=[],
            data_classes=[],
        )

        assert len(scores["code_complexity"].evidence) > 0
        assert "God Class" in scores["code_complexity"].evidence

    def test_compute_risk_scores_capped_at_10(self, service):
        """Risk scores should never exceed 10.0."""
        # Create an extreme number of god classes
        commits = [
            create_commit(
                f"commit_{i}",
                "alice@example.com",
                "add massive file",
                [FileChange(f"src/module{i}/HugeClass.java", 1000, 0)],
            )
            for i in range(50)
        ]

        god_classes = service.detect_god_classes(commits)

        scores = service.compute_risk_scores(
            god_classes=god_classes,
            feature_envy=[],
            shotgun_surgery=[],
            data_classes=[],
        )

        assert scores["code_complexity"].value <= 10.0
        assert scores["code_duplication"].value <= 10.0

    def test_compute_risk_scores_duplication_from_shotgun_surgery(self, service):
        """Shotgun surgery candidates should contribute to code_duplication score."""
        # Build commits that trigger shotgun surgery detection
        external_files = [
            "api/routes/main.py",
            "db/models/user.py",
            "auth/handler.py",
            "utils/helpers.py",
            "config/settings.py",
            "web/views.py",
        ]
        commits = [
            create_commit(
                f"commit_{i}",
                "alice@example.com",
                "widespread change",
                [FileChange("core/engine.py", 10, 5)]
                + [FileChange(f, 2, 1) for f in external_files],
            )
            for i in range(5)
        ]

        shotgun_surgery = service.detect_shotgun_surgery(commits, min_support=3)

        scores = service.compute_risk_scores(
            god_classes=[],
            feature_envy=[],
            shotgun_surgery=shotgun_surgery,
            data_classes=[],
        )

        if len(shotgun_surgery) > 0:
            assert scores["code_duplication"].value > 0.0
