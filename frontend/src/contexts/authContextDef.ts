/**
 * Auth context value type definition — shared between context and hook.
 */

import { createContext } from 'react';
import type { AuthUser, LoginRequest, RegisterRequest } from '../services/auth';

export interface AuthContextValue {
  user: AuthUser | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (data: LoginRequest) => Promise<void>;
  register: (data: RegisterRequest) => Promise<void>;
  logout: () => void;
}

export const AuthContext = createContext<AuthContextValue | null>(null);
