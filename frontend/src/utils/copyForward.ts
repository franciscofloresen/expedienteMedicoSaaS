/**
 * copyForward — build a NEW-draft seed from a previous consult (Fase 13).
 *
 * Roadmap constraint: "copiar desde consulta previa sólo como borrador… nunca
 * clonar fechas, signos o exploración sin revisión." So this copies ONLY the
 * narrative continuity fields (motivo and plan) and NEVER vital signs, physical
 * exam, diagnosis codes, or any date — those must be re-taken/re-evaluated each
 * visit. The copied fields are seeded into an editable draft the doctor must
 * review and save; nothing is persisted automatically.
 */
import type { Nota } from '../types';

export interface CopyForwardDraft {
  motivo_consulta?: string;
  plan_tratamiento?: string;
}

export function buildCopyForwardDraft(source: Nota): CopyForwardDraft {
  const motivo =
    source.motivo_consulta || source.contenido?.evolucion_y_actualizacion_cuadro || undefined;
  const plan = source.plan_tratamiento || source.contenido?.tratamiento || undefined;

  const draft: CopyForwardDraft = {};
  if (motivo) draft.motivo_consulta = motivo;
  if (plan) draft.plan_tratamiento = plan;
  return draft;
}
