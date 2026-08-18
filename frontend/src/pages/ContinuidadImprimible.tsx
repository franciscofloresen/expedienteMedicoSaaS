/**
 * ContinuidadImprimible — printable clinical-continuity format (Fase 10).
 *
 * When the system cannot confirm a save, the practice records the encounter on
 * this form (on paper or filled here then printed) and reconciles it afterwards,
 * preserving the ORIGINAL author and time of attention. It never claims the data
 * was stored in the record; it is explicitly a temporary document to reconcile.
 *
 * Deliberately server-independent: it holds state only in memory (no
 * localStorage — no PHI at rest on the device) so it works during an outage.
 */
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Printer, ArrowLeft, AlertTriangle } from 'lucide-react';

function Field({
  label,
  value,
  onChange,
  lines = 1,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  lines?: number;
  placeholder?: string;
}) {
  return (
    <label style={{ display: 'block', marginBottom: '0.9rem' }}>
      <span className="overline" style={{ display: 'block', marginBottom: '0.3rem' }}>
        {label}
      </span>
      {lines > 1 ? (
        <textarea
          value={value}
          onChange={(e) => onChange(e.target.value)}
          rows={lines}
          placeholder={placeholder}
          style={{ width: '100%', resize: 'vertical', fontFamily: 'inherit', padding: '0.5rem' }}
        />
      ) : (
        <input
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          style={{ width: '100%', padding: '0.5rem' }}
        />
      )}
    </label>
  );
}

export default function ContinuidadImprimible() {
  const navigate = useNavigate();
  const [f, setF] = useState({
    fechaHoraAtencion: '',
    paciente: '',
    identificador: '',
    medico: '',
    cedula: '',
    motivo: '',
    hallazgos: '',
    diagnostico: '',
    plan: '',
    receta: '',
  });
  const set = (k: keyof typeof f) => (v: string) => setF((prev) => ({ ...prev, [k]: v }));

  return (
    <div className="fade-in">
      <div className="no-print" style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem' }}>
        <button className="btn btn-outline" onClick={() => navigate(-1)} aria-label="Volver">
          <ArrowLeft size={15} /> Volver
        </button>
        <button className="btn btn-primary" onClick={() => window.print()}>
          <Printer size={15} /> Imprimir formato
        </button>
      </div>

      <div
        role="note"
        style={{
          border: '2px solid var(--color-danger, #b42318)',
          borderRadius: '8px',
          padding: '0.85rem 1rem',
          marginBottom: '1.25rem',
          display: 'flex',
          gap: '0.6rem',
          alignItems: 'flex-start',
        }}
      >
        <AlertTriangle size={18} style={{ flexShrink: 0, marginTop: '2px' }} />
        <div style={{ fontSize: '0.9rem' }}>
          <strong>Registro temporal de continuidad.</strong> Este documento se usa cuando el
          sistema no puede confirmar el guardado. <strong>No</strong> forma parte del
          expediente hasta conciliarlo después, conservando el autor y la hora
          <strong> originales</strong> de la atención. No sustituye la firma electrónica ni
          el registro definitivo.
        </div>
      </div>

      <div className="glass-card" style={{ maxWidth: '820px' }}>
        <h1 className="font-serif" style={{ fontSize: '1.3rem', margin: '0 0 0.25rem' }}>
          Formato de continuidad clínica
        </h1>
        <p className="text-muted" style={{ fontSize: '0.85rem', marginTop: 0 }}>
          Complete durante la contingencia. Al restablecerse el sistema, transcriba la
          atención con esta misma fecha y hora, y archive este formato como evidencia.
        </p>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '0 1.5rem' }}>
          <Field label="Fecha y hora reales de atención" value={f.fechaHoraAtencion} onChange={set('fechaHoraAtencion')} placeholder="dd/mm/aaaa hh:mm" />
          <Field label="Paciente (nombre completo)" value={f.paciente} onChange={set('paciente')} />
          <Field label="Identificador (CURP / expediente)" value={f.identificador} onChange={set('identificador')} />
          <Field label="Médico tratante" value={f.medico} onChange={set('medico')} />
          <Field label="Cédula profesional" value={f.cedula} onChange={set('cedula')} />
        </div>

        <Field label="Motivo de consulta" value={f.motivo} onChange={set('motivo')} lines={2} />
        <Field label="Exploración / hallazgos" value={f.hallazgos} onChange={set('hallazgos')} lines={4} />
        <Field label="Diagnóstico" value={f.diagnostico} onChange={set('diagnostico')} lines={2} />
        <Field label="Plan e indicaciones" value={f.plan} onChange={set('plan')} lines={4} />
        <Field label="Receta (medicamento, dosis, vía, frecuencia, duración)" value={f.receta} onChange={set('receta')} lines={4} />

        <div style={{ marginTop: '2.5rem', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2rem' }}>
          <div style={{ borderTop: '1px solid var(--color-text)', paddingTop: '0.4rem', fontSize: '0.82rem' }}>
            Firma autógrafa del médico
          </div>
          <div style={{ borderTop: '1px solid var(--color-text)', paddingTop: '0.4rem', fontSize: '0.82rem' }}>
            Conciliado en el sistema por / fecha
          </div>
        </div>
      </div>
    </div>
  );
}
