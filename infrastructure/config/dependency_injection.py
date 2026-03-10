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
    - Fallback adapters used when optional services are unavailable:
      * NoOpNarrativeAdapter when no ANTHROPIC_API_KEY
      * JsonReportAdapter when pango/WeasyPrint unavailable
    - Phase 2 connectors (GitHub, Jira) are optional — wired only when
      environment variables are present. ``None`` signals "not configured".
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any

from domain.services.evolution_analysis_service import EvolutionAnalysisService
from domain.services.commit_quality_service import CommitQualityService
from domain.services.design_antipattern_service import DesignAntipatternService
from domain.services.dependency_risk_service import DependencyRiskService
from domain.services.risk_aggregation_service import RiskAggregationService

from infrastructure.adapters.git_log_parser import GitLogParser
from infrastructure.adapters.manifest_parser import ManifestParser
from infrastructure.adapters.nvd_vulnerability_adapter import NvdVulnerabilityAdapter
from infrastructure.adapters.claude_narrative_adapter import ClaudeNarrativeAdapter
from infrastructure.adapters.fallback_adapters import NoOpNarrativeAdapter, JsonReportAdapter

logger = logging.getLogger(__name__)


@dataclass
class Container:
    """Composition root holding all wired dependencies.

    All port-typed fields are guaranteed non-None — fallback adapters are used
    when optional services (Claude API, WeasyPrint) are unavailable. This
    eliminates null-checking throughout the codebase.

    Phase 2 connector fields (``github_adapter``, ``jira_adapter``) are
    ``None`` when the corresponding environment variables are not set.
    Router code checks for ``None`` and falls back to per-request
    token-based adapter construction.
    """

    # Infrastructure adapters (port-compliant — always non-None)
    git_log_parser: Any  # GitLogPort
    manifest_parser: ManifestParser
    nvd_adapter: Any  # VulnerabilityDbPort
    narrative_adapter: Any  # AINarrativePort (ClaudeNarrativeAdapter or NoOpNarrativeAdapter)
    report_adapter: Any  # ReportGeneratorPort (WeasyprintReportAdapter or JsonReportAdapter)

    # Phase 2 connectors (optional — None when env vars not set)
    github_adapter: Any | None  # GitHubPort (GitHubAdapter or None)
    jira_adapter: Any | None  # JiraPort (JiraAdapter or None)

    # Domain services
    evolution_service: EvolutionAnalysisService
    commit_quality_service: CommitQualityService
    design_antipattern_service: DesignAntipatternService
    dependency_risk_service: DependencyRiskService
    risk_aggregation_service: RiskAggregationService

    @classmethod
    def create(
        cls,
        *,
        anthropic_api_key: str | None = None,
        nvd_api_key: str | None = None,
        github_token: str | None = None,
        jira_url: str | None = None,
        jira_email: str | None = None,
        jira_token: str | None = None,
    ) -> Container:
        """Create a fully wired Container with all dependencies.

        Configuration is resolved from explicit arguments first, then
        environment variables. Fallback adapters are used for optional
        services (Claude narrative, PDF rendering).

        Args:
            anthropic_api_key: Anthropic API key for Claude narrative generation.
                Falls back to ``ANTHROPIC_API_KEY`` env var.
            nvd_api_key: NIST NVD API key for higher rate limits.
                Falls back to ``NVD_API_KEY`` env var.
            github_token: GitHub personal access token or App installation token.
                Falls back to ``GITHUB_TOKEN`` env var. Optional.
            jira_url: Jira Cloud instance URL.
                Falls back to ``JIRA_URL`` env var. Optional.
            jira_email: Jira user email for API auth.
                Falls back to ``JIRA_EMAIL`` env var. Optional.
            jira_token: Jira API token.
                Falls back to ``JIRA_TOKEN`` env var. Optional.

        Returns:
            A fully initialised :class:`Container`.
        """
        logger.info("Initialising Stratum dependency container")

        # --- Infrastructure adapters ---

        git_log_parser = GitLogParser()

        manifest_parser = ManifestParser()

        resolved_nvd_key = nvd_api_key or os.environ.get("NVD_API_KEY")
        nvd_adapter = NvdVulnerabilityAdapter(api_key=resolved_nvd_key)

        # Narrative adapter: Claude if API key available, otherwise no-op fallback
        resolved_anthropic_key = anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY")
        narrative_adapter: Any
        if resolved_anthropic_key:
            try:
                narrative_adapter = ClaudeNarrativeAdapter(api_key=resolved_anthropic_key)
                logger.info("Claude narrative adapter enabled")
            except Exception as exc:
                logger.warning("Claude adapter init failed (%s) — using fallback", exc)
                narrative_adapter = NoOpNarrativeAdapter()
        else:
            logger.info(
                "No ANTHROPIC_API_KEY — using placeholder narrative adapter. "
                "Set ANTHROPIC_API_KEY for Claude-powered executive summaries."
            )
            narrative_adapter = NoOpNarrativeAdapter()

        # Report adapter: WeasyPrint if pango available, otherwise JSON fallback
        try:
            from infrastructure.adapters.weasyprint_report_adapter import WeasyprintReportAdapter
            report_adapter: Any = WeasyprintReportAdapter()
            logger.info("WeasyPrint PDF adapter enabled")
        except (OSError, RuntimeError, ImportError):
            logger.info(
                "WeasyPrint unavailable (missing pango) — using JSON report fallback. "
                "Install pango for PDF output: brew install pango (macOS)"
            )
            report_adapter = JsonReportAdapter()

        # --- Phase 2 connectors (optional) ---

        # GitHub adapter
        github_adapter: Any | None = None
        resolved_github_token = github_token or os.environ.get("GITHUB_TOKEN")
        if resolved_github_token:
            try:
                from infrastructure.adapters.github_adapter import GitHubAdapter
                github_adapter = GitHubAdapter(token=resolved_github_token)
                logger.info("GitHub adapter enabled (token from environment)")
            except Exception as exc:
                logger.warning("GitHub adapter init failed (%s) — connector disabled", exc)
        else:
            logger.info(
                "No GITHUB_TOKEN — GitHub connector not pre-configured. "
                "Users can connect via POST /api/connectors/github/connect."
            )

        # Jira adapter
        jira_adapter: Any | None = None
        resolved_jira_url = jira_url or os.environ.get("JIRA_URL")
        resolved_jira_email = jira_email or os.environ.get("JIRA_EMAIL")
        resolved_jira_token = jira_token or os.environ.get("JIRA_TOKEN")
        if resolved_jira_url and resolved_jira_email and resolved_jira_token:
            try:
                from infrastructure.adapters.jira_adapter import JiraAdapter
                jira_adapter = JiraAdapter(
                    base_url=resolved_jira_url,
                    email=resolved_jira_email,
                    api_token=resolved_jira_token,
                )
                logger.info("Jira adapter enabled (credentials from environment)")
            except Exception as exc:
                logger.warning("Jira adapter init failed (%s) — connector disabled", exc)
        else:
            logger.info(
                "No JIRA_URL/JIRA_EMAIL/JIRA_TOKEN — Jira connector not pre-configured. "
                "Users can connect via POST /api/connectors/jira/connect."
            )

        # --- Domain services (stateless, no infrastructure dependencies) ---

        evolution_service = EvolutionAnalysisService()
        commit_quality_service = CommitQualityService()
        design_antipattern_service = DesignAntipatternService()
        dependency_risk_service = DependencyRiskService()
        risk_aggregation_service = RiskAggregationService()

        container = cls(
            git_log_parser=git_log_parser,
            manifest_parser=manifest_parser,
            nvd_adapter=nvd_adapter,
            narrative_adapter=narrative_adapter,
            report_adapter=report_adapter,
            github_adapter=github_adapter,
            jira_adapter=jira_adapter,
            evolution_service=evolution_service,
            commit_quality_service=commit_quality_service,
            design_antipattern_service=design_antipattern_service,
            dependency_risk_service=dependency_risk_service,
            risk_aggregation_service=risk_aggregation_service,
        )

        logger.info("Stratum dependency container initialised successfully")
        return container
