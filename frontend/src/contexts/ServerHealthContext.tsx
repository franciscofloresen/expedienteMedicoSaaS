/* eslint-disable react-hooks/set-state-in-effect */
/**
 * ServerHealthProvider — polls the server's readiness so the app can be honest
 * about whether a write can be confirmed (Fase 10).
 *
 * A single poller lives here and is consumed via `useServerHealth`, so the
 * degraded banner and the sign-gating in the record view share one signal
 * instead of each opening their own poll loop.
 */
import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react';
import { checkReadiness } from '../services/api';
import {
  ServerHealthContext,
  type ServerHealthStatus,
} from './serverHealthContextDef';

const POLL_INTERVAL_MS = 20_000;

export function ServerHealthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<ServerHealthStatus>('ok');
  const [lastHealthyAt, setLastHealthyAt] = useState<number | null>(null);
  const inFlight = useRef<AbortController | null>(null);

  const runCheck = useCallback(async () => {
    // If the browser itself is offline, don't even try — report offline.
    if (typeof navigator !== 'undefined' && navigator.onLine === false) {
      setStatus('offline');
      return;
    }
    inFlight.current?.abort();
    const controller = new AbortController();
    inFlight.current = controller;
    const ready = await checkReadiness(controller.signal);
    if (controller.signal.aborted) return;
    if (ready) {
      setStatus('ok');
      setLastHealthyAt(Date.now());
    } else {
      setStatus((prev) => (prev === 'offline' ? 'offline' : 'degraded'));
    }
  }, []);

  useEffect(() => {
    runCheck();
    const id = setInterval(runCheck, POLL_INTERVAL_MS);

    const handleOnline = () => runCheck();
    const handleOffline = () => setStatus('offline');
    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    return () => {
      clearInterval(id);
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
      inFlight.current?.abort();
    };
  }, [runCheck]);

  return (
    <ServerHealthContext.Provider
      value={{
        status,
        isDegraded: status !== 'ok',
        lastHealthyAt,
        refresh: runCheck,
      }}
    >
      {children}
    </ServerHealthContext.Provider>
  );
}
