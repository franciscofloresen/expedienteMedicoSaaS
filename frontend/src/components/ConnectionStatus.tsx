/* eslint-disable react-hooks/set-state-in-effect */
import React, { useEffect, useState } from 'react';

/**
 * ConnectionStatus — Displays an offline banner when network is lost.
 *
 * CRIT-07: Informs the doctor that they are offline and that their
 * work will be saved locally using the useAutosave hook.
 */
export const ConnectionStatus: React.FC = () => {
  const [isOnline, setIsOnline] = useState<boolean>(true);

  useEffect(() => {
    // Initial state
    setIsOnline(navigator.onLine);

    const handleOnline = () => setIsOnline(true);
    const handleOffline = () => setIsOnline(false);

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);

  if (isOnline) {
    return null;
  }

  return (
    <div
      style={{
        backgroundColor: '#fef2f2', // light red
        color: '#991b1b', // dark red
        padding: '0.75rem',
        textAlign: 'center',
        fontWeight: 500,
        fontSize: '0.875rem',
        borderBottom: '1px solid #fecaca',
        position: 'sticky',
        top: 0,
        zIndex: 50,
      }}
      role="alert"
    >
      ⚠️ Sin conexión a internet. Los cambios se guardarán localmente en su dispositivo.
    </div>
  );
};
