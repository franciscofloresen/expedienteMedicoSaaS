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
      className="cita-modal modal-dialog"
    >
      <div className="modal-content" style={{ padding: '1.75rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
          <h2 style={{ margin: 0, fontSize: '1.1rem' }}>
            {cita?.id ? 'Editar cita' : 'Nueva cita'}
          </h2>
          <button type="button" className="btn-icon" onClick={onClose} aria-label="Cerrar">
            <X size={18} />
          </button>
        </div>

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          {error && (
            <div style={{ padding: '0.7rem 0.9rem', borderRadius: 'var(--radius-md)', backgroundColor: 'var(--color-danger-tint)', border: '1px solid rgba(248,81,73,0.35)', color: 'var(--color-danger)', fontSize: '0.85rem', fontWeight: 500 }}>
              {error}
            </div>
          )}

          <div>
            <label className="form-label">Título</label>
            <input
              required type="text" value={titulo} onChange={e => setTitulo(e.target.value)}
              className="form-input"
              placeholder="Ej. Consulta general"
            />
          </div>

          <div>
            <label className="form-label">Paciente (opcional)</label>
            <select
              value={pacienteId} onChange={e => setPacienteId(e.target.value)}
              className="form-input"
            >
              <option value="">— Sin paciente asignado —</option>
              {pacientes.map(p => (
                <option key={p.id} value={p.id}>{p.nombre_completo}</option>
              ))}
            </select>
          </div>

          <div className="form-grid-2">
            <div>
              <label className="form-label">Inicio</label>
              <input
                required type="datetime-local" value={fechaInicio} onChange={e => setFechaInicio(e.target.value)}
                className="form-input"
              />
            </div>
            <div>
              <label className="form-label">Fin</label>
              <input
                required type="datetime-local" value={fechaFin} onChange={e => setFechaFin(e.target.value)}
                className="form-input"
              />
            </div>
          </div>

          <div>
            <label className="form-label">Notas (opcional)</label>
            <textarea
              value={notas} onChange={e => setNotas(e.target.value)}
              className="form-input"
              style={{ minHeight: '80px' }}
            />
          </div>

          <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '0.5rem', gap: '0.75rem' }}>
            {cita?.id && onDelete ? (
              <button
                type="button"
                className="btn btn-danger-soft"
                onClick={() => onDelete(cita.id!)}
              >
                Eliminar
              </button>
            ) : <div></div>}

            <div style={{ display: 'flex', gap: '0.5rem' }}>
              <button type="button" className="btn btn-outline" onClick={onClose}>
                Cancelar
              </button>
              <button type="submit" className="btn btn-primary">
                Guardar
              </button>
            </div>
          </div>
        </form>
      </div>
    </dialog>
  );
}
