"""
Stratum MCP Server

Exposes Stratum code intelligence capabilities as MCP tools, resources, and prompts
for consumption by Claude Code, Claude Desktop, and other MCP-compatible clients.

Follows skill2026 Rule 6: one MCP server per bounded context.
Stratum is a single bounded context — all analysis capabilities live here.

Transport: stdio (default for Claude Code / Claude Desktop integration).
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, UTC
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.types import (
    GetPromptResult,
    Prompt,
    PromptArgument,
    PromptMessage,
    Resource,
    ResourceTemplate,
    TextContent,
    Tool,
)

from infrastructure.config.dependency_injection import Container

logger = logging.getLogger("stratum.mcp")

# ---------------------------------------------------------------------------
# Server instance
# ---------------------------------------------------------------------------

server = Server("stratum")

# Module-level state: DI container and report cache
_container: Container | None = None
_report_cache: dict[str, dict] = {}


def _get_container() -> Container:
    """Lazy-initialise the DI container."""
    global _container
    if _container is None:
        _container = Container.create()
    return _container


# ---------------------------------------------------------------------------
# TOOLS
# ---------------------------------------------------------------------------


@server.list_tools()
async def list_tools() -> list[Tool]:
    """Advertise available Stratum tools to MCP clients."""
    return [
        Tool(
            name="analyze_repository",
            description=(
                "Run a full Stratum code intelligence analysis on a repository. "
                "Ingests git history, analyses code evolution (P1), commit quality (P2), "
                "dependency risk (P4), and produces an integrated risk model (P6) with "
                "15 quality dimensions scored on a 1-10 severity scale."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "git_log_path": {
                        "type": "string",
                        "description": (
                            "Absolute path to a git log file generated via: "
                            "git log --numstat --pretty=format:'%H|%ae|%an|%aI|%s' > git.log"
                        ),
                    },
                    "project_name": {
                        "type": "string",
                        "description": "Human-readable project name for the report.",
                    },
                    "scenario": {
                        "type": "string",
                        "description": "Analysis scenario determining report framing.",
                        "enum": [
                            "ma_due_diligence",
                            "vendor_audit",
                            "post_merger",
                            "decommission",
                            "cto_onboarding",
                            "oss_assessment",
                        ],
                    },
                    "manifest_paths": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "Paths to package manifest files "
                            "(package.json, requirements.txt, Cargo.toml, pom.xml) "
                            "for dependency risk analysis."
                        ),
                    },
                },
                "required": ["git_log_path", "project_name", "scenario"],
            },
        ),
        Tool(
            name="scan_dependencies",
            description=(
                "Quick dependency-only scan. Parses manifest files and assesses "
                "library risk, version currency, and known CVE exposure without "
                "requiring git history."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "manifest_paths": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "Paths to package manifest files to scan for dependency risk."
                        ),
                    },
                },
                "required": ["manifest_paths"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Dispatch tool calls to the appropriate handler."""
    try:
        if name == "analyze_repository":
            return await _handle_analyze_repository(arguments)
        elif name == "scan_dependencies":
            return await _handle_scan_dependencies(arguments)
        else:
            return [
                TextContent(
                    type="text",
                    text=json.dumps(
                        {"error": f"Unknown tool: {name}", "available_tools": ["analyze_repository", "scan_dependencies"]},
                        indent=2,
                    ),
                )
            ]
    except Exception as exc:
        logger.exception("Tool %s failed", name)
        return [
            TextContent(
                type="text",
                text=json.dumps(
                    {
                        "error": str(exc),
                        "tool": name,
                        "hint": "Check that all input paths exist and are readable.",
                    },
                    indent=2,
                ),
            )
        ]


async def _handle_analyze_repository(arguments: dict[str, Any]) -> list[TextContent]:
    """Execute full Stratum analysis pipeline."""
    git_log_path = arguments["git_log_path"]
    project_name = arguments["project_name"]
    scenario = arguments["scenario"]
    manifest_paths = arguments.get("manifest_paths", [])

    # Validate inputs
    log_path = Path(git_log_path)
    if not log_path.exists():
        return [
            TextContent(
                type="text",
                text=json.dumps(
                    {"error": f"Git log file not found: {git_log_path}"},
                    indent=2,
                ),
            )
        ]

    container = _get_container()

    # --- Phase 1: Parse git history ---
    if container.git_log_adapter is not None:
        commits = await container.git_log_adapter.parse(git_log_path)
    else:
        # Fallback: attempt inline parse for MVP
        commits = _parse_git_log_inline(log_path)

    if not commits:
        return [
            TextContent(
                type="text",
                text=json.dumps(
                    {"error": "No commits parsed from git log. Verify file format."},
                    indent=2,
                ),
            )
        ]

    # --- Phase 2: Run P1, P2, P4 analyses concurrently ---
    p1_task = asyncio.to_thread(
        _run_p1_analysis, container, commits
    )
    p2_task = asyncio.to_thread(
        _run_p2_analysis, container, commits
    )

    (p1_scores, knowledge_risks, churn_anomalies), (p2_scores, bug_magnets) = (
        await asyncio.gather(p1_task, p2_task)
    )

    # P4: dependency analysis (if manifests provided)
    p4_scores: dict[str, Any] = {}
    if manifest_paths:
        # Dependency scanning is a placeholder until adapters are wired
        p4_scores = {}

    # --- Phase 3: Aggregate into P6 risk model ---
    report = container.risk_aggregation_service.build_report(
        project_name=project_name,
        scenario=scenario,
        p1_scores=p1_scores,
        p2_scores=p2_scores,
        p4_scores=p4_scores,
        knowledge_risks=knowledge_risks,
        bug_magnets=bug_magnets,
        churn_anomalies=churn_anomalies,
        commits=commits,
    )

    # --- Phase 4: AI narrative (if adapter available) ---
    if container.ai_narrative_adapter is not None:
        try:
            narrative = await container.ai_narrative_adapter.generate_narrative(
                report.to_dict(), scenario
            )
            report = report.with_ai_narrative(narrative)
        except Exception as exc:
            logger.warning("AI narrative generation failed: %s", exc)

    # Cache report for resource access
    report_dict = report.to_dict()
    _report_cache[project_name] = report_dict

    return [
        TextContent(
            type="text",
            text=json.dumps(report_dict, indent=2, default=str),
        )
    ]


async def _handle_scan_dependencies(arguments: dict[str, Any]) -> list[TextContent]:
    """Quick dependency-only scan without git history."""
    manifest_paths = arguments["manifest_paths"]

    # Validate paths
    missing = [p for p in manifest_paths if not Path(p).exists()]
    if missing:
        return [
            TextContent(
                type="text",
                text=json.dumps(
                    {"error": "Manifest files not found", "missing": missing},
                    indent=2,
                ),
            )
        ]

    container = _get_container()

    # Placeholder: in production, adapters parse manifests and query vulnerability DBs.
    # For now, return a structured skeleton showing what the scan would produce.
    result = {
        "scan_timestamp": datetime.now(UTC).isoformat(),
        "manifests_scanned": manifest_paths,
        "dependencies_found": 0,
        "vulnerabilities_found": 0,
        "risk_summary": {
            "critical": 0,
            "high": 0,
            "medium": 0,
            "low": 0,
        },
        "note": (
            "Full dependency scanning requires configured adapters. "
            "Wire VulnerabilityDbPort and manifest parser adapters in the DI container."
        ),
    }

    return [
        TextContent(
            type="text",
            text=json.dumps(result, indent=2),
        )
    ]


# ---------------------------------------------------------------------------
# RESOURCES
# ---------------------------------------------------------------------------


@server.list_resource_templates()
async def list_resource_templates() -> list[ResourceTemplate]:
    """Advertise available Stratum resource templates."""
    return [
        ResourceTemplate(
            uriTemplate="stratum://reports/{project_name}",
            name="Stratum Risk Report",
            description=(
                "Read-only access to a previously generated Stratum risk report. "
                "The project_name must match a report generated via analyze_repository."
            ),
            mimeType="application/json",
        ),
    ]


@server.read_resource()
async def read_resource(uri: str) -> str:
    """Serve cached report data by project name."""
    # Parse URI: stratum://reports/{project_name}
    prefix = "stratum://reports/"
    if not uri.startswith(prefix):
        return json.dumps(
            {
                "error": f"Unknown resource URI scheme: {uri}",
                "expected_format": "stratum://reports/{{project_name}}",
            },
            indent=2,
        )

    project_name = uri[len(prefix):]
    if not project_name:
        return json.dumps(
            {"error": "Missing project_name in URI"},
            indent=2,
        )

    report_data = _report_cache.get(project_name)
    if report_data is None:
        available = list(_report_cache.keys()) if _report_cache else []
        return json.dumps(
            {
                "error": f"No report found for project: {project_name}",
                "available_reports": available,
                "hint": "Run the analyze_repository tool first to generate a report.",
            },
            indent=2,
        )

    return json.dumps(report_data, indent=2, default=str)


# ---------------------------------------------------------------------------
# PROMPTS
# ---------------------------------------------------------------------------


@server.list_prompts()
async def list_prompts() -> list[Prompt]:
    """Advertise available Stratum prompts."""
    return [
        Prompt(
            name="risk_summary",
            description=(
                "Generate a quick human-readable risk summary from a Stratum analysis. "
                "Provide a project_name for a cached report, or pass raw report JSON."
            ),
            arguments=[
                PromptArgument(
                    name="project_name",
                    description="Project name of a previously generated report.",
                    required=False,
                ),
                PromptArgument(
                    name="report_json",
                    description="Raw Stratum report JSON (alternative to project_name).",
                    required=False,
                ),
            ],
        ),
    ]


@server.get_prompt()
async def get_prompt(name: str, arguments: dict[str, str] | None = None) -> GetPromptResult:
    """Build prompt messages for the requested prompt."""
    if name != "risk_summary":
        return GetPromptResult(
            description=f"Unknown prompt: {name}",
            messages=[
                PromptMessage(
                    role="user",
                    content=TextContent(
                        type="text",
                        text=f"Error: prompt '{name}' is not available. Use 'risk_summary'.",
                    ),
                ),
            ],
        )

    arguments = arguments or {}
    report_data = None

    # Resolve report data from project_name or raw JSON
    project_name = arguments.get("project_name")
    report_json = arguments.get("report_json")

    if project_name:
        report_data = _report_cache.get(project_name)
        if report_data is None:
            return GetPromptResult(
                description="Report not found",
                messages=[
                    PromptMessage(
                        role="user",
                        content=TextContent(
                            type="text",
                            text=(
                                f"No cached report found for '{project_name}'. "
                                "Run analyze_repository first, or provide report_json directly."
                            ),
                        ),
                    ),
                ],
            )
    elif report_json:
        try:
            report_data = json.loads(report_json)
        except json.JSONDecodeError as exc:
            return GetPromptResult(
                description="Invalid JSON",
                messages=[
                    PromptMessage(
                        role="user",
                        content=TextContent(
                            type="text",
                            text=f"Failed to parse report_json: {exc}",
                        ),
                    ),
                ],
            )
    else:
        return GetPromptResult(
            description="Missing arguments",
            messages=[
                PromptMessage(
                    role="user",
                    content=TextContent(
                        type="text",
                        text="Provide either 'project_name' or 'report_json' argument.",
                    ),
                ),
            ],
        )

    # Build the risk summary prompt
    report_text = json.dumps(report_data, indent=2, default=str)
    scenario = report_data.get("scenario", "general")
    project = report_data.get("project_name", "Unknown Project")
    health = report_data.get("overall_health_score", "N/A")

    system_instruction = (
        "You are a senior software engineering advisor. Analyze the following "
        "Stratum code intelligence report and produce a concise executive risk summary.\n\n"
        "Guidelines:\n"
        "- Lead with the overall health score and what it means\n"
        "- Highlight the top 3 risk dimensions with their severity and evidence\n"
        "- Call out any systemic risks (components scoring >7 across 3+ dimensions)\n"
        "- Identify the most critical file hotspots needing immediate attention\n"
        "- Provide 3-5 prioritized remediation recommendations\n"
        f"- Frame the analysis for a '{scenario}' scenario\n"
        "- Use clear, non-technical language suitable for executive stakeholders\n"
        "- Keep the summary under 500 words\n"
    )

    user_message = (
        f"Here is the Stratum risk report for **{project}** "
        f"(health score: {health}/10.0):\n\n"
        f"```json\n{report_text}\n```\n\n"
        "Please generate a concise executive risk summary."
    )

    return GetPromptResult(
        description=f"Risk summary prompt for {project}",
        messages=[
            PromptMessage(
                role="user",
                content=TextContent(
                    type="text",
                    text=f"{system_instruction}\n\n{user_message}",
                ),
            ),
        ],
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _run_p1_analysis(
    container: Container, commits: list,
) -> tuple[dict, list, list]:
    """Run P1 evolution analysis (synchronous, called via asyncio.to_thread)."""
    svc = container.evolution_service

    knowledge_risks = svc.analyze_knowledge_distribution(commits)
    couplings = svc.detect_temporal_coupling(commits)
    churn_anomalies = svc.detect_churn_anomalies(commits)

    # Determine total components for scoring
    components = set()
    for commit in commits:
        for fc in commit.file_changes:
            components.add(fc.module)
    total_components = len(components)

    p1_scores = svc.compute_risk_scores(
        knowledge_risks, couplings, churn_anomalies, total_components
    )

    return p1_scores, knowledge_risks, churn_anomalies


def _run_p2_analysis(
    container: Container, commits: list,
) -> tuple[dict, list]:
    """Run P2 commit quality analysis (synchronous, called via asyncio.to_thread)."""
    svc = container.commit_quality_service

    quality_report = svc.assess_commit_quality(commits)
    bug_magnets = svc.detect_bug_magnets(commits)
    trends = svc.compute_feature_bug_trends(commits)
    p2_scores = svc.compute_risk_scores(quality_report, bug_magnets, trends)

    return p2_scores, bug_magnets


def _parse_git_log_inline(log_path: Path) -> list:
    """
    Minimal inline git log parser for MVP.

    Expects format produced by:
        git log --numstat --pretty=format:'%H|%ae|%an|%aI|%s'

    In production, use the GitLogPort adapter instead.
    """
    from domain.entities.commit import Commit
    from domain.entities.file_change import FileChange

    commits: list[Commit] = []
    current_hash = None
    current_email = ""
    current_name = ""
    current_timestamp = None
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
# Server entry point
# ---------------------------------------------------------------------------


async def main() -> None:
    """Run the Stratum MCP server over stdio transport."""
    from mcp.server.stdio import stdio_server

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())
