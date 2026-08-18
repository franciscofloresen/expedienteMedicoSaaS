import { describe, it, expect } from 'vitest';
import { computeAgeYears, formatSexo, formatIdentityLine } from './patient';

const NOW = new Date('2026-08-18T12:00:00');

describe('computeAgeYears', () => {
  it('computes full years for a past birthday this year', () => {
    expect(computeAgeYears('1990-01-01', NOW)).toBe(36);
  });

  it('subtracts a year when the birthday has not occurred yet', () => {
    expect(computeAgeYears('1990-12-31', NOW)).toBe(35);
  });

  it('is 0 for an infant born earlier the same year', () => {
    expect(computeAgeYears('2026-02-01', NOW)).toBe(0);
  });

  it('returns null for a future date of birth', () => {
    expect(computeAgeYears('2027-01-01', NOW)).toBeNull();
  });

  it('returns null for empty or unparseable input', () => {
    expect(computeAgeYears('', NOW)).toBeNull();
    expect(computeAgeYears('not-a-date', NOW)).toBeNull();
  });
});

describe('formatSexo', () => {
  it('maps M/F and defaults unknown to Otro', () => {
    expect(formatSexo('M')).toBe('Masculino');
    expect(formatSexo('F')).toBe('Femenino');
    expect(formatSexo('X')).toBe('Otro');
    expect(formatSexo(undefined)).toBe('Otro');
  });
});

describe('formatIdentityLine', () => {
  it('joins name, age, sex and CURP', () => {
    expect(
      formatIdentityLine(
        { nombre_completo: 'Ana López', fecha_nacimiento: '1990-01-01', sexo: 'F', curp: 'LOPA900101MDFXYZ01' },
        NOW,
      ),
    ).toBe('Ana López · 36 a · Femenino · LOPA900101MDFXYZ01');
  });

  it('falls back to "sin CURP" and omits age when unknown', () => {
    expect(
      formatIdentityLine({ nombre_completo: 'Sin Fecha', fecha_nacimiento: '', sexo: 'M' }, NOW),
    ).toBe('Sin Fecha · Masculino · sin CURP');
  });
});
