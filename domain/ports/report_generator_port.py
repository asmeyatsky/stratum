"""
ReportGeneratorPort — Port for PDF/export report generation.

Adapters: WeasyPrint HTML-to-PDF renderer.
"""

from __future__ import annotations

from typing import Protocol


class ReportGeneratorPort(Protocol):
    async def generate_pdf(self, report_data: dict, output_path: str) -> str:
        """Generate PDF report and return the output file path."""
        ...
