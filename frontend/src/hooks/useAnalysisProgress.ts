/**
 * Custom React hook for real-time analysis progress via WebSocket.
 *
 * Manages the WebSocket lifecycle (connect, reconnect, cleanup) and
 * exposes the latest progress payload plus connection state.
 *
 * Usage:
 *   const { progress, connected } = useAnalysisProgress(projectId);
 */

import { useCallback, useEffect, useRef, useState } from 'react';

export interface AnalysisProgress {
  type: string;
  project_id: string;
  step: string;
  status: string;
  progress: number;
  message: string;
}

interface UseAnalysisProgressResult {
  progress: AnalysisProgress | null;
  connected: boolean;
}

const WS_BASE_URL =
  import.meta.env.VITE_WS_BASE_URL ||
  `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}`;

const RECONNECT_DELAY_MS = 3000;
const MAX_RECONNECT_ATTEMPTS = 10;

export function useAnalysisProgress(
  projectId: string | null,
): UseAnalysisProgressResult {
  const [progress, setProgress] = useState<AnalysisProgress | null>(null);
  const [connected, setConnected] = useState(false);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttempts = useRef(0);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const cleanup = useCallback(() => {
    if (reconnectTimer.current) {
      clearTimeout(reconnectTimer.current);
      reconnectTimer.current = null;
    }
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setConnected(false);
  }, []);

  const connect = useCallback(() => {
    if (!projectId) return;

    const url = `${WS_BASE_URL}/ws/analysis/${projectId}`;
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
      reconnectAttempts.current = 0;
    };

    ws.onmessage = (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data) as AnalysisProgress;
        if (data.type === 'analysis_progress') {
          setProgress(data);
        }
      } catch {
        // Ignore malformed messages
      }
    };

    ws.onclose = () => {
      setConnected(false);
      wsRef.current = null;

      // Auto-reconnect with back-off
      if (
        projectId &&
        reconnectAttempts.current < MAX_RECONNECT_ATTEMPTS
      ) {
        reconnectAttempts.current += 1;
        reconnectTimer.current = setTimeout(connect, RECONNECT_DELAY_MS);
      }
    };

    ws.onerror = () => {
      // The onclose handler will fire after onerror, triggering reconnect
      ws.close();
    };
  }, [projectId]);

  useEffect(() => {
    cleanup();
    setProgress(null);
    reconnectAttempts.current = 0;

    if (projectId) {
      connect();
    }

    return cleanup;
  }, [projectId, connect, cleanup]);

  return { progress, connected };
}

export default useAnalysisProgress;
