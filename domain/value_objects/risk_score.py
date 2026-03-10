"""
RiskScore Value Object

1-10 severity scale used across all P6 quality dimensions.
Immutable, validated on construction.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RiskScore:
    value: float
    label: str = ""
    evidence: str = ""

    def __post_init__(self):
        if not 0.0 <= self.value <= 10.0:
            raise ValueError(f"RiskScore must be between 0 and 10, got {self.value}")

    @property
    def severity(self) -> str:
        if self.value >= 8:
            return "critical"
        if self.value >= 6:
            return "high"
        if self.value >= 4:
            return "medium"
        if self.value >= 2:
            return "low"
        return "minimal"

    def to_dict(self) -> dict:
        return {
            "value": self.value,
            "severity": self.severity,
            "label": self.label,
            "evidence": self.evidence,
        }
