"""
AnalyzeRepositoryCommand — Primary use case for full repository analysis.

Architectural Intent (skill2026 Rule: one use case per class):
- Single responsibility: orchestrate a complete P1+P2+P4+P6 analysis run
- Constructor-injected ports — no infrastructure imports, fully testable
- Delegates workflow execution to DAGOrchestrator via the analysis workflow
- Converts domain results to DTOs at the application boundary
- Emits timing and lifecycle logging for observability

Usage::

    cmd = AnalyzeRepositoryCommand(
        git_log_port=git_adapter,
        vulnerability_db_port=vuln_adapter,
        ai_narrative_port=ai_adapter,
        report_generator_port=pdf_adapter,
    )
    result = await cmd.execute(AnalysisRequest(
        git_log_source="/data/repo.log",
        project_name="acme-platform",
        scenario="M&A",
        output_path="/reports/acme.pdf",
        manifest_paths=["package.json", "requirements.txt"],
    ))
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from domain.ports.git_log_port import GitLogPort
from domain.ports.vulnerability_db_port import VulnerabilityDbPort
from domain.ports.ai_narrative_port import AINarrativePort
from domain.ports.report_generator_port import ReportGeneratorPort

from application.dtos.analysis_dto import AnalysisRequest, AnalysisResultDTO, risk_report_to_dto
from application.orchestration.analysis_workflow import build_analysis_dag

logger = logging.getLogger(__name__)


class AnalyzeRepositoryCommand:
    """
    Execute a full Stratum repository analysis.

    This is the primary entry point for the application layer.  It wires
    infrastructure adapters (via ports) into the analysis DAG, executes
    the workflow, and returns a serializable ``AnalysisResultDTO``.

    All four ports are constructor-injected so the command itself carries
    no infrastructure knowledge — only domain and application imports.
    """

    def __init__(
        self,
        *,
        git_log_port: GitLogPort,
        vulnerability_db_port: VulnerabilityDbPort,
        ai_narrative_port: AINarrativePort,
        report_generator_port: ReportGeneratorPort,
    ) -> None:
        self._git_log_port = git_log_port
        self._vulnerability_db_port = vulnerability_db_port
        self._ai_narrative_port = ai_narrative_port
        self._report_generator_port = report_generator_port

    async def execute(self, request: AnalysisRequest) -> AnalysisResultDTO:
        """
        Run the full analysis pipeline and return a serializable result.

        Steps (executed via DAGOrchestrator):
          1. P1 Evolution Analysis   ┐
          2. P2 Commit Quality       ├─ parallel
          3. P4 Dependency Risk      ┘
          4. P6 Risk Aggregation     ← depends on 1-3
          5. AI Narrative            ← depends on 4
          6. PDF Report Generation   ← depends on 5

        Args:
            request: Analysis input parameters.

        Returns:
            ``AnalysisResultDTO`` with all analysis results and the PDF path.

        Raises:
            Exception: Any failure from port adapters or domain services
                propagates to the caller.
        """
        logger.info(
            "Starting analysis: project=%s scenario=%s source=%s",
            request.project_name,
            request.scenario,
            request.git_log_source,
        )
        start_time = time.monotonic()

        # Build the DAG with injected ports
        dag = build_analysis_dag(
            git_log_port=self._git_log_port,
            vulnerability_db_port=self._vulnerability_db_port,
            ai_narrative_port=self._ai_narrative_port,
            report_generator_port=self._report_generator_port,
        )

        # Seed context with request parameters
        initial_context = {
            "git_log_source": request.git_log_source,
            "project_name": request.project_name,
            "scenario": request.scenario,
            "output_path": request.output_path,
            "manifest_paths": request.manifest_paths,
        }

        # Execute the full pipeline
        final_context = await dag.execute(initial_context)

        elapsed = time.monotonic() - start_time

        # Extract final report and PDF path from context
        pdf_result = final_context["pdf_report"]
        enriched_report = pdf_result["report"]
        pdf_path = pdf_result["pdf_path"]

        # Convert domain entity to DTO at the application boundary
        result = risk_report_to_dto(enriched_report, pdf_output_path=pdf_path)

        logger.info(
            "Analysis complete: project=%s health=%.1f/10 elapsed=%.1fs pdf=%s",
            request.project_name,
            result.overall_health_score,
            elapsed,
            pdf_path,
        )

        return result
