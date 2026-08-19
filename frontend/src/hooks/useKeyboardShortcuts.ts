/**
 * useKeyboardShortcuts — keyboard-driven documentation (Fase 13: "atajos de
 * teclado, navegación sin ratón"). Attaches a single keydown listener while
 * `enabled`, matches Ctrl/Cmd combos or bare keys (e.g. Escape), and runs the
 * handler. Data-agnostic and unit-testable.
 */
import { useEffect, useRef } from 'react';

export interface Shortcut {
  /** Key to match, case-insensitive (e.g. 's', 'Enter', 'Escape'). */
  key: string;
  /** Require Ctrl (Windows/Linux) or Cmd (macOS). Default false. */
  ctrlOrMeta?: boolean;
  handler: () => void;
  /** preventDefault when matched (e.g. stop the browser's Save dialog). Default true. */
  preventDefault?: boolean;
}

export function useKeyboardShortcuts(shortcuts: Shortcut[], enabled: boolean): void {
  const ref = useRef(shortcuts);
  useEffect(() => {
    ref.current = shortcuts;
  }, [shortcuts]);

  useEffect(() => {
    if (!enabled) return;
    const onKeyDown = (e: KeyboardEvent) => {
      const hasCtrlOrMeta = e.metaKey || e.ctrlKey;
      for (const s of ref.current) {
        if (e.key.toLowerCase() !== s.key.toLowerCase()) continue;
        if (Boolean(s.ctrlOrMeta) !== hasCtrlOrMeta) continue;
        if (s.preventDefault !== false) e.preventDefault();
        s.handler();
        return;
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [enabled]);
}
