import { describe, it, expect } from 'vitest';
import { buildCopyForwardDraft } from './copyForward';
import type { Nota } from '../types';

const fullNote = {
  id: 'n1',
  tipo_nota: 'evolucion',
  contenido: { evolucion_y_actualizacion_cuadro: 'Motivo previo', tratamiento: 'Plan previo' },
  signos_vitales: { frecuencia_cardiaca: 80, tension_arterial: '120/80' },
  motivo_consulta: 'Control de hipertensión',
  exploracion_fisica: 'Abdomen blando',
  plan_tratamiento: 'Continuar losartán 50 mg',
  diagnostico_cie10: 'I10',
  firmada: true,
  es_editable: false,
  creado_en: '2026-01-01T10:00:00Z',
} as unknown as Nota;

describe('buildCopyForwardDraft', () => {
  it('copies only the narrative continuity fields (motivo + plan)', () => {
    const draft = buildCopyForwardDraft(fullNote);
    expect(draft).toEqual({
      motivo_consulta: 'Control de hipertensión',
      plan_tratamiento: 'Continuar losartán 50 mg',
    });
  });

  it('NEVER carries vitals, physical exam, diagnosis, or dates', () => {
    const draft = buildCopyForwardDraft(fullNote) as Record<string, unknown>;
    expect(draft.signos_vitales).toBeUndefined();
    expect(draft.exploracion_fisica).toBeUndefined();
    expect(draft.diagnostico_cie10).toBeUndefined();
    expect(draft.creado_en).toBeUndefined();
    expect(Object.keys(draft).sort()).toEqual(['motivo_consulta', 'plan_tratamiento']);
  });

  it('falls back to contenido fields and omits empty ones', () => {
    const note = {
      id: 'n2',
      tipo_nota: 'evolucion',
      contenido: { tratamiento: 'Reposo' },
      firmada: false,
      es_editable: true,
      creado_en: '2026-02-01T10:00:00Z',
    } as unknown as Nota;
    expect(buildCopyForwardDraft(note)).toEqual({ plan_tratamiento: 'Reposo' });
  });

  it('returns an empty object when there is nothing to copy', () => {
    const note = {
      id: 'n3',
      tipo_nota: 'evolucion',
      contenido: {},
      firmada: false,
      es_editable: true,
      creado_en: '2026-02-01T10:00:00Z',
    } as unknown as Nota;
    expect(buildCopyForwardDraft(note)).toEqual({});
  });
});
