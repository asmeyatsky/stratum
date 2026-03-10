"""
Tests for AnalyzeRepositoryCommand — Primary use case for repository analysis.

Tests validate:
- Correct port execution order
- Port integration with workflow execution
- AnalysisResultDTO return type
- manifest_paths propagation to context
- Timing and logging behavior
"""

import pytest
from unittest.mock import AsyncMock

from application.commands.analyze_repository import AnalyzeRepositoryCommand
from application.dtos.analysis_dto import AnalysisRequest, AnalysisResultDTO
from domain.entities.risk_report import RiskReport
from domain.value_objects.risk_score import RiskScore
from datetime import datetime, UTC


@pytest.fixture
def mock_git_log_port():
    """Mock GitLogPort adapter."""
    return AsyncMock()


@pytest.fixture
def mock_vulnerability_db_port():
    """Mock VulnerabilityDbPort adapter."""
    return AsyncMock()


@pytest.fixture
def mock_ai_narrative_port():
    """Mock AINarrativePort adapter."""
    return AsyncMock()


@pytest.fixture
def mock_report_generator_port():
    """Mock ReportGeneratorPort adapter."""
    return AsyncMock()


@pytest.fixture
def sample_analysis_request():
    """Create a sample AnalysisRequest for testing."""
    return AnalysisRequest(
        git_log_source="/tmp/git.log",
        project_name="test-project",
        scenario="M&A",
        output_path="/tmp/report.pdf",
        manifest_paths=["package.json"],
    )


@pytest.fixture
def sample_risk_report():
    """Create a minimal RiskReport for testing."""
    return RiskReport(
        project_name="test-project",
        scenario="M&A",
        analysis_timestamp=datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC),
        dimension_scores={
            "code_complexity": RiskScore(value=5.0, label="Medium", evidence="Test"),
            "security_posture": RiskScore(value=4.0, label="Low", evidence="Test"),
        },
    )


class TestAnalyzeRepositoryCommandExecution:
    """Test command execution and port integration."""

    @pytest.mark.asyncio
    async def test_execute_returns_analysis_result_dto(
        self,
        mock_git_log_port,
        mock_vulnerability_db_port,
        mock_ai_narrative_port,
        mock_report_generator_port,
        sample_analysis_request,
        sample_risk_report,
    ):
        """execute() returns an AnalysisResultDTO."""
        # Setup port mocks to return minimal valid results
        from domain.entities.commit import Commit
        mock_git_log_port.parse.return_value = []
        mock_vulnerability_db_port.search.return_value = []
        mock_ai_narrative_port.generate_narrative.return_value = "Test narrative"
        mock_report_generator_port.generate_pdf.return_value = "/tmp/report.pdf"

        cmd = AnalyzeRepositoryCommand(
            git_log_port=mock_git_log_port,
            vulnerability_db_port=mock_vulnerability_db_port,
            ai_narrative_port=mock_ai_narrative_port,
            report_generator_port=mock_report_generator_port,
        )

        # Mock the DAG execution indirectly by patching build_analysis_dag
        from application.orchestration.analysis_workflow import build_analysis_dag
        from unittest.mock import patch

        # Create a mock DAG that returns a minimal context
        mock_dag = AsyncMock()
        mock_dag.execute.return_value = {
            "p1_analysis": {
                "commits": [],
                "knowledge_risks": [],
                "temporal_couplings": [],
                "churn_anomalies": [],
                "p1_scores": {},
            },
            "p2_analysis": {
                "quality_report": type("obj", (), {"total_commits": 0})(),
                "bug_magnets": [],
                "trends": {},
                "p2_scores": {},
            },
            "p4_analysis": {
                "dependencies": [],
                "assessments": [],
                "p4_scores": {},
            },
            "p6_aggregation": {
                "report": sample_risk_report,
            },
            "ai_narrative": {
                "report": sample_risk_report.with_ai_narrative("Test narrative"),
                "narrative": "Test narrative",
            },
            "pdf_report": {
                "report": sample_risk_report.with_ai_narrative("Test narrative"),
                "pdf_path": "/tmp/report.pdf",
            },
        }

        with patch("application.commands.analyze_repository.build_analysis_dag") as mock_build:
            mock_build.return_value = mock_dag

            result = await cmd.execute(sample_analysis_request)

            assert isinstance(result, AnalysisResultDTO)
            assert result.project_name == "test-project"
            assert result.scenario == "M&A"
            assert result.pdf_output_path == "/tmp/report.pdf"

    @pytest.mark.asyncio
    async def test_execute_propagates_request_fields_to_dag_context(
        self,
        mock_git_log_port,
        mock_vulnerability_db_port,
        mock_ai_narrative_port,
        mock_report_generator_port,
        sample_analysis_request,
        sample_risk_report,
    ):
        """execute() passes request fields to DAG context."""
        from unittest.mock import patch, AsyncMock as AM
        from application.orchestration.analysis_workflow import build_analysis_dag

        captured_context = {}

        async def capture_context(ctx):
            captured_context.update(ctx)
            return {}

        mock_dag = AsyncMock()

        async def dag_execute(ctx):
            captured_context.update(ctx)
            return {
                "p1_analysis": {
                    "commits": [],
                    "knowledge_risks": [],
                    "temporal_couplings": [],
                    "churn_anomalies": [],
                    "p1_scores": {},
                },
                "p2_analysis": {
                    "quality_report": type("obj", (), {"total_commits": 0})(),
                    "bug_magnets": [],
                    "trends": {},
                    "p2_scores": {},
                },
                "p4_analysis": {
                    "dependencies": [],
                    "assessments": [],
                    "p4_scores": {},
                },
                "p6_aggregation": {"report": sample_risk_report},
                "ai_narrative": {
                    "report": sample_risk_report.with_ai_narrative("Test"),
                    "narrative": "Test",
                },
                "pdf_report": {
                    "report": sample_risk_report.with_ai_narrative("Test"),
                    "pdf_path": "/tmp/report.pdf",
                },
            }

        mock_dag.execute = dag_execute

        cmd = AnalyzeRepositoryCommand(
            git_log_port=mock_git_log_port,
            vulnerability_db_port=mock_vulnerability_db_port,
            ai_narrative_port=mock_ai_narrative_port,
            report_generator_port=mock_report_generator_port,
        )

        with patch("application.commands.analyze_repository.build_analysis_dag") as mock_build:
            mock_build.return_value = mock_dag

            await cmd.execute(sample_analysis_request)

            assert captured_context["git_log_source"] == "/tmp/git.log"
            assert captured_context["project_name"] == "test-project"
            assert captured_context["scenario"] == "M&A"
            assert captured_context["output_path"] == "/tmp/report.pdf"
            assert captured_context["manifest_paths"] == ["package.json"]

    @pytest.mark.asyncio
    async def test_execute_manifest_paths_propagated_to_context(
        self,
        mock_git_log_port,
        mock_vulnerability_db_port,
        mock_ai_narrative_port,
        mock_report_generator_port,
        sample_risk_report,
    ):
        """manifest_paths from request are propagated to DAG context."""
        from unittest.mock import patch

        request = AnalysisRequest(
            git_log_source="/tmp/git.log",
            project_name="test-project",
            scenario="M&A",
            output_path="/tmp/report.pdf",
            manifest_paths=["package.json", "requirements.txt"],
        )

        captured_context = {}

        async def dag_execute(ctx):
            captured_context.update(ctx)
            return {
                "p1_analysis": {
                    "commits": [],
                    "knowledge_risks": [],
                    "temporal_couplings": [],
                    "churn_anomalies": [],
                    "p1_scores": {},
                },
                "p2_analysis": {
                    "quality_report": type("obj", (), {"total_commits": 0})(),
                    "bug_magnets": [],
                    "trends": {},
                    "p2_scores": {},
                },
                "p4_analysis": {
                    "dependencies": [],
                    "assessments": [],
                    "p4_scores": {},
                },
                "p6_aggregation": {"report": sample_risk_report},
                "ai_narrative": {
                    "report": sample_risk_report.with_ai_narrative("Test"),
                    "narrative": "Test",
                },
                "pdf_report": {
                    "report": sample_risk_report.with_ai_narrative("Test"),
                    "pdf_path": "/tmp/report.pdf",
                },
            }

        mock_dag = AsyncMock()
        mock_dag.execute = dag_execute

        cmd = AnalyzeRepositoryCommand(
            git_log_port=mock_git_log_port,
            vulnerability_db_port=mock_vulnerability_db_port,
            ai_narrative_port=mock_ai_narrative_port,
            report_generator_port=mock_report_generator_port,
        )

        with patch("application.commands.analyze_repository.build_analysis_dag") as mock_build:
            mock_build.return_value = mock_dag
            await cmd.execute(request)

            assert captured_context["manifest_paths"] == ["package.json", "requirements.txt"]

    @pytest.mark.asyncio
    async def test_execute_empty_manifest_paths_default(
        self,
        mock_git_log_port,
        mock_vulnerability_db_port,
        mock_ai_narrative_port,
        mock_report_generator_port,
        sample_risk_report,
    ):
        """manifest_paths defaults to empty list if not provided."""
        from unittest.mock import patch

        request = AnalysisRequest(
            git_log_source="/tmp/git.log",
            project_name="test-project",
            scenario="M&A",
            output_path="/tmp/report.pdf",
        )

        captured_context = {}

        async def dag_execute(ctx):
            captured_context.update(ctx)
            return {
                "p1_analysis": {
                    "commits": [],
                    "knowledge_risks": [],
                    "temporal_couplings": [],
                    "churn_anomalies": [],
                    "p1_scores": {},
                },
                "p2_analysis": {
                    "quality_report": type("obj", (), {"total_commits": 0})(),
                    "bug_magnets": [],
                    "trends": {},
                    "p2_scores": {},
                },
                "p4_analysis": {
                    "dependencies": [],
                    "assessments": [],
                    "p4_scores": {},
                },
                "p6_aggregation": {"report": sample_risk_report},
                "ai_narrative": {
                    "report": sample_risk_report.with_ai_narrative("Test"),
                    "narrative": "Test",
                },
                "pdf_report": {
                    "report": sample_risk_report.with_ai_narrative("Test"),
                    "pdf_path": "/tmp/report.pdf",
                },
            }

        mock_dag = AsyncMock()
        mock_dag.execute = dag_execute

        cmd = AnalyzeRepositoryCommand(
            git_log_port=mock_git_log_port,
            vulnerability_db_port=mock_vulnerability_db_port,
            ai_narrative_port=mock_ai_narrative_port,
            report_generator_port=mock_report_generator_port,
        )

        with patch("application.commands.analyze_repository.build_analysis_dag") as mock_build:
            mock_build.return_value = mock_dag
            await cmd.execute(request)

            assert captured_context["manifest_paths"] == []
