"""
ThemedReportAdapter — Infrastructure adapter extending WeasyprintReportAdapter.

Architectural Intent:
    Extends the base PDF report adapter with white-label theming support for
    partner deployments. Partners can supply a theme configuration (logo URL,
    primary colour, company name, footer text) to produce branded reports
    that appear to originate from the partner's own platform.

    This adapter inherits all rendering logic from WeasyprintReportAdapter
    and overrides the template context and CSS to inject partner branding.

Design Decisions:
    - Theme is applied by overriding CSS custom properties and injecting
      partner-specific content into the HTML header/footer sections.
    - Logo is embedded via an <img> tag referencing the partner's logo URL.
      For on-prem deployments, this can be a local file:// URL or a data URI.
    - CSS colour overrides use the partner's primary colour for headers,
      badges, and accent elements.
    - The ``@page`` CSS rule is overridden to replace the default Stratum
      footer with partner branding.
    - Falls back gracefully: if no theme config is provided, the adapter
      behaves identically to the base WeasyprintReportAdapter.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from pathlib import Path

import jinja2

try:
    import weasyprint
except OSError:
    weasyprint = None  # type: ignore[assignment]  # pango not available

from infrastructure.adapters.weasyprint_report_adapter import WeasyprintReportAdapter

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ThemeConfig:
    """White-label theme configuration for partner-branded reports.

    Attributes:
        logo_url: URL or data URI for the partner's logo image.
        primary_color: CSS colour value for branding (e.g., ``"#2563eb"``).
        company_name: Partner's company name displayed in the report header.
        footer_text: Custom footer text replacing the default Stratum branding.
    """

    logo_url: str = ""
    primary_color: str = "#1e293b"  # Stratum default dark slate
    company_name: str = "Stratum"
    footer_text: str = "Stratum Code Intelligence"


# ------------------------------------------------------------------
# CSS override template for partner theming
# ------------------------------------------------------------------

_THEME_CSS_TEMPLATE = """\
<style>
  /* Partner theme overrides */
  @page {
    @bottom-center {
      content: "{{ footer_text }} — Page " counter(page) " of " counter(pages);
      font-size: 8pt;
      color: #6b7280;
    }
  }

  .report-header {
    background: linear-gradient(135deg, {{ primary_color }}, {{ primary_color_light }}) !important;
  }

  .severity-critical { background: {{ primary_color }}22; color: {{ primary_color }}; }

  .score-bar.bar-critical { background: {{ primary_color }} !important; }

  .narrative {
    border-left-color: {{ primary_color }} !important;
  }

  /* Partner logo and branding */
  .partner-branding {
    display: flex;
    align-items: center;
    gap: 16px;
    margin-bottom: 8px;
  }

  .partner-branding img {
    max-height: 40px;
    max-width: 200px;
  }

  .partner-branding .partner-name {
    font-size: 10pt;
    color: #94a3b8;
    font-weight: 400;
  }
</style>
"""

_PARTNER_HEADER_TEMPLATE = """\
<div class="partner-branding">
  {% if logo_url %}
  <img src="{{ logo_url }}" alt="{{ company_name }} logo">
  {% endif %}
  <span class="partner-name">Powered by {{ company_name }}</span>
</div>
"""


class ThemedReportAdapter(WeasyprintReportAdapter):
    """Renders partner-branded PDF reports with white-label theming.

    Extends :class:`WeasyprintReportAdapter` to inject partner branding
    (logo, colours, footer text) into the generated PDF.

    Implements :class:`domain.ports.ReportGeneratorPort`.

    Args:
        theme: Theme configuration for partner branding. If ``None``,
            defaults to standard Stratum branding.
    """

    def __init__(self, theme: ThemeConfig | None = None) -> None:
        super().__init__()
        self._theme = theme or ThemeConfig()
        self._theme_css_env = jinja2.Environment(
            loader=jinja2.BaseLoader(),
            autoescape=True,
            undefined=jinja2.StrictUndefined,
        )

    async def generate_pdf(self, report_data: dict, output_path: str) -> str:
        """Generate a partner-branded PDF report from P6 risk model data.

        Args:
            report_data: Report data dictionary (from ``RiskReport.to_dict()``).
            output_path: Filesystem path for the output PDF file.

        Returns:
            The absolute path to the generated PDF file.

        Raises:
            RuntimeError: If WeasyPrint/pango is not available.
        """
        if weasyprint is None:
            raise RuntimeError(
                "WeasyPrint requires system libraries (pango, cairo). "
                "Install via: brew install pango (macOS) or apt install libpango-1.0-0 (Linux)"
            )

        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        # Build the base template context
        context = self._build_template_context(report_data)

        # Render the base HTML
        html_content = self._template.render(**context)

        # Inject partner theming
        html_content = self._apply_theme(html_content)

        # Generate PDF via WeasyPrint (synchronous — run in thread pool)
        await asyncio.to_thread(self._render_pdf, html_content, str(output))

        abs_path = str(output.resolve())
        logger.info("Generated themed PDF report: %s", abs_path)
        return abs_path

    def _apply_theme(self, html_content: str) -> str:
        """Inject partner CSS overrides and branding into the HTML.

        Inserts theme CSS before ``</head>`` and partner branding after
        the opening ``<div class="report-header">`` tag.

        Args:
            html_content: Base HTML rendered by the parent template.

        Returns:
            HTML with partner theming applied.
        """
        theme = self._theme

        # Compute a lighter shade of the primary colour for gradient
        primary_light = self._lighten_color(theme.primary_color, 0.2)

        # Render theme CSS
        css_template = self._theme_css_env.from_string(_THEME_CSS_TEMPLATE)
        theme_css = css_template.render(
            primary_color=theme.primary_color,
            primary_color_light=primary_light,
            footer_text=theme.footer_text,
        )

        # Render partner header branding
        header_template = self._theme_css_env.from_string(_PARTNER_HEADER_TEMPLATE)
        partner_header = header_template.render(
            logo_url=theme.logo_url,
            company_name=theme.company_name,
        )

        # Inject CSS before </head>
        html_content = html_content.replace("</head>", f"{theme_css}\n</head>")

        # Replace default report title with partner company name
        html_content = html_content.replace(
            "<h1>Stratum Risk Report</h1>",
            f"<h1>{theme.company_name} Risk Report</h1>",
        )

        # Replace default subtitle
        html_content = html_content.replace(
            '<div class="subtitle">P6 Integrated Code Intelligence Assessment</div>',
            f'<div class="subtitle">Integrated Code Intelligence Assessment</div>'
            f"\n  {partner_header}",
        )

        return html_content

    @staticmethod
    def _lighten_color(hex_color: str, factor: float) -> str:
        """Lighten a hex colour by mixing it towards white.

        Args:
            hex_color: CSS hex colour (e.g., ``"#1e293b"``).
            factor: Lightening factor (0.0 = no change, 1.0 = white).

        Returns:
            Lightened hex colour string.
        """
        hex_color = hex_color.lstrip("#")
        if len(hex_color) != 6:
            return f"#{hex_color}"

        try:
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
        except ValueError:
            return f"#{hex_color}"

        r = int(r + (255 - r) * factor)
        g = int(g + (255 - g) * factor)
        b = int(b + (255 - b) * factor)

        return f"#{r:02x}{g:02x}{b:02x}"
