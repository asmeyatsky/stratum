"""
Dependency Injection — Composition Root for the Stratum platform.

Architectural Intent:
    This module is the single point where all adapters, domain services, and
    application use cases are instantiated and wired together. No other module
    should construct infrastructure adapters or domain services directly.

    The Container class follows the Composition Root pattern: it creates
    concrete implementations and injects them into consumers via constructor
    arguments. This keeps the domain and application layers free of
    infrastructure coupling.

Design Decisions:
    - Simple ``Container`` dataclass — no DI framework overhead.
    - ``Container.create()`` factory method performs all wiring.
    - Configuration sourced from environment variables with sensible defaults.
    - Adapters are created eagerly (fail-fast on misconfiguration).
    - Domain services are stateless and shared across requests.
    - The Claude adapter is optional — if no API key is provided, it is set
      to ``None`` and callers must handle the absence.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

from domain.services.evolution_analysis_service import EvolutionAnalysisService
from domain.services.commit_quality_service import CommitQualityService
from domain.services.dependency_risk_service import DependencyRiskService
from domain.services.risk_aggregation_service import RiskAggregationService

from infrastructure.adapters.git_log_parser import GitLogParser
from infrastructure.adapters.manifest_parser import ManifestParser
from infrastructure.adapters.nvd_vulnerability_adapter import NvdVulnerabilityAdapter
from infrastructure.adapters.claude_narrative_adapter import ClaudeNarrativeAdapter
from infrastructure.adapters.weasyprint_report_adapter import WeasyprintReportAdapter

logger = logging.getLogger(__name__)


@dataclass
class Container:
    """Composition root holding all wired dependencies.

    Access adapters and services via the container instance returned by
    :meth:`create`. All fields are typed against their concrete classes
    (not protocols) — the container is infrastructure-aware by design.

    Attributes:
        git_log_parser: Adapter for parsing git log output files.
        manifest_parser: Adapter for parsing dependency manifests.
        nvd_adapter: Adapter for querying the NIST NVD vulnerability database.
        claude_adapter: Adapter for AI narrative generation (``None`` if no API key).
        report_adapter: Adapter for PDF report rendering.
        evolution_service: P1 — code and team evolution analysis.
        commit_quality_service: P2 — commit quality and bug magnet detection.
        dependency_risk_service: P4 — library dependency risk analysis.
        risk_aggregation_service: P6 — integrated risk model assembly.
    """

    # Infrastructure adapters
    git_log_parser: GitLogParser
    manifest_parser: ManifestParser
    nvd_adapter: NvdVulnerabilityAdapter
    claude_adapter: ClaudeNarrativeAdapter | None
    report_adapter: WeasyprintReportAdapter

    # Domain services
    evolution_service: EvolutionAnalysisService
    commit_quality_service: CommitQualityService
    dependency_risk_service: DependencyRiskService
    risk_aggregation_service: RiskAggregationService

    @classmethod
    def create(
        cls,
        *,
        anthropic_api_key: str | None = None,
        nvd_api_key: str | None = None,
    ) -> Container:
        """Create a fully wired Container with all dependencies.

        Configuration is resolved from explicit arguments first, then
        environment variables.

        Args:
            anthropic_api_key: Anthropic API key for Claude narrative generation.
                Falls back to ``ANTHROPIC_API_KEY`` env var. If neither is set,
                the Claude adapter is omitted.
            nvd_api_key: NIST NVD API key for higher rate limits.
                Falls back to ``NVD_API_KEY`` env var. If neither is set,
                the adapter runs unauthenticated (slower rate limit).

        Returns:
            A fully initialised :class:`Container`.
        """
        logger.info("Initialising Stratum dependency container")

        # --- Infrastructure adapters ---

        git_log_parser = GitLogParser()
        logger.debug("Created GitLogParser adapter")

        manifest_parser = ManifestParser()
        logger.debug("Created ManifestParser adapter")

        resolved_nvd_key = nvd_api_key or os.environ.get("NVD_API_KEY")
        nvd_adapter = NvdVulnerabilityAdapter(api_key=resolved_nvd_key)
        logger.debug(
            "Created NvdVulnerabilityAdapter (authenticated=%s)",
            resolved_nvd_key is not None,
        )

        resolved_anthropic_key = anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY")
        claude_adapter: ClaudeNarrativeAdapter | None = None
        if resolved_anthropic_key:
            try:
                claude_adapter = ClaudeNarrativeAdapter(api_key=resolved_anthropic_key)
                logger.debug("Created ClaudeNarrativeAdapter")
            except ValueError as exc:
                logger.warning("Claude adapter not available: %s", exc)
        else:
            logger.info(
                "No Anthropic API key provided — Claude narrative adapter disabled. "
                "Set ANTHROPIC_API_KEY to enable AI-generated narratives."
            )

        report_adapter = WeasyprintReportAdapter()
        logger.debug("Created WeasyprintReportAdapter")

        # --- Domain services (stateless, no infrastructure dependencies) ---

        evolution_service = EvolutionAnalysisService()
        commit_quality_service = CommitQualityService()
        dependency_risk_service = DependencyRiskService()
        risk_aggregation_service = RiskAggregationService()
        logger.debug("Created domain services (P1, P2, P4, P6)")

        container = cls(
            git_log_parser=git_log_parser,
            manifest_parser=manifest_parser,
            nvd_adapter=nvd_adapter,
            claude_adapter=claude_adapter,
            report_adapter=report_adapter,
            evolution_service=evolution_service,
            commit_quality_service=commit_quality_service,
            dependency_risk_service=dependency_risk_service,
            risk_aggregation_service=risk_aggregation_service,
        )

        logger.info("Stratum dependency container initialised successfully")
        return container
