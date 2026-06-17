import axios, { AxiosError } from 'axios';
import type {
  Paciente,
  PacienteCreate,
  PacienteUpdate,
  Expediente,
  ExpedienteCreate,
  Nota,
  NotaCreate,
  Cita,
  CitaBase,
} from '../types';

// API base URL from environment variable (defaults to local dev)
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000/api/v1';

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

let getToken: (() => Promise<string | null>) | null = null;

export const setTokenFetcher = (fetcher: () => Promise<string | null>) => {
  getToken = fetcher;
};

// Interceptor: inject auth headers
api.interceptors.request.use(async (config) => {
  if (getToken) {
    const token = await getToken();
    if (token) {
      config.headers['Authorization'] = `Bearer ${token}`;
    }
  }
  

  return config;
});

export const authApi = {
  getProfile: async (): Promise<any> => {
    const res = await api.get('/auth/me');
    return res.data;
  },
  updateProfile: async (data: { cedula?: string; especialidad?: string }): Promise<any> => {
    const res = await api.put('/auth/profile', data);
    return res.data;
  },
  onboarding: async (data: { nombre_medico: string; cedula: string; especialidad?: string }): Promise<any> => {
    const res = await api.post('/auth/onboarding', data);
    return res.data;
  }
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

export const citasApi = {
  getAll: async (start_date?: string, end_date?: string): Promise<Cita[]> => {
    const params: any = {};
    if (start_date) params.start_date = start_date;
    if (end_date) params.end_date = end_date;
    const res = await api.get('/citas', { params });
    return res.data;
  },
  create: async (data: CitaBase): Promise<Cita> => {
    const res = await api.post('/citas', data);
    return res.data;
  },
  update: async (id: string, data: Partial<CitaBase>): Promise<Cita> => {
    const res = await api.put(`/citas/${id}`, data);
    return res.data;
  },
  delete: async (id: string): Promise<void> => {
    await api.delete(`/citas/${id}`);
  }
};

