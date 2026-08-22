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
  EncuentroTipo,
  TipoSugerido,
  CIE10,
  MedicoFavorito,
  MedicoFavoritoCreate,
  FavoritoKind,
  NotaPlantilla,
  NotaPlantillaCreate,
  ProcedimientoChecklist,
  ChecklistItem,
  EventoAdverso,
  FotografiaClinica,
  FotografiaCreate,
} from '../types';

// API base URL from environment variable (defaults to local dev)
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000/api/v1';
const API_ROOT_URL = API_BASE_URL.replace(/\/api\/v1\/?$/, '');

let getToken: (() => Promise<string | null>) | null = null;

export const setTokenFetcher = (fetcher: () => Promise<string | null>) => {
  getToken = fetcher;
};

/**
 * checkReadiness — honest server-write signal for degraded mode (Fase 10).
 *
 * Hits the public, unauthenticated `/health/ready`, which does a bounded round
 * trip to PostgreSQL and returns 200 only when writes can be confirmed (503
 * otherwise). Used to decide whether it is safe to sign; never claim a save
 * succeeded without a 2xx from the server.
 */
export async function checkReadiness(signal?: AbortSignal): Promise<boolean> {
  try {
    const response = await fetch(`${API_ROOT_URL}/health/ready`, {
      method: 'GET',
      signal,
      cache: 'no-store',
    });
    return response.ok;
  } catch {
    // Network failure / server unreachable — treat as not ready.
    return false;
  }
}

// Native fetch wrapper
async function fetchClient<T>(
  endpoint: string,
  {
    data,
    params,
    allowReverificationHint = false,
    ...customConfig
  }: {
    data?: any;
    params?: Record<string, string | number>;
    allowReverificationHint?: boolean;
    [key: string]: any;
  } = {}
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
      // Clerk's useReverification hook detects this standard response body and
      // transparently retries the original request after a fresh MFA challenge.
      if (
        allowReverificationHint
        && response.status === 403
        && errBody?.clerk_error?.reason === 'reverification-error'
      ) {
        return errBody as T;
      }
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
  getWithReauthentication: <T>(url: string, params?: any) => fetchClient<T>(url, {
    method: 'GET',
    params,
    allowReverificationHint: true,
  }),
  post: <T>(url: string, data?: any) => fetchClient<T>(url, { method: 'POST', data }),
  postWithReauthentication: <T>(url: string, data?: any) => fetchClient<T>(url, {
    method: 'POST',
    data,
    allowReverificationHint: true,
  }),
  put: <T>(url: string, data?: any) => fetchClient<T>(url, { method: 'PUT', data }),
  putWithReauthentication: <T>(url: string, data?: any) => fetchClient<T>(url, {
    method: 'PUT',
    data,
    allowReverificationHint: true,
  }),
  patch: <T>(url: string, data?: any) => fetchClient<T>(url, { method: 'PATCH', data }),
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
    return api.putWithReauthentication('/auth/profile', data);
  },
  onboarding: async (data: { nombre_medico: string; cedula: string; especialidad?: string }): Promise<any> => {
    return api.post('/auth/onboarding', data);
  },
  // Fase 13A: UI theme preference (separate from the professional profile).
  setTheme: async (tema: string): Promise<{ tema: string }> => {
    return api.put<{ tema: string }>('/auth/preferences/theme', { tema });
  },
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
    return api.postWithReauthentication(`/notas/${notaId}/firmar`);
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

export const favoritosApi = {
  list: async (kind?: FavoritoKind): Promise<MedicoFavorito[]> =>
    api.get<MedicoFavorito[]>('/favoritos/', kind ? { kind } : undefined),
  create: async (data: MedicoFavoritoCreate): Promise<MedicoFavorito> =>
    api.post<MedicoFavorito>('/favoritos/', data),
  update: async (id: string, data: { label: string; texto: string }): Promise<MedicoFavorito> =>
    api.put<MedicoFavorito>(`/favoritos/${id}`, data),
  remove: async (id: string): Promise<void> => api.delete<void>(`/favoritos/${id}`),
};

export const plantillasNotaApi = {
  list: async (): Promise<NotaPlantilla[]> => api.get<NotaPlantilla[]>('/plantillas-nota/'),
  create: async (data: NotaPlantillaCreate): Promise<NotaPlantilla> =>
    api.post<NotaPlantilla>('/plantillas-nota/', data),
  update: async (id: string, data: NotaPlantillaCreate): Promise<NotaPlantilla> =>
    api.put<NotaPlantilla>(`/plantillas-nota/${id}`, data),
  remove: async (id: string): Promise<void> => api.delete<void>(`/plantillas-nota/${id}`),
};

export const procedimientosApi = {
  listChecklists: async (pacienteId: string): Promise<ProcedimientoChecklist[]> =>
    api.get<ProcedimientoChecklist[]>('/procedimientos/checklists', { paciente_id: pacienteId }),
  createChecklist: async (data: {
    paciente_id: string;
    momento: 'pre' | 'post';
    items: ChecklistItem[];
  }): Promise<ProcedimientoChecklist> =>
    api.post<ProcedimientoChecklist>('/procedimientos/checklists', data),
  updateChecklist: async (
    id: string,
    data: { items: ChecklistItem[]; observaciones?: string | null },
  ): Promise<ProcedimientoChecklist> =>
    api.put<ProcedimientoChecklist>(`/procedimientos/checklists/${id}`, data),
  removeChecklist: async (id: string): Promise<void> =>
    api.delete<void>(`/procedimientos/checklists/${id}`),

  listEventos: async (pacienteId: string): Promise<EventoAdverso[]> =>
    api.get<EventoAdverso[]>('/procedimientos/eventos-adversos', { paciente_id: pacienteId }),
  createEvento: async (data: {
    paciente_id: string;
    descripcion: string;
    severidad: 'leve' | 'moderado' | 'grave';
  }): Promise<EventoAdverso> =>
    api.post<EventoAdverso>('/procedimientos/eventos-adversos', data),
  updateEvento: async (
    id: string,
    data: { descripcion: string; severidad: 'leve' | 'moderado' | 'grave'; estado: 'abierto' | 'resuelto'; manejo?: string | null },
  ): Promise<EventoAdverso> =>
    api.put<EventoAdverso>(`/procedimientos/eventos-adversos/${id}`, data),
};

export const fotografiasApi = {
  list: async (pacienteId: string): Promise<FotografiaClinica[]> =>
    api.get<FotografiaClinica[]>('/fotografias/', { paciente_id: pacienteId }),
  create: async (data: FotografiaCreate): Promise<FotografiaClinica> =>
    api.post<FotografiaClinica>('/fotografias/', data),
  update: async (
    id: string,
    data: Omit<FotografiaCreate, 'paciente_id' | 'clinical_file_id'>,
  ): Promise<FotografiaClinica> => api.put<FotografiaClinica>(`/fotografias/${id}`, data),
  remove: async (id: string): Promise<void> => api.delete<void>(`/fotografias/${id}`),
};

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
  corregirTipo: async (
    id: string,
    tipo: EncuentroTipo,
    motivoCorreccion: string,
  ): Promise<Encuentro> => {
    return api.patch<Encuentro>(`/encuentros/${id}/tipo`, {
      tipo,
      motivo_correccion: motivoCorreccion,
    });
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
    api.getWithReauthentication(`/files/${fileId}/download-url`),
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
    return api.postWithReauthentication(`/recetas/${id}/firmar`);
  },
  print: async (id: string): Promise<any> => {
    return api.get(`/recetas/${id}/print`);
  }
};

export const consentimientosApi = {
  templates: async (): Promise<any[]> => api.get('/consentimientos/templates'),
  credencialesFirma: async (): Promise<any[]> => api.get('/consentimientos/credenciales-firma'),
  getByExpedienteId: async (expedienteId: string): Promise<any[]> => {
    return api.get(`/consentimientos/expediente/${expedienteId}`);
  },
  create: async (data: any): Promise<any> => api.post('/consentimientos', data),
  firmarPaciente: async (id: string, data: any): Promise<any> => {
    return api.post(`/consentimientos/${id}/firmar-paciente`, data);
  },
  firmarMedico: async (id: string, credencialId?: string): Promise<any> => api.postWithReauthentication(
    `/consentimientos/${id}/firmar-medico`,
    credencialId ? { credencial_id: credencialId } : undefined,
  ),
  revocar: async (id: string, motivo: string): Promise<any> => api.postWithReauthentication(
    `/consentimientos/${id}/revocar`,
    { motivo },
  ),
  print: async (id: string): Promise<any> => api.get(`/consentimientos/${id}/print`),
};

// Exportación «Descargar todo» — portabilidad de datos (sin gate por plan).
// Ambos endpoints exigen reautenticación (step-up MFA): los componentes deben
// envolver estas llamadas con useReverification, igual que la firma de notas.
export interface ExportIndexPaciente {
  paciente_id: string;
  nombre_completo: string;
  expediente_id: string;
  folio: string;
  conteos: Record<string, number>;
  exportacion_url: string;
}

export interface ExportIndexConsultorio {
  formato_version: string;
  generado_en: string;
  consultorio: { nombre_medico: string; cedula: string | null; especialidad: string | null };
  pacientes: ExportIndexPaciente[];
  next_cursor: string | null;
}

export const exportacionApi = {
  indiceConsultorio: async (cursor?: string): Promise<ExportIndexConsultorio> =>
    api.getWithReauthentication<ExportIndexConsultorio>(
      '/exportacion/consultorio',
      cursor ? { cursor } : undefined,
    ),
  expediente: async (expedienteId: string): Promise<any> =>
    api.getWithReauthentication(`/expedientes/${expedienteId}/exportacion`),
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
