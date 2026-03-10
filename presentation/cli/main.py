"""
Stratum CLI

Architectural Intent:
    Presentation layer entry point. This module is a thin wrapper that:
    1. Parses CLI arguments via Click
    2. Delegates to AnalyzeRepositoryCommand (application layer) for analysis
    3. Displays results — no business logic lives here

    The CLI never orchestrates domain services directly. All analysis flows
    through the application layer's DAG-based workflow.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

import click

# ---------------------------------------------------------------------------
# Optional rich integration — fall back to plain click.echo
# ---------------------------------------------------------------------------

_rich_available = False
_console = None

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel

    _rich_available = True
    _console = Console(stderr=True)
except ImportError:
    pass


def _echo(message: str, *, err: bool = False, style: str | None = None) -> None:
    if _rich_available and _console is not None and style:
        _console.print(message, style=style)
    else:
        click.echo(message, err=err)


def _echo_success(message: str) -> None:
    _echo(message, style="bold green")


def _echo_warning(message: str) -> None:
    _echo(message, style="bold yellow")


def _echo_error(message: str) -> None:
    _echo(message, err=True, style="bold red")


def _echo_info(message: str) -> None:
    _echo(message, style="cyan")


# ---------------------------------------------------------------------------
# CLI group
# ---------------------------------------------------------------------------


@click.group()
@click.version_option(package_name="stratum", prog_name="stratum")
def cli() -> None:
    """Stratum -- AI-native code intelligence platform.

    Every layer of your codebase, decoded. Analyse git history, commit quality,
    dependency risk, and produce integrated risk reports across 15 quality
    dimensions.
    """


# ---------------------------------------------------------------------------
# stratum analyze
# ---------------------------------------------------------------------------


SCENARIO_CHOICES = click.Choice(
    [
        "ma_due_diligence",
        "vendor_audit",
        "post_merger",
        "decommission",
        "cto_onboarding",
        "oss_assessment",
    ],
    case_sensitive=False,
)


@cli.command()
@click.option(
    "--git-log",
    required=True,
    type=click.Path(exists=True, dir_okay=False, resolve_path=True),
    help="Path to the git log file (generated via: git log --numstat --pretty=format:'%%H|%%ae|%%an|%%aI|%%s').",
)
@click.option(
    "--project",
    required=True,
    type=str,
    help="Human-readable project name for the report.",
)
@click.option(
    "--scenario",
    type=SCENARIO_CHOICES,
    default="cto_onboarding",
    show_default=True,
    help="Analysis scenario determining report framing and emphasis.",
)
@click.option(
    "--output",
    type=click.Path(dir_okay=False, resolve_path=True),
    default="stratum_report.pdf",
    show_default=True,
    help="Output path for the PDF report.",
)
@click.option(
    "--manifests",
    multiple=True,
    type=click.Path(exists=True, dir_okay=False, resolve_path=True),
    help="Paths to package manifest files (repeatable: --manifests a.json --manifests b.txt).",
)
@click.option(
    "--json-output",
    type=click.Path(dir_okay=False, resolve_path=True),
    default=None,
    help="Optional path to write the raw analysis JSON.",
)
def analyze(
    git_log: str,
    project: str,
    scenario: str,
    output: str,
    manifests: tuple[str, ...],
    json_output: str | None,
) -> None:
    """Run a full Stratum code intelligence analysis.

    Analyses git history for code evolution (P1), commit quality (P2),
    dependency risk (P4), and produces an integrated risk model (P6) with
    15 quality dimensions scored on a 1-10 severity scale.
    """
    try:
        asyncio.run(_run_analysis(git_log, project, scenario, output, manifests, json_output))
    except KeyboardInterrupt:
        _echo_warning("\nAnalysis interrupted by user.")
        sys.exit(130)
    except Exception as exc:
        _echo_error(f"Analysis failed: {exc}")
        sys.exit(1)


async def _run_analysis(
    git_log: str,
    project: str,
    scenario: str,
    output: str,
    manifests: tuple[str, ...],
    json_output: str | None,
) -> None:
    """Delegate to AnalyzeRepositoryCommand via the application layer."""
    from infrastructure.config.dependency_injection import Container
    from application.commands.analyze_repository import AnalyzeRepositoryCommand
    from application.dtos.analysis_dto import AnalysisRequest

    _echo_info(f"Stratum analysis starting for project: {project}")
    _echo_info(f"Scenario: {scenario}")
    _echo_info(f"Git log: {git_log}")
    if manifests:
        _echo_info(f"Manifests: {', '.join(manifests)}")
    click.echo("")

    container = Container.create()

    # Build the use case with port-compliant adapters from the container
    command = AnalyzeRepositoryCommand(
        git_log_port=container.git_log_parser,
        vulnerability_db_port=container.nvd_adapter,
        ai_narrative_port=container.narrative_adapter,
        report_generator_port=container.report_adapter,
    )

    request = AnalysisRequest(
        git_log_source=git_log,
        project_name=project,
        scenario=scenario,
        output_path=output,
        manifest_paths=list(manifests),
    )

    click.echo("  Running P1 (evolution) || P2 (commit quality) || P4 (dependency risk)...")
    result = await command.execute(request)

    _echo_success(f"  Analysis complete. Health score: {result.overall_health_score}/10.0")

    if result.pdf_output_path:
        _echo_success(f"  Report written to: {result.pdf_output_path}")

    # --- Write JSON output if requested ---
    if json_output:
        json_path = Path(json_output)
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(
            json.dumps(result.to_dict(), indent=2, default=str),
            encoding="utf-8",
        )
        _echo_success(f"  JSON output written to: {json_output}")

    # --- Print summary ---
    click.echo("")
    _print_summary(result.to_dict())


# ---------------------------------------------------------------------------
# stratum scan-deps
# ---------------------------------------------------------------------------


@cli.command("scan-deps")
@click.option(
    "--manifests",
    multiple=True,
    required=True,
    type=click.Path(exists=True, dir_okay=False, resolve_path=True),
    help="Paths to package manifest files (repeatable).",
)
@click.option(
    "--json-output",
    type=click.Path(dir_okay=False, resolve_path=True),
    default=None,
    help="Optional path to write scan results as JSON.",
)
def scan_deps(manifests: tuple[str, ...], json_output: str | None) -> None:
    """Quick dependency-only scan.

    Parses manifest files and reports on library risk, version currency,
    and known CVE exposure. Does not require git history.
    """
    try:
        asyncio.run(_run_scan_deps(manifests, json_output))
    except KeyboardInterrupt:
        _echo_warning("\nScan interrupted by user.")
        sys.exit(130)
    except Exception as exc:
        _echo_error(f"Dependency scan failed: {exc}")
        sys.exit(1)


async def _run_scan_deps(manifests: tuple[str, ...], json_output: str | None) -> None:
    """Scan dependency manifests using real infrastructure adapters."""
    from infrastructure.config.dependency_injection import Container

    _echo_info(f"Scanning {len(manifests)} manifest file(s)...")
    for m in manifests:
        click.echo(f"  - {m}")
    click.echo("")

    container = Container.create()

    # Parse all manifests
    all_dependencies = []
    for manifest_path in manifests:
        deps = container.manifest_parser.parse(manifest_path)
        all_dependencies.extend(deps)

    if not all_dependencies:
        _echo_warning("No dependencies found in provided manifests.")
        return

    _echo_success(f"  Found {len(all_dependencies)} dependencies.")

    # Look up vulnerabilities concurrently
    click.echo("  Checking CVE database...")
    vuln_map: dict[str, list] = {}
    tasks = [
        container.nvd_adapter.search(dep.name, dep.current_version)
        for dep in all_dependencies
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    for dep, result in zip(all_dependencies, results):
        if isinstance(result, BaseException):
            vuln_map[dep.name] = []
        else:
            vuln_map[dep.name] = result

    # Assess risk
    assessments = container.dependency_risk_service.assess_all(all_dependencies, vuln_map)
    scores = container.dependency_risk_service.compute_risk_scores(assessments, all_dependencies)

    total_vulns = sum(len(a.vulnerabilities) for a in assessments)
    critical = [a for a in assessments if a.risk_level in ("critical", "high")]

    _echo_success(f"  {total_vulns} CVEs found, {len(critical)} high/critical risk dependencies.")
    click.echo("")

    # Display results
    if _rich_available and _console is not None:
        from rich.table import Table
        table = Table(title="Dependency Risk Assessment", show_lines=True)
        table.add_column("Library", style="bold")
        table.add_column("Version")
        table.add_column("Ecosystem")
        table.add_column("CVEs", justify="right")
        table.add_column("Risk Level")
        table.add_column("Coupling")

        for assessment in assessments[:20]:
            dep = assessment.dependency
            risk_style = {"critical": "bold red", "high": "red", "medium": "yellow"}.get(
                assessment.risk_level, "green"
            )
            table.add_row(
                dep.name,
                dep.current_version,
                dep.ecosystem,
                str(len(assessment.vulnerabilities)),
                f"[{risk_style}]{assessment.risk_level}[/{risk_style}]",
                dep.coupling_strength,
            )
        _console.print(table)
    else:
        click.echo("  Dependency Risk Summary:")
        click.echo("  " + "-" * 60)
        for assessment in assessments[:20]:
            dep = assessment.dependency
            click.echo(
                f"    {dep.name:<30} {dep.current_version:<10} "
                f"CVEs={len(assessment.vulnerabilities)}  risk={assessment.risk_level}"
            )

    # Dimension scores
    click.echo("")
    for dim, score in scores.items():
        click.echo(f"  {score.label}: {score.value}/10 ({score.severity}) — {score.evidence}")

    # JSON output
    if json_output:
        result = {
            "dependencies": [
                {
                    "name": a.dependency.name,
                    "version": a.dependency.current_version,
                    "ecosystem": a.dependency.ecosystem,
                    "cve_count": len(a.vulnerabilities),
                    "risk_level": a.risk_level,
                    "max_exploitability_score": a.max_exploitability_score,
                    "coupling_strength": a.dependency.coupling_strength,
                }
                for a in assessments
            ],
            "scores": {dim: s.to_dict() for dim, s in scores.items()},
        }
        out = Path(json_output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
        _echo_success(f"  JSON written to: {json_output}")


# ---------------------------------------------------------------------------
# stratum version
# ---------------------------------------------------------------------------


@cli.command()
def version() -> None:
    """Print Stratum version information."""
    try:
        from importlib.metadata import version as pkg_version
        ver = pkg_version("stratum")
    except Exception:
        ver = "1.0.0"
    click.echo(f"stratum {ver}")


# ---------------------------------------------------------------------------
# Summary display
# ---------------------------------------------------------------------------


def _print_summary(report_data: dict) -> None:
    """Print a human-readable summary of the analysis results."""
    health = report_data.get("overall_health_score", "N/A")
    project = report_data.get("project_name", "Unknown")
    scenario = report_data.get("scenario", "N/A")
    top_risks = report_data.get("top_risks", [])
    hotspots = report_data.get("file_hotspots", [])

    if _rich_available and _console is not None:
        _print_rich_summary(project, scenario, health, top_risks, hotspots)
    else:
        _print_plain_summary(project, scenario, health, top_risks, hotspots)


def _print_rich_summary(
    project: str,
    scenario: str,
    health: Any,
    top_risks: list[dict],
    hotspots: list[dict],
) -> None:
    from rich.table import Table
    from rich.panel import Panel

    if isinstance(health, (int, float)):
        if health >= 7:
            health_style = "bold green"
        elif health >= 4:
            health_style = "bold yellow"
        else:
            health_style = "bold red"
        health_display = f"[{health_style}]{health}/10.0[/{health_style}]"
    else:
        health_display = str(health)

    _console.print(
        Panel(
            f"Project: [bold]{project}[/bold]\n"
            f"Scenario: {scenario}\n"
            f"Overall Health Score: {health_display}",
            title="Stratum Analysis Complete",
            border_style="blue",
        )
    )

    if top_risks:
        table = Table(title="Top Risk Dimensions", show_lines=True)
        table.add_column("Dimension", style="bold")
        table.add_column("Score", justify="right")
        table.add_column("Severity")
        table.add_column("Evidence")

        for risk in top_risks[:5]:
            score_val = risk.get("value", 0)
            severity = risk.get("severity", "")
            score_style = "red" if score_val >= 7 else ("yellow" if score_val >= 4 else "green")
            table.add_row(
                risk.get("dimension", risk.get("label", "")),
                f"[{score_style}]{score_val}[/{score_style}]",
                severity,
                risk.get("evidence", ""),
            )
        _console.print(table)

    critical_hotspots = [h for h in hotspots if h.get("score", 0) >= 7.0]
    if critical_hotspots:
        ht = Table(title="Critical File Hotspots", show_lines=True)
        ht.add_column("File", style="bold")
        ht.add_column("Score", justify="right")
        ht.add_column("Effort")
        for h in critical_hotspots[:10]:
            ht.add_row(
                h.get("file", ""),
                f"[red]{h.get('score', 0)}[/red]",
                h.get("effort", ""),
            )
        _console.print(ht)


def _print_plain_summary(
    project: str,
    scenario: str,
    health: Any,
    top_risks: list[dict],
    hotspots: list[dict],
) -> None:
    click.echo("=" * 60)
    click.echo("  STRATUM ANALYSIS COMPLETE")
    click.echo("=" * 60)
    click.echo(f"  Project:              {project}")
    click.echo(f"  Scenario:             {scenario}")
    click.echo(f"  Overall Health Score: {health}/10.0")
    click.echo("")

    if top_risks:
        click.echo("  Top Risk Dimensions:")
        click.echo("  " + "-" * 56)
        for risk in top_risks[:5]:
            dim = risk.get("dimension", risk.get("label", ""))
            val = risk.get("value", 0)
            sev = risk.get("severity", "")
            evidence = risk.get("evidence", "")
            click.echo(f"    {dim:<25} {val:>4}  ({sev})  {evidence}")
        click.echo("")

    critical_hotspots = [h for h in hotspots if h.get("score", 0) >= 7.0]
    if critical_hotspots:
        click.echo("  Critical File Hotspots:")
        click.echo("  " + "-" * 56)
        for h in critical_hotspots[:10]:
            click.echo(f"    {h.get('file', ''):<40} score={h.get('score', 0)}")
        click.echo("")

    click.echo("=" * 60)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    cli()
