"""
Integration test for the full analysis flow.

Tests validate:
- End-to-end execution of AnalyzeRepositoryCommand
- Real GitLogParser and domain services work together
- Fallback adapters (NoOp narrative, JSON report) work in the pipeline
- Result has populated dimension scores, health score, and hotspots
"""

import pytest
import json
from datetime import datetime, UTC
from pathlib import Path
from unittest.mock import AsyncMock

from application.commands.analyze_repository import AnalyzeRepositoryCommand
from application.dtos.analysis_dto import AnalysisRequest, AnalysisResultDTO
from infrastructure.adapters.git_log_parser import GitLogParser
from infrastructure.adapters.fallback_adapters import (
    NoOpNarrativeAdapter,
    JsonReportAdapter,
)
from domain.entities.commit import Commit
from domain.entities.file_change import FileChange


@pytest.fixture
def sample_git_log(tmp_path):
    """Create a sample git log file for testing."""
    log_file = tmp_path / "git.log"
    log_content = (
        "abc123def456|alice@example.com|Alice|2024-01-01 10:00:00 +0000|Initial commit\n"
        "50\t10\tsrc/main.py\n"
        "30\t5\tsrc/utils.py\n"
        "\n"
        "def456ghi789|bob@example.com|Bob|2024-01-05 14:30:00 +0000|Add feature X\n"
        "100\t20\tsrc/feature_x.py\n"
        "10\t5\ttests/test_feature_x.py\n"
        "\n"
        "ghi789jkl012|alice@example.com|Alice|2024-01-10 09:15:00 +0000|Fix bug in module\n"
        "5\t15\tsrc/utils.py\n"
        "\n"
        "jkl012mno345|charlie@example.com|Charlie|2024-01-15 16:45:00 +0000|Refactor code structure\n"
        "50\t50\tsrc/main.py\n"
        "30\t10\tsrc/utils.py\n"
    )
    log_file.write_text(log_content)
    return str(log_file)


@pytest.fixture
def sample_package_json(tmp_path):
    """Create a sample package.json manifest file."""
    package_file = tmp_path / "package.json"
    content = {
        "name": "test-project",
        "dependencies": {
            "react": "^18.0.0",
            "express": "^4.18.0",
        },
        "devDependencies": {
            "jest": "^29.0.0",
            "eslint": "^8.0.0",
        },
    }
    package_file.write_text(json.dumps(content))
    return str(package_file)


class TestAnalysisFlowEndToEnd:
    """Test complete analysis pipeline integration."""

    @pytest.mark.asyncio
    async def test_analyze_command_full_execution(
        self, sample_git_log, sample_package_json, tmp_path
    ):
        """Execute full analysis pipeline with real components."""
        # Setup real adapters
        git_log_parser = GitLogParser()

        # Mock ports that require external services
        mock_vuln_db = AsyncMock()
        mock_vuln_db.search.return_value = []

        mock_ai_narrative = NoOpNarrativeAdapter()
        mock_report_gen = JsonReportAdapter()

        # Create command with all ports
        cmd = AnalyzeRepositoryCommand(
            git_log_port=git_log_parser,
            vulnerability_db_port=mock_vuln_db,
            ai_narrative_port=mock_ai_narrative,
            report_generator_port=mock_report_gen,
        )

        # Execute analysis
        request = AnalysisRequest(
            git_log_source=sample_git_log,
            project_name="test-project",
            scenario="M&A",
            output_path=str(tmp_path / "report.pdf"),
            manifest_paths=[sample_package_json],
        )

        result = await cmd.execute(request)

        # Verify result type
        assert isinstance(result, AnalysisResultDTO)
        assert result.project_name == "test-project"
        assert result.scenario == "M&A"

    @pytest.mark.asyncio
    async def test_analysis_result_has_dimension_scores(
        self, sample_git_log, tmp_path
    ):
        """Analysis result includes populated dimension scores."""
        git_log_parser = GitLogParser()
        mock_vuln_db = AsyncMock()
        mock_vuln_db.search.return_value = []

        cmd = AnalyzeRepositoryCommand(
            git_log_port=git_log_parser,
            vulnerability_db_port=mock_vuln_db,
            ai_narrative_port=NoOpNarrativeAdapter(),
            report_generator_port=JsonReportAdapter(),
        )

        request = AnalysisRequest(
            git_log_source=sample_git_log,
            project_name="test-project",
            scenario="M&A",
            output_path=str(tmp_path / "report.pdf"),
            manifest_paths=[],
        )

        result = await cmd.execute(request)

        # Result should have dimension scores populated
        assert len(result.dimension_scores) > 0
        for dim, score in result.dimension_scores.items():
            assert 0 <= score.value <= 10
            assert score.severity in ["minimal", "low", "medium", "high", "critical"]

    @pytest.mark.asyncio
    async def test_analysis_result_has_overall_health_score(
        self, sample_git_log, tmp_path
    ):
        """Analysis result includes overall health score."""
        git_log_parser = GitLogParser()
        mock_vuln_db = AsyncMock()
        mock_vuln_db.search.return_value = []

        cmd = AnalyzeRepositoryCommand(
            git_log_port=git_log_parser,
            vulnerability_db_port=mock_vuln_db,
            ai_narrative_port=NoOpNarrativeAdapter(),
            report_generator_port=JsonReportAdapter(),
        )

        request = AnalysisRequest(
            git_log_source=sample_git_log,
            project_name="test-project",
            scenario="M&A",
            output_path=str(tmp_path / "report.pdf"),
            manifest_paths=[],
        )

        result = await cmd.execute(request)

        # Overall health score should be between 1-10
        assert 1 <= result.overall_health_score <= 10

    @pytest.mark.asyncio
    async def test_analysis_result_has_file_hotspots(
        self, sample_git_log, tmp_path
    ):
        """Analysis result includes file hotspots."""
        git_log_parser = GitLogParser()
        mock_vuln_db = AsyncMock()
        mock_vuln_db.search.return_value = []

        cmd = AnalyzeRepositoryCommand(
            git_log_port=git_log_parser,
            vulnerability_db_port=mock_vuln_db,
            ai_narrative_port=NoOpNarrativeAdapter(),
            report_generator_port=JsonReportAdapter(),
        )

        request = AnalysisRequest(
            git_log_source=sample_git_log,
            project_name="test-project",
            scenario="M&A",
            output_path=str(tmp_path / "report.pdf"),
            manifest_paths=[],
        )

        result = await cmd.execute(request)

        # Result should have file hotspots (from commits with high churn)
        # Note: may be empty if no files hit hotspot criteria
        if result.file_hotspots:
            for hotspot in result.file_hotspots:
                assert hotspot.file_path
                assert 0 <= hotspot.composite_risk_score <= 10

    @pytest.mark.asyncio
    async def test_analysis_includes_ai_narrative(
        self, sample_git_log, tmp_path
    ):
        """Analysis result includes AI-generated narrative."""
        git_log_parser = GitLogParser()
        mock_vuln_db = AsyncMock()
        mock_vuln_db.search.return_value = []

        cmd = AnalyzeRepositoryCommand(
            git_log_port=git_log_parser,
            vulnerability_db_port=mock_vuln_db,
            ai_narrative_port=NoOpNarrativeAdapter(),
            report_generator_port=JsonReportAdapter(),
        )

        request = AnalysisRequest(
            git_log_source=sample_git_log,
            project_name="test-project",
            scenario="M&A",
            output_path=str(tmp_path / "report.pdf"),
            manifest_paths=[],
        )

        result = await cmd.execute(request)

        # Narrative should be populated
        assert result.ai_narrative
        assert isinstance(result.ai_narrative, str)
        assert len(result.ai_narrative) > 0

    @pytest.mark.asyncio
    async def test_analysis_generates_json_report_file(
        self, sample_git_log, tmp_path
    ):
        """Analysis creates a JSON report file (since PDF adapter is fallback)."""
        git_log_parser = GitLogParser()
        mock_vuln_db = AsyncMock()
        mock_vuln_db.search.return_value = []

        cmd = AnalyzeRepositoryCommand(
            git_log_port=git_log_parser,
            vulnerability_db_port=mock_vuln_db,
            ai_narrative_port=NoOpNarrativeAdapter(),
            report_generator_port=JsonReportAdapter(),
        )

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        request = AnalysisRequest(
            git_log_source=sample_git_log,
            project_name="test-project",
            scenario="M&A",
            output_path=str(output_dir / "report.pdf"),
            manifest_paths=[],
        )

        result = await cmd.execute(request)

        # JSON report should be created
        assert result.pdf_output_path
        json_path = Path(result.pdf_output_path)
        assert json_path.exists()
        assert json_path.suffix == ".json"

        # Verify JSON content
        with open(json_path) as f:
            report_data = json.load(f)

        assert report_data["project_name"] == "test-project"
        assert report_data["scenario"] == "M&A"

    @pytest.mark.asyncio
    async def test_analysis_with_manifest_paths_includes_dependencies(
        self, sample_git_log, sample_package_json, tmp_path
    ):
        """Analysis with manifest paths processes dependencies."""
        git_log_parser = GitLogParser()
        mock_vuln_db = AsyncMock()
        mock_vuln_db.search.return_value = []

        cmd = AnalyzeRepositoryCommand(
            git_log_port=git_log_parser,
            vulnerability_db_port=mock_vuln_db,
            ai_narrative_port=NoOpNarrativeAdapter(),
            report_generator_port=JsonReportAdapter(),
        )

        request = AnalysisRequest(
            git_log_source=sample_git_log,
            project_name="test-project",
            scenario="M&A",
            output_path=str(tmp_path / "report.pdf"),
            manifest_paths=[sample_package_json],
        )

        result = await cmd.execute(request)

        # Vulnerability DB should have been called for dependencies
        assert mock_vuln_db.search.called
        # Called for react, express, jest, eslint
        assert mock_vuln_db.search.call_count >= 4

    @pytest.mark.asyncio
    async def test_analysis_without_manifest_paths_skips_p4(
        self, sample_git_log, tmp_path
    ):
        """Analysis without manifest paths skips dependency analysis."""
        git_log_parser = GitLogParser()
        mock_vuln_db = AsyncMock()
        mock_vuln_db.search.return_value = []

        cmd = AnalyzeRepositoryCommand(
            git_log_port=git_log_parser,
            vulnerability_db_port=mock_vuln_db,
            ai_narrative_port=NoOpNarrativeAdapter(),
            report_generator_port=JsonReportAdapter(),
        )

        request = AnalysisRequest(
            git_log_source=sample_git_log,
            project_name="test-project",
            scenario="M&A",
            output_path=str(tmp_path / "report.pdf"),
            manifest_paths=[],  # No manifests
        )

        result = await cmd.execute(request)

        # Vulnerability DB should not have been called
        assert not mock_vuln_db.search.called

    @pytest.mark.asyncio
    async def test_analysis_result_serializes_to_dict(
        self, sample_git_log, tmp_path
    ):
        """Analysis result DTO serializes correctly to dict."""
        git_log_parser = GitLogParser()
        mock_vuln_db = AsyncMock()
        mock_vuln_db.search.return_value = []

        cmd = AnalyzeRepositoryCommand(
            git_log_port=git_log_parser,
            vulnerability_db_port=mock_vuln_db,
            ai_narrative_port=NoOpNarrativeAdapter(),
            report_generator_port=JsonReportAdapter(),
        )

        request = AnalysisRequest(
            git_log_source=sample_git_log,
            project_name="test-project",
            scenario="M&A",
            output_path=str(tmp_path / "report.pdf"),
            manifest_paths=[],
        )

        result = await cmd.execute(request)

        # DTO should serialize to dict
        result_dict = result.to_dict()

        assert isinstance(result_dict, dict)
        assert result_dict["project_name"] == "test-project"
        assert result_dict["scenario"] == "M&A"
        assert "overall_health_score" in result_dict
        assert "dimension_scores" in result_dict

    @pytest.mark.asyncio
    async def test_analysis_with_multiple_scenarios(
        self, sample_git_log, tmp_path
    ):
        """Analysis works with different scenarios."""
        git_log_parser = GitLogParser()
        mock_vuln_db = AsyncMock()
        mock_vuln_db.search.return_value = []

        cmd = AnalyzeRepositoryCommand(
            git_log_port=git_log_parser,
            vulnerability_db_port=mock_vuln_db,
            ai_narrative_port=NoOpNarrativeAdapter(),
            report_generator_port=JsonReportAdapter(),
        )

        scenarios = ["M&A", "vendor_audit", "post_merger", "oss_assessment"]

        for scenario in scenarios:
            request = AnalysisRequest(
                git_log_source=sample_git_log,
                project_name="test-project",
                scenario=scenario,
                output_path=str(tmp_path / f"report_{scenario}.pdf"),
                manifest_paths=[],
            )

            result = await cmd.execute(request)

            assert result.scenario == scenario
            assert result.overall_health_score >= 1
            assert result.overall_health_score <= 10
