import axios from 'axios';

// En desarrollo local, usamos un JWT "mock" o simplemente omitimos auth
// si el backend tiene el tenant fijo. Para simplificar, configuramos el backend
// local para leer el tenant de los headers o de un token de prueba.
export const api = axios.create({
  baseURL: 'http://127.0.0.1:8000/api/v1',
  headers: {
    'Content-Type': 'application/json',
  },
});

// Mock interceptor para inyectar un tenant_id en local (simulando JWT)
// En producción, aquí inyectarías el accessToken de Cognito.
api.interceptors.request.use((config) => {
  // Simulando un token que el backend decodificará 
  // O como lo tengamos configurado localmente.
  // Por ahora, asumimos que el backend acepta un header X-Tenant-ID para dev
  config.headers['X-Tenant-ID'] = '00000000-0000-0000-0000-000000000000';
  return config;
});

// Servicios de Pacientes
export const pacientesApi = {
  getAll: async () => {
    const res = await api.get('/pacientes/');
    return res.data;
  },
  create: async (data: any) => {
    const res = await api.post('/pacientes/', data);
    return res.data;
  }
};

export const expedientesApi = {
  getByPacienteId: async (pacienteId: string) => {
    try {
      const res = await api.get(`/expedientes/paciente/${pacienteId}`);
      return res.data;
    } catch (error: any) {
      if (error.response?.status === 404) return null;
      throw error;
    }
  },
  create: async (data: any) => {
    const res = await api.post('/expedientes/', data);
    return res.data;
  }
};

export const notasApi = {
  create: async (data: any) => {
    const res = await api.post('/notas/', data);
    return res.data;
  },
  firmar: async (notaId: string) => {
    const res = await api.post(`/notas/${notaId}/firmar`);
    return res.data;
  }
};
