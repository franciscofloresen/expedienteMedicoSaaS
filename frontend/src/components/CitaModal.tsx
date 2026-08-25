/* eslint-disable react-hooks/set-state-in-effect */
import React, { useState, useEffect } from 'react';
import Sheet from './Sheet';
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
    <Sheet
      isOpen={isOpen}
      onClose={onClose}
      title={cita?.id ? 'Editar cita' : 'Nueva cita'}
      /* Una cita a medio capturar no debe irse con un gesto accidental. */
      dismissibleByDrag={false}
    >
      <form onSubmit={handleSubmit} className="stack-form">
          {error && (
            <div className="alert alert-danger" role="alert">
              {error}
            </div>
          )}

          <div>
            <label className="form-label" htmlFor="cita-titulo">Título <span className="required-mark">*</span></label>
            <input
              id="cita-titulo"
              required type="text" value={titulo} onChange={e => setTitulo(e.target.value)}
              className="form-input"
              placeholder="Ej. Consulta general"
              autoComplete="off"
            />
          </div>

          <div>
            <label className="form-label" htmlFor="cita-paciente">Paciente</label>
            <select
              id="cita-paciente"
              value={pacienteId} onChange={e => setPacienteId(e.target.value)}
              className="form-input"
            >
              <option value="">Sin paciente asignado</option>
              {pacientes.map(p => (
                <option key={p.id} value={p.id}>{p.nombre_completo}</option>
              ))}
            </select>
          </div>

          <div className="form-grid-2">
            <div>
              <label className="form-label" htmlFor="cita-inicio">Inicio <span className="required-mark">*</span></label>
              <input
                id="cita-inicio"
                required type="datetime-local" value={fechaInicio} onChange={e => setFechaInicio(e.target.value)}
                className="form-input"
              />
            </div>
            <div>
              <label className="form-label" htmlFor="cita-fin">Fin <span className="required-mark">*</span></label>
              <input
                id="cita-fin"
                required type="datetime-local" value={fechaFin} onChange={e => setFechaFin(e.target.value)}
                className="form-input"
              />
            </div>
          </div>

          <div>
            <label className="form-label" htmlFor="cita-notas">Notas internas</label>
            <textarea
              id="cita-notas"
              value={notas} onChange={e => setNotas(e.target.value)}
              className="form-input"
              style={{ minHeight: '80px' }}
              placeholder="Motivo breve, preparación o recordatorios para la consulta."
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
    </Sheet>
  );
}
