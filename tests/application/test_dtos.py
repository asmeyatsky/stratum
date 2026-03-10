"""
Tests for Analysis DTOs — Data Transfer Objects for analysis input and output.

Tests validate:
- AnalysisRequest immutability and construction
- AnalysisResultDTO serialization to dict
- risk_report_to_dto() factory function
- Nested DTO serialization
"""

import pytest
from datetime import datetime, UTC

from application.dtos.analysis_dto import (
    AnalysisRequest,
    AnalysisResultDTO,
    RiskScoreDTO,
    ComponentRiskDTO,
    FileHotspotDTO,
    risk_report_to_dto,
)
from domain.entities.risk_report import (
    RiskReport,
    ComponentRisk,
    FileHotspot,
)
from domain.value_objects.risk_score import RiskScore


class TestAnalysisRequest:
    """Test AnalysisRequest DTO."""

    def test_analysis_request_construction_with_all_fields(self):
        """Can construct AnalysisRequest with all fields."""
        req = AnalysisRequest(
            git_log_source="/tmp/git.log",
            project_name="test-project",
            scenario="M&A",
            output_path="/tmp/report.pdf",
            manifest_paths=["package.json", "requirements.txt"],
        )

        assert req.git_log_source == "/tmp/git.log"
        assert req.project_name == "test-project"
        assert req.scenario == "M&A"
        assert req.output_path == "/tmp/report.pdf"
        assert req.manifest_paths == ["package.json", "requirements.txt"]

    def test_analysis_request_manifest_paths_default_to_empty_list(self):
        """manifest_paths defaults to empty list."""
        req = AnalysisRequest(
            git_log_source="/tmp/git.log",
            project_name="test-project",
            scenario="M&A",
            output_path="/tmp/report.pdf",
        )

        assert req.manifest_paths == []

    def test_analysis_request_is_immutable(self):
        """AnalysisRequest is frozen (immutable)."""
        req = AnalysisRequest(
            git_log_source="/tmp/git.log",
            project_name="test-project",
            scenario="M&A",
            output_path="/tmp/report.pdf",
        )

        with pytest.raises(AttributeError):
            req.project_name = "new-project"


class TestRiskScoreDTO:
    """Test RiskScoreDTO serialization."""

    def test_risk_score_dto_construction(self):
        """Can construct RiskScoreDTO with all fields."""
        score = RiskScoreDTO(
            value=7.5,
            severity="high",
            label="High Risk",
            evidence="3 critical issues detected",
        )

        assert score.value == 7.5
        assert score.severity == "high"
        assert score.label == "High Risk"
        assert score.evidence == "3 critical issues detected"

    def test_risk_score_dto_to_dict(self):
        """to_dict() returns dict representation."""
        score = RiskScoreDTO(
            value=7.5,
            severity="high",
            label="High Risk",
            evidence="Critical issues",
        )

        result = score.to_dict()

        assert result == {
            "value": 7.5,
            "severity": "high",
            "label": "High Risk",
            "evidence": "Critical issues",
        }


class TestComponentRiskDTO:
    """Test ComponentRiskDTO serialization."""

    def test_component_risk_dto_construction(self):
        """Can construct ComponentRiskDTO."""
        dim_scores = {
            "code_complexity": RiskScoreDTO(
                value=6.0, severity="high", label="Complex", evidence="Test"
            ),
            "security_posture": RiskScoreDTO(
                value=5.0, severity="medium", label="Medium", evidence="Test"
            ),
        }
        comp = ComponentRiskDTO(
            component_name="auth_module",
            composite_score=5.5,
            systemic_risk=False,
            dimension_scores=dim_scores,
        )

        assert comp.component_name == "auth_module"
        assert comp.composite_score == 5.5
        assert comp.systemic_risk is False
        assert len(comp.dimension_scores) == 2

    def test_component_risk_dto_to_dict(self):
        """to_dict() serializes nested dimension scores."""
        dim_scores = {
            "code_complexity": RiskScoreDTO(
                value=6.0, severity="high", label="Complex", evidence="Test"
            ),
        }
        comp = ComponentRiskDTO(
            component_name="auth_module",
            composite_score=5.5,
            systemic_risk=True,
            dimension_scores=dim_scores,
        )

        result = comp.to_dict()

        assert result["component_name"] == "auth_module"
        assert result["composite_score"] == 5.5
        assert result["systemic_risk"] is True
        assert "dimensions" in result
        assert "code_complexity" in result["dimensions"]


class TestFileHotspotDTO:
    """Test FileHotspotDTO serialization."""

    def test_file_hotspot_dto_construction(self):
        """Can construct FileHotspotDTO."""
        hotspot = FileHotspotDTO(
            file_path="src/auth/login.py",
            composite_risk_score=8.2,
            risk_indicators={"churn": 45.0, "complexity": 8},
            refactoring_recommendation="Split into smaller functions",
            effort_estimate="large",
        )

        assert hotspot.file_path == "src/auth/login.py"
        assert hotspot.composite_risk_score == 8.2
        assert hotspot.effort_estimate == "large"

    def test_file_hotspot_dto_to_dict(self):
        """to_dict() returns dict representation."""
        hotspot = FileHotspotDTO(
            file_path="src/auth/login.py",
            composite_risk_score=8.2,
            risk_indicators={"churn": 45.0},
            refactoring_recommendation="Refactor",
            effort_estimate="large",
        )

        result = hotspot.to_dict()

        assert result == {
            "file_path": "src/auth/login.py",
            "composite_risk_score": 8.2,
            "risk_indicators": {"churn": 45.0},
            "refactoring_recommendation": "Refactor",
            "effort_estimate": "large",
        }


class TestAnalysisResultDTO:
    """Test AnalysisResultDTO serialization."""

    def test_analysis_result_dto_construction(self):
        """Can construct AnalysisResultDTO with all fields."""
        dim_scores = {
            "code_complexity": RiskScoreDTO(
                value=5.0, severity="medium", label="Medium", evidence="Test"
            ),
        }
        result = AnalysisResultDTO(
            project_name="test-project",
            scenario="M&A",
            analysis_timestamp="2024-01-15T10:00:00+00:00",
            overall_health_score=7.5,
            dimension_scores=dim_scores,
            ai_narrative="Test narrative",
            pdf_output_path="/tmp/report.pdf",
        )

        assert result.project_name == "test-project"
        assert result.overall_health_score == 7.5
        assert result.ai_narrative == "Test narrative"

    def test_analysis_result_dto_to_dict(self):
        """to_dict() returns complete JSON-serializable dict."""
        dim_scores = {
            "code_complexity": RiskScoreDTO(
                value=5.0, severity="medium", label="Medium", evidence="Test"
            ),
        }
        result = AnalysisResultDTO(
            project_name="test-project",
            scenario="M&A",
            analysis_timestamp="2024-01-15T10:00:00+00:00",
            overall_health_score=7.5,
            dimension_scores=dim_scores,
            ai_narrative="Test narrative",
            pdf_output_path="/tmp/report.pdf",
        )

        dto_dict = result.to_dict()

        assert dto_dict["project_name"] == "test-project"
        assert dto_dict["scenario"] == "M&A"
        assert dto_dict["overall_health_score"] == 7.5
        assert "dimension_scores" in dto_dict
        assert "code_complexity" in dto_dict["dimension_scores"]

    def test_analysis_result_dto_to_dict_includes_nested_structures(self):
        """to_dict() recursively serializes nested DTOs."""
        dim_scores = {
            "complexity": RiskScoreDTO(
                value=6.0, severity="high", label="High", evidence="Test"
            ),
        }
        comp_risks = [
            ComponentRiskDTO(
                component_name="module1",
                composite_score=6.5,
                systemic_risk=True,
                dimension_scores={
                    "complexity": RiskScoreDTO(
                        value=6.0, severity="high", label="High", evidence="Test"
                    ),
                },
            ),
        ]
        file_hotspots = [
            FileHotspotDTO(
                file_path="file1.py",
                composite_risk_score=7.0,
                risk_indicators={"churn": 30},
                effort_estimate="medium",
            ),
        ]

        result = AnalysisResultDTO(
            project_name="test-project",
            scenario="M&A",
            analysis_timestamp="2024-01-15T10:00:00+00:00",
            overall_health_score=6.5,
            dimension_scores=dim_scores,
            component_risks=comp_risks,
            file_hotspots=file_hotspots,
        )

        dto_dict = result.to_dict()

        assert len(dto_dict["component_risks"]) == 1
        assert dto_dict["component_risks"][0]["component_name"] == "module1"
        assert len(dto_dict["file_hotspots"]) == 1
        assert dto_dict["file_hotspots"][0]["file_path"] == "file1.py"


class TestRiskReportToDto:
    """Test risk_report_to_dto() factory function."""

    def test_risk_report_to_dto_basic_conversion(self):
        """risk_report_to_dto() converts RiskReport to AnalysisResultDTO."""
        report = RiskReport(
            project_name="test-project",
            scenario="M&A",
            analysis_timestamp=datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC),
            dimension_scores={
                "code_complexity": RiskScore(
                    value=5.0, label="Medium", evidence="Test evidence"
                ),
                "security_posture": RiskScore(
                    value=4.0, label="Low", evidence="No issues"
                ),
            },
        )

        result = risk_report_to_dto(report, pdf_output_path="/tmp/report.pdf")

        assert isinstance(result, AnalysisResultDTO)
        assert result.project_name == "test-project"
        assert result.scenario == "M&A"
        assert result.pdf_output_path == "/tmp/report.pdf"
        assert "code_complexity" in result.dimension_scores

    def test_risk_report_to_dto_preserves_dimension_scores(self):
        """risk_report_to_dto() converts dimension scores correctly."""
        report = RiskReport(
            project_name="test-project",
            scenario="vendor_audit",
            analysis_timestamp=datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC),
            dimension_scores={
                "code_complexity": RiskScore(
                    value=7.5, label="High", evidence="Complex patterns detected"
                ),
                "dependency_coupling": RiskScore(
                    value=6.0, label="High", evidence="Tight coupling"
                ),
            },
        )

        result = risk_report_to_dto(report)

        assert len(result.dimension_scores) == 2
        assert result.dimension_scores["code_complexity"].value == 7.5
        assert result.dimension_scores["code_complexity"].severity == "high"
        assert result.dimension_scores["dependency_coupling"].value == 6.0

    def test_risk_report_to_dto_with_component_risks(self):
        """risk_report_to_dto() includes worst 5 component risks."""
        report = RiskReport(
            project_name="test-project",
            scenario="M&A",
            analysis_timestamp=datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC),
            dimension_scores={},
            component_risks=(
                ComponentRisk(
                    component_name="auth_module",
                    dimension_scores={
                        "code_complexity": RiskScore(value=6.0, label="High", evidence="Test"),
                    },
                ),
                ComponentRisk(
                    component_name="api_module",
                    dimension_scores={
                        "code_complexity": RiskScore(value=7.0, label="High", evidence="Test"),
                    },
                ),
            ),
        )

        result = risk_report_to_dto(report)

        assert len(result.component_risks) == 2
        assert result.component_risks[0].component_name in ["auth_module", "api_module"]

    def test_risk_report_to_dto_with_file_hotspots(self):
        """risk_report_to_dto() includes file hotspots (max 25)."""
        hotspots = tuple(
            FileHotspot(
                file_path=f"src/module_{i}.py",
                composite_risk_score=7.0 + (i * 0.1),
                risk_indicators={"churn": 20 + i},
            )
            for i in range(10)
        )

        report = RiskReport(
            project_name="test-project",
            scenario="M&A",
            analysis_timestamp=datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC),
            dimension_scores={},
            file_hotspots=hotspots,
        )

        result = risk_report_to_dto(report)

        assert len(result.file_hotspots) == 10
        assert result.file_hotspots[0].file_path == "src/module_0.py"

    def test_risk_report_to_dto_caps_file_hotspots_at_25(self):
        """risk_report_to_dto() limits file hotspots to 25."""
        hotspots = tuple(
            FileHotspot(
                file_path=f"src/module_{i}.py",
                composite_risk_score=7.0,
                risk_indicators={},
            )
            for i in range(50)
        )

        report = RiskReport(
            project_name="test-project",
            scenario="M&A",
            analysis_timestamp=datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC),
            dimension_scores={},
            file_hotspots=hotspots,
        )

        result = risk_report_to_dto(report)

        assert len(result.file_hotspots) == 25

    def test_risk_report_to_dto_with_ai_narrative(self):
        """risk_report_to_dto() includes AI narrative if present."""
        narrative = "This project has significant technical debt in authentication modules."
        report = RiskReport(
            project_name="test-project",
            scenario="M&A",
            analysis_timestamp=datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC),
            dimension_scores={},
            ai_narrative=narrative,
        )

        result = risk_report_to_dto(report)

        assert result.ai_narrative == narrative

    def test_risk_report_to_dto_default_pdf_output_path(self):
        """risk_report_to_dto() defaults pdf_output_path to empty string."""
        report = RiskReport(
            project_name="test-project",
            scenario="M&A",
            analysis_timestamp=datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC),
            dimension_scores={},
        )

        result = risk_report_to_dto(report)

        assert result.pdf_output_path == ""

    def test_risk_report_to_dto_overall_health_score(self):
        """risk_report_to_dto() preserves overall_health_score from report."""
        report = RiskReport(
            project_name="test-project",
            scenario="M&A",
            analysis_timestamp=datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC),
            dimension_scores={
                "complexity": RiskScore(value=3.0, label="Low", evidence="Test"),
                "security": RiskScore(value=5.0, label="Medium", evidence="Test"),
            },
        )

        result = risk_report_to_dto(report)

        # overall_health = 10 - avg_risk = 10 - 4 = 6
        assert result.overall_health_score == 6.0

    def test_risk_report_to_dto_top_risks_included(self):
        """risk_report_to_dto() includes top risks."""
        report = RiskReport(
            project_name="test-project",
            scenario="M&A",
            analysis_timestamp=datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC),
            dimension_scores={
                "complexity": RiskScore(value=8.0, label="Critical", evidence="High"),
                "security": RiskScore(value=3.0, label="Low", evidence="Good"),
            },
        )

        result = risk_report_to_dto(report)

        assert len(result.top_risks) > 0
        # Top risk should be complexity with value 8
        assert result.top_risks[0]["dimension"] == "complexity"
        assert result.top_risks[0]["value"] == 8.0
