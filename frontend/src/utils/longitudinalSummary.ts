/**
 * longitudinalSummary — read-only aggregation of a patient's record (Fase 13
 * "Resumen longitudinal"). Pure and testable; the parent passes already-loaded
 * data.
 *
 * Structured allergies / problems / medications arrive with Fase 12; until then
 * this surfaces the legacy free-text allergies plus what already exists (signed
 * consultations, active consents). Files live in their own tab.
 */
import type { Nota, Paciente } from '../types';
import { computeAgeYears, formatSexo } from './patient';

export interface SummaryConsult {
  fecha: string;
  tipo: string;
  diagnostico?: string;
}

export interface SummaryConsent {
  procedimiento: string;
  fecha?: string;
}

export interface LongitudinalSummary {
  identidad: {
    nombre: string;
    edad: number | null;
    sexo: string;
    curp?: string;
    tipoSangre?: string;
  };
  alergiasLegacy?: string;
  ultimasConsultas: SummaryConsult[];
  consentimientosVigentes: SummaryConsent[];
  totalConsultas: number;
  totalConsultasFirmadas: number;
}

interface ConsentLike {
  procedimiento?: string;
  status?: string;
  revocacion?: unknown;
  creado_en?: string;
  firmado_paciente_en?: string;
}

type PacienteLike = Pick<
  Paciente,
  'nombre_completo' | 'fecha_nacimiento' | 'sexo' | 'curp' | 'tipo_sangre' | 'alergias'
>;

function noteDate(n: Nota): string {
  return (n as { firmado_en?: string }).firmado_en || n.creado_en;
}

export function buildLongitudinalSummary(
  paciente: PacienteLike | null | undefined,
  notas: Nota[],
  consentimientos: ConsentLike[],
  opts: { maxConsultas?: number; now?: Date } = {},
): LongitudinalSummary {
  const maxConsultas = opts.maxConsultas ?? 5;

  const firmadas = notas.filter((n) => n.firmada);
  const ultimasConsultas = [...firmadas]
    .sort((a, b) => new Date(noteDate(b)).getTime() - new Date(noteDate(a)).getTime())
    .slice(0, maxConsultas)
    .map((n) => ({
      fecha: noteDate(n),
      tipo: n.tipo_nota,
      diagnostico: n.diagnostico_cie10 || n.motivo_consulta || undefined,
    }));

  const consentimientosVigentes = consentimientos
    .filter((c) => c.status === 'signed' && !c.revocacion)
    .map((c) => ({
      procedimiento: c.procedimiento || 'Consentimiento',
      fecha: c.firmado_paciente_en || c.creado_en,
    }));

  return {
    identidad: {
      nombre: paciente?.nombre_completo ?? '',
      edad: paciente?.fecha_nacimiento
        ? computeAgeYears(paciente.fecha_nacimiento, opts.now)
        : null,
      sexo: formatSexo(paciente?.sexo),
      curp: paciente?.curp || undefined,
      tipoSangre: paciente?.tipo_sangre || undefined,
    },
    alergiasLegacy: paciente?.alergias || undefined,
    ultimasConsultas,
    consentimientosVigentes,
    totalConsultas: notas.length,
    totalConsultasFirmadas: firmadas.length,
  };
}
