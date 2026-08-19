import { renderHook, waitFor } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { useServerAutosave } from './useServerAutosave';

const wait = (ms: number) => new Promise((r) => setTimeout(r, ms));

describe('useServerAutosave', () => {
  it('saves the data to the server after the interval and reports "saved"', async () => {
    const save = vi.fn().mockResolvedValue(undefined);
    const { result } = renderHook(() =>
      useServerAutosave({ data: { motivo: 'cefalea' }, save, enabled: true, intervalMs: 30 }),
    );
    expect(result.current.status).toBe('idle');

    await waitFor(() => expect(save).toHaveBeenCalledWith({ motivo: 'cefalea' }));
    await waitFor(() => expect(result.current.status).toBe('saved'));
    expect(result.current.lastSavedAt).not.toBeNull();
  });

  it('does not save while disabled', async () => {
    const save = vi.fn().mockResolvedValue(undefined);
    renderHook(() =>
      useServerAutosave({ data: { a: 1 }, save, enabled: false, intervalMs: 20 }),
    );
    await wait(120);
    expect(save).not.toHaveBeenCalled();
  });

  it('does not re-save unchanged data on later ticks', async () => {
    const save = vi.fn().mockResolvedValue(undefined);
    renderHook(() =>
      useServerAutosave({ data: { a: 1 }, save, enabled: true, intervalMs: 20 }),
    );
    await waitFor(() => expect(save).toHaveBeenCalledTimes(1));
    await wait(80);
    expect(save).toHaveBeenCalledTimes(1);
  });

  it('reports "error" (not "saved") when the server call fails', async () => {
    const save = vi.fn().mockRejectedValue(new Error('503'));
    const { result } = renderHook(() =>
      useServerAutosave({ data: { a: 1 }, save, enabled: true, intervalMs: 30 }),
    );
    await waitFor(() => expect(result.current.status).toBe('error'));
    expect(result.current.lastSavedAt).toBeNull();
  });

  it('never saves a null snapshot', async () => {
    const save = vi.fn().mockResolvedValue(undefined);
    renderHook(() =>
      useServerAutosave({ data: null, save, enabled: true, intervalMs: 20 }),
    );
    await wait(120);
    expect(save).not.toHaveBeenCalled();
  });
});
