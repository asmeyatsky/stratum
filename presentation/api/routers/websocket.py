"""
WebSocket endpoint for real-time analysis progress updates.

Architectural Intent:
    Provides a bidirectional channel so the React frontend can display
    live progress feedback while a long-running analysis executes.  Each
    WebSocket connection is scoped to a ``project_id``; the
    ``ConnectionManager`` singleton handles fan-out to all clients
    watching a given project.

    The ``broadcast_progress`` helper is importable by background tasks
    (e.g. the analysis runner) so they can push updates without direct
    knowledge of WebSocket internals.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

router = APIRouter()


class ConnectionManager:
    """Manages active WebSocket connections grouped by project_id."""

    def __init__(self) -> None:
        self._connections: dict[str, list[WebSocket]] = {}

    async def connect(self, project_id: str, websocket: WebSocket) -> None:
        """Accept and register a WebSocket for a given project."""
        await websocket.accept()
        self._connections.setdefault(project_id, []).append(websocket)
        logger.info("WebSocket connected: project=%s", project_id)

    def disconnect(self, project_id: str, websocket: WebSocket) -> None:
        """Remove a WebSocket from the project's connection list."""
        connections = self._connections.get(project_id, [])
        if websocket in connections:
            connections.remove(websocket)
        if not connections:
            self._connections.pop(project_id, None)
        logger.info("WebSocket disconnected: project=%s", project_id)

    async def broadcast(self, project_id: str, data: dict[str, Any]) -> None:
        """Send a JSON message to all clients watching a project."""
        connections = self._connections.get(project_id, [])
        stale: list[WebSocket] = []
        for ws in connections:
            try:
                await ws.send_json(data)
            except Exception:
                stale.append(ws)
        for ws in stale:
            self.disconnect(project_id, ws)


# Module-level singleton used across the application
manager = ConnectionManager()


async def broadcast_progress(
    project_id: str,
    step: str,
    status: str,
    progress: float,
    message: str,
) -> None:
    """Convenience helper for broadcasting structured progress updates.

    Args:
        project_id: The project being analysed.
        step: Current analysis step name (e.g. ``"parsing"``, ``"scoring"``).
        status: Step status (``"running"``, ``"completed"``, ``"failed"``).
        progress: Completion fraction ``0.0`` – ``1.0``.
        message: Human-readable status message.
    """
    await manager.broadcast(project_id, {
        "type": "analysis_progress",
        "project_id": project_id,
        "step": step,
        "status": status,
        "progress": progress,
        "message": message,
    })


@router.websocket("/ws/analysis/{project_id}")
async def analysis_progress_ws(websocket: WebSocket, project_id: str) -> None:
    """WebSocket endpoint for live analysis progress on a single project."""
    await manager.connect(project_id, websocket)
    try:
        while True:
            # Keep connection alive; clients may send pings or control messages
            data = await websocket.receive_text()
            # Echo back as acknowledgement (clients can send JSON commands later)
            try:
                parsed = json.loads(data)
                if parsed.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        manager.disconnect(project_id, websocket)
