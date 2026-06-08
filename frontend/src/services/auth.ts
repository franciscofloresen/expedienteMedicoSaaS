/**
 * Authentication API service.
 *
 * Handles register, login, logout, and session persistence.
 * Tokens are stored in localStorage — this is acceptable for
 * a development/MVP phase. In production with Cognito, the
 * Amplify SDK handles token storage securely.
 */

import { api } from './api';

export interface AuthUser {
  tenant_id: string;
  nombre_medico: string;
  email: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface RegisterRequest {
  nombre_medico: string;
  cedula: string;
  especialidad?: string;
  email: string;
  password: string;
}

interface AuthResponse {
  access_token: string;
  token_type: string;
  tenant_id: string;
  nombre_medico: string;
  email: string;
}

const TOKEN_KEY = 'access_token';
const USER_KEY = 'auth_user';

export const authApi = {
  register: async (data: RegisterRequest): Promise<AuthUser> => {
    const res = await api.post<AuthResponse>('/auth/register', data);
    _persistSession(res.data);
    return _extractUser(res.data);
  },

  login: async (data: LoginRequest): Promise<AuthUser> => {
    const res = await api.post<AuthResponse>('/auth/login', data);
    _persistSession(res.data);
    return _extractUser(res.data);
  },

  logout: (): void => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  },

  /** Restore session from localStorage (called on app init). */
  getStoredUser: (): AuthUser | null => {
    const raw = localStorage.getItem(USER_KEY);
    if (!raw) return null;
    try {
      return JSON.parse(raw) as AuthUser;
    } catch {
      return null;
    }
  },

  /** Check if a stored token exists. */
  isAuthenticated: (): boolean => {
    return !!localStorage.getItem(TOKEN_KEY);
  },
};

function _persistSession(data: AuthResponse): void {
  localStorage.setItem(TOKEN_KEY, data.access_token);
  localStorage.setItem(USER_KEY, JSON.stringify(_extractUser(data)));
}

function _extractUser(data: AuthResponse): AuthUser {
  return {
    tenant_id: data.tenant_id,
    nombre_medico: data.nombre_medico,
    email: data.email,
  };
}
