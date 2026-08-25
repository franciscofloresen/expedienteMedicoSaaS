/**
 * LongitudinalSummary — read-only at-a-glance view of the patient's record
 * (Fase 13). Presentational: takes a computed summary, renders sections.
 */
import type { ReactNode } from 'react';
import { AlertTriangle, CalendarClock, FileCheck2, Info } from 'lucide-react';
import type { LongitudinalSummary as Summary } from '../utils/longitudinalSummary';

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="glass-card" style={{ marginBottom: '1rem' }}>
      <span className="overline" style={{ display: 'block', marginBottom: '0.6rem' }}>{title}</span>
      {children}
    </div>
  );
}

export default function LongitudinalSummary({ summary }: { summary: Summary }) {
  const { identidad, alergiasLegacy, ultimasConsultas, consentimientosVigentes } = summary;

  return (
    <div className="fade-in" data-testid="longitudinal-summary">
      <Section title="Identidad">
        <div style={{ display: 'flex', gap: '1.25rem', flexWrap: 'wrap', fontSize: '0.9rem' }}>
          <span><strong>{identidad.nombre || '—'}</strong></span>
          <span>{identidad.edad === null ? '—' : `${identidad.edad} años`}</span>
          <span>{identidad.sexo}</span>
          <span className="mono">{identidad.curp || 'Sin CURP'}</span>
          {identidad.tipoSangre && <span>Sangre: {identidad.tipoSangre}</span>}
        </div>
      </Section>

      <Section title="Alergias">
        {alergiasLegacy ? (
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--color-danger)' }}>
            <AlertTriangle size={16} /> <span>{alergiasLegacy}</span>
          </div>
        ) : (
          <span className="text-muted">Ninguna registrada.</span>
        )}
      </Section>

      <Section title="Problemas y medicamentos">
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: '0.5rem', fontSize: '0.85rem', color: 'var(--color-muted)' }}>
          <Info size={15} style={{ flexShrink: 0, marginTop: '2px' }} />
          <span>
            La lista estructurada de problemas y medicamentos longitudinales se habilita con
            la captura estructurada (Fase 12). Por ahora consulta las notas firmadas.
          </span>
        </div>
      </Section>

      <Section title={`Últimas consultas (${summary.totalConsultasFirmadas} firmadas)`}>
        {ultimasConsultas.length === 0 ? (
          <span className="text-muted">Sin consultas firmadas.</span>
        ) : (
          <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            {ultimasConsultas.map((c, i) => (
              <li key={i} style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', fontSize: '0.88rem' }}>
                <CalendarClock size={15} style={{ flexShrink: 0, color: 'var(--color-muted)' }} />
                <span style={{ color: 'var(--color-muted)' }}>{new Date(c.fecha).toLocaleDateString()}</span>
                <span style={{ textTransform: 'capitalize' }}>{c.tipo}</span>
                {c.diagnostico && <span className="text-muted">· {c.diagnostico}</span>}
              </li>
            ))}
          </ul>
        )}
      </Section>

      <Section title="Consentimientos vigentes">
        {consentimientosVigentes.length === 0 ? (
          <span className="text-muted">Sin consentimientos vigentes.</span>
        ) : (
          <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            {consentimientosVigentes.map((c, i) => (
              <li key={i} style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', fontSize: '0.88rem' }}>
                <FileCheck2 size={15} style={{ flexShrink: 0, color: 'var(--color-success)' }} />
                <span>{c.procedimiento}</span>
                {c.fecha && <span className="text-muted">· {new Date(c.fecha).toLocaleDateString()}</span>}
              </li>
            ))}
          </ul>
        )}
      </Section>
    </div>
  );
}
