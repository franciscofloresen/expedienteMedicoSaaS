import { useContext } from 'react';
import {
  ServerHealthContext,
  type ServerHealthContextValue,
} from '../contexts/serverHealthContextDef';

export function useServerHealth(): ServerHealthContextValue {
  const ctx = useContext(ServerHealthContext);
  if (!ctx) {
    throw new Error('useServerHealth must be used within a ServerHealthProvider');
  }
  return ctx;
}
