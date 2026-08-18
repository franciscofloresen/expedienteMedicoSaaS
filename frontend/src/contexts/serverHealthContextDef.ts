/**
 * Server-health context value definition (Fase 10 — honest degraded mode).
 *
 * `ok`       — server confirmed writable (last /health/ready was 200).
 * `degraded` — server reachable-ish but writes can't be confirmed (503), or
 *              the browser reports offline. In this state the UI must not claim
 *              anything was saved and must block signing.
 * `offline`  — the browser itself reports no network.
 */
import { createContext } from 'react';

export type ServerHealthStatus = 'ok' | 'degraded' | 'offline';

export interface ServerHealthContextValue {
  status: ServerHealthStatus;
  /** True whenever writes cannot be confirmed (degraded or offline). */
  isDegraded: boolean;
  /** Unix ms of the last successful readiness check, or null if never. */
  lastHealthyAt: number | null;
  /** Force an immediate readiness re-check (e.g. before attempting to sign). */
  refresh: () => void;
}

export const ServerHealthContext = createContext<ServerHealthContextValue | null>(null);
