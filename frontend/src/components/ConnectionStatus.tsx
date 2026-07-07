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
    <div className="offline-banner" role="alert">
      ⚠️ Sin conexión a internet. Los cambios se guardarán localmente en su dispositivo.
    </div>
  );
};
