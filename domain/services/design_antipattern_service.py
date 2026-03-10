"""
P3 — Design Anti-Pattern Detection Service

Architectural Intent:
- Pure domain service — no infrastructure dependencies
- Heuristic-based detection of common OOP design anti-patterns from
  file metrics, naming patterns, and commit history
- Contributes code_complexity and code_duplication dimension scores to P6
- Operates on commit history and file-level metrics since we don't have
  full AST parsing in MVP

Key Design Decisions:
1. God Class threshold: >20 methods or >15 fields (estimated from file metrics)
2. Feature Envy: methods using more external references than internal
   (estimated from import density and cross-module coupling)
3. Shotgun Surgery: files whose changes consistently trigger changes across
   many other files (uses P1 temporal coupling data)
4. Data Class: classes with very low method-to-field ratio (mostly getters/setters)
5. All detection is heuristic-based — intended as risk signals, not definitive diagnoses
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from itertools import combinations

from domain.entities.commit import Commit
from domain.entities.file_change import FileChange
from domain.value_objects.risk_score import RiskScore


# ---------------------------------------------------------------------------
# Anti-pattern finding dataclasses
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class GodClassCandidate:
    file_path: str
    estimated_methods: int
    estimated_fields: int
    total_lines: int
    reason: str  # "excessive_methods", "excessive_fields", "both"

    @property
    def is_critical(self) -> bool:
        return self.estimated_methods > 30 or self.estimated_fields > 25


@dataclass(frozen=True)
class FeatureEnvyCandidate:
    file_path: str
    external_module_references: int
    own_module_references: int
    coupling_ratio: float  # external / (external + own)

    @property
    def is_significant(self) -> bool:
        return self.coupling_ratio > 0.7 and self.external_module_references > 5


@dataclass(frozen=True)
class ShotgunSurgeryCandidate:
    file_path: str
    co_changing_files_count: int
    co_changing_modules_count: int
    avg_co_change_ratio: float

    @property
    def is_significant(self) -> bool:
        return self.co_changing_modules_count >= 3 and self.co_changing_files_count >= 5


@dataclass(frozen=True)
class DataClassCandidate:
    file_path: str
    estimated_methods: int
    estimated_fields: int
    method_to_field_ratio: float

    @property
    def is_significant(self) -> bool:
        return self.estimated_fields >= 5 and self.method_to_field_ratio < 0.5


# ---------------------------------------------------------------------------
# Heuristic thresholds
# ---------------------------------------------------------------------------

_GOD_CLASS_METHOD_THRESHOLD = 20
_GOD_CLASS_FIELD_THRESHOLD = 15

# Heuristic: average lines per method in typical codebases
_AVG_LINES_PER_METHOD = 15
# Heuristic: average lines per field declaration
_AVG_LINES_PER_FIELD = 2

# Data class: ratio of methods to fields below which a class is likely data-only
_DATA_CLASS_RATIO_THRESHOLD = 0.5

# File extensions we analyse for OOP patterns
_OOP_EXTENSIONS = frozenset({
    ".py", ".java", ".cs", ".ts", ".tsx", ".kt", ".scala", ".rb", ".cpp", ".hpp",
})


class DesignAntipatternService:
    """P3 domain service — heuristic-based design anti-pattern detection.

    All detection methods operate on commit history and file-level metrics.
    This is intentionally heuristic: we estimate structural properties from
    churn data, file sizes, and naming patterns rather than performing full
    AST parsing. Findings are risk signals, not definitive diagnoses.
    """

    def detect_god_classes(
        self, commits: list[Commit]
    ) -> list[GodClassCandidate]:
        """Detect God Class candidates — files with excessive methods or fields.

        Heuristic: estimates method count from total churn (lines added/deleted
        over the file's history) and file change frequency. Files with an
        estimated >20 methods or >15 fields are flagged.

        Args:
            commits: Full commit history.

        Returns:
            List of God Class candidates sorted by estimated method count.
        """
        file_stats = self._aggregate_file_stats(commits)
        candidates: list[GodClassCandidate] = []

        for file_path, stats in file_stats.items():
            if not self._is_oop_file(file_path):
                continue

            total_lines = stats["total_lines_added"]
            if total_lines < 50:
                continue

            # Heuristic estimation of methods and fields
            estimated_methods = max(total_lines // _AVG_LINES_PER_METHOD, 1)
            estimated_fields = self._estimate_fields_from_name(file_path, total_lines)

            excessive_methods = estimated_methods > _GOD_CLASS_METHOD_THRESHOLD
            excessive_fields = estimated_fields > _GOD_CLASS_FIELD_THRESHOLD

            if excessive_methods or excessive_fields:
                if excessive_methods and excessive_fields:
                    reason = "both"
                elif excessive_methods:
                    reason = "excessive_methods"
                else:
                    reason = "excessive_fields"

                candidates.append(
                    GodClassCandidate(
                        file_path=file_path,
                        estimated_methods=estimated_methods,
                        estimated_fields=estimated_fields,
                        total_lines=total_lines,
                        reason=reason,
                    )
                )

        return sorted(candidates, key=lambda c: c.estimated_methods, reverse=True)

    def detect_feature_envy(
        self, commits: list[Commit]
    ) -> list[FeatureEnvyCandidate]:
        """Detect Feature Envy candidates — files coupling more to external modules.

        Heuristic: files that co-change more frequently with files in other
        modules than with files in their own module exhibit feature envy — they
        likely reference external data more than their own class's data.

        Args:
            commits: Full commit history.

        Returns:
            List of Feature Envy candidates sorted by coupling ratio.
        """
        # Count how often each file co-changes with files in its own vs other modules
        file_own_module: Counter[str] = Counter()
        file_external_module: Counter[str] = Counter()

        for commit in commits:
            files = [fc.file_path for fc in commit.file_changes]
            if len(files) < 2:
                continue

            file_modules = {f: self._get_module(f) for f in files}

            for file_path in files:
                if not self._is_oop_file(file_path):
                    continue
                own_module = file_modules[file_path]
                for other_file in files:
                    if other_file == file_path:
                        continue
                    other_module = file_modules[other_file]
                    if other_module == own_module:
                        file_own_module[file_path] += 1
                    else:
                        file_external_module[file_path] += 1

        candidates: list[FeatureEnvyCandidate] = []
        all_files = set(file_own_module.keys()) | set(file_external_module.keys())

        for file_path in all_files:
            own = file_own_module.get(file_path, 0)
            external = file_external_module.get(file_path, 0)
            total = own + external
            if total < 5:
                continue

            ratio = external / total
            if ratio > 0.6:
                candidates.append(
                    FeatureEnvyCandidate(
                        file_path=file_path,
                        external_module_references=external,
                        own_module_references=own,
                        coupling_ratio=round(ratio, 3),
                    )
                )

        return sorted(candidates, key=lambda c: c.coupling_ratio, reverse=True)

    def detect_shotgun_surgery(
        self, commits: list[Commit], min_support: int = 3
    ) -> list[ShotgunSurgeryCandidate]:
        """Detect Shotgun Surgery — files whose changes ripple across many files/modules.

        Uses temporal coupling data from commit history. A file exhibits shotgun
        surgery if changes to it consistently require changes to many other files
        spread across multiple modules.

        Args:
            commits: Full commit history.
            min_support: Minimum co-change count to consider a coupling.

        Returns:
            List of Shotgun Surgery candidates sorted by co-changing module count.
        """
        # Count co-changes per file pair
        co_change_count: Counter[tuple[str, str]] = Counter()
        file_commit_count: Counter[str] = Counter()

        for commit in commits:
            files = sorted({fc.file_path for fc in commit.file_changes})
            for f in files:
                file_commit_count[f] += 1
            for a, b in combinations(files, 2):
                co_change_count[(a, b)] += 1

        # For each file, count how many distinct files and modules it co-changes with
        file_co_changers: dict[str, set[str]] = defaultdict(set)
        file_co_change_ratios: dict[str, list[float]] = defaultdict(list)

        for (file_a, file_b), count in co_change_count.items():
            if count < min_support:
                continue
            min_changes = min(
                file_commit_count[file_a], file_commit_count[file_b]
            )
            ratio = count / min_changes if min_changes > 0 else 0

            file_co_changers[file_a].add(file_b)
            file_co_changers[file_b].add(file_a)
            file_co_change_ratios[file_a].append(ratio)
            file_co_change_ratios[file_b].append(ratio)

        candidates: list[ShotgunSurgeryCandidate] = []
        for file_path, co_changers in file_co_changers.items():
            if not self._is_oop_file(file_path):
                continue
            if len(co_changers) < 5:
                continue

            co_changing_modules = {self._get_module(f) for f in co_changers}
            # Exclude the file's own module
            own_module = self._get_module(file_path)
            external_modules = co_changing_modules - {own_module}

            if len(external_modules) < 3:
                continue

            ratios = file_co_change_ratios.get(file_path, [])
            avg_ratio = sum(ratios) / len(ratios) if ratios else 0.0

            candidates.append(
                ShotgunSurgeryCandidate(
                    file_path=file_path,
                    co_changing_files_count=len(co_changers),
                    co_changing_modules_count=len(external_modules),
                    avg_co_change_ratio=round(avg_ratio, 3),
                )
            )

        return sorted(
            candidates, key=lambda c: c.co_changing_modules_count, reverse=True
        )

    def detect_data_classes(
        self, commits: list[Commit]
    ) -> list[DataClassCandidate]:
        """Detect Data Class candidates — classes with mostly fields and no behaviour.

        Heuristic: files with a high field-to-method ratio (many fields, few methods)
        are likely data holders without meaningful behaviour. Uses naming conventions
        (e.g., model/dto/entity/schema in the path) as a secondary signal.

        Args:
            commits: Full commit history.

        Returns:
            List of Data Class candidates sorted by method-to-field ratio.
        """
        file_stats = self._aggregate_file_stats(commits)
        candidates: list[DataClassCandidate] = []

        for file_path, stats in file_stats.items():
            if not self._is_oop_file(file_path):
                continue

            total_lines = stats["total_lines_added"]
            if total_lines < 20:
                continue

            estimated_methods = max(total_lines // _AVG_LINES_PER_METHOD, 1)
            estimated_fields = self._estimate_fields_from_name(file_path, total_lines)

            if estimated_fields < 5:
                continue

            ratio = estimated_methods / estimated_fields if estimated_fields > 0 else 0
            is_data_path = self._has_data_class_naming(file_path)

            if ratio < _DATA_CLASS_RATIO_THRESHOLD or (is_data_path and ratio < 1.0):
                candidates.append(
                    DataClassCandidate(
                        file_path=file_path,
                        estimated_methods=estimated_methods,
                        estimated_fields=estimated_fields,
                        method_to_field_ratio=round(ratio, 3),
                    )
                )

        return sorted(candidates, key=lambda c: c.method_to_field_ratio)

    def compute_risk_scores(
        self,
        god_classes: list[GodClassCandidate],
        feature_envy: list[FeatureEnvyCandidate],
        shotgun_surgery: list[ShotgunSurgeryCandidate],
        data_classes: list[DataClassCandidate],
    ) -> dict[str, RiskScore]:
        """Compute P3-related quality dimension scores for P6.

        Returns scores for the ``code_complexity`` and ``code_duplication``
        dimensions of the 15-point risk model.

        Args:
            god_classes: Detected God Class candidates.
            feature_envy: Detected Feature Envy candidates.
            shotgun_surgery: Detected Shotgun Surgery candidates.
            data_classes: Detected Data Class candidates.

        Returns:
            Dict mapping dimension name to :class:`RiskScore`.
        """
        scores: dict[str, RiskScore] = {}

        # Code Complexity (dimension 1)
        # God classes and feature envy contribute to complexity
        complexity_signals = len(god_classes) + len(feature_envy)
        critical_god_classes = sum(1 for g in god_classes if g.is_critical)
        complexity_score = min(
            complexity_signals * 0.8 + critical_god_classes * 1.5, 10.0
        )

        evidence_parts = []
        if god_classes:
            evidence_parts.append(
                f"{len(god_classes)} God Class candidates "
                f"({critical_god_classes} critical)"
            )
        if feature_envy:
            significant_fe = sum(1 for f in feature_envy if f.is_significant)
            evidence_parts.append(
                f"{len(feature_envy)} Feature Envy candidates "
                f"({significant_fe} significant)"
            )

        scores["code_complexity"] = RiskScore(
            value=round(complexity_score, 1),
            label="Code Complexity",
            evidence="; ".join(evidence_parts) if evidence_parts else "No anti-patterns detected",
        )

        # Code Duplication (dimension 2)
        # Shotgun surgery and data classes contribute to structural duplication
        duplication_signals = len(shotgun_surgery) + len(data_classes)
        significant_surgery = sum(1 for s in shotgun_surgery if s.is_significant)
        duplication_score = min(
            duplication_signals * 0.6 + significant_surgery * 1.5, 10.0
        )

        dup_evidence_parts = []
        if shotgun_surgery:
            dup_evidence_parts.append(
                f"{len(shotgun_surgery)} Shotgun Surgery candidates "
                f"({significant_surgery} significant)"
            )
        if data_classes:
            significant_dc = sum(1 for d in data_classes if d.is_significant)
            dup_evidence_parts.append(
                f"{len(data_classes)} Data Class candidates "
                f"({significant_dc} significant)"
            )

        scores["code_duplication"] = RiskScore(
            value=round(duplication_score, 1),
            label="Code Duplication",
            evidence=(
                "; ".join(dup_evidence_parts)
                if dup_evidence_parts
                else "No structural duplication patterns detected"
            ),
        )

        return scores

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _aggregate_file_stats(commits: list[Commit]) -> dict[str, dict[str, int]]:
        """Aggregate lines added/deleted per file across all commits."""
        stats: dict[str, dict[str, int]] = defaultdict(
            lambda: {"total_lines_added": 0, "total_lines_deleted": 0, "commit_count": 0}
        )
        for commit in commits:
            for fc in commit.file_changes:
                stats[fc.file_path]["total_lines_added"] += fc.lines_added
                stats[fc.file_path]["total_lines_deleted"] += fc.lines_deleted
                stats[fc.file_path]["commit_count"] += 1
        return dict(stats)

    @staticmethod
    def _is_oop_file(file_path: str) -> bool:
        """Check if a file has an OOP-language extension."""
        lower = file_path.lower()
        return any(lower.endswith(ext) for ext in _OOP_EXTENSIONS)

    @staticmethod
    def _get_module(file_path: str) -> str:
        """Extract the top-level module from a file path."""
        parts = file_path.split("/")
        return parts[0] if len(parts) > 1 else "(root)"

    @staticmethod
    def _estimate_fields_from_name(file_path: str, total_lines: int) -> int:
        """Estimate field count using file size and naming heuristics.

        Files with 'model', 'entity', 'dto', 'schema', or 'data' in their
        path are assumed to have a higher field density.
        """
        lower = file_path.lower()
        data_indicators = ("model", "entity", "dto", "schema", "data", "record", "bean")
        is_data_like = any(indicator in lower for indicator in data_indicators)

        if is_data_like:
            # Data-oriented files have roughly 1 field per 2-3 lines
            return total_lines // _AVG_LINES_PER_FIELD
        else:
            # General files have fewer fields — estimate 1 per 10 lines
            return total_lines // 10

    @staticmethod
    def _has_data_class_naming(file_path: str) -> bool:
        """Check if file path suggests a data-holder class."""
        lower = file_path.lower()
        return any(
            indicator in lower
            for indicator in ("model", "entity", "dto", "schema", "record", "pojo", "bean")
        )
