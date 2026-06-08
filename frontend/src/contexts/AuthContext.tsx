/**
 * AuthProvider component — provides auth state to the component tree.
 * Only exports the component (satisfies react-refresh/only-export-components).
 */

import { useState, useCallback, type ReactNode } from 'react';
import { authApi, type LoginRequest, type RegisterRequest } from '../services/auth';
import { AuthContext } from './authContextDef';

/** Read initial auth state synchronously from localStorage (avoids effect + setState). */
function getInitialUser() {
  const stored = authApi.getStoredUser();
  return stored && authApi.isAuthenticated() ? stored : null;
}

export default function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState(getInitialUser);

  const login = useCallback(async (data: LoginRequest) => {
    const authUser = await authApi.login(data);
    setUser(authUser);
  }, []);

  const register = useCallback(async (data: RegisterRequest) => {
    const authUser = await authApi.register(data);
    setUser(authUser);
  }, []);

  const logout = useCallback(() => {
    authApi.logout();
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider
      value={{
        user,
        isLoading: false,
        isAuthenticated: !!user,
        login,
        register,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}
