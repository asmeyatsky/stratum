"""
AnalysisWorkflow — Concrete DAG wiring for the Stratum analysis pipeline.

Architectural Intent:
- Wires P1, P2, P3, P4 analysis as parallel steps (no mutual data dependency)
- P6 aggregation depends on all four analysis steps
- AI narrative generation depends on P6 output
- PDF report generation depends on the AI narrative (which enriches the report)
- All infrastructure access goes through constructor-injected ports; the
  workflow never imports infrastructure modules

Execution Graph::

    ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐
    │  P1      │   │  P2      │   │  P3      │   │  P4      │
    │ Evolution│   │ Commit   │   │ Design   │   │ Dep Risk │
    │ Analysis │   │ Quality  │   │ Anti-pat │   │ Analysis │
    └────┬─────┘   └────┬─────┘   └────┬─────┘   └────┬─────┘
         │              │              │              │
         └──────────┬───┴──────────┬───┴──────────────┘
                    │
              ┌─────▼─────┐
              │  P6       │
              │ Risk      │
              │ Aggregation│
              └─────┬─────┘
                    │
              ┌─────▼─────┐
              │  AI       │
              │ Narrative │
              └─────┬─────┘
                    │
              ┌─────▼─────┐
              │  PDF      │
              │ Report    │
              └───────────┘

Design Decisions:
1. Each step is a thin async closure that reads its inputs from the shared
   context dict and writes its outputs back — the DAGOrchestrator handles
   concurrency and ordering.
2. Domain services are instantiated once per workflow run (they are stateless
   pure services).
3. The workflow factory function ``build_analysis_dag`` returns a configured
   ``DAGOrchestrator`` ready to execute — separating construction from
   execution for testability.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from domain.entities.dependency import Dependency
from domain.entities.vulnerability import Vulnerability
from domain.ports.git_log_port import GitLogPort
from domain.ports.vulnerability_db_port import VulnerabilityDbPort
from domain.ports.ai_narrative_port import AINarrativePort
from domain.ports.report_generator_port import ReportGeneratorPort
from domain.services.evolution_analysis_service import EvolutionAnalysisService
from domain.services.commit_quality_service import CommitQualityService
from domain.services.design_antipattern_service import DesignAntipatternService
from domain.services.dependency_risk_service import DependencyRiskService
from domain.services.risk_aggregation_service import RiskAggregationService

from application.orchestration.dag_orchestrator import DAGOrchestrator

logger = logging.getLogger(__name__)


def build_analysis_dag(
    *,
    git_log_port: GitLogPort,
    vulnerability_db_port: VulnerabilityDbPort,
    ai_narrative_port: AINarrativePort,
    report_generator_port: ReportGeneratorPort,
) -> DAGOrchestrator:
    """
    Construct and return a fully-wired ``DAGOrchestrator`` for the Stratum
    analysis pipeline.

    The returned DAG expects the following keys in its initial context:

    - ``git_log_source`` (str): Path or URL for git log ingestion.
    - ``project_name`` (str): Name of the project being analysed.
    - ``scenario`` (str): Analysis scenario (e.g. ``"M&A"``).
    - ``output_path`` (str): Destination file path for the PDF report.
    - ``manifest_paths`` (list[str]): Paths to dependency manifest files.

    After execution the context will contain results keyed by step name
    (``p1_analysis``, ``p2_analysis``, ``p3_analysis``, ``p4_analysis``,
    ``p6_aggregation``, ``ai_narrative``, ``pdf_report``).

    Args:
        git_log_port: Adapter for git history ingestion.
        vulnerability_db_port: Adapter for CVE/vulnerability lookup.
        ai_narrative_port: Adapter for AI-generated executive narrative.
        report_generator_port: Adapter for PDF report generation.

    Returns:
        A configured ``DAGOrchestrator`` ready for ``await dag.execute(ctx)``.
    """

    # Domain services — stateless, instantiated once per workflow
    evolution_svc = EvolutionAnalysisService()
    commit_quality_svc = CommitQualityService()
    design_antipattern_svc = DesignAntipatternService()
    dependency_risk_svc = DependencyRiskService()
    risk_aggregation_svc = RiskAggregationService()

    # ------------------------------------------------------------------
    # Step definitions
    # ------------------------------------------------------------------

    async def p1_analysis(ctx: dict[str, Any]) -> dict[str, Any]:
        """P1 — Code & Team Evolution Analysis (parallel)."""
        logger.info("P1: parsing git log from %s", ctx["git_log_source"])
        commits = await git_log_port.parse(ctx["git_log_source"])
        ctx["_commits"] = commits  # shared with P2 and P6

        knowledge_risks = evolution_svc.analyze_knowledge_distribution(commits)
        temporal_couplings = evolution_svc.detect_temporal_coupling(commits)
        churn_anomalies = evolution_svc.detect_churn_anomalies(commits)

        # Unique modules for total_components denominator
        all_modules: set[str] = set()
        for commit in commits:
            all_modules.update(fc.module for fc in commit.file_changes)

        p1_scores = evolution_svc.compute_risk_scores(
            knowledge_risks=knowledge_risks,
            couplings=temporal_couplings,
            churn_anomalies=churn_anomalies,
            total_components=len(all_modules),
        )

        logger.info(
            "P1: found %d knowledge risks, %d couplings, %d churn anomalies",
            len(knowledge_risks),
            len(temporal_couplings),
            len(churn_anomalies),
        )

        return {
            "commits": commits,
            "knowledge_risks": knowledge_risks,
            "temporal_couplings": temporal_couplings,
            "churn_anomalies": churn_anomalies,
            "p1_scores": p1_scores,
        }

    async def p2_analysis(ctx: dict[str, Any]) -> dict[str, Any]:
        """P2 — Commit Quality Analysis (parallel, shares git log with P1)."""
        # P2 also needs commits; if P1 hasn't populated _commits yet
        # (running concurrently), parse independently.
        commits = ctx.get("_commits")
        if commits is None:
            logger.info("P2: parsing git log independently")
            commits = await git_log_port.parse(ctx["git_log_source"])

        quality_report = commit_quality_svc.assess_commit_quality(commits)
        bug_magnets = commit_quality_svc.detect_bug_magnets(commits)
        trends = commit_quality_svc.compute_feature_bug_trends(commits)

        p2_scores = commit_quality_svc.compute_risk_scores(
            quality_report=quality_report,
            bug_magnets=bug_magnets,
            trends=trends,
        )

        logger.info(
            "P2: %d total commits assessed, %d bug magnets detected",
            quality_report.total_commits,
            len(bug_magnets),
        )

        return {
            "quality_report": quality_report,
            "bug_magnets": bug_magnets,
            "trends": trends,
            "p2_scores": p2_scores,
        }

    async def p3_analysis(ctx: dict[str, Any]) -> dict[str, Any]:
        """P3 — Design Anti-Pattern Detection (parallel)."""
        commits = ctx.get("_commits")
        if commits is None:
            logger.info("P3: parsing git log independently")
            commits = await git_log_port.parse(ctx["git_log_source"])

        god_classes = design_antipattern_svc.detect_god_classes(commits)
        feature_envy = design_antipattern_svc.detect_feature_envy(commits)
        shotgun_surgery = design_antipattern_svc.detect_shotgun_surgery(commits)
        data_classes = design_antipattern_svc.detect_data_classes(commits)

        p3_scores = design_antipattern_svc.compute_risk_scores(
            god_classes=god_classes,
            feature_envy=feature_envy,
            shotgun_surgery=shotgun_surgery,
            data_classes=data_classes,
        )

        logger.info(
            "P3: found %d god classes, %d feature envy, %d shotgun surgery, %d data classes",
            len(god_classes), len(feature_envy), len(shotgun_surgery), len(data_classes),
        )

        return {
            "god_classes": god_classes,
            "feature_envy": feature_envy,
            "shotgun_surgery": shotgun_surgery,
            "data_classes": data_classes,
            "p3_scores": p3_scores,
        }

    async def p4_analysis(ctx: dict[str, Any]) -> dict[str, Any]:
        """P4 — Dependency Risk Analysis (parallel)."""
        manifest_paths: list[str] = ctx.get("manifest_paths", [])
        if not manifest_paths:
            logger.info("P4: no manifest paths provided — skipping dependency scan")
            return {
                "dependencies": [],
                "assessments": [],
                "p4_scores": dependency_risk_svc.compute_risk_scores([], []),
            }

        # Parse dependencies from manifest files.
        # The git_log_port.parse is for git logs; dependency manifests are
        # simple enough to parse in-band for MVP.  For now we create
        # placeholder Dependency objects — a dedicated ManifestParserPort
        # can be introduced later.
        dependencies = _parse_manifests(manifest_paths)

        # Look up vulnerabilities for each dependency concurrently
        vuln_tasks = [
            vulnerability_db_port.search(dep.name, dep.current_version)
            for dep in dependencies
        ]
        vuln_results = await asyncio.gather(*vuln_tasks, return_exceptions=True)

        vulnerability_map: dict[str, list[Vulnerability]] = {}
        for dep, result in zip(dependencies, vuln_results):
            if isinstance(result, BaseException):
                logger.warning(
                    "P4: vulnerability lookup failed for %s: %s", dep.name, result
                )
                vulnerability_map[dep.name] = []
            else:
                vulnerability_map[dep.name] = result

        assessments = dependency_risk_svc.assess_all(dependencies, vulnerability_map)
        p4_scores = dependency_risk_svc.compute_risk_scores(assessments, dependencies)

        logger.info(
            "P4: assessed %d dependencies, %d total vulnerabilities",
            len(dependencies),
            sum(len(v) for v in vulnerability_map.values()),
        )

        return {
            "dependencies": dependencies,
            "assessments": assessments,
            "p4_scores": p4_scores,
        }

    async def p6_aggregation(ctx: dict[str, Any]) -> dict[str, Any]:
        """P6 — Integrated Risk Aggregation (depends on P1 + P2 + P3 + P4)."""
        p1 = ctx["p1_analysis"]
        p2 = ctx["p2_analysis"]
        p3 = ctx["p3_analysis"]
        p4 = ctx["p4_analysis"]

        report = risk_aggregation_svc.build_report(
            project_name=ctx["project_name"],
            scenario=ctx["scenario"],
            p1_scores=p1["p1_scores"],
            p2_scores=p2["p2_scores"],
            p4_scores=p4["p4_scores"],
            p3_scores=p3["p3_scores"],
            knowledge_risks=p1["knowledge_risks"],
            bug_magnets=p2["bug_magnets"],
            churn_anomalies=p1["churn_anomalies"],
            commits=p1["commits"],
        )

        logger.info(
            "P6: aggregated risk report — overall health %.1f/10, %d dimensions scored",
            report.overall_health_score,
            len(report.dimension_scores),
        )

        return {"report": report}

    async def ai_narrative(ctx: dict[str, Any]) -> dict[str, Any]:
        """AI narrative generation (depends on P6)."""
        p6 = ctx["p6_aggregation"]
        report = p6["report"]

        risk_model = report.to_dict()
        narrative = await ai_narrative_port.generate_narrative(
            risk_model=risk_model,
            scenario=ctx["scenario"],
        )

        enriched_report = report.with_ai_narrative(narrative)
        logger.info("AI narrative generated (%d characters)", len(narrative))

        return {"report": enriched_report, "narrative": narrative}

    async def pdf_report(ctx: dict[str, Any]) -> dict[str, Any]:
        """PDF report generation (depends on AI narrative)."""
        enriched_report = ctx["ai_narrative"]["report"]
        report_data = enriched_report.to_dict()

        output_path = await report_generator_port.generate_pdf(
            report_data=report_data,
            output_path=ctx["output_path"],
        )

        logger.info("PDF report written to %s", output_path)

        return {"pdf_path": output_path, "report": enriched_report}

    # ------------------------------------------------------------------
    # Wire the DAG
    # ------------------------------------------------------------------

    dag = DAGOrchestrator()
    dag.add_step("p1_analysis", p1_analysis)
    dag.add_step("p2_analysis", p2_analysis)
    dag.add_step("p3_analysis", p3_analysis)
    dag.add_step("p4_analysis", p4_analysis)
    dag.add_step("p6_aggregation", p6_aggregation, depends_on=["p1_analysis", "p2_analysis", "p3_analysis", "p4_analysis"])
    dag.add_step("ai_narrative", ai_narrative, depends_on=["p6_aggregation"])
    dag.add_step("pdf_report", pdf_report, depends_on=["ai_narrative"])

    return dag


# ---------------------------------------------------------------------------
# Manifest parsing helper (MVP — inline for now)
# ---------------------------------------------------------------------------

def _parse_manifests(manifest_paths: list[str]) -> list[Dependency]:
    """
    Parse dependency manifests into ``Dependency`` entities.

    This is a minimal MVP implementation that reads JSON-based manifests
    (package.json) and requirements-style text files (requirements.txt,
    Pipfile).  A dedicated ``ManifestParserPort`` should replace this once
    the infrastructure layer supports multiple ecosystems.
    """
    import json
    from pathlib import Path

    dependencies: list[Dependency] = []

    for path_str in manifest_paths:
        path = Path(path_str)
        if not path.exists():
            logger.warning("Manifest file not found: %s", path_str)
            continue

        try:
            if path.name == "package.json":
                dependencies.extend(_parse_package_json(path))
            elif path.name in ("requirements.txt", "requirements-dev.txt"):
                dependencies.extend(_parse_requirements_txt(path))
            else:
                logger.warning("Unsupported manifest format: %s", path.name)
        except Exception:
            logger.exception("Failed to parse manifest: %s", path_str)

    return dependencies


def _parse_package_json(path: Any) -> list[Dependency]:
    """Extract dependencies from a package.json file."""
    import json

    content = path.read_text(encoding="utf-8")
    data = json.loads(content)
    deps: list[Dependency] = []

    for section in ("dependencies", "devDependencies"):
        for name, version_spec in data.get(section, {}).items():
            # Strip common version prefixes (^, ~, >=)
            version = version_spec.lstrip("^~>=<! ")
            deps.append(
                Dependency(
                    name=name,
                    current_version=version,
                    ecosystem="npm",
                    manifest_path=str(path),
                )
            )

    return deps


def _parse_requirements_txt(path: Any) -> list[Dependency]:
    """Extract dependencies from a pip requirements.txt file."""
    import re

    content = path.read_text(encoding="utf-8")
    deps: list[Dependency] = []
    pattern = re.compile(r"^([A-Za-z0-9_.-]+)\s*(?:[=<>!~]+\s*(.+))?$")

    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        match = pattern.match(line)
        if match:
            name = match.group(1)
            version = match.group(2) or "0.0.0"
            deps.append(
                Dependency(
                    name=name,
                    current_version=version.strip(),
                    ecosystem="pip",
                    manifest_path=str(path),
                )
            )

    return deps
