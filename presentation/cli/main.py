"""
Stratum CLI

Click-based command-line interface for the Stratum code intelligence platform.
Entry point registered in pyproject.toml as: stratum = "presentation.cli.main:cli"
"""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime, UTC
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
    """Print with rich styling if available, otherwise plain click.echo."""
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
    """Async analysis workflow orchestration."""
    from infrastructure.config.dependency_injection import Container

    _echo_info(f"Stratum analysis starting for project: {project}")
    _echo_info(f"Scenario: {scenario}")
    _echo_info(f"Git log: {git_log}")
    if manifests:
        _echo_info(f"Manifests: {', '.join(manifests)}")
    click.echo("")

    container = Container.create()

    # --- Phase 1: Parse git history ---
    click.echo("  [1/4] Parsing git history...")
    if container.git_log_parser is not None:
        commits = await container.git_log_parser.parse(git_log)
    else:
        commits = _parse_git_log(Path(git_log))

    if not commits:
        _echo_error(
            "No commits found in git log. "
            "Verify the file was generated with: "
            "git log --numstat --pretty=format:'%H|%ae|%an|%aI|%s'"
        )
        sys.exit(1)

    _echo_success(f"  Parsed {len(commits):,} commits.")

    # --- Phase 2: Run P1, P2, P4 concurrently ---
    click.echo("  [2/4] Running analysis engines...")

    p1_task = asyncio.to_thread(_run_p1, container, commits)
    p2_task = asyncio.to_thread(_run_p2, container, commits)

    (p1_scores, knowledge_risks, churn_anomalies), (p2_scores, bug_magnets) = (
        await asyncio.gather(p1_task, p2_task)
    )

    _echo_success(
        f"  P1: {len(knowledge_risks)} knowledge risks, "
        f"{len(churn_anomalies)} churn anomalies."
    )
    _echo_success(f"  P2: {len(bug_magnets)} bug magnets detected.")

    # P4: dependency analysis
    p4_scores: dict[str, Any] = {}
    if manifests:
        click.echo("  Running dependency risk analysis...")
        # Placeholder until manifest parser adapters are wired
        _echo_warning("  P4: Manifest parsing adapters not yet configured. Skipping dependency scan.")

    # --- Phase 3: Aggregate P6 risk model ---
    click.echo("  [3/4] Building integrated risk model...")

    report = container.risk_aggregation_service.build_report(
        project_name=project,
        scenario=scenario,
        p1_scores=p1_scores,
        p2_scores=p2_scores,
        p4_scores=p4_scores,
        knowledge_risks=knowledge_risks,
        bug_magnets=bug_magnets,
        churn_anomalies=churn_anomalies,
        commits=commits,
    )

    # --- Phase 4: AI narrative + PDF generation ---
    click.echo("  [4/4] Generating report...")

    if container.claude_adapter is not None:
        try:
            narrative = await container.claude_adapter.generate_narrative(
                report.to_dict(), scenario
            )
            report = report.with_ai_narrative(narrative)
            _echo_success("  AI narrative generated.")
        except Exception as exc:
            _echo_warning(f"  AI narrative generation skipped: {exc}")
    else:
        _echo_warning("  AI narrative adapter not configured. Skipping narrative generation.")

    # Generate PDF
    if container.report_adapter is not None:
        try:
            pdf_path = await container.report_adapter.generate_pdf(
                report.to_dict(), output
            )
            _echo_success(f"  PDF report written to: {pdf_path}")
        except Exception as exc:
            _echo_warning(f"  PDF generation skipped: {exc}")
    else:
        _echo_warning(f"  PDF generator not configured. Skipping PDF output ({output}).")

    # --- Write JSON output if requested ---
    report_dict = report.to_dict()

    if json_output:
        json_path = Path(json_output)
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(
            json.dumps(report_dict, indent=2, default=str),
            encoding="utf-8",
        )
        _echo_success(f"  JSON output written to: {json_output}")

    # --- Print summary ---
    click.echo("")
    _print_summary(report_dict)


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
    """Print summary using rich tables and panels."""
    from rich.table import Table
    from rich.panel import Panel

    # Health score with colour coding
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

    # Top risks table
    if top_risks:
        table = Table(title="Top Risk Dimensions", show_lines=True)
        table.add_column("Dimension", style="bold")
        table.add_column("Score", justify="right")
        table.add_column("Severity")
        table.add_column("Evidence")

        for risk in top_risks[:5]:
            score_val = risk.get("value", 0)
            severity = risk.get("severity", "")
            if score_val >= 7:
                score_style = "red"
            elif score_val >= 4:
                score_style = "yellow"
            else:
                score_style = "green"

            table.add_row(
                risk.get("dimension", risk.get("label", "")),
                f"[{score_style}]{score_val}[/{score_style}]",
                severity,
                risk.get("evidence", ""),
            )
        _console.print(table)

    # Hotspots table
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
    """Print summary using plain click.echo output."""
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
def scan_deps(manifests: tuple[str, ...]) -> None:
    """Quick dependency-only scan.

    Parses manifest files and reports on library risk, version currency,
    and known CVE exposure. Does not require git history.
    """
    try:
        asyncio.run(_run_scan_deps(manifests))
    except KeyboardInterrupt:
        _echo_warning("\nScan interrupted by user.")
        sys.exit(130)
    except Exception as exc:
        _echo_error(f"Dependency scan failed: {exc}")
        sys.exit(1)


async def _run_scan_deps(manifests: tuple[str, ...]) -> None:
    """Async dependency scan workflow."""
    from infrastructure.config.dependency_injection import Container

    _echo_info(f"Scanning {len(manifests)} manifest file(s)...")
    for m in manifests:
        click.echo(f"  - {m}")
    click.echo("")

    container = Container.create()

    # Placeholder: until manifest parsers and vulnerability DB adapters are wired
    _echo_warning(
        "Full dependency scanning requires configured adapters.\n"
        "Wire VulnerabilityDbPort and manifest parser adapters in the DI container."
    )

    result = {
        "scan_timestamp": datetime.now(UTC).isoformat(),
        "manifests_scanned": list(manifests),
        "dependencies_found": 0,
        "vulnerabilities_found": 0,
        "risk_summary": {
            "critical": 0,
            "high": 0,
            "medium": 0,
            "low": 0,
        },
    }

    click.echo(json.dumps(result, indent=2))


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
# Git log parser (shared with MCP server via identical logic)
# ---------------------------------------------------------------------------


def _parse_git_log(log_path: Path) -> list:
    """
    Parse a git log file into Commit domain entities.

    Expected format (generated by):
        git log --numstat --pretty=format:'%H|%ae|%an|%aI|%s'
    """
    from domain.entities.commit import Commit
    from domain.entities.file_change import FileChange

    commits: list[Commit] = []
    current_hash: str | None = None
    current_email = ""
    current_name = ""
    current_timestamp: datetime | None = None
    current_message = ""
    current_changes: list[FileChange] = []

    text = log_path.read_text(encoding="utf-8", errors="replace")
    lines = text.strip().split("\n")

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Try to parse as a commit header line
        if "|" in line and line.count("|") >= 4:
            parts = line.split("|", maxsplit=4)
            if len(parts) == 5 and len(parts[0]) >= 7:
                # Flush previous commit
                if current_hash is not None:
                    commits.append(
                        Commit(
                            hash=current_hash,
                            author_email=current_email,
                            author_name=current_name,
                            timestamp=current_timestamp,
                            message=current_message,
                            file_changes=tuple(current_changes),
                        )
                    )
                current_hash = parts[0]
                current_email = parts[1]
                current_name = parts[2]
                try:
                    current_timestamp = datetime.fromisoformat(parts[3])
                except ValueError:
                    current_timestamp = datetime.now(UTC)
                current_message = parts[4]
                current_changes = []
                continue

        # Try to parse as numstat line (added\tdeleted\tfilepath)
        if "\t" in line:
            numstat_parts = line.split("\t")
            if len(numstat_parts) >= 3:
                try:
                    added = int(numstat_parts[0]) if numstat_parts[0] != "-" else 0
                    deleted = int(numstat_parts[1]) if numstat_parts[1] != "-" else 0
                    filepath = numstat_parts[2]
                    current_changes.append(
                        FileChange(
                            file_path=filepath,
                            lines_added=added,
                            lines_deleted=deleted,
                        )
                    )
                except (ValueError, IndexError):
                    pass

    # Flush last commit
    if current_hash is not None:
        commits.append(
            Commit(
                hash=current_hash,
                author_email=current_email,
                author_name=current_name,
                timestamp=current_timestamp,
                message=current_message,
                file_changes=tuple(current_changes),
            )
        )

    return commits


# ---------------------------------------------------------------------------
# P1 / P2 analysis helpers (synchronous, run via asyncio.to_thread)
# ---------------------------------------------------------------------------


def _run_p1(container: Any, commits: list) -> tuple[dict, list, list]:
    """Run P1 evolution analysis."""
    svc = container.evolution_service

    knowledge_risks = svc.analyze_knowledge_distribution(commits)
    couplings = svc.detect_temporal_coupling(commits)
    churn_anomalies = svc.detect_churn_anomalies(commits)

    components = set()
    for commit in commits:
        for fc in commit.file_changes:
            components.add(fc.module)

    p1_scores = svc.compute_risk_scores(
        knowledge_risks, couplings, churn_anomalies, len(components)
    )
    return p1_scores, knowledge_risks, churn_anomalies


def _run_p2(container: Any, commits: list) -> tuple[dict, list]:
    """Run P2 commit quality analysis."""
    svc = container.commit_quality_service

    quality_report = svc.assess_commit_quality(commits)
    bug_magnets = svc.detect_bug_magnets(commits)
    trends = svc.compute_feature_bug_trends(commits)
    p2_scores = svc.compute_risk_scores(quality_report, bug_magnets, trends)

    return p2_scores, bug_magnets


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    cli()
