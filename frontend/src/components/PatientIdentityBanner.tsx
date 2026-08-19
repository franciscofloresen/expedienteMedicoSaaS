/**
 * PatientIdentityBanner — always-visible patient identity at the moments where a
 * wrong-patient error is most costly: capturing a note, prescribing, and signing
 * (Fase 12 §1). Shows name, age + date of birth, sex, and a second identifier
 * (CURP). Read-only; it never mutates data.
 */
import { UserRound } from 'lucide-react';
import { computeAgeYears, formatSexo } from '../utils/patient';
import type { Paciente } from '../types';

export default function PatientIdentityBanner({
  paciente,
  context,
}: {
  paciente: Pick<Paciente, 'nombre_completo' | 'fecha_nacimiento' | 'sexo' | 'curp'> | null | undefined;
  context?: 'captura' | 'receta' | 'firma';
}) {
  if (!paciente) return null;
  const age = computeAgeYears(paciente.fecha_nacimiento);

  const contextLabel =
    context === 'firma' ? 'Vas a firmar para' :
    context === 'receta' ? 'Vas a recetar para' :
    context === 'captura' ? 'Estás documentando a' : undefined;

  return (
    <div
      className="patient-identity-banner"
      role="group"
      aria-label="Identidad del paciente"
      data-testid="patient-identity-banner"
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '0.75rem',
        padding: '0.6rem 0.85rem',
        border: '1px solid var(--color-border)',
        borderLeft: '3px solid var(--color-primary, #2563eb)',
        borderRadius: '8px',
        background: 'var(--color-surface, rgba(0,0,0,0.02))',
        marginBottom: '1rem',
        flexWrap: 'wrap',
      }}
    >
      <UserRound size={18} style={{ flexShrink: 0 }} aria-hidden="true" />
      <div style={{ display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        {contextLabel && (
          <span className="overline" style={{ fontSize: '0.7rem' }}>{contextLabel}</span>
        )}
        <strong style={{ fontSize: '0.98rem' }}>{paciente.nombre_completo}</strong>
      </div>
      <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap', fontSize: '0.85rem', color: 'var(--color-muted)' }}>
        <span>
          <span className="overline" style={{ fontSize: '0.65rem', marginRight: '0.3rem' }}>Edad</span>
          {age === null ? '—' : `${age} años`} ({paciente.fecha_nacimiento})
        </span>
        <span>
          <span className="overline" style={{ fontSize: '0.65rem', marginRight: '0.3rem' }}>Sexo</span>
          {formatSexo(paciente.sexo)}
        </span>
        <span className="mono">
          <span className="overline" style={{ fontSize: '0.65rem', marginRight: '0.3rem' }}>CURP</span>
          {paciente.curp || '—'}
        </span>
      </div>
    </div>
  );
}
