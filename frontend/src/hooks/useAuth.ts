/**
 * useAuth hook — access auth context from any component.
 */

import { useContext } from 'react';
import { AuthContext, type AuthContextValue } from '../contexts/authContextDef';

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return ctx;
}
