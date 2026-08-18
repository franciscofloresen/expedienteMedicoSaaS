import React from 'react';
import { WifiOff, AlertTriangle } from 'lucide-react';
import { Link } from 'react-router-dom';
import { useServerHealth } from '../hooks/useServerHealth';

/**
 * ConnectionStatus — honest degraded-mode banner (Fase 10).
 *
 * Replaces the old "se guardarán localmente" promise, which claimed a save the
 * server never confirmed. Now it polls readiness (`useServerHealth`) and tells
 * the truth: while degraded/offline nothing is saved until the server confirms,
 * signing is blocked, and the printable continuity format is the fallback.
 */
export const ConnectionStatus: React.FC = () => {
  const { status } = useServerHealth();

  if (status === 'ok') return null;

  const offline = status === 'offline';

  return (
    <div className="offline-banner" role="alert">
      {offline ? (
        <WifiOff size={16} style={{ verticalAlign: '-3px', marginRight: '0.4rem' }} />
      ) : (
        <AlertTriangle size={16} style={{ verticalAlign: '-3px', marginRight: '0.4rem' }} />
      )}
      {offline
        ? 'Sin conexión. Tus cambios NO quedan guardados hasta que el servidor los confirme.'
        : 'No podemos confirmar el guardado con el servidor. La firma está bloqueada.'}{' '}
      No firmes ni des por guardada una atención sin confirmación.{' '}
      <Link to="/app/continuidad" style={{ textDecoration: 'underline', fontWeight: 600 }}>
        Usar formato de continuidad
      </Link>
    </div>
  );
};
