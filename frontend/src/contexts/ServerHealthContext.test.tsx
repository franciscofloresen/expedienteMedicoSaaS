import { render, screen, waitFor, renderHook } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ServerHealthProvider } from './ServerHealthContext';
import { useServerHealth } from '../hooks/useServerHealth';

vi.mock('../services/api', () => ({ checkReadiness: vi.fn() }));
import { checkReadiness } from '../services/api';

function Probe() {
  const { status, isDegraded } = useServerHealth();
  return <div data-testid="s">{`${status}:${isDegraded}`}</div>;
}

describe('ServerHealthProvider', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // jsdom reports online by default; make it explicit and stable.
    Object.defineProperty(window.navigator, 'onLine', { value: true, configurable: true });
  });

  it('reports ok when the readiness check passes', async () => {
    vi.mocked(checkReadiness).mockResolvedValue(true);
    render(
      <ServerHealthProvider>
        <Probe />
      </ServerHealthProvider>,
    );
    await waitFor(() => expect(screen.getByTestId('s')).toHaveTextContent('ok:false'));
  });

  it('reports degraded when the readiness check fails (server 503/unreachable)', async () => {
    vi.mocked(checkReadiness).mockResolvedValue(false);
    render(
      <ServerHealthProvider>
        <Probe />
      </ServerHealthProvider>,
    );
    await waitFor(() => expect(screen.getByTestId('s')).toHaveTextContent('degraded:true'));
  });

  it('reports offline without hitting the server when the browser is offline', async () => {
    Object.defineProperty(window.navigator, 'onLine', { value: false, configurable: true });
    vi.mocked(checkReadiness).mockResolvedValue(true);
    render(
      <ServerHealthProvider>
        <Probe />
      </ServerHealthProvider>,
    );
    await waitFor(() => expect(screen.getByTestId('s')).toHaveTextContent('offline:true'));
    expect(checkReadiness).not.toHaveBeenCalled();
  });
});

describe('useServerHealth', () => {
  it('throws when used outside a ServerHealthProvider', () => {
    expect(() => renderHook(() => useServerHealth())).toThrow(/ServerHealthProvider/);
  });
});
