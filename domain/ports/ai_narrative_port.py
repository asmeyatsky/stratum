"""
AINarrativePort — Port for AI-generated executive narratives.

Adapters: Claude API client.
"""

from __future__ import annotations

from typing import Protocol


class AINarrativePort(Protocol):
    async def generate_narrative(
        self, risk_model: dict, scenario: str
    ) -> str:
        """Generate executive narrative from P6 risk model JSON."""
        ...
