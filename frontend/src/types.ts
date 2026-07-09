/**
 * CloudMedRecord Frontend — API Data Transfer Objects
 *
 * These types mirror the backend Pydantic/SQLAlchemy schemas.
 * Keep in sync with backend model changes.
 */

// ── Pacientes ──

export interface Paciente {
  id: string;
  nombre_completo: string;
  sexo: 'M' | 'F' | 'X';
  fecha_nacimiento: string;
  curp?: string;
  domicilio?: string;
  telefono?: string;
  email?: string;
  ocupacion?: string;
  aseguradora?: string;
  num_poliza?: string;
  contacto_emergencia?: string;
  telefono_emergencia?: string;
  tipo_sangre?: string;
  alergias?: string;
  creado_en: string;
  activo: boolean;
}

export interface PacienteCreate {
  nombre_completo: string;
  sexo: 'M' | 'F' | 'X';
  fecha_nacimiento: string;
  curp?: string;
  telefono?: string;
  email?: string;
  domicilio?: string;
  ocupacion?: string;
  contacto_emergencia?: string;
  telefono_emergencia?: string;
  tipo_sangre?: string;
  alergias?: string;
}

export interface PacienteUpdate {
  nombre_completo?: string;
  sexo?: 'M' | 'F' | 'X';
  fecha_nacimiento?: string;
  curp?: string;
  telefono?: string;
  email?: string;
  domicilio?: string;
  ocupacion?: string;
  contacto_emergencia?: string;
  telefono_emergencia?: string;
  tipo_sangre?: string;
  alergias?: string;
}

// ── Expedientes ──

export interface Expediente {
  id: string;
  paciente_id: string;
  numero_expediente: string;
  antecedentes?: string;
  creado_en: string;
}

export interface ExpedienteCreate {
  paciente_id: string;
}

// ── Notas Médicas ──

export interface SignosVitales {
  frecuencia_cardiaca?: number;
  frecuencia_respiratoria?: number;
  temperatura?: number;
  tension_arterial?: string;
}

export interface NotaContenido {
  evolucion_y_actualizacion_cuadro?: string;
  diagnosticos?: string[];
  tratamiento?: string;
  contenido?: string;
  [key: string]: unknown;
}

export interface Nota {
  id: string;
  tipo_nota: string;
  contenido: NotaContenido;
  signos_vitales?: SignosVitales;
  motivo_consulta?: string;
  exploracion_fisica?: string;
  plan_tratamiento?: string;
  diagnostico_cie10?: string;
  estado?: string;
  firmada: boolean;
  es_editable: boolean;
  firmado_en?: string;
  medico_nombre?: string;
  medico_cedula?: string;
  medico_especialidad?: string;
  firma_hash_contenido?: string;
  firma_algoritmo?: string;
  creado_en: string;
}

export interface NotaCreate {
  expediente_id: string;
  tipo_nota: string;
  contenido: NotaContenido;
  signos_vitales: SignosVitales;
  diagnosticos: string[];
  tratamiento: string;
  diagnostico_cie10?: string;
  motivo_consulta?: string;
  exploracion_fisica?: string;
  plan_tratamiento?: string;
}

// ── Recetas ──

export interface Receta {
  id: string;
  nota_id: string;
  medicamentos: Record<string, unknown>[]; // JSON array
  indicaciones_generales?: string;
  creado_en: string;
  firmada?: boolean;
  firmada_en?: string;
  firma_hash_contenido?: string;
  firma_algoritmo?: string;
  es_editable?: boolean;
  medico_nombre?: string;
  medico_cedula?: string;
  medico_especialidad?: string;
}

export interface RecetaCreate {
  nota_id: string;
  medicamentos: Record<string, unknown>[];
  indicaciones_generales?: string;
}

// ── CIE-10 ──

export interface CIE10 {
  code: string;
  description: string;
  category?: string;
}

// ── API Responses ──

export interface ApiError {
  detail: string;
}

export interface CitaBase {
  paciente_id?: string | null;
  titulo: string;
  fecha_inicio: string;
  fecha_fin: string;
  estado: string;
  notas?: string | null;
}

export interface Cita extends CitaBase {
  id: string;
  tenant_id: string;
  creado_en: string;
  modificado_en: string;
  
  // Useful for frontend only
  paciente?: Paciente;
}
