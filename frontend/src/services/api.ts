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
  Receta,
  Encuentro,
  EncuentroCreate,
  TipoSugerido,
  CIE10,
} from '../types';

// API base URL from environment variable (defaults to local dev)
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000/api/v1';
const API_ROOT_URL = API_BASE_URL.replace(/\/api\/v1\/?$/, '');

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
    let errorCode: string | undefined;
    try {
      const errBody = await response.json();
      if (errBody.detail) {
        if (Array.isArray(errBody.detail)) {
          errorDetail = errBody.detail.map((e: any) => `${e.loc?.[e.loc?.length-1] || 'Campo'}: ${e.msg}`).join(', ');
        } else if (typeof errBody.detail === 'object' && errBody.detail.message) {
          errorDetail = errBody.detail.message;
          // Structured errors may carry a machine-readable code alongside the message
          // (e.g. primera_vez_duplicada) so callers can branch without parsing text.
          errorCode = errBody.detail.code;
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
    if (errorCode) error.code = errorCode;
    throw error;
  }

  // Handle empty responses (like 204 No Content)
  const text = await response.text();
  return text ? JSON.parse(text) : ({} as T);
}

export const api = {
  // `options.signal` lets callers abort a request (e.g. React Query cancels a stale
  // query when the search text changes); it is forwarded to fetch via customConfig.
  get: <T>(url: string, params?: any, options?: { signal?: AbortSignal }) =>
    fetchClient<T>(url, { method: 'GET', params, signal: options?.signal }),
  post: <T>(url: string, data?: any) => fetchClient<T>(url, { method: 'POST', data }),
  put: <T>(url: string, data?: any) => fetchClient<T>(url, { method: 'PUT', data }),
  delete: <T>(url: string) => fetchClient<T>(url, { method: 'DELETE' }),
};

// Servicios de CIE-10 (catálogo de diagnósticos)
export const cie10Api = {
  // Accent-insensitive search backed by pg_trgm; `signal` cancels stale requests.
  search: async (q: string, options?: { signal?: AbortSignal }): Promise<CIE10[]> => {
    if (!q || q.length < 2) return [];
    return api.get<CIE10[]>('/cie10', { q }, options);
  },
};

export const authApi = {
  getProfile: async (): Promise<any> => {
    return api.get('/auth/me');
  },
  updateProfile: async (data: { cedula?: string; especialidad?: string; notification_email?: string }): Promise<any> => {
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
  },
  legalPreview: async (notaId: string): Promise<any> => {
    return api.get(`/notas/${notaId}/legal-preview`);
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

/**
 * A completed `primera_vez` already exists for the patient (backend HTTP 409 with
 * code `primera_vez_duplicada`, enforced by the partial unique index). This is a
 * reconcilable conflict, NOT a crash: the patient's first consultation was recorded
 * elsewhere (another tab / concurrent request), so the UI should re-fetch and offer
 * to complete this encounter as `subsecuente` (roadmap Fase 2 → Aceptación).
 */
export function isPrimeraVezConflict(
  error: unknown,
): error is Error & { status: 409; code: 'primera_vez_duplicada' } {
  const e = error as { status?: number; code?: string } | null;
  return Boolean(e) && e!.status === 409 && e!.code === 'primera_vez_duplicada';
}

export const encuentrosApi = {
  list: async (pacienteId?: string): Promise<Encuentro[]> => {
    return api.get<Encuentro[]>(
      '/encuentros/',
      pacienteId ? { paciente_id: pacienteId } : undefined,
    );
  },
  getById: async (id: string): Promise<Encuentro> => {
    return api.get<Encuentro>(`/encuentros/${id}`);
  },
  sugerencia: async (pacienteId: string): Promise<TipoSugerido> => {
    return api.get<TipoSugerido>('/encuentros/sugerencia', { paciente_id: pacienteId });
  },
  create: async (data: EncuentroCreate): Promise<Encuentro> => {
    return api.post<Encuentro>('/encuentros/', data);
  },
  iniciar: async (id: string): Promise<Encuentro> => {
    return api.post<Encuentro>(`/encuentros/${id}/iniciar`);
  },
  completar: async (id: string): Promise<Encuentro> => {
    return api.post<Encuentro>(`/encuentros/${id}/completar`);
  },
};

export interface AuditEntry {
  timestamp: string;
  action: string;
  status_code: number | null;
  ip_address: string | null;
}

export const auditApi = {
  list: async (limit = 50, offset = 0): Promise<AuditEntry[]> => {
    return api.get<AuditEntry[]>('/audit/', { limit, offset });
  },
};

export interface StorageUsage {
  plan: string;
  quota_bytes: number;
  used_bytes: number;
  reserved_bytes: number;
  available_bytes: number;
  percent_used: number;
}

export interface ClinicalFile {
  id: string;
  expediente_id: string;
  paciente_id: string;
  filename: string;
  content_type: string;
  size_bytes: number;
  category: 'analysis' | 'xray' | 'prescription' | 'consent' | 'other';
  status: string;
  scan_status: string;
  created_at: string;
  completed_at: string | null;
}

interface UploadGrant {
  file_id: string;
  upload_url: string;
  upload_fields: Record<string, string>;
  expires_in: number;
}

export const filesApi = {
  usage: (): Promise<StorageUsage> => api.get('/files/usage'),
  list: (expedienteId: string): Promise<ClinicalFile[]> =>
    api.get(`/files/expedientes/${expedienteId}`),
  upload: async (
    expedienteId: string,
    file: File,
    category: ClinicalFile['category'] = 'other'
  ): Promise<ClinicalFile> => {
    const contentType = file.type || (file.name.toLowerCase().endsWith('.dcm') ? 'application/dicom' : 'application/octet-stream');
    const grant = await api.post<UploadGrant>(`/files/expedientes/${expedienteId}/upload-url`, {
      filename: file.name,
      content_type: contentType,
      size_bytes: file.size,
      category,
    });
    const form = new FormData();
    Object.entries(grant.upload_fields).forEach(([key, value]) => form.append(key, value));
    form.append('file', file);
    const uploadResponse = await fetch(grant.upload_url, { method: 'POST', body: form });
    if (!uploadResponse.ok) {
      throw new Error('S3 no pudo completar la carga del archivo');
    }
    return api.post<ClinicalFile>(`/files/${grant.file_id}/complete`);
  },
  downloadUrl: (fileId: string): Promise<{ url: string; expires_in: number }> =>
    api.get(`/files/${fileId}/download-url`),
  archive: (fileId: string): Promise<void> => api.delete(`/files/${fileId}`),
};

export const recetasApi = {
  getByNotaId: async (notaId: string): Promise<Receta[]> => {
    return api.get('/recetas', { nota_id: notaId });
  },
  create: async (data: any): Promise<Receta> => {
    return api.post('/recetas', data);
  },
  firmar: async (id: string): Promise<Receta & { verification_url?: string }> => {
    return api.post(`/recetas/${id}/firmar`);
  },
  print: async (id: string): Promise<any> => {
    return api.get(`/recetas/${id}/print`);
  }
};

export const consentimientosApi = {
  templates: async (): Promise<any[]> => api.get('/consentimientos/templates'),
  getByExpedienteId: async (expedienteId: string): Promise<any[]> => {
    return api.get(`/consentimientos/expediente/${expedienteId}`);
  },
  create: async (data: any): Promise<any> => api.post('/consentimientos', data),
  firmarPaciente: async (id: string, data: any): Promise<any> => {
    return api.post(`/consentimientos/${id}/firmar-paciente`, data);
  },
  firmarMedico: async (id: string): Promise<any> => api.post(`/consentimientos/${id}/firmar-medico`),
  print: async (id: string): Promise<any> => api.get(`/consentimientos/${id}/print`),
};

export const messagesApi = {
  logWhatsAppManual: async (data: any): Promise<any> => api.post('/messages/log-whatsapp-manual', data),
  getByPacienteId: async (pacienteId: string): Promise<any[]> => api.get(`/messages/paciente/${pacienteId}`),
};

export const publicApi = {
  verify: async (token: string): Promise<any> => {
    const response = await fetch(`${API_ROOT_URL}/verify/${encodeURIComponent(token)}`);
    if (!response.ok) throw new Error('No se pudo verificar el documento');
    return response.json();
  },
};
