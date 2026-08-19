import { renderHook } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { useKeyboardShortcuts, type Shortcut } from './useKeyboardShortcuts';

function press(key: string, opts: { ctrlKey?: boolean; metaKey?: boolean } = {}) {
  const ev = new KeyboardEvent('keydown', { key, cancelable: true, ...opts });
  window.dispatchEvent(ev);
  return ev;
}

describe('useKeyboardShortcuts', () => {
  it('runs a Ctrl/Cmd combo handler and prevents default', () => {
    const save = vi.fn();
    const shortcuts: Shortcut[] = [{ key: 's', ctrlOrMeta: true, handler: save }];
    renderHook(() => useKeyboardShortcuts(shortcuts, true));

    const ev = press('s', { ctrlKey: true });
    expect(save).toHaveBeenCalledOnce();
    expect(ev.defaultPrevented).toBe(true);

    press('s', { metaKey: true }); // Cmd on macOS also matches
    expect(save).toHaveBeenCalledTimes(2);
  });

  it('does not fire a Ctrl/Cmd combo without the modifier', () => {
    const save = vi.fn();
    renderHook(() => useKeyboardShortcuts([{ key: 's', ctrlOrMeta: true, handler: save }], true));
    press('s');
    expect(save).not.toHaveBeenCalled();
  });

  it('matches a bare key like Escape', () => {
    const close = vi.fn();
    renderHook(() => useKeyboardShortcuts([{ key: 'Escape', handler: close }], true));
    press('Escape');
    expect(close).toHaveBeenCalledOnce();
  });

  it('does nothing while disabled', () => {
    const save = vi.fn();
    renderHook(() => useKeyboardShortcuts([{ key: 's', ctrlOrMeta: true, handler: save }], false));
    press('s', { ctrlKey: true });
    expect(save).not.toHaveBeenCalled();
  });

  it('can opt out of preventDefault', () => {
    const handler = vi.fn();
    renderHook(() =>
      useKeyboardShortcuts([{ key: 'Enter', ctrlOrMeta: true, handler, preventDefault: false }], true),
    );
    const ev = press('Enter', { ctrlKey: true });
    expect(handler).toHaveBeenCalledOnce();
    expect(ev.defaultPrevented).toBe(false);
  });
});
