import { describe, it, expect, vi, afterEach } from 'vitest';
import { checkReadiness, isPrimeraVezConflict } from './api';

describe('isPrimeraVezConflict', () => {
  it('is true only for a 409 with the primera_vez_duplicada code', () => {
    expect(isPrimeraVezConflict({ status: 409, code: 'primera_vez_duplicada' })).toBe(true);
  });

  it('is false for a 409 with a different code (e.g. terminal cancelado)', () => {
    expect(isPrimeraVezConflict({ status: 409, code: 'cancelado' })).toBe(false);
  });

  it('is false for the right code but a non-409 status', () => {
    expect(isPrimeraVezConflict({ status: 500, code: 'primera_vez_duplicada' })).toBe(false);
  });

  it('is false for null/undefined/non-error input', () => {
    expect(isPrimeraVezConflict(null)).toBe(false);
    expect(isPrimeraVezConflict(undefined)).toBe(false);
    expect(isPrimeraVezConflict('boom')).toBe(false);
  });
});

describe('checkReadiness', () => {
  afterEach(() => vi.restoreAllMocks());

  it('returns true when readiness responds ok (writes confirmable)', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true }));
    expect(await checkReadiness()).toBe(true);
  });

  it('returns false when readiness responds 503 (degraded)', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false }));
    expect(await checkReadiness()).toBe(false);
  });

  it('returns false when the server is unreachable (fetch rejects)', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('network down')));
    expect(await checkReadiness()).toBe(false);
  });
});
