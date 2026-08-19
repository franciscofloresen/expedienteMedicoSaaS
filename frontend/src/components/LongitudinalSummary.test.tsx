import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import LongitudinalSummary from './LongitudinalSummary';
import type { LongitudinalSummary as Summary } from '../utils/longitudinalSummary';

const summary: Summary = {
  identidad: { nombre: 'Ana López', edad: 36, sexo: 'Femenino', curp: 'LOPA900101MDFXYZ01', tipoSangre: 'O+' },
  alergiasLegacy: 'Penicilina',
  ultimasConsultas: [{ fecha: '2026-05-01T10:00:00Z', tipo: 'evolucion', diagnostico: 'Control' }],
  consentimientosVigentes: [{ procedimiento: 'Toxina botulínica', fecha: '2026-06-01' }],
  totalConsultas: 3,
  totalConsultasFirmadas: 2,
};

describe('LongitudinalSummary', () => {
  it('renders identity, allergies, consultations and active consents', () => {
    render(<LongitudinalSummary summary={summary} />);
    expect(screen.getByText('Ana López')).toBeInTheDocument();
    expect(screen.getByText('Penicilina')).toBeInTheDocument();
    expect(screen.getByText(/Toxina botulínica/)).toBeInTheDocument();
    expect(screen.getByText(/2 firmadas/)).toBeInTheDocument();
  });

  it('flags that structured problems/medications arrive with Fase 12', () => {
    render(<LongitudinalSummary summary={summary} />);
    expect(screen.getByText(/captura estructurada \(Fase 12\)/i)).toBeInTheDocument();
  });
});
