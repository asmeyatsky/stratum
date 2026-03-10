"""
Stratum MCP Server

Architectural Intent:
    Exposes Stratum code intelligence capabilities as MCP tools, resources,
    and prompts for consumption by Claude Code, Claude Desktop, and other
    MCP-compatible clients.

    Follows skill2026 Rule 6: one MCP server per bounded context.
    The server is a thin transport layer — all analysis flows through the
    AnalyzeRepositoryCommand (application layer) and the DAG orchestrator.

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

_container: Container | None = None
_report_cache: dict[str, dict] = {}


def _get_container() -> Container:
    global _container
    if _container is None:
        _container = Container.create()
    return _container


# ---------------------------------------------------------------------------
# TOOLS
# ---------------------------------------------------------------------------


@server.list_tools()
async def list_tools() -> list[Tool]:
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
                            "ma_due_diligence", "vendor_audit", "post_merger",
                            "decommission", "cto_onboarding", "oss_assessment",
                        ],
                    },
                    "manifest_paths": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Paths to package manifest files for dependency risk analysis.",
                    },
                },
                "required": ["git_log_path", "project_name", "scenario"],
            },
        ),
        Tool(
            name="scan_dependencies",
            description=(
                "Quick dependency-only scan. Parses manifest files and assesses "
                "library risk, version currency, and known CVE exposure."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "manifest_paths": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Paths to package manifest files to scan.",
                    },
                },
                "required": ["manifest_paths"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    try:
        if name == "analyze_repository":
            return await _handle_analyze_repository(arguments)
        elif name == "scan_dependencies":
            return await _handle_scan_dependencies(arguments)
        else:
            return [TextContent(
                type="text",
                text=json.dumps({"error": f"Unknown tool: {name}"}, indent=2),
            )]
    except Exception as exc:
        logger.exception("Tool %s failed", name)
        return [TextContent(
            type="text",
            text=json.dumps({"error": str(exc), "tool": name}, indent=2),
        )]


async def _handle_analyze_repository(arguments: dict[str, Any]) -> list[TextContent]:
    """Delegate to AnalyzeRepositoryCommand via the application layer."""
    from application.commands.analyze_repository import AnalyzeRepositoryCommand
    from application.dtos.analysis_dto import AnalysisRequest

    git_log_path = arguments["git_log_path"]
    project_name = arguments["project_name"]
    scenario = arguments["scenario"]
    manifest_paths = arguments.get("manifest_paths", [])

    if not Path(git_log_path).exists():
        return [TextContent(
            type="text",
            text=json.dumps({"error": f"Git log file not found: {git_log_path}"}, indent=2),
        )]

    container = _get_container()

    command = AnalyzeRepositoryCommand(
        git_log_port=container.git_log_parser,
        vulnerability_db_port=container.nvd_adapter,
        ai_narrative_port=container.narrative_adapter,
        report_generator_port=container.report_adapter,
    )

    request = AnalysisRequest(
        git_log_source=git_log_path,
        project_name=project_name,
        scenario=scenario,
        output_path=f"/tmp/stratum_{project_name}.pdf",
        manifest_paths=manifest_paths,
    )

    result = await command.execute(request)

    # Cache for resource access
    result_dict = result.to_dict()
    _report_cache[project_name] = result_dict

    return [TextContent(
        type="text",
        text=json.dumps(result_dict, indent=2, default=str),
    )]


async def _handle_scan_dependencies(arguments: dict[str, Any]) -> list[TextContent]:
    """Quick dependency scan using real infrastructure adapters."""
    manifest_paths = arguments["manifest_paths"]

    missing = [p for p in manifest_paths if not Path(p).exists()]
    if missing:
        return [TextContent(
            type="text",
            text=json.dumps({"error": "Manifest files not found", "missing": missing}, indent=2),
        )]

    container = _get_container()

    all_deps = []
    for path in manifest_paths:
        all_deps.extend(container.manifest_parser.parse(path))

    if not all_deps:
        return [TextContent(
            type="text",
            text=json.dumps({"dependencies_found": 0, "message": "No dependencies found."}, indent=2),
        )]

    # CVE lookup concurrently
    vuln_map: dict[str, list] = {}
    tasks = [container.nvd_adapter.search(dep.name, dep.current_version) for dep in all_deps]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    for dep, result in zip(all_deps, results):
        vuln_map[dep.name] = [] if isinstance(result, BaseException) else result

    assessments = container.dependency_risk_service.assess_all(all_deps, vuln_map)
    scores = container.dependency_risk_service.compute_risk_scores(assessments, all_deps)

    scan_result = {
        "scan_timestamp": datetime.now(UTC).isoformat(),
        "manifests_scanned": manifest_paths,
        "dependencies_found": len(all_deps),
        "vulnerabilities_found": sum(len(a.vulnerabilities) for a in assessments),
        "dependencies": [
            {
                "name": a.dependency.name,
                "version": a.dependency.current_version,
                "ecosystem": a.dependency.ecosystem,
                "cve_count": len(a.vulnerabilities),
                "risk_level": a.risk_level,
                "coupling_strength": a.dependency.coupling_strength,
            }
            for a in assessments
        ],
        "scores": {dim: s.to_dict() for dim, s in scores.items()},
    }

    return [TextContent(
        type="text",
        text=json.dumps(scan_result, indent=2, default=str),
    )]


# ---------------------------------------------------------------------------
# RESOURCES
# ---------------------------------------------------------------------------


@server.list_resource_templates()
async def list_resource_templates() -> list[ResourceTemplate]:
    return [
        ResourceTemplate(
            uriTemplate="stratum://reports/{project_name}",
            name="Stratum Risk Report",
            description="Read-only access to a previously generated Stratum risk report.",
            mimeType="application/json",
        ),
    ]


@server.read_resource()
async def read_resource(uri: str) -> str:
    prefix = "stratum://reports/"
    if not uri.startswith(prefix):
        return json.dumps({"error": f"Unknown resource URI: {uri}"}, indent=2)

    project_name = uri[len(prefix):]
    if not project_name:
        return json.dumps({"error": "Missing project_name in URI"}, indent=2)

    report_data = _report_cache.get(project_name)
    if report_data is None:
        return json.dumps({
            "error": f"No report found for project: {project_name}",
            "available_reports": list(_report_cache.keys()),
            "hint": "Run the analyze_repository tool first.",
        }, indent=2)

    return json.dumps(report_data, indent=2, default=str)


# ---------------------------------------------------------------------------
# PROMPTS
# ---------------------------------------------------------------------------


@server.list_prompts()
async def list_prompts() -> list[Prompt]:
    return [
        Prompt(
            name="risk_summary",
            description="Generate a human-readable risk summary from a Stratum analysis.",
            arguments=[
                PromptArgument(name="project_name", description="Project name of a cached report.", required=False),
                PromptArgument(name="report_json", description="Raw Stratum report JSON.", required=False),
            ],
        ),
    ]


@server.get_prompt()
async def get_prompt(name: str, arguments: dict[str, str] | None = None) -> GetPromptResult:
    if name != "risk_summary":
        return GetPromptResult(
            description=f"Unknown prompt: {name}",
            messages=[PromptMessage(role="user", content=TextContent(type="text", text=f"Error: prompt '{name}' not available."))],
        )

    arguments = arguments or {}
    report_data = None

    project_name = arguments.get("project_name")
    report_json = arguments.get("report_json")

    if project_name:
        report_data = _report_cache.get(project_name)
        if report_data is None:
            return GetPromptResult(
                description="Report not found",
                messages=[PromptMessage(role="user", content=TextContent(type="text", text=f"No cached report for '{project_name}'. Run analyze_repository first."))],
            )
    elif report_json:
        try:
            report_data = json.loads(report_json)
        except json.JSONDecodeError as exc:
            return GetPromptResult(
                description="Invalid JSON",
                messages=[PromptMessage(role="user", content=TextContent(type="text", text=f"Failed to parse report_json: {exc}"))],
            )
    else:
        return GetPromptResult(
            description="Missing arguments",
            messages=[PromptMessage(role="user", content=TextContent(type="text", text="Provide either 'project_name' or 'report_json'."))],
        )

    report_text = json.dumps(report_data, indent=2, default=str)
    scenario = report_data.get("scenario", "general")
    project = report_data.get("project_name", "Unknown")
    health = report_data.get("overall_health_score", "N/A")

    user_message = (
        "You are a senior software engineering advisor. Analyze the following "
        "Stratum code intelligence report and produce a concise executive risk summary.\n\n"
        "Guidelines:\n"
        "- Lead with the overall health score and what it means\n"
        "- Highlight the top 3 risk dimensions with severity and evidence\n"
        "- Call out any systemic risks\n"
        "- Identify the most critical file hotspots\n"
        "- Provide 3-5 prioritized remediation recommendations\n"
        f"- Frame for a '{scenario}' scenario\n"
        "- Use clear, non-technical language for executive stakeholders\n"
        "- Keep under 500 words\n\n"
        f"Report for **{project}** (health: {health}/10.0):\n\n"
        f"```json\n{report_text}\n```"
    )

    return GetPromptResult(
        description=f"Risk summary prompt for {project}",
        messages=[PromptMessage(role="user", content=TextContent(type="text", text=user_message))],
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


async def main() -> None:
    from mcp.server.stdio import stdio_server
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
