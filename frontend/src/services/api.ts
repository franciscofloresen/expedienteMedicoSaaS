/* eslint-disable @typescript-eslint/no-explicit-any */
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

let getToken: (() => Promise<string | null>) | null = null;

export const setTokenFetcher = (fetcher: () => Promise<string | null>) => {
  getToken = fetcher;
};

// Native fetch wrapper
async function fetchClient<T>(
  endpoint: string,
  { data, params, ...customConfig }: { data?: any; params?: Record<string, string | number>; [key: string]: any } = {}
): Promise<T> {
  let url = `${API_BASE_URL}${endpoint}`;
  
  if (params) {
    const searchParams = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        searchParams.append(key, String(value));
      }
    });
    const queryString = searchParams.toString();
    if (queryString) {
      url += `?${queryString}`;
    }
  }

  const headers: HeadersInit = {
    'Content-Type': 'application/json',
  };

  if (getToken) {
    const token = await getToken();
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
  }

  const config: RequestInit = {
    method: data ? 'POST' : 'GET',
    ...customConfig,
    headers: {
      ...headers,
      ...customConfig.headers,
    },
  };

  if (data) {
    config.body = JSON.stringify(data);
  }

  const response = await fetch(url, config);
  
  if (!response.ok) {
    let errorDetail = `HTTP Error ${response.status}`;
    try {
      const errBody = await response.json();
      if (errBody.detail) {
        if (Array.isArray(errBody.detail)) {
          errorDetail = errBody.detail.map((e: any) => `${e.loc?.[e.loc?.length-1] || 'Campo'}: ${e.msg}`).join(', ');
        } else {
          errorDetail = errBody.detail;
        }
      } else {
        errorDetail = errBody.message || errorDetail;
      }
    } catch {
      // Body is not JSON
    }
    const error = new Error(errorDetail) as any;
    error.status = response.status;
    throw error;
  }

  // Handle empty responses (like 204 No Content)
  const text = await response.text();
  return text ? JSON.parse(text) : ({} as T);
}

// REST helper methods
const api = {
  get: <T>(url: string, params?: any) => fetchClient<T>(url, { method: 'GET', params }),
  post: <T>(url: string, data?: any) => fetchClient<T>(url, { method: 'POST', data }),
  put: <T>(url: string, data?: any) => fetchClient<T>(url, { method: 'PUT', data }),
  delete: <T>(url: string) => fetchClient<T>(url, { method: 'DELETE' }),
};

export const authApi = {
  getProfile: async (): Promise<any> => {
    return api.get('/auth/me');
  },
  updateProfile: async (data: { cedula?: string; especialidad?: string }): Promise<any> => {
    return api.put('/auth/profile', data);
  },
  onboarding: async (data: { nombre_medico: string; cedula: string; especialidad?: string }): Promise<any> => {
    return api.post('/auth/onboarding', data);
  }
};

// Servicios de Pacientes
export const pacientesApi = {
  getAll: async (q?: string): Promise<Paciente[]> => {
    return api.get<Paciente[]>('/pacientes/', q ? { q } : undefined);
  },
  getById: async (id: string): Promise<Paciente> => {
    return api.get<Paciente>(`/pacientes/${id}`);
  },
  create: async (data: PacienteCreate): Promise<Paciente> => {
    return api.post<Paciente>('/pacientes/', data);
  },
  update: async (id: string, data: PacienteUpdate): Promise<Paciente> => {
    return api.put<Paciente>(`/pacientes/${id}`, data);
  },
  delete: async (id: string): Promise<void> => {
    await api.delete(`/pacientes/${id}`);
  }
};

export const expedientesApi = {
  getAll: async (): Promise<any[]> => {
    return api.get('/expedientes/');
  },
  getByPacienteId: async (pacienteId: string): Promise<Expediente | null> => {
    try {
      return await api.get<Expediente>(`/expedientes/paciente/${pacienteId}`);
    } catch (error: any) {
      if (error.status === 404) return null;
      throw error;
    }
  },
  create: async (data: ExpedienteCreate): Promise<Expediente> => {
    return api.post<Expediente>('/expedientes/', data);
  },
  updateAntecedentes: async (id: string, antecedentes: string): Promise<void> => {
    await api.put(`/expedientes/${id}/antecedentes`, { antecedentes });
  },

};

export const notasApi = {
  getAll: async (): Promise<any[]> => {
    return api.get('/notas/');
  },
  getByExpedienteId: async (expedienteId: string): Promise<Nota[]> => {
    return api.get<Nota[]>(`/notas/expediente/${expedienteId}`);
  },
  create: async (data: NotaCreate): Promise<{ id: string; status: string }> => {
    return api.post('/notas/', data);
  },
  update: async (notaId: string, data: Partial<NotaCreate>): Promise<{ id: string; status: string }> => {
    return api.put(`/notas/${notaId}`, data);
  },
  firmar: async (notaId: string): Promise<{ id: string; firma_digital: string; firmado_en: string }> => {
    return api.post(`/notas/${notaId}/firmar`);
  }
};


export const citasApi = {
  getAll: async (start_date?: string, end_date?: string): Promise<Cita[]> => {
    const params: any = {};
    if (start_date) params.start_date = start_date;
    if (end_date) params.end_date = end_date;
    return api.get('/citas/', params);
  },
  create: async (data: CitaBase): Promise<Cita> => {
    return api.post('/citas/', data);
  },
  update: async (id: string, data: Partial<CitaBase>): Promise<Cita> => {
    return api.put(`/citas/${id}`, data);
  },
  delete: async (id: string): Promise<void> => {
    await api.delete(`/citas/${id}`);
  }
};
