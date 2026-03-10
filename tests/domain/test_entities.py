"""
Comprehensive tests for all domain entities.

Tests cover:
- Author: canonical_id normalization, aliases, email matching
- FileChange: churn calculation, module extraction, binary detection
- Commit: classification (bug_fix, feature, refactor), jira references, mega_commit, scatter_score
- Dependency: outdated detection, coupling_strength, end_of_life, immutability
- Vulnerability: exploitability_adjusted_score calculation, remediation_action
- RiskReport: overall_health_score, top_risks, immutability, to_dict serialization
"""

import pytest
from datetime import datetime, timedelta, UTC

from domain.entities.author import Author
from domain.entities.file_change import FileChange
from domain.entities.commit import Commit
from domain.entities.dependency import Dependency
from domain.entities.vulnerability import Vulnerability
from domain.entities.risk_report import RiskReport, ComponentRisk, FileHotspot
from domain.value_objects.risk_score import RiskScore


# ============================================================================
# Fixtures & Factories
# ============================================================================


@pytest.fixture
def sample_author():
    """Factory fixture for author."""
    return Author(name="Alice Developer", email="alice@example.com")


@pytest.fixture
def sample_file_change():
    """Factory fixture for file change."""
    return FileChange(file_path="src/module/file.py", lines_added=50, lines_deleted=10)


@pytest.fixture
def sample_commit(sample_author):
    """Factory fixture for commit."""
    return Commit(
        hash="abc123def456",
        author_email=sample_author.email,
        author_name=sample_author.name,
        timestamp=datetime.now(UTC),
        message="fix: resolve critical bug in auth module",
        file_changes=(FileChange("src/auth/login.py", 20, 5),),
    )


@pytest.fixture
def sample_dependency():
    """Factory fixture for dependency."""
    return Dependency(
        name="requests",
        current_version="2.28.0",
        latest_version="2.31.0",
        ecosystem="pip",
        manifest_path="requirements.txt",
        call_site_count=150,
        license="Apache-2.0",
    )


@pytest.fixture
def sample_vulnerability():
    """Factory fixture for vulnerability."""
    return Vulnerability(
        cve_id="CVE-2023-12345",
        description="Code execution vulnerability in requests library",
        cvss_score=7.5,
        severity="HIGH",
        affected_library="requests",
        affected_versions="<=2.28.0",
        fix_version="2.28.1",
    )


@pytest.fixture
def sample_risk_score():
    """Factory fixture for risk score."""
    return RiskScore(value=5.5, label="Test Dimension", evidence="Test evidence")


@pytest.fixture
def sample_risk_report():
    """Factory fixture for risk report."""
    return RiskReport(
        project_name="my-project",
        analysis_timestamp=datetime.now(UTC),
        scenario="M&A",
    )


# ============================================================================
# Author Tests
# ============================================================================


class TestAuthor:
    """Tests for Author entity."""

    def test_canonical_id_normalizes_email(self):
        """canonical_id returns lowercase stripped email."""
        author = Author(name="Alice", email="  ALICE@EXAMPLE.COM  ")
        assert author.canonical_id == "alice@example.com"

    def test_canonical_id_consistent_across_instances(self):
        """canonical_id is same for different Author instances with same email."""
        a1 = Author(name="Alice", email="alice@example.com")
        a2 = Author(name="Alice Smith", email="ALICE@EXAMPLE.COM")
        assert a1.canonical_id == a2.canonical_id

    def test_canonical_id_empty_email(self):
        """canonical_id handles empty email."""
        author = Author(name="Unknown", email="")
        assert author.canonical_id == ""

    def test_with_alias_adds_new_alias(self):
        """with_alias returns new Author instance with added alias."""
        author = Author(name="Alice", email="alice@example.com")
        author_with_alias = author.with_alias("alice.smith@example.com")

        assert author_with_alias.aliases == ("alice.smith@example.com",)
        assert author.aliases == ()
        assert author_with_alias.name == author.name
        assert author_with_alias.email == author.email

    def test_with_alias_prevents_duplicate_case_insensitive(self):
        """with_alias ignores duplicate aliases (case-insensitive)."""
        author = Author(name="Alice", email="alice@example.com", aliases=("alice2@example.com",))
        author_with_alias = author.with_alias("ALICE2@EXAMPLE.COM")

        assert author_with_alias.aliases == ("alice2@example.com",)

    def test_with_alias_chains_multiple_aliases(self):
        """with_alias can chain to add multiple aliases."""
        author = Author(name="Alice", email="alice@example.com")
        author = author.with_alias("alice2@example.com")
        author = author.with_alias("alice3@example.com")

        assert author.aliases == ("alice2@example.com", "alice3@example.com")

    def test_with_alias_immutability(self):
        """with_alias returns new instance, original unchanged."""
        original = Author(name="Alice", email="alice@example.com")
        modified = original.with_alias("alias@example.com")

        assert original is not modified
        assert original.aliases == ()
        assert modified.aliases == ("alias@example.com",)

    def test_matches_canonical_email(self):
        """matches returns True for canonical email."""
        author = Author(name="Alice", email="alice@example.com")
        assert author.matches("alice@example.com")
        assert author.matches("ALICE@EXAMPLE.COM")
        assert author.matches("  alice@example.com  ")

    def test_matches_alias_email(self):
        """matches returns True for aliased emails."""
        author = Author(
            name="Alice",
            email="alice@example.com",
            aliases=("alice.smith@example.com", "asmith@example.com")
        )
        assert author.matches("alice.smith@example.com")
        assert author.matches("ASMITH@EXAMPLE.COM")
        assert author.matches("  alice.smith@example.com  ")

    def test_matches_returns_false_for_non_matching_email(self):
        """matches returns False for unrelated email."""
        author = Author(name="Alice", email="alice@example.com")
        assert not author.matches("bob@example.com")
        assert not author.matches("alice@different.com")

    def test_author_is_frozen(self):
        """Author instance is immutable."""
        author = Author(name="Alice", email="alice@example.com")
        with pytest.raises(AttributeError):
            author.name = "Bob"


# ============================================================================
# FileChange Tests
# ============================================================================


class TestFileChange:
    """Tests for FileChange entity."""

    def test_churn_sums_lines_added_and_deleted(self):
        """churn returns sum of lines_added and lines_deleted."""
        fc = FileChange(file_path="src/file.py", lines_added=50, lines_deleted=30)
        assert fc.churn == 80

    def test_churn_with_zero_changes(self):
        """churn handles zero changes."""
        fc = FileChange(file_path="src/file.py", lines_added=0, lines_deleted=0)
        assert fc.churn == 0

    def test_churn_with_large_numbers(self):
        """churn handles large numbers."""
        fc = FileChange(file_path="src/file.py", lines_added=10000, lines_deleted=5000)
        assert fc.churn == 15000

    def test_is_binary_true_for_zero_changes_with_path(self):
        """is_binary returns True for 0/0 lines with non-empty path."""
        fc = FileChange(file_path="assets/image.png", lines_added=0, lines_deleted=0)
        assert fc.is_binary

    def test_is_binary_false_for_empty_path(self):
        """is_binary returns False for empty path."""
        fc = FileChange(file_path="", lines_added=0, lines_deleted=0)
        assert not fc.is_binary

    def test_is_binary_false_for_text_changes(self):
        """is_binary returns False for text file with changes."""
        fc = FileChange(file_path="src/file.py", lines_added=10, lines_deleted=5)
        assert not fc.is_binary

    def test_module_extraction_single_level(self):
        """module returns top-level directory from multi-level path."""
        fc = FileChange(file_path="src/module/submodule/file.py", lines_added=10, lines_deleted=5)
        assert fc.module == "src"

    def test_module_extraction_root_file(self):
        """module returns (root) for files without directory."""
        fc = FileChange(file_path="README.md", lines_added=10, lines_deleted=5)
        assert fc.module == "(root)"

    def test_module_extraction_single_directory(self):
        """module returns the single directory."""
        fc = FileChange(file_path="config/settings.yaml", lines_added=5, lines_deleted=2)
        assert fc.module == "config"

    def test_module_with_nested_directories(self):
        """module returns first-level directory from nested path."""
        fc = FileChange(
            file_path="src/api/v1/routes/users.py",
            lines_added=20,
            lines_deleted=10
        )
        assert fc.module == "src"

    def test_file_change_is_frozen(self):
        """FileChange instance is immutable."""
        fc = FileChange(file_path="src/file.py", lines_added=10, lines_deleted=5)
        with pytest.raises(AttributeError):
            fc.file_path = "other/file.py"


# ============================================================================
# Commit Tests
# ============================================================================


class TestCommit:
    """Tests for Commit entity."""

    def test_is_bug_fix_detects_fix_keyword(self):
        """is_bug_fix returns True for commit with 'fix' keyword."""
        commit = Commit(
            hash="abc123",
            author_email="dev@example.com",
            author_name="Dev",
            timestamp=datetime.now(UTC),
            message="fix: critical authentication bug",
        )
        assert commit.is_bug_fix

    def test_is_bug_fix_detects_multiple_keywords(self):
        """is_bug_fix detects various bug-related keywords."""
        keywords = ["fix", "bug", "defect", "patch", "hotfix", "resolve", "issue"]
        for kw in keywords:
            commit = Commit(
                hash="abc123",
                author_email="dev@example.com",
                author_name="Dev",
                timestamp=datetime.now(UTC),
                message=f"WIP: {kw} something broken",
            )
            assert commit.is_bug_fix, f"Failed for keyword: {kw}"

    def test_is_bug_fix_case_insensitive(self):
        """is_bug_fix is case-insensitive."""
        commit = Commit(
            hash="abc123",
            author_email="dev@example.com",
            author_name="Dev",
            timestamp=datetime.now(UTC),
            message="BUGFIX: Something",
        )
        assert commit.is_bug_fix

    def test_is_bug_fix_false_for_non_bug_commit(self):
        """is_bug_fix returns False for non-bug commits."""
        commit = Commit(
            hash="abc123",
            author_email="dev@example.com",
            author_name="Dev",
            timestamp=datetime.now(UTC),
            message="add new user interface component",
        )
        assert not commit.is_bug_fix

    def test_is_refactor_detects_refactor_keyword(self):
        """is_refactor returns True for commits with refactor keyword."""
        keywords = ["refactor", "restructure", "cleanup", "clean up", "extract", "simplify"]
        for kw in keywords:
            commit = Commit(
                hash="abc123",
                author_email="dev@example.com",
                author_name="Dev",
                timestamp=datetime.now(UTC),
                message=f"work: {kw} module structure",
            )
            assert commit.is_refactor, f"Failed for keyword: {kw}"

    def test_is_refactor_false_for_bug_fix(self):
        """is_refactor returns False for bug fixes."""
        commit = Commit(
            hash="abc123",
            author_email="dev@example.com",
            author_name="Dev",
            timestamp=datetime.now(UTC),
            message="fix: critical bug",
        )
        assert not commit.is_refactor

    def test_is_feature_true_for_non_bugfix_non_refactor(self):
        """is_feature returns True when not a bug fix or refactor."""
        commit = Commit(
            hash="abc123",
            author_email="dev@example.com",
            author_name="Dev",
            timestamp=datetime.now(UTC),
            message="add OAuth2 authentication support",
        )
        assert commit.is_feature
        assert not commit.is_bug_fix
        assert not commit.is_refactor

    def test_commit_type_bug_fix(self):
        """commit_type returns 'bug_fix' for bug-fix commits."""
        commit = Commit(
            hash="abc123",
            author_email="dev@example.com",
            author_name="Dev",
            timestamp=datetime.now(UTC),
            message="fix: memory leak in parser",
        )
        assert commit.commit_type == "bug_fix"

    def test_commit_type_refactor(self):
        """commit_type returns 'refactor' for refactor commits."""
        commit = Commit(
            hash="abc123",
            author_email="dev@example.com",
            author_name="Dev",
            timestamp=datetime.now(UTC),
            message="refactor: simplify request handler",
        )
        assert commit.commit_type == "refactor"

    def test_commit_type_feature(self):
        """commit_type returns 'feature' for feature commits."""
        commit = Commit(
            hash="abc123",
            author_email="dev@example.com",
            author_name="Dev",
            timestamp=datetime.now(UTC),
            message="add REST API endpoints",
        )
        assert commit.commit_type == "feature"

    def test_jira_references_single_reference(self):
        """jira_references extracts single JIRA ticket reference."""
        commit = Commit(
            hash="abc123",
            author_email="dev@example.com",
            author_name="Dev",
            timestamp=datetime.now(UTC),
            message="PROJ-123: Fix authentication flow",
        )
        assert commit.jira_references == ("PROJ-123",)

    def test_jira_references_multiple_references(self):
        """jira_references extracts multiple JIRA references."""
        commit = Commit(
            hash="abc123",
            author_email="dev@example.com",
            author_name="Dev",
            timestamp=datetime.now(UTC),
            message="Fix PROJ-123 and PROJ-456 related to auth and payment",
        )
        assert set(commit.jira_references) == {"PROJ-123", "PROJ-456"}

    def test_jira_references_no_references(self):
        """jira_references returns empty tuple when no JIRA refs."""
        commit = Commit(
            hash="abc123",
            author_email="dev@example.com",
            author_name="Dev",
            timestamp=datetime.now(UTC),
            message="Fix something without jira reference",
        )
        assert commit.jira_references == ()

    def test_has_jira_reference_true(self):
        """has_jira_reference returns True when JIRA refs present."""
        commit = Commit(
            hash="abc123",
            author_email="dev@example.com",
            author_name="Dev",
            timestamp=datetime.now(UTC),
            message="PROJ-123: Important fix",
        )
        assert commit.has_jira_reference

    def test_has_jira_reference_false(self):
        """has_jira_reference returns False when no JIRA refs."""
        commit = Commit(
            hash="abc123",
            author_email="dev@example.com",
            author_name="Dev",
            timestamp=datetime.now(UTC),
            message="Some commit without ticket",
        )
        assert not commit.has_jira_reference

    def test_is_mega_commit_true_above_threshold(self):
        """is_mega_commit returns True for >50 file changes."""
        file_changes = tuple(
            FileChange(f"src/file_{i}.py", 1, 1) for i in range(51)
        )
        commit = Commit(
            hash="abc123",
            author_email="dev@example.com",
            author_name="Dev",
            timestamp=datetime.now(UTC),
            message="Large refactor",
            file_changes=file_changes,
        )
        assert commit.is_mega_commit

    def test_is_mega_commit_false_below_threshold(self):
        """is_mega_commit returns False for <=50 file changes."""
        file_changes = tuple(
            FileChange(f"src/file_{i}.py", 1, 1) for i in range(50)
        )
        commit = Commit(
            hash="abc123",
            author_email="dev@example.com",
            author_name="Dev",
            timestamp=datetime.now(UTC),
            message="Normal commit",
            file_changes=file_changes,
        )
        assert not commit.is_mega_commit

    def test_modules_touched_single_module(self):
        """modules_touched returns single module."""
        file_changes = (
            FileChange("src/auth/login.py", 10, 5),
            FileChange("src/auth/logout.py", 5, 2),
        )
        commit = Commit(
            hash="abc123",
            author_email="dev@example.com",
            author_name="Dev",
            timestamp=datetime.now(UTC),
            message="auth fixes",
            file_changes=file_changes,
        )
        assert commit.modules_touched == frozenset({"src"})

    def test_modules_touched_multiple_modules(self):
        """modules_touched returns multiple modules."""
        file_changes = (
            FileChange("src/auth/login.py", 10, 5),
            FileChange("api/v1/users.py", 5, 2),
            FileChange("tests/test_auth.py", 20, 10),
        )
        commit = Commit(
            hash="abc123",
            author_email="dev@example.com",
            author_name="Dev",
            timestamp=datetime.now(UTC),
            message="large refactor",
            file_changes=file_changes,
        )
        assert commit.modules_touched == frozenset({"src", "api", "tests"})

    def test_scatter_score_equals_modules_touched_count(self):
        """scatter_score returns number of distinct modules."""
        file_changes = (
            FileChange("src/auth/login.py", 10, 5),
            FileChange("api/v1/users.py", 5, 2),
            FileChange("tests/test_auth.py", 20, 10),
        )
        commit = Commit(
            hash="abc123",
            author_email="dev@example.com",
            author_name="Dev",
            timestamp=datetime.now(UTC),
            message="large refactor",
            file_changes=file_changes,
        )
        assert commit.scatter_score == 3

    def test_is_scattered_true_above_threshold(self):
        """is_scattered returns True for >3 modules."""
        file_changes = (
            FileChange("a/file.py", 1, 1),
            FileChange("b/file.py", 1, 1),
            FileChange("c/file.py", 1, 1),
            FileChange("d/file.py", 1, 1),
        )
        commit = Commit(
            hash="abc123",
            author_email="dev@example.com",
            author_name="Dev",
            timestamp=datetime.now(UTC),
            message="scattered changes",
            file_changes=file_changes,
        )
        assert commit.is_scattered

    def test_is_scattered_false_at_threshold(self):
        """is_scattered returns False for <=3 modules."""
        file_changes = (
            FileChange("a/file.py", 1, 1),
            FileChange("b/file.py", 1, 1),
            FileChange("c/file.py", 1, 1),
        )
        commit = Commit(
            hash="abc123",
            author_email="dev@example.com",
            author_name="Dev",
            timestamp=datetime.now(UTC),
            message="normal commit",
            file_changes=file_changes,
        )
        assert not commit.is_scattered

    def test_has_empty_message_true(self):
        """has_empty_message returns True for empty message."""
        commit = Commit(
            hash="abc123",
            author_email="dev@example.com",
            author_name="Dev",
            timestamp=datetime.now(UTC),
            message="",
        )
        assert commit.has_empty_message

    def test_has_empty_message_false_with_content(self):
        """has_empty_message returns False for non-empty message."""
        commit = Commit(
            hash="abc123",
            author_email="dev@example.com",
            author_name="Dev",
            timestamp=datetime.now(UTC),
            message="Some commit message",
        )
        assert not commit.has_empty_message

    def test_has_empty_message_whitespace_only(self):
        """has_empty_message returns True for whitespace-only message."""
        commit = Commit(
            hash="abc123",
            author_email="dev@example.com",
            author_name="Dev",
            timestamp=datetime.now(UTC),
            message="   \n\t  ",
        )
        assert commit.has_empty_message

    def test_total_churn_sums_all_file_changes(self):
        """total_churn sums churn from all file changes."""
        file_changes = (
            FileChange("src/file1.py", 50, 10),
            FileChange("src/file2.py", 30, 20),
            FileChange("src/file3.py", 20, 5),
        )
        commit = Commit(
            hash="abc123",
            author_email="dev@example.com",
            author_name="Dev",
            timestamp=datetime.now(UTC),
            message="large changes",
            file_changes=file_changes,
        )
        assert commit.total_churn == 135  # (50+10) + (30+20) + (20+5)

    def test_total_churn_empty_files(self):
        """total_churn returns 0 for commits with no file changes."""
        commit = Commit(
            hash="abc123",
            author_email="dev@example.com",
            author_name="Dev",
            timestamp=datetime.now(UTC),
            message="empty commit",
            file_changes=(),
        )
        assert commit.total_churn == 0

    def test_files_changed_count(self):
        """files_changed_count returns number of file changes."""
        file_changes = (
            FileChange("src/file1.py", 50, 10),
            FileChange("src/file2.py", 30, 20),
        )
        commit = Commit(
            hash="abc123",
            author_email="dev@example.com",
            author_name="Dev",
            timestamp=datetime.now(UTC),
            message="changes",
            file_changes=file_changes,
        )
        assert commit.files_changed_count == 2

    def test_commit_is_frozen(self):
        """Commit instance is immutable."""
        commit = Commit(
            hash="abc123",
            author_email="dev@example.com",
            author_name="Dev",
            timestamp=datetime.now(UTC),
            message="test",
        )
        with pytest.raises(AttributeError):
            commit.message = "changed"


# ============================================================================
# Dependency Tests
# ============================================================================


class TestDependency:
    """Tests for Dependency entity."""

    def test_is_outdated_true_when_versions_differ(self):
        """is_outdated returns True when latest_version differs from current."""
        dep = Dependency(
            name="requests",
            current_version="2.28.0",
            latest_version="2.31.0",
            ecosystem="pip",
            manifest_path="requirements.txt",
        )
        assert dep.is_outdated

    def test_is_outdated_false_when_versions_match(self):
        """is_outdated returns False when versions are same."""
        dep = Dependency(
            name="requests",
            current_version="2.28.0",
            latest_version="2.28.0",
            ecosystem="pip",
            manifest_path="requirements.txt",
        )
        assert not dep.is_outdated

    def test_is_outdated_false_when_latest_unknown(self):
        """is_outdated returns False when latest_version is None."""
        dep = Dependency(
            name="requests",
            current_version="2.28.0",
            latest_version=None,
            ecosystem="pip",
            manifest_path="requirements.txt",
        )
        assert not dep.is_outdated

    def test_is_end_of_life_true_beyond_24_months(self):
        """is_end_of_life returns True for last_upstream_release >24 months ago."""
        cutoff = datetime.now(UTC) - timedelta(days=731)
        dep = Dependency(
            name="old-lib",
            current_version="1.0.0",
            ecosystem="pip",
            manifest_path="requirements.txt",
            last_upstream_release=cutoff,
        )
        assert dep.is_end_of_life

    def test_is_end_of_life_false_within_24_months(self):
        """is_end_of_life returns False for recent upstream release."""
        cutoff = datetime.now(UTC) - timedelta(days=365)
        dep = Dependency(
            name="active-lib",
            current_version="1.0.0",
            ecosystem="pip",
            manifest_path="requirements.txt",
            last_upstream_release=cutoff,
        )
        assert not dep.is_end_of_life

    def test_is_end_of_life_false_when_none(self):
        """is_end_of_life returns False when last_upstream_release is None."""
        dep = Dependency(
            name="lib",
            current_version="1.0.0",
            ecosystem="pip",
            manifest_path="requirements.txt",
            last_upstream_release=None,
        )
        assert not dep.is_end_of_life

    def test_is_high_migration_cost_true_above_200(self):
        """is_high_migration_cost returns True for >200 call sites."""
        dep = Dependency(
            name="lib",
            current_version="1.0.0",
            ecosystem="pip",
            manifest_path="requirements.txt",
            call_site_count=201,
        )
        assert dep.is_high_migration_cost

    def test_is_high_migration_cost_false_at_200(self):
        """is_high_migration_cost returns False for <=200 call sites."""
        dep = Dependency(
            name="lib",
            current_version="1.0.0",
            ecosystem="pip",
            manifest_path="requirements.txt",
            call_site_count=200,
        )
        assert not dep.is_high_migration_cost

    def test_coupling_strength_high_above_200_call_sites(self):
        """coupling_strength returns 'high' for >200 call sites."""
        dep = Dependency(
            name="lib",
            current_version="1.0.0",
            ecosystem="pip",
            manifest_path="requirements.txt",
            call_site_count=250,
        )
        assert dep.coupling_strength == "high"

    def test_coupling_strength_medium_50_to_200_call_sites(self):
        """coupling_strength returns 'medium' for 50-200 call sites."""
        dep = Dependency(
            name="lib",
            current_version="1.0.0",
            ecosystem="pip",
            manifest_path="requirements.txt",
            call_site_count=100,
        )
        assert dep.coupling_strength == "medium"

    def test_coupling_strength_low_below_50_call_sites(self):
        """coupling_strength returns 'low' for <50 call sites."""
        dep = Dependency(
            name="lib",
            current_version="1.0.0",
            ecosystem="pip",
            manifest_path="requirements.txt",
            call_site_count=25,
        )
        assert dep.coupling_strength == "low"

    def test_with_latest_version_returns_new_instance(self):
        """with_latest_version returns new Dependency with updated version."""
        dep = Dependency(
            name="requests",
            current_version="2.28.0",
            latest_version="2.28.0",
            ecosystem="pip",
            manifest_path="requirements.txt",
        )
        updated = dep.with_latest_version("2.31.0")

        assert updated.latest_version == "2.31.0"
        assert dep.latest_version == "2.28.0"
        assert updated.name == dep.name
        assert updated is not dep

    def test_with_latest_version_immutability(self):
        """with_latest_version maintains immutability."""
        dep = Dependency(
            name="requests",
            current_version="2.28.0",
            ecosystem="pip",
            manifest_path="requirements.txt",
        )
        updated = dep.with_latest_version("3.0.0")

        assert dep.latest_version is None
        assert updated.latest_version == "3.0.0"

    def test_with_call_sites_returns_new_instance(self):
        """with_call_sites returns new Dependency with updated call site count."""
        dep = Dependency(
            name="lib",
            current_version="1.0.0",
            ecosystem="pip",
            manifest_path="requirements.txt",
            call_site_count=100,
        )
        updated = dep.with_call_sites(250)

        assert updated.call_site_count == 250
        assert dep.call_site_count == 100
        assert updated.coupling_strength == "high"
        assert dep.coupling_strength == "medium"

    def test_dependency_is_frozen(self):
        """Dependency instance is immutable."""
        dep = Dependency(
            name="lib",
            current_version="1.0.0",
            ecosystem="pip",
            manifest_path="requirements.txt",
        )
        with pytest.raises(AttributeError):
            dep.current_version = "2.0.0"


# ============================================================================
# Vulnerability Tests
# ============================================================================


class TestVulnerability:
    """Tests for Vulnerability entity."""

    def test_has_fix_true_when_fix_version_set(self):
        """has_fix returns True when fix_version is not None."""
        vuln = Vulnerability(
            cve_id="CVE-2023-12345",
            description="Test vuln",
            cvss_score=7.5,
            severity="HIGH",
            affected_library="lib",
            affected_versions="<2.0",
            fix_version="2.0",
        )
        assert vuln.has_fix

    def test_has_fix_false_when_no_fix_available(self):
        """has_fix returns False when fix_version is None."""
        vuln = Vulnerability(
            cve_id="CVE-2023-12345",
            description="Test vuln",
            cvss_score=7.5,
            severity="HIGH",
            affected_library="lib",
            affected_versions="<2.0",
            fix_version=None,
        )
        assert not vuln.has_fix

    def test_exploitability_adjusted_score_base_cvss(self):
        """exploitability_adjusted_score with 0 call sites = base CVSS."""
        vuln = Vulnerability(
            cve_id="CVE-2023-12345",
            description="Test",
            cvss_score=5.0,
            severity="MEDIUM",
            affected_library="lib",
            affected_versions="<2.0",
        )
        assert vuln.exploitability_adjusted_score(0) == 5.0

    def test_exploitability_adjusted_score_increases_with_call_sites(self):
        """exploitability_adjusted_score increases with call site count."""
        vuln = Vulnerability(
            cve_id="CVE-2023-12345",
            description="Test",
            cvss_score=5.0,
            severity="MEDIUM",
            affected_library="lib",
            affected_versions="<2.0",
        )
        score_low = vuln.exploitability_adjusted_score(50)
        score_high = vuln.exploitability_adjusted_score(200)

        assert score_high > score_low

    def test_exploitability_adjusted_score_calculation(self):
        """exploitability_adjusted_score = CVSS × (1 + call_sites/100)."""
        vuln = Vulnerability(
            cve_id="CVE-2023-12345",
            description="Test",
            cvss_score=5.0,
            severity="MEDIUM",
            affected_library="lib",
            affected_versions="<2.0",
        )
        # 100 call sites: 5.0 × (1 + 100/100) = 5.0 × 2 = 10.0
        assert vuln.exploitability_adjusted_score(100) == 10.0
        # 200 call sites: 5.0 × (1 + 200/100) = 5.0 × 3 = 15.0
        assert vuln.exploitability_adjusted_score(200) == 15.0

    def test_exploitability_adjusted_score_capped_at_3x(self):
        """exploitability_adjusted_score coupling factor capped at 3x."""
        vuln = Vulnerability(
            cve_id="CVE-2023-12345",
            description="Test",
            cvss_score=5.0,
            severity="MEDIUM",
            affected_library="lib",
            affected_versions="<2.0",
        )
        # 500 call sites would be 5x, but capped at 3x: 5.0 × 4 = 20.0 -> capped to 15.0
        result = vuln.exploitability_adjusted_score(500)
        assert result == 20.0  # 5.0 × (1 + min(500/100, 3.0)) = 5.0 × 4

    def test_remediation_action_with_fix(self):
        """remediation_action returns upgrade instruction when fix available."""
        vuln = Vulnerability(
            cve_id="CVE-2023-12345",
            description="Test",
            cvss_score=7.5,
            severity="HIGH",
            affected_library="lib",
            affected_versions="<2.0",
            fix_version="2.0.1",
        )
        assert vuln.remediation_action == "upgrade to 2.0.1"

    def test_remediation_action_without_fix(self):
        """remediation_action recommends replacement when no fix."""
        vuln = Vulnerability(
            cve_id="CVE-2023-12345",
            description="Test",
            cvss_score=7.5,
            severity="HIGH",
            affected_library="lib",
            affected_versions="*",
            fix_version=None,
        )
        assert vuln.remediation_action == "evaluate replacement library"

    def test_vulnerability_is_frozen(self):
        """Vulnerability instance is immutable."""
        vuln = Vulnerability(
            cve_id="CVE-2023-12345",
            description="Test",
            cvss_score=7.5,
            severity="HIGH",
            affected_library="lib",
            affected_versions="<2.0",
        )
        with pytest.raises(AttributeError):
            vuln.cvss_score = 5.0


# ============================================================================
# RiskReport Tests
# ============================================================================


class TestComponentRisk:
    """Tests for ComponentRisk entity."""

    def test_composite_score_averages_dimension_scores(self):
        """composite_score averages all dimension scores."""
        scores = {
            "team_knowledge": RiskScore(value=5.0),
            "code_instability": RiskScore(value=7.0),
            "bug_concentration": RiskScore(value=9.0),
        }
        comp = ComponentRisk(component_name="auth", dimension_scores=scores)
        assert comp.composite_score == 7.0  # (5 + 7 + 9) / 3

    def test_composite_score_empty_dimensions(self):
        """composite_score returns 0.0 for empty dimension_scores."""
        comp = ComponentRisk(component_name="auth", dimension_scores={})
        assert comp.composite_score == 0.0

    def test_composite_score_single_dimension(self):
        """composite_score handles single dimension."""
        scores = {"team_knowledge": RiskScore(value=6.5)}
        comp = ComponentRisk(component_name="auth", dimension_scores=scores)
        assert comp.composite_score == 6.5

    def test_systemic_risk_true_three_high_dimensions(self):
        """systemic_risk returns True for 3+ dimensions with score >=7."""
        scores = {
            "team_knowledge": RiskScore(value=8.0),
            "code_instability": RiskScore(value=7.5),
            "bug_concentration": RiskScore(value=7.0),
            "commit_quality": RiskScore(value=3.0),
        }
        comp = ComponentRisk(component_name="auth", dimension_scores=scores)
        assert comp.systemic_risk

    def test_systemic_risk_false_less_than_three_high_dimensions(self):
        """systemic_risk returns False for <3 dimensions with score >=7."""
        scores = {
            "team_knowledge": RiskScore(value=8.0),
            "code_instability": RiskScore(value=7.5),
            "bug_concentration": RiskScore(value=5.0),
            "commit_quality": RiskScore(value=3.0),
        }
        comp = ComponentRisk(component_name="auth", dimension_scores=scores)
        assert not comp.systemic_risk


class TestFileHotspot:
    """Tests for FileHotspot entity."""

    def test_is_critical_true_at_or_above_7_0(self):
        """is_critical returns True for composite_risk_score >=7.0."""
        hotspot = FileHotspot(
            file_path="src/core/auth.py",
            composite_risk_score=7.0,
        )
        assert hotspot.is_critical

    def test_is_critical_false_below_7_0(self):
        """is_critical returns False for composite_risk_score <7.0."""
        hotspot = FileHotspot(
            file_path="src/core/auth.py",
            composite_risk_score=6.99,
        )
        assert not hotspot.is_critical


class TestRiskReport:
    """Tests for RiskReport aggregate."""

    def test_overall_health_score_inverse_of_average_risk(self):
        """overall_health_score returns 10 - average_risk."""
        scores = {
            "team_knowledge": RiskScore(value=4.0),
            "code_instability": RiskScore(value=6.0),
            "bug_concentration": RiskScore(value=2.0),
        }
        report = RiskReport(
            project_name="test-proj",
            analysis_timestamp=datetime.now(UTC),
            scenario="M&A",
            dimension_scores=scores,
        )
        avg_risk = (4.0 + 6.0 + 2.0) / 3  # 4.0
        expected_health = 10.0 - avg_risk  # 6.0
        assert report.overall_health_score == expected_health

    def test_overall_health_score_perfect_health(self):
        """overall_health_score is 10.0 when all dimensions are 0."""
        scores = {
            "team_knowledge": RiskScore(value=0.0),
            "code_instability": RiskScore(value=0.0),
        }
        report = RiskReport(
            project_name="test-proj",
            analysis_timestamp=datetime.now(UTC),
            scenario="M&A",
            dimension_scores=scores,
        )
        assert report.overall_health_score == 10.0

    def test_overall_health_score_empty_dimensions(self):
        """overall_health_score is 10.0 when no dimension_scores."""
        report = RiskReport(
            project_name="test-proj",
            analysis_timestamp=datetime.now(UTC),
            scenario="M&A",
        )
        assert report.overall_health_score == 10.0

    def test_top_risks_returns_top_5_sorted(self):
        """top_risks returns top 5 dimensions sorted by severity."""
        scores = {
            "team_knowledge": RiskScore(value=3.0),
            "code_instability": RiskScore(value=9.0),
            "bug_concentration": RiskScore(value=7.0),
            "commit_quality": RiskScore(value=5.0),
            "code_duplication": RiskScore(value=8.0),
            "security_posture": RiskScore(value=2.0),
        }
        report = RiskReport(
            project_name="test-proj",
            analysis_timestamp=datetime.now(UTC),
            scenario="M&A",
            dimension_scores=scores,
        )
        top = report.top_risks

        assert len(top) == 5
        assert top[0][0] == "code_instability"  # 9.0
        assert top[1][0] == "code_duplication"  # 8.0
        assert top[2][0] == "bug_concentration"  # 7.0

    def test_top_risks_less_than_5_dimensions(self):
        """top_risks returns all dimensions when <5."""
        scores = {
            "team_knowledge": RiskScore(value=3.0),
            "code_instability": RiskScore(value=9.0),
        }
        report = RiskReport(
            project_name="test-proj",
            analysis_timestamp=datetime.now(UTC),
            scenario="M&A",
            dimension_scores=scores,
        )
        top = report.top_risks

        assert len(top) == 2

    def test_worst_components_returns_top_5_sorted(self):
        """worst_components returns top 5 components by composite score."""
        components = tuple([
            ComponentRisk(
                component_name=f"comp_{i}",
                dimension_scores={
                    "team_knowledge": RiskScore(value=float(i))
                }
            )
            for i in range(10, 0, -1)
        ])
        report = RiskReport(
            project_name="test-proj",
            analysis_timestamp=datetime.now(UTC),
            scenario="M&A",
            component_risks=components,
        )
        worst = report.worst_components

        assert len(worst) == 5
        assert worst[0].component_name == "comp_10"
        assert worst[4].component_name == "comp_6"

    def test_with_dimension_score_returns_new_instance(self):
        """with_dimension_score returns new RiskReport with added score."""
        report = RiskReport(
            project_name="test-proj",
            analysis_timestamp=datetime.now(UTC),
            scenario="M&A",
        )
        new_score = RiskScore(value=5.0, label="Team Knowledge")
        updated = report.with_dimension_score("team_knowledge", new_score)

        assert "team_knowledge" in updated.dimension_scores
        assert updated.dimension_scores["team_knowledge"] == new_score
        assert "team_knowledge" not in report.dimension_scores
        assert updated is not report

    def test_with_dimension_score_immutability(self):
        """with_dimension_score maintains immutability."""
        original_score = RiskScore(value=3.0)
        report = RiskReport(
            project_name="test-proj",
            analysis_timestamp=datetime.now(UTC),
            scenario="M&A",
            dimension_scores={"team_knowledge": original_score},
        )
        new_score = RiskScore(value=7.0)
        updated = report.with_dimension_score("team_knowledge", new_score)

        assert report.dimension_scores["team_knowledge"] == original_score
        assert updated.dimension_scores["team_knowledge"] == new_score

    def test_with_component_risks_returns_new_instance(self):
        """with_component_risks returns new RiskReport with component risks."""
        report = RiskReport(
            project_name="test-proj",
            analysis_timestamp=datetime.now(UTC),
            scenario="M&A",
        )
        risks = (ComponentRisk(component_name="auth"),)
        updated = report.with_component_risks(risks)

        assert updated.component_risks == risks
        assert report.component_risks == ()
        assert updated is not report

    def test_with_file_hotspots_returns_new_instance(self):
        """with_file_hotspots returns new RiskReport with hotspots."""
        report = RiskReport(
            project_name="test-proj",
            analysis_timestamp=datetime.now(UTC),
            scenario="M&A",
        )
        hotspots = (FileHotspot(file_path="src/auth.py", composite_risk_score=8.0),)
        updated = report.with_file_hotspots(hotspots)

        assert updated.file_hotspots == hotspots
        assert report.file_hotspots == ()
        assert updated is not report

    def test_with_ai_narrative_returns_new_instance(self):
        """with_ai_narrative returns new RiskReport with narrative."""
        report = RiskReport(
            project_name="test-proj",
            analysis_timestamp=datetime.now(UTC),
            scenario="M&A",
        )
        narrative = "This codebase shows signs of..."
        updated = report.with_ai_narrative(narrative)

        assert updated.ai_narrative == narrative
        assert report.ai_narrative == ""
        assert updated is not report

    def test_with_ai_narrative_emits_event(self):
        """with_ai_narrative emits ReportGeneratedEvent."""
        report = RiskReport(
            project_name="test-proj",
            analysis_timestamp=datetime.now(UTC),
            scenario="M&A",
        )
        updated = report.with_ai_narrative("Narrative")

        assert len(updated.domain_events) == 1
        event = updated.domain_events[0]
        assert event.aggregate_id == "test-proj"
        assert event.scenario == "M&A"

    def test_with_ai_narrative_immutability(self):
        """with_ai_narrative maintains immutability."""
        original_events = (object(),)
        report = RiskReport(
            project_name="test-proj",
            analysis_timestamp=datetime.now(UTC),
            scenario="M&A",
            domain_events=original_events,
        )
        updated = report.with_ai_narrative("Narrative")

        assert len(report.domain_events) == 1
        assert len(updated.domain_events) == 2

    def test_to_dict_serialization_complete(self):
        """to_dict returns complete serialized representation."""
        scores = {
            "team_knowledge": RiskScore(value=5.0, label="Team Knowledge"),
            "code_instability": RiskScore(value=3.0),
        }
        hotspots = (
            FileHotspot(
                file_path="src/auth.py",
                composite_risk_score=8.0,
                risk_indicators={"bug_fix_ratio": 0.5},
                refactoring_recommendation="High priority refactor",
                effort_estimate="large",
            ),
        )
        report = RiskReport(
            project_name="test-proj",
            analysis_timestamp=datetime(2024, 1, 1, tzinfo=UTC),
            scenario="M&A",
            dimension_scores=scores,
            file_hotspots=hotspots,
            ai_narrative="Narrative text",
        )

        result = report.to_dict()

        assert result["project_name"] == "test-proj"
        assert result["scenario"] == "M&A"
        assert result["overall_health_score"] == 6.0  # 10 - ((5+3)/2) = 10 - 4 = 6
        assert "team_knowledge" in result["dimension_scores"]
        assert len(result["top_risks"]) == 2
        assert len(result["file_hotspots"]) == 1
        assert result["ai_narrative"] == "Narrative text"

    def test_to_dict_file_hotspots_limited_to_25(self):
        """to_dict limits file_hotspots to top 25."""
        hotspots = tuple([
            FileHotspot(
                file_path=f"src/file_{i}.py",
                composite_risk_score=float(i),
            )
            for i in range(30)
        ])
        report = RiskReport(
            project_name="test-proj",
            analysis_timestamp=datetime.now(UTC),
            scenario="M&A",
            file_hotspots=hotspots,
        )

        result = report.to_dict()
        assert len(result["file_hotspots"]) == 25

    def test_to_dict_contains_timestamp_iso_format(self):
        """to_dict converts timestamp to ISO format."""
        ts = datetime(2024, 1, 15, 10, 30, 45, tzinfo=UTC)
        report = RiskReport(
            project_name="test-proj",
            analysis_timestamp=ts,
            scenario="M&A",
        )

        result = report.to_dict()
        assert result["analysis_timestamp"] == "2024-01-15T10:30:45+00:00"

    def test_risk_report_is_frozen(self):
        """RiskReport instance is immutable."""
        report = RiskReport(
            project_name="test-proj",
            analysis_timestamp=datetime.now(UTC),
            scenario="M&A",
        )
        with pytest.raises(AttributeError):
            report.project_name = "other-proj"
