"""
Fallback Adapters — No-op implementations of optional ports.

Architectural Intent:
    These adapters provide graceful degradation when optional external
    services (Claude API, WeasyPrint/pango) are unavailable. They
    implement the same port protocols as the real adapters, returning
    sensible defaults rather than raising errors.

    Used by the DI Container when:
    - No ANTHROPIC_API_KEY is set → NoOpNarrativeAdapter
    - pango system library missing → JsonReportAdapter (writes JSON instead of PDF)
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class NoOpNarrativeAdapter:
    """Fallback AINarrativePort — returns a placeholder narrative."""

    async def generate_narrative(self, risk_model: dict, scenario: str) -> str:
        logger.info("AI narrative adapter not configured — using placeholder narrative")
        health = risk_model.get("overall_health_score", "N/A")
        project = risk_model.get("project_name", "Unknown")
        top_risks = risk_model.get("top_risks", [])

        lines = [
            f"# Executive Summary — {project}",
            "",
            f"Overall health score: {health}/10.0 (scenario: {scenario})",
            "",
            "## Top Risks",
        ]
        for risk in top_risks[:5]:
            dim = risk.get("dimension", risk.get("label", ""))
            val = risk.get("value", 0)
            evidence = risk.get("evidence", "")
            lines.append(f"- **{dim}** (severity {val}/10): {evidence}")

        lines.extend([
            "",
            "---",
            "*This is a placeholder narrative. Configure ANTHROPIC_API_KEY to enable "
            "Claude-powered executive summaries with scenario-specific framing.*",
        ])
        return "\n".join(lines)


class JsonReportAdapter:
    """Fallback ReportGeneratorPort — writes JSON when PDF rendering is unavailable."""

    async def generate_pdf(self, report_data: dict, output_path: str) -> str:
        json_path = output_path.replace(".pdf", ".json")
        out = Path(json_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps(report_data, indent=2, default=str),
            encoding="utf-8",
        )
        logger.info(
            "PDF rendering unavailable (missing pango). "
            "Wrote JSON report to %s instead.",
            json_path,
        )
        return str(out.resolve())
