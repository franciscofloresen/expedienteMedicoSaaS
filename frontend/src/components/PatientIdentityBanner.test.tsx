import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import PatientIdentityBanner from './PatientIdentityBanner';
import type { Paciente } from '../types';

const paciente = {
  nombre_completo: 'Ana López',
  fecha_nacimiento: '1990-01-01',
  sexo: 'F',
  curp: 'LOPA900101MDFXYZ01',
} as Pick<Paciente, 'nombre_completo' | 'fecha_nacimiento' | 'sexo' | 'curp'>;

describe('PatientIdentityBanner', () => {
  it('renders name, sex and the second identifier (CURP)', () => {
    render(<PatientIdentityBanner paciente={paciente} />);
    expect(screen.getByText('Ana López')).toBeInTheDocument();
    expect(screen.getByText('Femenino')).toBeInTheDocument();
    expect(screen.getByText('LOPA900101MDFXYZ01')).toBeInTheDocument();
  });

  it('shows the date of birth for cross-checking', () => {
    render(<PatientIdentityBanner paciente={paciente} />);
    expect(screen.getByText(/1990-01-01/)).toBeInTheDocument();
  });

  it('renders a context label at the moment of signing', () => {
    render(<PatientIdentityBanner paciente={paciente} context="firma" />);
    expect(screen.getByText(/Vas a firmar para/i)).toBeInTheDocument();
  });

  it('renders nothing when no patient is provided', () => {
    const { container } = render(<PatientIdentityBanner paciente={null} />);
    expect(container).toBeEmptyDOMElement();
  });
});
