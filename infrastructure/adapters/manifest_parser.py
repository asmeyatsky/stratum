"""
ManifestParser — Infrastructure adapter for dependency manifest parsing.

Architectural Intent:
    Extracts Dependency entities from package manager manifest files.
    Supports npm (package.json), pip (requirements.txt), and maven (pom.xml).

    This adapter is a pure translation layer — it converts ecosystem-specific
    manifest formats into the domain's unified Dependency entity. No risk
    assessment, version comparison, or business logic belongs here.

Design Decisions:
    - Async interface for consistency with the adapter layer, even though
      file parsing is synchronous.
    - Version strings are preserved as-is (e.g., "^1.2.3", ">=3.0") — the
      domain layer is responsible for interpreting version semantics.
    - XML parsing for pom.xml uses the stdlib xml.etree (no lxml dependency).
    - Unknown manifest types raise ValueError rather than silently returning
      empty results.
"""

from __future__ import annotations

import json
import logging
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from domain.entities.dependency import Dependency

logger = logging.getLogger(__name__)

# Maven POM namespace
_MAVEN_NS = "{http://maven.apache.org/POM/4.0.0}"


class ManifestParser:
    """Parses dependency manifests into domain Dependency entities.

    Supported ecosystems:
        - **npm**: ``package.json``
        - **pip**: ``requirements.txt``
        - **maven**: ``pom.xml``
    """

    async def parse(self, manifest_path: str) -> list[Dependency]:
        """Parse a dependency manifest file.

        Args:
            manifest_path: Filesystem path to the manifest file.

        Returns:
            List of :class:`Dependency` entities extracted from the manifest.

        Raises:
            FileNotFoundError: If *manifest_path* does not exist.
            ValueError: If the manifest type is not recognised.
        """
        path = Path(manifest_path)
        if not path.exists():
            raise FileNotFoundError(f"Manifest file not found: {manifest_path}")
        if not path.is_file():
            raise ValueError(f"Not a file: {manifest_path}")

        filename = path.name.lower()

        if filename == "package.json":
            return self._parse_npm(path)
        elif filename == "requirements.txt":
            return self._parse_pip(path)
        elif filename == "pom.xml":
            return self._parse_maven(path)
        else:
            raise ValueError(
                f"Unsupported manifest type: {filename}. "
                f"Supported: package.json, requirements.txt, pom.xml"
            )

    # ------------------------------------------------------------------
    # npm (package.json)
    # ------------------------------------------------------------------

    def _parse_npm(self, path: Path) -> list[Dependency]:
        """Parse package.json for dependencies and devDependencies."""
        raw = path.read_text(encoding="utf-8")

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            logger.error("Invalid JSON in %s: %s", path, exc)
            return []

        dependencies: list[Dependency] = []
        manifest_str = str(path)

        # Production dependencies
        for name, version in data.get("dependencies", {}).items():
            dependencies.append(
                Dependency(
                    name=name,
                    current_version=_clean_npm_version(version),
                    ecosystem="npm",
                    manifest_path=manifest_str,
                )
            )

        # Dev dependencies
        for name, version in data.get("devDependencies", {}).items():
            dependencies.append(
                Dependency(
                    name=name,
                    current_version=_clean_npm_version(version),
                    ecosystem="npm",
                    manifest_path=manifest_str,
                )
            )

        logger.info("Parsed %d npm dependencies from %s", len(dependencies), path)
        return dependencies

    # ------------------------------------------------------------------
    # pip (requirements.txt)
    # ------------------------------------------------------------------

    def _parse_pip(self, path: Path) -> list[Dependency]:
        """Parse requirements.txt for pinned and ranged dependencies."""
        raw = path.read_text(encoding="utf-8")
        dependencies: list[Dependency] = []
        manifest_str = str(path)

        for line in raw.splitlines():
            line = line.strip()

            # Skip comments, blank lines, and option flags
            if not line or line.startswith("#") or line.startswith("-"):
                continue

            # Skip editable installs and URL references
            if line.startswith("git+") or line.startswith("http"):
                continue

            dep = self._parse_pip_line(line, manifest_str)
            if dep is not None:
                dependencies.append(dep)

        logger.info("Parsed %d pip dependencies from %s", len(dependencies), path)
        return dependencies

    @staticmethod
    def _parse_pip_line(line: str, manifest_path: str) -> Dependency | None:
        """Parse a single requirements.txt line.

        Handles formats:
            - ``package==1.2.3``
            - ``package>=1.0,<2.0``
            - ``package~=1.4``
            - ``package`` (no version specifier)
            - ``package[extra]==1.0``
            - ``package ; python_version>='3.8'`` (environment markers)
        """
        # Strip inline comments
        if " #" in line:
            line = line[: line.index(" #")]

        # Strip environment markers
        if ";" in line:
            line = line[: line.index(";")]

        line = line.strip()
        if not line:
            return None

        # Split on version specifiers
        match = re.match(
            r"^([A-Za-z0-9][\w.*-]*(?:\[[^\]]*\])?)\s*([<>=!~]+.*)?$",
            line,
        )
        if not match:
            logger.debug("Skipping unparseable pip line: %s", line)
            return None

        name = match.group(1)
        version_spec = match.group(2) or ""

        # Strip extras from name: package[extra] -> package
        if "[" in name:
            name = name[: name.index("[")]

        # Extract pinned version if available (e.g., "==1.2.3")
        pinned_match = re.search(r"==\s*([^\s,]+)", version_spec)
        current_version = pinned_match.group(1) if pinned_match else version_spec.strip()

        if not current_version:
            current_version = "*"

        return Dependency(
            name=name.strip(),
            current_version=current_version,
            ecosystem="pip",
            manifest_path=manifest_path,
        )

    # ------------------------------------------------------------------
    # Maven (pom.xml)
    # ------------------------------------------------------------------

    def _parse_maven(self, path: Path) -> list[Dependency]:
        """Parse pom.xml for <dependency> elements."""
        raw = path.read_text(encoding="utf-8")

        try:
            root = ET.fromstring(raw)
        except ET.ParseError as exc:
            logger.error("Invalid XML in %s: %s", path, exc)
            return []

        dependencies: list[Dependency] = []
        manifest_str = str(path)

        # Find all <dependency> elements (with and without namespace)
        dep_elements = root.findall(f".//{_MAVEN_NS}dependency")
        if not dep_elements:
            dep_elements = root.findall(".//dependency")

        for dep_elem in dep_elements:
            dep = self._parse_maven_dependency(dep_elem, manifest_str)
            if dep is not None:
                dependencies.append(dep)

        logger.info("Parsed %d maven dependencies from %s", len(dependencies), path)
        return dependencies

    @staticmethod
    def _parse_maven_dependency(
        elem: ET.Element, manifest_path: str
    ) -> Dependency | None:
        """Parse a single <dependency> XML element."""
        # Try with namespace first, then without
        group_id = (
            _find_text(elem, f"{_MAVEN_NS}groupId")
            or _find_text(elem, "groupId")
        )
        artifact_id = (
            _find_text(elem, f"{_MAVEN_NS}artifactId")
            or _find_text(elem, "artifactId")
        )
        version = (
            _find_text(elem, f"{_MAVEN_NS}version")
            or _find_text(elem, "version")
        )

        if not artifact_id:
            return None

        # Maven canonical name: groupId:artifactId
        name = f"{group_id}:{artifact_id}" if group_id else artifact_id

        return Dependency(
            name=name,
            current_version=version or "unspecified",
            ecosystem="maven",
            manifest_path=manifest_path,
        )


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _clean_npm_version(version: str) -> str:
    """Strip npm-specific prefixes (^, ~, >=, etc.) for storage.

    The raw specifier is preserved so the domain layer can interpret ranges
    if needed.
    """
    return version.strip()


def _find_text(element: ET.Element, tag: str) -> str | None:
    """Safely extract text from an XML child element."""
    child = element.find(tag)
    return child.text.strip() if child is not None and child.text else None
