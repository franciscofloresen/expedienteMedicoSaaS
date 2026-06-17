/* eslint-disable react-hooks/set-state-in-effect */
/**
 * useAutosave — Auto-saves form data to localStorage for offline resilience.
 *
 * CRIT-07: Prevents data loss when a doctor loses internet during a consultation.
 * Saves draft every 30 seconds, recovers on mount, clears on successful submit.
 *
 * Usage:
 *   const { draft, hasDraft, draftAge, saveDraft, clearDraft } = useAutosave('nota-draft-123');
 */

import { useState, useEffect, useCallback, useRef } from 'react';

interface AutosaveDraft<T> {
  data: T;
  savedAt: number; // Unix timestamp ms
}

interface UseAutosaveReturn<T> {
  /** The recovered draft data, or null if no draft exists */
  draft: T | null;
  /** Whether a draft exists in localStorage */
  hasDraft: boolean;
  /** Human-readable age of the draft (e.g., "hace 2 minutos") */
  draftAge: string | null;
  /** Save current form data as a draft */
  saveDraft: (data: T) => void;
  /** Clear the draft (call after successful submission) */
  clearDraft: () => void;
  /** Seconds since last save, for UI indicator */
  lastSaveSecondsAgo: number | null;
}

const AUTOSAVE_INTERVAL_MS = 30_000; // 30 seconds

function formatDraftAge(savedAt: number): string {
  const diffMs = Date.now() - savedAt;
  const diffMin = Math.floor(diffMs / 60_000);
  const diffHr = Math.floor(diffMs / 3_600_000);

  if (diffMin < 1) return 'hace unos segundos';
  if (diffMin < 60) return `hace ${diffMin} minuto${diffMin > 1 ? 's' : ''}`;
  if (diffHr < 24) return `hace ${diffHr} hora${diffHr > 1 ? 's' : ''}`;
  return `hace más de un día`;
}

export function useAutosave<T>(key: string): UseAutosaveReturn<T> {
  const [draft, setDraft] = useState<T | null>(null);
  const [savedAt, setSavedAt] = useState<number | null>(null);
  const [lastSaveSecondsAgo, setLastSaveSecondsAgo] = useState<number | null>(null);
  const latestDataRef = useRef<T | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const storageKey = `cloudmedrecord-autosave:${key}`;

  // Recover draft on mount
  useEffect(() => {
    try {
      const raw = localStorage.getItem(storageKey);
      if (raw) {
        const parsed: AutosaveDraft<T> = JSON.parse(raw);
        // Only recover drafts less than 24 hours old
        if (Date.now() - parsed.savedAt < 86_400_000) {
          setDraft(parsed.data);
          setSavedAt(parsed.savedAt);
        } else {
          // Expired draft, clean up
          localStorage.removeItem(storageKey);
        }
      }
    } catch {
      // Corrupted data, clean up
      localStorage.removeItem(storageKey);
    }
  }, [storageKey]);

  // Update "time since last save" every 10 seconds
  useEffect(() => {
    if (!savedAt) return;

    const tick = () => {
      setLastSaveSecondsAgo(Math.floor((Date.now() - savedAt) / 1000));
    };
    tick();

    const id = setInterval(tick, 10_000);
    return () => clearInterval(id);
  }, [savedAt]);

  const saveDraft = useCallback(
    (data: T) => {
      latestDataRef.current = data;
      const now = Date.now();
      const entry: AutosaveDraft<T> = { data, savedAt: now };
      try {
        localStorage.setItem(storageKey, JSON.stringify(entry));
        setSavedAt(now);
      } catch {
        // localStorage full or disabled — fail silently
        console.warn('Autosave: No se pudo guardar el borrador localmente.');
      }
    },
    [storageKey]
  );

  const clearDraft = useCallback(() => {
    localStorage.removeItem(storageKey);
    setDraft(null);
    setSavedAt(null);
    setLastSaveSecondsAgo(null);
    latestDataRef.current = null;
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }, [storageKey]);

  // Auto-save interval: save latest data every 30 seconds
  useEffect(() => {
    intervalRef.current = setInterval(() => {
      if (latestDataRef.current) {
        saveDraft(latestDataRef.current);
      }
    }, AUTOSAVE_INTERVAL_MS);

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [saveDraft]);

  return {
    draft,
    hasDraft: draft !== null,
    draftAge: savedAt ? formatDraftAge(savedAt) : null,
    saveDraft,
    clearDraft,
    lastSaveSecondsAgo,
  };
}
