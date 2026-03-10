"""
Author Entity

Architectural Intent:
- Represents a code contributor with normalised identity
- Tracks contribution patterns for knowledge risk analysis (P1)
- Immutable — state changes produce new instances
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class Author:
    name: str
    email: str
    aliases: tuple[str, ...] = field(default=())

    @property
    def canonical_id(self) -> str:
        """Primary identity key — normalised email."""
        return self.email.lower().strip()

    def with_alias(self, alias_email: str) -> Author:
        if alias_email.lower().strip() in (a.lower() for a in self.aliases):
            return self
        return Author(
            name=self.name,
            email=self.email,
            aliases=self.aliases + (alias_email,),
        )

    def matches(self, email: str) -> bool:
        normalised = email.lower().strip()
        return normalised == self.canonical_id or normalised in (
            a.lower() for a in self.aliases
        )
