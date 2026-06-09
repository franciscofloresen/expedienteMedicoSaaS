import axios, { AxiosError } from 'axios';
import type {
  Paciente,
  PacienteCreate,
  PacienteUpdate,
  Expediente,
  ExpedienteCreate,
  Nota,
  NotaCreate,
} from '../types';

// API base URL from environment variable (defaults to local dev)
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000/api/v1';
const IS_DEV = import.meta.env.VITE_ENV === 'development' || import.meta.env.DEV;

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Interceptor: inject auth headers
// In production, this will inject the Cognito access token.
// In development, it falls back to the X-Tenant-ID header for local testing.
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');

  if (token) {
    config.headers['Authorization'] = `Bearer ${token}`;
  } else if (IS_DEV) {
    // Dev-only bypass: backend also guards this behind ENVIRONMENT=development
    config.headers['X-Tenant-ID'] = '00000000-0000-0000-0000-000000000000';
  }

  return config;
});

export const authApi = {
  getProfile: async (): Promise<any> => {
    const res = await api.get('/auth/me');
    return res.data;
  },
};

// Servicios de Pacientes
export const pacientesApi = {
  getAll: async (q?: string): Promise<Paciente[]> => {
    const params = q ? { q } : {};
    const res = await api.get<Paciente[]>('/pacientes/', { params });
    return res.data;
  },
  getById: async (id: string): Promise<Paciente> => {
    const res = await api.get<Paciente>(`/pacientes/${id}`);
    return res.data;
  },
  create: async (data: PacienteCreate): Promise<Paciente> => {
    const res = await api.post<Paciente>('/pacientes/', data);
    return res.data;
  },
  update: async (id: string, data: PacienteUpdate): Promise<Paciente> => {
    const res = await api.put<Paciente>(`/pacientes/${id}`, data);
    return res.data;
  },
  delete: async (id: string): Promise<void> => {
    await api.delete(`/pacientes/${id}`);
  }
};

export const expedientesApi = {
  getAll: async (): Promise<any[]> => {
    const res = await api.get('/expedientes/');
    return res.data;
  },
  getByPacienteId: async (pacienteId: string): Promise<Expediente | null> => {
    try {
      const res = await api.get<Expediente>(`/expedientes/paciente/${pacienteId}`);
      return res.data;
    } catch (error: unknown) {
      if (error instanceof AxiosError && error.response?.status === 404) return null;
      throw error;
    }
  },
  create: async (data: ExpedienteCreate): Promise<Expediente> => {
    const res = await api.post<Expediente>('/expedientes/', data);
    return res.data;
  },
  updateAntecedentes: async (id: string, antecedentes: string): Promise<void> => {
    await api.put(`/expedientes/${id}/antecedentes`, { antecedentes });
  }
};

export const notasApi = {
  getAll: async (): Promise<any[]> => {
    const res = await api.get('/notas/');
    return res.data;
  },
  getByExpedienteId: async (expedienteId: string): Promise<Nota[]> => {
    const res = await api.get<Nota[]>(`/notas/expediente/${expedienteId}`);
    return res.data;
  },
  create: async (data: NotaCreate): Promise<{ id: string; status: string }> => {
    const res = await api.post('/notas/', data);
    return res.data;
  },
  update: async (notaId: string, data: Partial<NotaCreate>): Promise<{ id: string; status: string }> => {
    const res = await api.put(`/notas/${notaId}`, data);
    return res.data;
  },
  firmar: async (notaId: string): Promise<{ id: string; firma_digital: string; firmado_en: string }> => {
    const res = await api.post(`/notas/${notaId}/firmar`);
    return res.data;
  }
};

export const auditApi = {
  getRecent: async (limit: number = 20): Promise<any[]> => {
    const res = await api.get('/audit/recent', { params: { limit } });
    return res.data;
  },
  registrarConsentimiento: async (paciente_id: string): Promise<void> => {
    await api.post('/audit/consentimiento', { paciente_id });
  }
};

