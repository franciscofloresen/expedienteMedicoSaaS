import { describe, it, expect } from 'vitest';
import { buildLongitudinalSummary } from './longitudinalSummary';
import type { Nota, Paciente } from '../types';

const NOW = new Date('2026-08-18T12:00:00');

const paciente = {
  nombre_completo: 'Ana López',
  fecha_nacimiento: '1990-01-01',
  sexo: 'F',
  curp: 'LOPA900101MDFXYZ01',
  tipo_sangre: 'O+',
  alergias: 'Penicilina',
} as Paciente;

function nota(over: Partial<Nota>): Nota {
  return {
    id: Math.random().toString(),
    tipo_nota: 'evolucion',
    contenido: {},
    firmada: false,
    es_editable: true,
    creado_en: '2026-01-01T10:00:00Z',
    ...over,
  } as Nota;
}

describe('buildLongitudinalSummary', () => {
  it('summarizes identity, legacy allergies and consultation totals', () => {
    const s = buildLongitudinalSummary(paciente, [nota({ firmada: true }), nota({})], []);
    expect(s.identidad).toEqual({
      nombre: 'Ana López',
      edad: 36,
      sexo: 'Femenino',
      curp: 'LOPA900101MDFXYZ01',
      tipoSangre: 'O+',
    });
    expect(s.alergiasLegacy).toBe('Penicilina');
    expect(s.totalConsultas).toBe(2);
    expect(s.totalConsultasFirmadas).toBe(1);
  });

  it('lists only signed consultations, newest first, limited', () => {
    const notas = [
      nota({ firmada: true, creado_en: '2026-03-01T10:00:00Z', diagnostico_cie10: 'I10' }),
      nota({ firmada: false, creado_en: '2026-04-01T10:00:00Z' }),
      nota({ firmada: true, creado_en: '2026-05-01T10:00:00Z', motivo_consulta: 'Control' }),
    ];
    const s = buildLongitudinalSummary(paciente, notas, [], { maxConsultas: 1, now: NOW });
    expect(s.ultimasConsultas).toHaveLength(1);
    expect(s.ultimasConsultas[0].fecha).toBe('2026-05-01T10:00:00Z'); // newest signed
    expect(s.ultimasConsultas[0].diagnostico).toBe('Control');
  });

  it('lists only active (signed, non-revoked) consents', () => {
    const consents = [
      { procedimiento: 'Toxina botulínica', status: 'signed', revocacion: null, firmado_paciente_en: '2026-06-01' },
      { procedimiento: 'Peeling', status: 'signed', revocacion: { id: 'r1' } }, // revoked
      { procedimiento: 'Láser', status: 'pending' }, // not signed
    ];
    const s = buildLongitudinalSummary(paciente, [], consents);
    expect(s.consentimientosVigentes).toEqual([
      { procedimiento: 'Toxina botulínica', fecha: '2026-06-01' },
    ]);
  });

  it('handles a missing patient without throwing', () => {
    const s = buildLongitudinalSummary(null, [], []);
    expect(s.identidad.nombre).toBe('');
    expect(s.identidad.edad).toBeNull();
    expect(s.alergiasLegacy).toBeUndefined();
  });
});
