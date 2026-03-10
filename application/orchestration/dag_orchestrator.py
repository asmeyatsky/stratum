"""
DAGOrchestrator — Generic directed-acyclic-graph workflow executor.

Architectural Intent (skill2026 Rule 7):
- Provides a reusable, domain-agnostic engine for executing multi-step
  workflows where steps may run in parallel when they have no data
  dependencies on each other.
- Steps are registered with explicit dependency declarations.  The
  orchestrator resolves execution order via topological sort and runs
  independent steps concurrently using ``asyncio.gather``.
- Each step receives a shared context dict and returns its result, which
  is merged back into the context under the step's name for downstream
  consumers.
- Cycle detection is performed at registration time so misconfigurations
  surface early.
- The orchestrator is stateless after construction — safe to reuse across
  multiple runs by calling ``execute`` with a fresh context each time.

Design Decisions:
1. Steps are async callables ``(context) -> Any`` — keeps the contract
   minimal and avoids framework lock-in.
2. Context is a plain ``dict[str, Any]`` — the simplest shared-state
   container; steps retrieve upstream results by key.
3. Errors in any step propagate immediately (fail-fast); partial results
   already written to context remain accessible for diagnostics.
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

logger = logging.getLogger(__name__)

# Step function signature: receives context dict, returns arbitrary result.
StepFn = Callable[[dict[str, Any]], Awaitable[Any]]


@dataclass
class _StepNode:
    """Internal representation of a registered workflow step."""

    name: str
    fn: StepFn
    depends_on: frozenset[str] = field(default_factory=frozenset)


class DAGOrchestrator:
    """
    Execute a workflow defined as a DAG of async steps.

    Usage::

        dag = DAGOrchestrator()
        dag.add_step("parse_logs", parse_fn)
        dag.add_step("scan_deps", scan_fn)
        dag.add_step("aggregate", agg_fn, depends_on=["parse_logs", "scan_deps"])

        result = await dag.execute({"input_path": "/data/repo.log"})
        # result["aggregate"] contains the aggregation output
    """

    def __init__(self) -> None:
        self._steps: dict[str, _StepNode] = {}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def add_step(
        self,
        name: str,
        fn: StepFn,
        depends_on: list[str] | None = None,
    ) -> DAGOrchestrator:
        """
        Register a named step with optional upstream dependencies.

        Returns ``self`` for fluent chaining.

        Raises:
            ValueError: If a step with the same name already exists, if a
                dependency references an unknown step, or if adding this
                step would introduce a cycle.
        """
        if name in self._steps:
            raise ValueError(f"Step '{name}' is already registered")

        deps = frozenset(depends_on) if depends_on else frozenset()
        unknown = deps - self._steps.keys()
        if unknown:
            raise ValueError(
                f"Step '{name}' depends on unregistered steps: {sorted(unknown)}"
            )

        node = _StepNode(name=name, fn=fn, depends_on=deps)
        self._steps[name] = node

        # Validate no cycles after adding
        self._assert_no_cycles()

        return self

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    async def execute(self, context: dict[str, Any] | None = None) -> dict[str, Any]:
        """
        Run all registered steps respecting dependency order.

        Independent steps (no mutual dependencies) execute concurrently via
        ``asyncio.gather``.  Results are stored in *context* under the step
        name so downstream steps can retrieve them.

        Args:
            context: Initial shared state. If ``None``, an empty dict is used.

        Returns:
            The final context dict with all step results merged in.

        Raises:
            RuntimeError: If the DAG has no steps.
            Exception: Any exception raised by a step propagates immediately.
        """
        if not self._steps:
            raise RuntimeError("DAG has no registered steps")

        ctx = context if context is not None else {}
        execution_order = self._topological_layers()

        for layer_index, layer in enumerate(execution_order):
            logger.info(
                "DAG layer %d: executing %d step(s) — %s",
                layer_index,
                len(layer),
                [s.name for s in layer],
            )
            if len(layer) == 1:
                # Single step — run directly for simpler stack traces
                step = layer[0]
                ctx[step.name] = await step.fn(ctx)
            else:
                # Multiple independent steps — run concurrently
                results = await asyncio.gather(
                    *(step.fn(ctx) for step in layer)
                )
                for step, result in zip(layer, results):
                    ctx[step.name] = result

        return ctx

    # ------------------------------------------------------------------
    # Topological sort — Kahn's algorithm producing parallel layers
    # ------------------------------------------------------------------

    def _topological_layers(self) -> list[list[_StepNode]]:
        """
        Partition steps into layers where each layer's steps are independent
        of each other (all dependencies satisfied by prior layers).
        """
        in_degree: dict[str, int] = {name: 0 for name in self._steps}
        dependents: dict[str, list[str]] = defaultdict(list)

        for name, node in self._steps.items():
            in_degree[name] = len(node.depends_on)
            for dep in node.depends_on:
                dependents[dep].append(name)

        queue: deque[str] = deque(
            name for name, degree in in_degree.items() if degree == 0
        )

        layers: list[list[_StepNode]] = []
        while queue:
            # All nodes currently in the queue have no unsatisfied deps —
            # they form one parallel layer.
            current_layer: list[_StepNode] = []
            next_queue: deque[str] = deque()

            while queue:
                name = queue.popleft()
                current_layer.append(self._steps[name])
                for dependent in dependents[name]:
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        next_queue.append(dependent)

            layers.append(current_layer)
            queue = next_queue

        # Sanity check — all steps should be placed
        placed = sum(len(layer) for layer in layers)
        if placed != len(self._steps):
            raise RuntimeError(
                "Topological sort did not place all steps — cycle detected "
                f"({placed}/{len(self._steps)} placed)"
            )

        return layers

    # ------------------------------------------------------------------
    # Cycle detection (DFS-based)
    # ------------------------------------------------------------------

    def _assert_no_cycles(self) -> None:
        """Raise ``ValueError`` if the current graph contains a cycle."""
        WHITE, GRAY, BLACK = 0, 1, 2
        color: dict[str, int] = {name: WHITE for name in self._steps}

        def visit(name: str) -> None:
            color[name] = GRAY
            for dep in self._steps[name].depends_on:
                if dep not in color:
                    continue
                if color[dep] == GRAY:
                    raise ValueError(
                        f"Cycle detected in DAG involving step '{dep}'"
                    )
                if color[dep] == WHITE:
                    visit(dep)
            color[name] = BLACK

        for name in self._steps:
            if color[name] == WHITE:
                visit(name)
