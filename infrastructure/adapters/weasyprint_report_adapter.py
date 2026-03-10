"""
WeasyprintReportAdapter — Infrastructure adapter implementing ReportGeneratorPort.

Architectural Intent:
    Renders the P6 risk report as a professional PDF using Jinja2 HTML
    templates and WeasyPrint. This adapter owns presentation formatting —
    no business logic resides here.

Design Decisions:
    - Jinja2 template is embedded in this module to keep the adapter
      self-contained and deployable without external template files.
    - CSS is inline for WeasyPrint compatibility and single-file portability.
    - Stratum branding: clean, professional design with a dark header,
      colour-coded severity badges, and structured data tables.
    - The generate_pdf method is async for port compliance but delegates
      to WeasyPrint's synchronous rendering via asyncio.to_thread.
    - Report sections: executive summary, dimension scores table, top risks,
      component risk matrix, file hotspots, and AI narrative.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import jinja2

try:
    import weasyprint
except OSError:
    weasyprint = None  # type: ignore[assignment]  # pango not available

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Jinja2 HTML report template
# ------------------------------------------------------------------

_REPORT_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Stratum Risk Report — {{ project_name }}</title>
<style>
  @page {
    size: A4;
    margin: 20mm 15mm 20mm 15mm;

    @bottom-center {
      content: "Stratum Code Intelligence — Page " counter(page) " of " counter(pages);
      font-size: 8pt;
      color: #6b7280;
    }
  }

  * {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
  }

  body {
    font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
    font-size: 10pt;
    line-height: 1.5;
    color: #1f2937;
    background: #ffffff;
  }

  /* Header */
  .report-header {
    background: linear-gradient(135deg, #1e293b, #334155);
    color: #ffffff;
    padding: 30px 35px;
    margin: -20mm -15mm 20px -15mm;
    page-break-after: avoid;
  }

  .report-header h1 {
    font-size: 22pt;
    font-weight: 700;
    margin-bottom: 4px;
    letter-spacing: -0.5px;
  }

  .report-header .subtitle {
    font-size: 11pt;
    color: #94a3b8;
    font-weight: 400;
  }

  .report-header .meta {
    margin-top: 12px;
    font-size: 9pt;
    color: #cbd5e1;
    display: flex;
    gap: 24px;
  }

  .report-header .meta span {
    display: inline-block;
  }

  /* Health score badge */
  .health-badge {
    display: inline-block;
    font-size: 28pt;
    font-weight: 700;
    padding: 8px 20px;
    border-radius: 8px;
    margin-top: 10px;
  }

  .health-good { background: #065f46; color: #d1fae5; }
  .health-moderate { background: #92400e; color: #fef3c7; }
  .health-poor { background: #991b1b; color: #fee2e2; }

  /* Sections */
  h2 {
    font-size: 14pt;
    font-weight: 700;
    color: #1e293b;
    border-bottom: 2px solid #e2e8f0;
    padding-bottom: 6px;
    margin: 24px 0 12px 0;
    page-break-after: avoid;
  }

  h3 {
    font-size: 11pt;
    font-weight: 600;
    color: #334155;
    margin: 16px 0 8px 0;
  }

  p {
    margin-bottom: 8px;
  }

  /* Tables */
  table {
    width: 100%;
    border-collapse: collapse;
    margin: 10px 0 16px 0;
    font-size: 9pt;
  }

  th {
    background: #f1f5f9;
    color: #475569;
    font-weight: 600;
    text-align: left;
    padding: 8px 10px;
    border-bottom: 2px solid #cbd5e1;
  }

  td {
    padding: 7px 10px;
    border-bottom: 1px solid #e2e8f0;
    vertical-align: top;
  }

  tr:nth-child(even) {
    background: #f8fafc;
  }

  /* Severity badges */
  .severity {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 8pt;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  .severity-critical { background: #fecaca; color: #991b1b; }
  .severity-high { background: #fed7aa; color: #9a3412; }
  .severity-medium { background: #fef08a; color: #854d0e; }
  .severity-low { background: #bbf7d0; color: #166534; }
  .severity-minimal { background: #e0e7ff; color: #3730a3; }

  /* Score bar */
  .score-bar-container {
    width: 100px;
    height: 10px;
    background: #e2e8f0;
    border-radius: 5px;
    display: inline-block;
    vertical-align: middle;
    margin-right: 6px;
  }

  .score-bar {
    height: 100%;
    border-radius: 5px;
    display: inline-block;
  }

  .bar-critical { background: #ef4444; }
  .bar-high { background: #f97316; }
  .bar-medium { background: #eab308; }
  .bar-low { background: #22c55e; }
  .bar-minimal { background: #6366f1; }

  /* AI Narrative section */
  .narrative {
    background: #f8fafc;
    border-left: 4px solid #3b82f6;
    padding: 16px 20px;
    margin: 12px 0;
    font-size: 10pt;
    line-height: 1.6;
    white-space: pre-wrap;
    word-wrap: break-word;
  }

  /* Hotspot effort badges */
  .effort {
    display: inline-block;
    padding: 2px 6px;
    border-radius: 3px;
    font-size: 8pt;
    font-weight: 500;
  }

  .effort-small { background: #d1fae5; color: #065f46; }
  .effort-medium { background: #fef3c7; color: #92400e; }
  .effort-large { background: #fee2e2; color: #991b1b; }

  /* Systemic risk flag */
  .systemic-flag {
    display: inline-block;
    background: #fecaca;
    color: #991b1b;
    padding: 1px 6px;
    border-radius: 3px;
    font-size: 8pt;
    font-weight: 600;
  }

  /* Print optimisation */
  .page-break {
    page-break-before: always;
  }

  .no-break {
    page-break-inside: avoid;
  }
</style>
</head>
<body>

<!-- Report Header -->
<div class="report-header">
  <h1>Stratum Risk Report</h1>
  <div class="subtitle">P6 Integrated Code Intelligence Assessment</div>
  <div class="meta">
    <span><strong>Project:</strong> {{ project_name }}</span>
    <span><strong>Scenario:</strong> {{ scenario }}</span>
    <span><strong>Generated:</strong> {{ analysis_timestamp }}</span>
  </div>
  <div class="health-badge {{ health_class }}">{{ overall_health_score }}/10</div>
</div>

<!-- Executive Summary -->
<h2>Executive Summary</h2>
<p>
  The <strong>{{ project_name }}</strong> codebase received an overall health score of
  <strong>{{ overall_health_score }}/10</strong>
  ({{ "Good" if overall_health_score >= 7 else ("Moderate" if overall_health_score >= 4 else "Poor") }})
  under the <strong>{{ scenario }}</strong> analysis scenario.
  {% if top_risks %}
  The highest-severity risk dimension is
  <strong>{{ top_risks[0].dimension }}</strong> at {{ top_risks[0].value }}/10
  ({{ top_risks[0].severity }}).
  {% endif %}
</p>

<!-- Risk Dimension Scores -->
<h2>Risk Dimensions (15-Point Model)</h2>
<table>
  <thead>
    <tr>
      <th style="width: 25%;">Dimension</th>
      <th style="width: 15%;">Score</th>
      <th style="width: 15%;">Severity</th>
      <th style="width: 45%;">Evidence</th>
    </tr>
  </thead>
  <tbody>
    {% for dim in dimension_scores %}
    <tr class="no-break">
      <td><strong>{{ dim.label or dim.dimension }}</strong></td>
      <td>
        <div class="score-bar-container">
          <div class="score-bar bar-{{ dim.severity }}"
               style="width: {{ (dim.value / 10 * 100) | int }}%;"></div>
        </div>
        {{ dim.value }}
      </td>
      <td>
        <span class="severity severity-{{ dim.severity }}">{{ dim.severity }}</span>
      </td>
      <td>{{ dim.evidence }}</td>
    </tr>
    {% endfor %}
  </tbody>
</table>

<!-- Top Risks -->
{% if top_risks %}
<h2>Top 5 Risk Areas</h2>
<table>
  <thead>
    <tr>
      <th style="width: 5%;">#</th>
      <th style="width: 25%;">Dimension</th>
      <th style="width: 12%;">Score</th>
      <th style="width: 12%;">Severity</th>
      <th style="width: 46%;">Evidence</th>
    </tr>
  </thead>
  <tbody>
    {% for risk in top_risks %}
    <tr class="no-break">
      <td>{{ loop.index }}</td>
      <td><strong>{{ risk.dimension }}</strong></td>
      <td>{{ risk.value }}</td>
      <td>
        <span class="severity severity-{{ risk.severity }}">{{ risk.severity }}</span>
      </td>
      <td>{{ risk.evidence }}</td>
    </tr>
    {% endfor %}
  </tbody>
</table>
{% endif %}

<!-- Component Risk Matrix -->
{% if component_risks %}
<div class="page-break"></div>
<h2>Component Risk Matrix</h2>
<table>
  <thead>
    <tr>
      <th style="width: 25%;">Component</th>
      <th style="width: 15%;">Composite Score</th>
      <th style="width: 15%;">Systemic Risk</th>
      <th style="width: 45%;">Top Dimension Scores</th>
    </tr>
  </thead>
  <tbody>
    {% for comp in component_risks %}
    <tr class="no-break">
      <td><strong>{{ comp.component }}</strong></td>
      <td>{{ comp.composite_score }}</td>
      <td>
        {% if comp.systemic_risk %}
        <span class="systemic-flag">SYSTEMIC</span>
        {% else %}
        —
        {% endif %}
      </td>
      <td>
        {% for dim_name, dim_data in comp.dimensions.items() %}
          {{ dim_name }}: {{ dim_data.value }}{% if not loop.last %}, {% endif %}
        {% endfor %}
      </td>
    </tr>
    {% endfor %}
  </tbody>
</table>
{% endif %}

<!-- File Hotspots -->
{% if file_hotspots %}
<h2>File Hotspots (Top 25)</h2>
<table>
  <thead>
    <tr>
      <th style="width: 40%;">File</th>
      <th style="width: 12%;">Risk Score</th>
      <th style="width: 10%;">Effort</th>
      <th style="width: 38%;">Recommendation</th>
    </tr>
  </thead>
  <tbody>
    {% for hotspot in file_hotspots %}
    <tr class="no-break">
      <td style="font-family: monospace; font-size: 8pt; word-break: break-all;">
        {{ hotspot.file }}
      </td>
      <td>
        <div class="score-bar-container">
          <div class="score-bar bar-{{ 'critical' if hotspot.score >= 8 else ('high' if hotspot.score >= 6 else ('medium' if hotspot.score >= 4 else 'low')) }}"
               style="width: {{ (hotspot.score / 10 * 100) | int }}%;"></div>
        </div>
        {{ hotspot.score }}
      </td>
      <td>
        <span class="effort effort-{{ hotspot.effort }}">{{ hotspot.effort }}</span>
      </td>
      <td>{{ hotspot.recommendation or "Review and assess refactoring priority" }}</td>
    </tr>
    {% endfor %}
  </tbody>
</table>
{% endif %}

<!-- AI Narrative -->
{% if ai_narrative %}
<div class="page-break"></div>
<h2>AI-Generated Executive Narrative</h2>
<div class="narrative">{{ ai_narrative }}</div>
{% endif %}

</body>
</html>
"""


class WeasyprintReportAdapter:
    """Renders P6 risk reports as PDF documents.

    Implements :class:`domain.ports.ReportGeneratorPort`.

    Uses Jinja2 for HTML templating and WeasyPrint for PDF rendering.
    The report features Stratum branding, colour-coded severity indicators,
    risk dimension tables, component matrix, file hotspots, and the
    AI-generated executive narrative.
    """

    def __init__(self) -> None:
        self._env = jinja2.Environment(
            loader=jinja2.BaseLoader(),
            autoescape=True,
            undefined=jinja2.StrictUndefined,
        )
        self._template = self._env.from_string(_REPORT_TEMPLATE)

    async def generate_pdf(self, report_data: dict, output_path: str) -> str:
        """Generate a PDF report from P6 risk model data.

        Args:
            report_data: Report data dictionary (from ``RiskReport.to_dict()``).
            output_path: Filesystem path for the output PDF file.

        Returns:
            The absolute path to the generated PDF file.

        Raises:
            OSError: If the output directory does not exist or is not writable.
        """
        if weasyprint is None:
            raise RuntimeError(
                "WeasyPrint requires system libraries (pango, cairo). "
                "Install via: brew install pango (macOS) or apt install libpango-1.0-0 (Linux)"
            )

        output = Path(output_path)

        # Ensure parent directory exists
        output.parent.mkdir(parents=True, exist_ok=True)

        # Prepare template context
        context = self._build_template_context(report_data)

        # Render HTML
        html_content = self._template.render(**context)

        # Generate PDF via WeasyPrint (synchronous — run in thread pool)
        await asyncio.to_thread(self._render_pdf, html_content, str(output))

        abs_path = str(output.resolve())
        logger.info("Generated PDF report: %s", abs_path)
        return abs_path

    @staticmethod
    def _build_template_context(report_data: dict) -> dict:
        """Transform the raw report_data dict into template-ready context."""
        overall_health = report_data.get("overall_health_score", 0.0)

        # Health class for badge colour
        if overall_health >= 7:
            health_class = "health-good"
        elif overall_health >= 4:
            health_class = "health-moderate"
        else:
            health_class = "health-poor"

        # Build dimension scores list with normalised keys
        dimension_scores = []
        for dim_name, dim_data in report_data.get("dimension_scores", {}).items():
            dimension_scores.append({
                "dimension": dim_name,
                "label": dim_data.get("label", dim_name.replace("_", " ").title()),
                "value": dim_data.get("value", 0.0),
                "severity": dim_data.get("severity", "minimal"),
                "evidence": dim_data.get("evidence", ""),
            })

        # Sort by score descending for visual impact
        dimension_scores.sort(key=lambda d: d["value"], reverse=True)

        # Top risks
        top_risks = []
        for risk in report_data.get("top_risks", []):
            top_risks.append({
                "dimension": risk.get("dimension", risk.get("label", "")),
                "value": risk.get("value", 0.0),
                "severity": risk.get("severity", "minimal"),
                "evidence": risk.get("evidence", ""),
            })

        return {
            "project_name": report_data.get("project_name", "Unknown Project"),
            "scenario": report_data.get("scenario", "General Assessment"),
            "analysis_timestamp": report_data.get("analysis_timestamp", "N/A"),
            "overall_health_score": overall_health,
            "health_class": health_class,
            "dimension_scores": dimension_scores,
            "top_risks": top_risks,
            "component_risks": report_data.get("component_risks", []),
            "file_hotspots": report_data.get("file_hotspots", []),
            "ai_narrative": report_data.get("ai_narrative", ""),
        }

    @staticmethod
    def _render_pdf(html_content: str, output_path: str) -> None:
        """Render HTML to PDF using WeasyPrint (synchronous)."""
        html_doc = weasyprint.HTML(string=html_content)
        html_doc.write_pdf(output_path)
        logger.debug("WeasyPrint rendered PDF to %s", output_path)
