/* eslint-disable react-hooks/set-state-in-effect */
import React, { useState, useEffect } from 'react';
import { X } from 'lucide-react';
import type { Paciente, CitaBase, Cita } from '../types';

interface CitaModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSave: (data: CitaBase) => void;
  onDelete?: (id: string) => void;
  cita: Partial<Cita> | null;
  pacientes: Paciente[];
  citas?: Cita[];
}

export default function CitaModal({ isOpen, onClose, onSave, onDelete, cita, pacientes, citas = [] }: CitaModalProps) {
  const [titulo, setTitulo] = useState('');
  const [pacienteId, setPacienteId] = useState('');
  const [fechaInicio, setFechaInicio] = useState('');
  const [fechaFin, setFechaFin] = useState('');
  const [notas, setNotas] = useState('');

  const [error, setError] = useState('');

  useEffect(() => {
    if (isOpen && cita) {
      setTitulo(cita.titulo || '');
      setPacienteId(cita.paciente_id || '');
      
      // Format dates for datetime-local input (YYYY-MM-DDThh:mm)
      if (cita.fecha_inicio) {
        const d = new Date(cita.fecha_inicio);
        setFechaInicio(new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16));
      }
      if (cita.fecha_fin) {
        const d = new Date(cita.fecha_fin);
        setFechaFin(new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16));
      }
      
      setNotas(cita.notas || '');
      setError('');
    } else if (isOpen) {
      setTitulo('');
      setPacienteId('');
      setFechaInicio('');
      setFechaFin('');
      setNotas('');
      setError('');
    }
  }, [isOpen, cita]);

  const dialogRef = React.useRef<HTMLDialogElement>(null);

  useEffect(() => {
    if (isOpen) {
      if (!dialogRef.current?.open) {
        dialogRef.current?.showModal();
      }
    } else {
      dialogRef.current?.close();
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    const start = new Date(fechaInicio);
    const end = new Date(fechaFin);

    if (start >= end) {
      setError('La fecha y hora de fin debe ser posterior al inicio.');
      return;
    }

    const overlap = citas.find(c => {
      if (cita?.id && c.id === cita.id) return false;
      const cStart = new Date(c.fecha_inicio);
      const cEnd = new Date(c.fecha_fin);
      return start < cEnd && end > cStart;
    });

    if (overlap) {
      setError('Ya existe una cita programada en ese horario exacto o intermedio.');
      return;
    }

    onSave({
      titulo,
      paciente_id: pacienteId || null,
      fecha_inicio: start.toISOString(),
      fecha_fin: end.toISOString(),
      estado: cita?.estado || 'Programada',
      notas
    });
  };


  return (
    <dialog
      ref={dialogRef}
      onCancel={onClose}
      style={{
        padding: '2rem',
        borderRadius: '16px',
        width: '100%',
        maxWidth: '500px',
        backgroundColor: 'var(--bg-card)',
        color: 'var(--text-main)',
        border: 'none',
        boxShadow: 'var(--shadow-lg)'
      }}
      className="cita-modal"
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
        <h2 style={{ margin: 0, fontSize: '1.25rem', color: 'var(--text-main)' }}>
          {cita?.id ? 'Editar Cita' : 'Nueva Cita'}
        </h2>
        <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)' }}>
          <X size={20} />
        </button>
      </div>

      <form method="dialog" onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        {error && (
          <div style={{ padding: '0.75rem', borderRadius: '8px', backgroundColor: '#fee2e2', color: '#dc2626', fontSize: '0.875rem', fontWeight: 500 }}>
            {error}
          </div>
        )}
        
        <div>
          <label style={{ display: 'block', marginBottom: '0.5rem', fontSize: '0.875rem', color: 'var(--text-muted)' }}>Título</label>
          <input 
            required type="text" value={titulo} onChange={e => setTitulo(e.target.value)}
            style={{ width: '100%', padding: '0.75rem', borderRadius: '8px', border: '1px solid var(--border-light)', backgroundColor: 'var(--bg-app)', color: 'var(--text-main)', boxSizing: 'border-box' }}
            placeholder="Ej. Consulta General"
          />
        </div>

        <div>
          <label style={{ display: 'block', marginBottom: '0.5rem', fontSize: '0.875rem', color: 'var(--text-muted)' }}>Paciente (Opcional)</label>
          <select 
            value={pacienteId} onChange={e => setPacienteId(e.target.value)}
            style={{ width: '100%', padding: '0.75rem', borderRadius: '8px', border: '1px solid var(--border-light)', backgroundColor: 'var(--bg-app)', color: 'var(--text-main)', boxSizing: 'border-box' }}
          >
            <option value="">-- Sin paciente asignado --</option>
            {pacientes.map(p => (
              <option key={p.id} value={p.id}>{p.nombre_completo}</option>
            ))}
          </select>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem' }}>
          <div>
            <label style={{ display: 'block', marginBottom: '0.5rem', fontSize: '0.875rem', color: 'var(--text-muted)' }}>Inicio</label>
            <input 
              required type="datetime-local" value={fechaInicio} onChange={e => setFechaInicio(e.target.value)}
              style={{ width: '100%', padding: '0.75rem', borderRadius: '8px', border: '1px solid var(--border-light)', backgroundColor: 'var(--bg-app)', color: 'var(--text-main)', boxSizing: 'border-box' }}
            />
          </div>
          <div>
            <label style={{ display: 'block', marginBottom: '0.5rem', fontSize: '0.875rem', color: 'var(--text-muted)' }}>Fin</label>
            <input 
              required type="datetime-local" value={fechaFin} onChange={e => setFechaFin(e.target.value)}
              style={{ width: '100%', padding: '0.75rem', borderRadius: '8px', border: '1px solid var(--border-light)', backgroundColor: 'var(--bg-app)', color: 'var(--text-main)', boxSizing: 'border-box' }}
            />
          </div>
        </div>

        <div>
          <label style={{ display: 'block', marginBottom: '0.5rem', fontSize: '0.875rem', color: 'var(--text-muted)' }}>Notas (Opcional)</label>
          <textarea 
            value={notas} onChange={e => setNotas(e.target.value)}
            style={{ width: '100%', padding: '0.75rem', borderRadius: '8px', border: '1px solid var(--border-light)', backgroundColor: 'var(--bg-app)', color: 'var(--text-main)', minHeight: '80px', boxSizing: 'border-box' }}
          />
        </div>

        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '1rem' }}>
          {cita?.id && onDelete ? (
            <button 
              type="button" 
              onClick={() => onDelete(cita.id!)}
              style={{ padding: '0.75rem 1rem', borderRadius: '8px', border: 'none', backgroundColor: '#fee2e2', color: '#dc2626', cursor: 'pointer', fontWeight: 500 }}
            >
              Eliminar
            </button>
          ) : <div></div>}
          
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <button 
              type="button" onClick={onClose}
              style={{ padding: '0.75rem 1.5rem', borderRadius: '8px', border: '1px solid var(--border-light)', backgroundColor: 'transparent', color: 'var(--text-main)', cursor: 'pointer' }}
            >
              Cancelar
            </button>
            <button 
              type="submit"
              style={{ padding: '0.75rem 1.5rem', borderRadius: '8px', border: 'none', backgroundColor: 'var(--primary)', color: 'white', cursor: 'pointer', fontWeight: 500 }}
            >
              Guardar
            </button>
          </div>
        </div>
      </form>
    </dialog>
  );
}
