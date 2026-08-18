import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ConnectionStatus } from './ConnectionStatus';
import type { ServerHealthStatus } from '../contexts/serverHealthContextDef';

vi.mock('../hooks/useServerHealth', () => ({ useServerHealth: vi.fn() }));
import { useServerHealth } from '../hooks/useServerHealth';

function mockHealth(status: ServerHealthStatus) {
  vi.mocked(useServerHealth).mockReturnValue({
    status,
    isDegraded: status !== 'ok',
    lastHealthyAt: null,
    refresh: vi.fn(),
  });
}

function renderBanner() {
  return render(
    <MemoryRouter>
      <ConnectionStatus />
    </MemoryRouter>,
  );
}

describe('ConnectionStatus (honest degraded banner)', () => {
  beforeEach(() => vi.clearAllMocks());

  it('renders nothing when the server is healthy', () => {
    mockHealth('ok');
    const { container } = renderBanner();
    expect(container).toBeEmptyDOMElement();
  });

  it('never promises a local save — the old dishonest message is gone', () => {
    mockHealth('offline');
    renderBanner();
    expect(screen.queryByText(/guardarán localmente/i)).not.toBeInTheDocument();
  });

  it('when degraded, states signing is blocked and links to the continuity format', () => {
    mockHealth('degraded');
    renderBanner();
    expect(screen.getByText(/firma está bloqueada/i)).toBeInTheDocument();
    const link = screen.getByRole('link', { name: /formato de continuidad/i });
    expect(link).toHaveAttribute('href', '/app/continuidad');
  });

  it('when offline, warns that nothing is saved until the server confirms', () => {
    mockHealth('offline');
    renderBanner();
    expect(screen.getByText(/NO quedan guardados hasta que el servidor/i)).toBeInTheDocument();
  });
});
