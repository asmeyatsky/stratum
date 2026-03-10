"""
Tests for Fallback Adapters — No-op implementations of optional ports.

Tests validate:
- NoOpNarrativeAdapter generates placeholder narratives
- JsonReportAdapter writes JSON files instead of PDFs
- Both adapters preserve report data
"""

import pytest
import json
from pathlib import Path

from infrastructure.adapters.fallback_adapters import (
    NoOpNarrativeAdapter,
    JsonReportAdapter,
)


class TestNoOpNarrativeAdapter:
    """Test NoOpNarrativeAdapter placeholder narrative generation."""

    @pytest.mark.asyncio
    async def test_generate_narrative_returns_placeholder_text(self):
        """generate_narrative returns a placeholder narrative."""
        adapter = NoOpNarrativeAdapter()
        risk_model = {
            "overall_health_score": 6.5,
            "project_name": "test-project",
            "scenario": "M&A",
            "top_risks": [],
        }

        narrative = await adapter.generate_narrative(
            risk_model=risk_model,
            scenario="M&A",
        )

        assert isinstance(narrative, str)
        assert len(narrative) > 0
        assert "placeholder" in narrative.lower()

    @pytest.mark.asyncio
    async def test_generate_narrative_includes_project_name(self):
        """Narrative includes project name from risk model."""
        adapter = NoOpNarrativeAdapter()
        risk_model = {
            "overall_health_score": 7.0,
            "project_name": "acme-platform",
            "scenario": "M&A",
            "top_risks": [],
        }

        narrative = await adapter.generate_narrative(
            risk_model=risk_model,
            scenario="M&A",
        )

        assert "acme-platform" in narrative

    @pytest.mark.asyncio
    async def test_generate_narrative_includes_health_score(self):
        """Narrative includes overall health score from risk model."""
        adapter = NoOpNarrativeAdapter()
        risk_model = {
            "overall_health_score": 7.5,
            "project_name": "test-project",
            "scenario": "M&A",
            "top_risks": [],
        }

        narrative = await adapter.generate_narrative(
            risk_model=risk_model,
            scenario="M&A",
        )

        assert "7.5" in narrative or "7" in narrative

    @pytest.mark.asyncio
    async def test_generate_narrative_includes_top_risks(self):
        """Narrative includes top risks from risk model."""
        adapter = NoOpNarrativeAdapter()
        risk_model = {
            "overall_health_score": 6.5,
            "project_name": "test-project",
            "scenario": "M&A",
            "top_risks": [
                {
                    "dimension": "code_complexity",
                    "label": "High",
                    "value": 8.0,
                    "evidence": "Complex functions detected",
                },
            ],
        }

        narrative = await adapter.generate_narrative(
            risk_model=risk_model,
            scenario="M&A",
        )

        # Narrative should mention risks
        assert "risk" in narrative.lower() or "complexity" in narrative.lower()

    @pytest.mark.asyncio
    async def test_generate_narrative_includes_scenario(self):
        """Narrative includes the scenario."""
        adapter = NoOpNarrativeAdapter()
        risk_model = {
            "overall_health_score": 6.5,
            "project_name": "test-project",
            "scenario": "vendor_audit",
            "top_risks": [],
        }

        narrative = await adapter.generate_narrative(
            risk_model=risk_model,
            scenario="vendor_audit",
        )

        assert "vendor_audit" in narrative

    @pytest.mark.asyncio
    async def test_generate_narrative_with_missing_fields(self):
        """Narrative handles missing fields gracefully."""
        adapter = NoOpNarrativeAdapter()
        risk_model = {}

        narrative = await adapter.generate_narrative(
            risk_model=risk_model,
            scenario="M&A",
        )

        assert isinstance(narrative, str)
        assert len(narrative) > 0


class TestJsonReportAdapter:
    """Test JsonReportAdapter JSON file generation."""

    @pytest.mark.asyncio
    async def test_generate_pdf_writes_json_file(self, tmp_path):
        """generate_pdf writes a JSON file instead of PDF."""
        adapter = JsonReportAdapter()
        report_data = {
            "project_name": "test-project",
            "overall_health_score": 7.0,
            "dimension_scores": {
                "code_complexity": {"value": 6.0, "severity": "high"},
            },
        }

        output_path = str(tmp_path / "report.pdf")
        result = await adapter.generate_pdf(
            report_data=report_data,
            output_path=output_path,
        )

        # Should return path to JSON file (PDF replaced with .json)
        assert result.endswith(".json")

        # File should exist and contain JSON
        json_file = Path(result)
        assert json_file.exists()

        # Content should be valid JSON
        content = json.loads(json_file.read_text())
        assert content["project_name"] == "test-project"
        assert content["overall_health_score"] == 7.0

    @pytest.mark.asyncio
    async def test_generate_pdf_converts_pdf_extension_to_json(self, tmp_path):
        """Output path .pdf is converted to .json."""
        adapter = JsonReportAdapter()
        report_data = {"test": "data"}

        output_path = str(tmp_path / "report.pdf")
        result = await adapter.generate_pdf(
            report_data=report_data,
            output_path=output_path,
        )

        assert result.endswith("report.json")
        assert not result.endswith(".pdf")

    @pytest.mark.asyncio
    async def test_generate_pdf_creates_parent_directories(self, tmp_path):
        """Parent directories are created if they don't exist."""
        adapter = JsonReportAdapter()
        report_data = {"test": "data"}

        output_path = str(tmp_path / "subdir1" / "subdir2" / "report.pdf")
        result = await adapter.generate_pdf(
            report_data=report_data,
            output_path=output_path,
        )

        assert Path(result).exists()
        assert Path(result).parent.exists()

    @pytest.mark.asyncio
    async def test_generate_pdf_preserves_report_data(self, tmp_path):
        """Report data is preserved in JSON output."""
        adapter = JsonReportAdapter()
        report_data = {
            "project_name": "acme-platform",
            "scenario": "M&A",
            "overall_health_score": 6.5,
            "dimension_scores": {
                "code_complexity": {"value": 7.0, "severity": "high"},
                "security_posture": {"value": 5.0, "severity": "medium"},
            },
            "component_risks": [
                {
                    "component_name": "auth_module",
                    "composite_score": 7.5,
                }
            ],
        }

        output_path = str(tmp_path / "report.pdf")
        result = await adapter.generate_pdf(
            report_data=report_data,
            output_path=output_path,
        )

        content = json.loads(Path(result).read_text())

        assert content["project_name"] == "acme-platform"
        assert content["scenario"] == "M&A"
        assert content["overall_health_score"] == 6.5
        assert len(content["dimension_scores"]) == 2
        assert len(content["component_risks"]) == 1

    @pytest.mark.asyncio
    async def test_generate_pdf_handles_datetime_serialization(self, tmp_path):
        """datetime objects are serialized with default=str."""
        adapter = JsonReportAdapter()
        from datetime import datetime

        report_data = {
            "project_name": "test-project",
            "timestamp": datetime(2024, 1, 15, 10, 0, 0),
        }

        output_path = str(tmp_path / "report.pdf")
        result = await adapter.generate_pdf(
            report_data=report_data,
            output_path=output_path,
        )

        content = json.loads(Path(result).read_text())
        assert isinstance(content["timestamp"], str)

    @pytest.mark.asyncio
    async def test_generate_pdf_returns_absolute_path(self, tmp_path):
        """Returned path is absolute."""
        adapter = JsonReportAdapter()
        report_data = {"test": "data"}

        output_path = str(tmp_path / "report.pdf")
        result = await adapter.generate_pdf(
            report_data=report_data,
            output_path=output_path,
        )

        result_path = Path(result)
        assert result_path.is_absolute()

    @pytest.mark.asyncio
    async def test_generate_pdf_indents_json_for_readability(self, tmp_path):
        """JSON output is indented for readability."""
        adapter = JsonReportAdapter()
        report_data = {
            "project_name": "test-project",
            "nested": {"key": "value"},
        }

        output_path = str(tmp_path / "report.pdf")
        result = await adapter.generate_pdf(
            report_data=report_data,
            output_path=output_path,
        )

        content = Path(result).read_text()
        # Indented JSON should have newlines and spaces
        assert "\n" in content
        assert "  " in content
