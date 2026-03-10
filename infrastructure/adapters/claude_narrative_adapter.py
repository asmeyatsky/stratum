"""
ClaudeNarrativeAdapter — Infrastructure adapter implementing AINarrativePort.

Architectural Intent:
    Calls the Anthropic Claude API to generate executive narratives from the
    P6 risk model JSON. The adapter owns prompt engineering and API transport —
    no business logic resides here.

    Scenario-specific system prompts ensure the narrative is tailored to
    the audience and decision context (M&A due diligence, vendor audit,
    CTO onboarding, etc.).

Design Decisions:
    - Uses the official ``anthropic`` Python SDK with async client.
    - Model: claude-sonnet-4-6 for optimal cost/quality balance on structured
      analytical tasks.
    - System prompts encode scenario framing; user prompt contains the raw
      risk model JSON. This separation keeps domain data clean.
    - Max output tokens capped at 4096 — narratives should be concise
      executive summaries, not full reports.
    - Graceful degradation: API failures return a structured fallback
      message rather than raising, so report generation can proceed.
"""

from __future__ import annotations

import json
import logging
import os

import anthropic

logger = logging.getLogger(__name__)

_MODEL = "claude-sonnet-4-6"
_MAX_TOKENS = 4096

# ------------------------------------------------------------------
# Scenario-specific system prompts
# ------------------------------------------------------------------

_SCENARIO_PROMPTS: dict[str, str] = {
    "M&A": (
        "You are Stratum, an AI code intelligence analyst providing executive "
        "narratives for M&A (Mergers & Acquisitions) due diligence.\n\n"
        "Your audience is non-technical decision-makers — C-suite executives, "
        "board members, and investment committee members evaluating an acquisition "
        "target.\n\n"
        "Focus your narrative on:\n"
        "1. **Acquisition risk** — hidden technical debt that could inflate "
        "post-acquisition integration costs.\n"
        "2. **Team dependency** — knowledge concentration risks that could "
        "cause value erosion if key engineers depart post-acquisition.\n"
        "3. **Security exposure** — CVEs and dependency risks that could "
        "create liability or require immediate remediation spend.\n"
        "4. **Technology currency** — whether the tech stack is modern and "
        "maintainable, or approaching end-of-life.\n"
        "5. **Hidden costs** — areas where the codebase will require "
        "significant investment before it can scale or integrate.\n\n"
        "Quantify findings with specific numbers from the risk model. Use "
        "business language, not developer jargon. Structure the narrative "
        "with clear sections and an executive summary at the top."
    ),

    "vendor_audit": (
        "You are Stratum, an AI code intelligence analyst providing executive "
        "narratives for vendor/supplier software audits.\n\n"
        "Your audience is procurement officers, vendor managers, and CTOs "
        "evaluating whether a vendor's software meets quality and security "
        "standards for continued engagement.\n\n"
        "Focus your narrative on:\n"
        "1. **Delivery quality** — commit quality patterns, bug concentration, "
        "and process discipline indicators.\n"
        "2. **Process maturity** — traceability (Jira references), commit "
        "hygiene, and code review indicators.\n"
        "3. **Security posture** — known vulnerabilities, dependency health, "
        "and exposure to supply chain risks.\n"
        "4. **Maintainability** — code stability, refactoring debt, and "
        "architectural coupling patterns.\n"
        "5. **Contract leverage points** — specific, evidence-backed findings "
        "that support renegotiation or remediation requirements.\n\n"
        "Be precise with metrics. Frame findings as risks to the business "
        "relationship. Structure the narrative with an executive summary, "
        "key findings, and recommended actions."
    ),

    "post_merger": (
        "You are Stratum, an AI code intelligence analyst providing executive "
        "narratives for post-merger technology integration planning.\n\n"
        "Your audience is integration PMO leads, engineering directors, and "
        "CTOs planning the technical integration of acquired codebases.\n\n"
        "Focus your narrative on:\n"
        "1. **Integration complexity** — architectural coupling, cross-module "
        "dependencies, and files requiring coordinated changes.\n"
        "2. **Team retention priorities** — which engineers hold critical "
        "knowledge that must be retained or transferred.\n"
        "3. **Quick wins** — areas where consolidation can reduce cost or "
        "complexity with minimal risk.\n"
        "4. **Debt remediation roadmap** — prioritised technical debt items "
        "that should be addressed during integration.\n"
        "5. **Timeline risks** — factors that could extend the integration "
        "timeline beyond initial estimates."
    ),

    "decommission": (
        "You are Stratum, an AI code intelligence analyst providing executive "
        "narratives for system decommission risk assessment.\n\n"
        "Your audience is engineering leadership and project managers planning "
        "a controlled retirement of a codebase or system.\n\n"
        "Focus your narrative on:\n"
        "1. **Dependency impact** — downstream systems and consumers that "
        "depend on this codebase.\n"
        "2. **Knowledge preservation** — critical domain logic that must be "
        "documented or migrated before decommission.\n"
        "3. **Data migration risks** — complexity of extracting and "
        "transferring data and state.\n"
        "4. **Timeline and sequencing** — recommended decommission order "
        "based on coupling analysis.\n"
        "5. **Residual risk** — what happens if decommission is delayed "
        "or abandoned."
    ),

    "cto_onboarding": (
        "You are Stratum, an AI code intelligence analyst providing a "
        "comprehensive technical landscape briefing for a new CTO.\n\n"
        "Your audience is a newly appointed CTO who needs to rapidly "
        "understand the health, risks, and opportunities in the codebase.\n\n"
        "Focus your narrative on:\n"
        "1. **Overall health** — a frank assessment of codebase quality "
        "across all dimensions.\n"
        "2. **Top risks** — the 3-5 most critical issues requiring "
        "immediate attention.\n"
        "3. **Team dynamics** — knowledge distribution, bus factor risks, "
        "and team health indicators.\n"
        "4. **Strategic debt** — technical debt that constrains business "
        "agility or feature velocity.\n"
        "5. **Quick wins** — high-impact, low-effort improvements that "
        "can build early credibility."
    ),

    "oss_assessment": (
        "You are Stratum, an AI code intelligence analyst providing executive "
        "narratives for open-source software adoption assessment.\n\n"
        "Your audience is engineering leads and architects evaluating whether "
        "an open-source project is suitable for production adoption.\n\n"
        "Focus your narrative on:\n"
        "1. **Community health** — contributor diversity, bus factor, and "
        "development velocity.\n"
        "2. **Code quality** — stability, testing indicators, and "
        "architectural cleanliness.\n"
        "3. **Security track record** — vulnerability history, response "
        "time to CVEs, and dependency hygiene.\n"
        "4. **Maintenance trajectory** — is the project actively maintained, "
        "slowing down, or at risk of abandonment?\n"
        "5. **Adoption risk** — licensing, coupling cost if the project "
        "is later abandoned, and migration difficulty."
    ),
}

_DEFAULT_SYSTEM_PROMPT = (
    "You are Stratum, an AI code intelligence analyst providing executive "
    "risk narratives for software codebases.\n\n"
    "Analyse the provided P6 risk model JSON and produce a clear, actionable "
    "executive narrative. Structure it with an executive summary, key findings "
    "organised by risk dimension, and prioritised recommendations.\n\n"
    "Use business language accessible to non-technical stakeholders. Quantify "
    "every finding with specific numbers from the data. Be direct about risks "
    "— do not soften critical findings."
)

_USER_PROMPT_TEMPLATE = (
    "Below is the P6 Integrated Risk Model for this codebase analysis. "
    "Generate an executive narrative based on these findings.\n\n"
    "```json\n{risk_model_json}\n```"
)


class ClaudeNarrativeAdapter:
    """Generates AI-powered executive narratives via the Anthropic Claude API.

    Implements :class:`domain.ports.AINarrativePort`.

    Args:
        api_key: Anthropic API key. If ``None``, reads from the
            ``ANTHROPIC_API_KEY`` environment variable.
        model: Model identifier to use. Defaults to ``claude-sonnet-4-6``.
        max_tokens: Maximum output tokens for the narrative.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str = _MODEL,
        max_tokens: int = _MAX_TOKENS,
    ) -> None:
        resolved_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not resolved_key:
            raise ValueError(
                "Anthropic API key is required. Pass api_key or set "
                "the ANTHROPIC_API_KEY environment variable."
            )

        self._client = anthropic.AsyncAnthropic(api_key=resolved_key)
        self._model = model
        self._max_tokens = max_tokens

    async def generate_narrative(
        self, risk_model: dict, scenario: str
    ) -> str:
        """Generate an executive narrative from the P6 risk model.

        Args:
            risk_model: P6 risk model dictionary (from ``RiskReport.to_dict()``).
            scenario: Analysis scenario key (e.g., ``"M&A"``, ``"vendor_audit"``).

        Returns:
            Executive narrative as a formatted string.
        """
        system_prompt = _SCENARIO_PROMPTS.get(scenario, _DEFAULT_SYSTEM_PROMPT)
        risk_model_json = json.dumps(risk_model, indent=2, default=str)
        user_message = _USER_PROMPT_TEMPLATE.format(risk_model_json=risk_model_json)

        try:
            response = await self._client.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": user_message},
                ],
            )

            # Extract text from the response content blocks
            narrative_parts: list[str] = []
            for block in response.content:
                if block.type == "text":
                    narrative_parts.append(block.text)

            narrative = "\n".join(narrative_parts)
            logger.info(
                "Generated %d-character narrative for scenario '%s' "
                "(tokens: input=%d, output=%d)",
                len(narrative),
                scenario,
                response.usage.input_tokens,
                response.usage.output_tokens,
            )
            return narrative

        except anthropic.AuthenticationError:
            logger.error("Anthropic API authentication failed — check API key")
            return self._fallback_narrative(risk_model, scenario, "authentication failure")

        except anthropic.RateLimitError:
            logger.error("Anthropic API rate limit exceeded")
            return self._fallback_narrative(risk_model, scenario, "rate limit exceeded")

        except anthropic.APIError as exc:
            logger.error("Anthropic API error: %s", exc)
            return self._fallback_narrative(risk_model, scenario, str(exc))

        except Exception as exc:
            logger.error("Unexpected error generating narrative: %s", exc, exc_info=True)
            return self._fallback_narrative(risk_model, scenario, str(exc))

    @staticmethod
    def _fallback_narrative(risk_model: dict, scenario: str, error: str) -> str:
        """Generate a structured fallback narrative when the API is unavailable.

        This ensures report generation can proceed even without AI enrichment.
        """
        health = risk_model.get("overall_health_score", "N/A")
        project = risk_model.get("project_name", "Unknown Project")
        top_risks = risk_model.get("top_risks", [])

        lines = [
            f"# Risk Assessment — {project}",
            f"**Scenario:** {scenario}",
            f"**Overall Health Score:** {health}/10",
            "",
            "## AI Narrative Unavailable",
            f"The AI narrative could not be generated due to: {error}.",
            "The quantitative findings below are drawn directly from the "
            "P6 risk model.",
            "",
            "## Top Risk Dimensions",
        ]

        for risk in top_risks[:5]:
            dim = risk.get("dimension", risk.get("label", "Unknown"))
            value = risk.get("value", "N/A")
            severity = risk.get("severity", "unknown")
            evidence = risk.get("evidence", "")
            lines.append(f"- **{dim}** — {value}/10 ({severity}): {evidence}")

        lines.append("")
        lines.append(
            "*This is an automated fallback summary. Re-run the analysis "
            "with a valid API connection for the full AI-generated narrative.*"
        )

        return "\n".join(lines)
