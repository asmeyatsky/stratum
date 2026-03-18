"""Unit tests for the Stratum CLI commands."""

import pytest
from click.testing import CliRunner

from presentation.cli.main import cli


@pytest.fixture
def runner():
    """Click CLI test runner."""
    return CliRunner()


class TestVersionCommand:
    """Tests for `stratum version`."""

    def test_version_outputs_stratum(self, runner):
        """stratum version prints a version string containing 'stratum'."""
        result = runner.invoke(cli, ["version"])
        assert result.exit_code == 0
        assert "stratum" in result.output.lower()

    def test_version_contains_number(self, runner):
        """stratum version output contains a version number."""
        result = runner.invoke(cli, ["version"])
        assert result.exit_code == 0
        # Version string should contain at least one digit
        assert any(ch.isdigit() for ch in result.output)


class TestAnalyzeCommand:
    """Tests for `stratum analyze`."""

    def test_analyze_missing_git_log_shows_error(self, runner):
        """stratum analyze without --git-log shows an error."""
        result = runner.invoke(cli, ["analyze", "--project", "test"])
        assert result.exit_code != 0
        assert "git-log" in result.output.lower() or "missing" in result.output.lower()

    def test_analyze_missing_project_shows_error(self, runner, tmp_path):
        """stratum analyze without --project shows an error."""
        # Create a temp file so --git-log validation passes
        git_log = tmp_path / "test.log"
        git_log.write_text("dummy")
        result = runner.invoke(cli, ["analyze", "--git-log", str(git_log)])
        assert result.exit_code != 0
        assert "project" in result.output.lower() or "required" in result.output.lower()

    def test_analyze_missing_all_args_shows_error(self, runner):
        """stratum analyze without any arguments shows an error."""
        result = runner.invoke(cli, ["analyze"])
        assert result.exit_code != 0

    def test_analyze_nonexistent_git_log_shows_error(self, runner):
        """stratum analyze with nonexistent --git-log file shows an error."""
        result = runner.invoke(cli, [
            "analyze",
            "--git-log", "/tmp/does_not_exist_stratum_test.log",
            "--project", "test",
        ])
        assert result.exit_code != 0


class TestScanDepsCommand:
    """Tests for `stratum scan-deps`."""

    def test_scan_deps_missing_manifests_shows_error(self, runner):
        """stratum scan-deps without --manifests shows an error."""
        result = runner.invoke(cli, ["scan-deps"])
        assert result.exit_code != 0
        assert "manifests" in result.output.lower() or "missing" in result.output.lower()

    def test_scan_deps_nonexistent_manifest_shows_error(self, runner):
        """stratum scan-deps with nonexistent manifest file shows an error."""
        result = runner.invoke(cli, [
            "scan-deps",
            "--manifests", "/tmp/does_not_exist_stratum_test.txt",
        ])
        assert result.exit_code != 0


class TestCliGroup:
    """Tests for the top-level CLI group."""

    def test_help_shows_description(self, runner):
        """stratum --help shows the platform description."""
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "stratum" in result.output.lower()

    def test_unknown_command_shows_error(self, runner):
        """stratum with an unknown subcommand shows an error."""
        result = runner.invoke(cli, ["nonexistent-command"])
        assert result.exit_code != 0
