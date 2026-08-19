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
  diagnosticos_cie10?: NotaDiagnosticoCie10[];
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
  diagnosticos_cie10?: NotaDiagnosticoCie10[];
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
  // Fase 2: optional link to the clinical encounter, written only at creation.
  encuentro_clinico_id?: string | null;
  tipo_nota: string;
  contenido: NotaContenido;
  signos_vitales: SignosVitales;
  diagnosticos: string[];
  tratamiento: string;
  diagnostico_cie10?: string;
  diagnosticos_cie10?: NotaDiagnosticoCie10Input[];
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

// ── Médico favoritos (Fase 13) ──

export type FavoritoKind = 'diagnostico' | 'plan' | 'indicacion' | 'receta';

export interface MedicoFavorito {
  id: string;
  kind: FavoritoKind;
  label: string;
  texto: string;
  creado_en: string;
  modificado_en: string;
}

export interface MedicoFavoritoCreate {
  kind: FavoritoKind;
  label: string;
  texto: string;
}

// ── Plantillas de nota (Fase 13) ──

export interface NotaPlantilla {
  id: string;
  nombre: string;
  campos: Record<string, string>;
  version: number;
  creado_en: string;
  modificado_en: string;
}

export interface NotaPlantillaCreate {
  nombre: string;
  campos: Record<string, string>;
}

// ── Procedimientos (Fase 13) ──

export interface ChecklistItem {
  texto: string;
  completado: boolean;
}

export interface ProcedimientoChecklist {
  id: string;
  paciente_id: string;
  encuentro_id?: string | null;
  momento: 'pre' | 'post';
  items: ChecklistItem[];
  observaciones?: string | null;
  creado_en: string;
  modificado_en: string;
}

export interface EventoAdverso {
  id: string;
  paciente_id: string;
  encuentro_id?: string | null;
  descripcion: string;
  severidad: 'leve' | 'moderado' | 'grave';
  fecha?: string | null;
  manejo?: string | null;
  estado: 'abierto' | 'resuelto';
  creado_en: string;
  modificado_en: string;
}

// ── CIE-10 ──

export interface CIE10 {
  code: string;
  description: string;
  category?: string;
}

export type Cie10Certeza = 'confirmado' | 'presuntivo' | 'descartado';

export interface NotaDiagnosticoCie10Input {
  code: string;
  es_principal: boolean;
  certeza: Cie10Certeza;
  orden?: number;
}

export interface NotaDiagnosticoCie10 extends NotaDiagnosticoCie10Input {
  description?: string;
  catalog_version?: string;
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

// ── Encuentros clínicos (Fase 2) ──

export type EncuentroTipo =
  | 'primera_vez'
  | 'subsecuente'
  | 'procedimiento'
  | 'urgencia'
  | 'otro';

export type EncuentroEstado =
  | 'programado'
  | 'iniciado'
  | 'completado'
  | 'cancelado';

export interface Encuentro {
  id: string;
  tenant_id: string;
  paciente_id: string;
  expediente_id: string;
  cita_id?: string | null;
  medico_id: string;
  tipo: EncuentroTipo;
  estado: EncuentroEstado;
  clasificacion_origen: string;
  motivo_correccion?: string | null;
  nota_inicial_id?: string | null;
  fecha_inicio?: string | null;
  fecha_fin?: string | null;
  creado_en: string;
  actualizado_en?: string;
}

export interface EncuentroCreate {
  expediente_id: string;
  cita_id?: string | null;
  // Omit to let the backend suggest the type from the patient's history.
  tipo?: EncuentroTipo;
}

export interface TipoSugerido {
  paciente_id: string;
  tipo_sugerido: EncuentroTipo;
}
