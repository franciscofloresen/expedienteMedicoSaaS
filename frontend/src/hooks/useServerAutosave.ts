/**
 * useServerAutosave — periodic, honest autosave to the SERVER (Fase 13).
 *
 * Replaces the old localStorage autosave, which stored PHI unencrypted on the
 * device and implied a save the server never confirmed. This hook saves the
 * caller's data snapshot to the server every `intervalMs` (10–15 s) only while
 * `enabled`, only when the data actually changed, and only reports `saved` after
 * the server call resolves — so the UI never claims a save that did not happen.
 *
 * Deliberately data-agnostic (no PHI logic here) so it is unit-testable and reused
 * across editors. The caller decides what to snapshot and how to persist it.
 */
import { useEffect, useRef, useState } from 'react';

export type AutosaveStatus = 'idle' | 'saving' | 'saved' | 'error';

export function useServerAutosave<T>({
  data,
  save,
  enabled,
  intervalMs = 12_000,
}: {
  data: T | null;
  save: (data: T) => Promise<void>;
  enabled: boolean;
  intervalMs?: number;
}): { status: AutosaveStatus; lastSavedAt: number | null } {
  const [status, setStatus] = useState<AutosaveStatus>('idle');
  const [lastSavedAt, setLastSavedAt] = useState<number | null>(null);

  const dataRef = useRef<T | null>(data);
  const saveRef = useRef(save);
  const savedSnapshotRef = useRef<string | null>(null);
  const savingRef = useRef(false);

  useEffect(() => {
    dataRef.current = data;
  }, [data]);
  useEffect(() => {
    saveRef.current = save;
  }, [save]);

  useEffect(() => {
    if (!enabled) return;

    const tick = async () => {
      const current = dataRef.current;
      if (current == null || savingRef.current) return;
      const snapshot = JSON.stringify(current);
      if (snapshot === savedSnapshotRef.current) return;

      savingRef.current = true;
      setStatus('saving');
      try {
        await saveRef.current(current);
        savedSnapshotRef.current = snapshot;
        setStatus('saved');
        setLastSavedAt(Date.now());
      } catch {
        // Honest: a failed save is surfaced as an error, never as "saved".
        setStatus('error');
      } finally {
        savingRef.current = false;
      }
    };

    const id = setInterval(tick, intervalMs);
    return () => clearInterval(id);
  }, [enabled, intervalMs]);

  return { status, lastSavedAt };
}
