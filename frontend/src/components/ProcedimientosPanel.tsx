/**
 * ProcedimientosPanel — pre/post-procedure checklists and adverse-event tracking
 * for a patient (Fase 13). Self-contained: owns its queries/mutations.
 */
import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { ClipboardCheck, AlertTriangle, Plus, Trash2, Check } from 'lucide-react';
import { procedimientosApi } from '../services/api';
import { defaultChecklistItems } from '../utils/procedimientos';
import { useToast } from '../hooks/useToast';
import type { ChecklistItem, ProcedimientoChecklist } from '../types';

export default function ProcedimientosPanel({ pacienteId }: { pacienteId: string }) {
  const qc = useQueryClient();
  const { showToast } = useToast();
  const [evDesc, setEvDesc] = useState('');
  const [evSev, setEvSev] = useState<'leve' | 'moderado' | 'grave'>('leve');

  const { data: checklists = [] } = useQuery({
    queryKey: ['procedimiento-checklists', pacienteId],
    queryFn: () => procedimientosApi.listChecklists(pacienteId),
  });
  const { data: eventos = [] } = useQuery({
    queryKey: ['eventos-adversos', pacienteId],
    queryFn: () => procedimientosApi.listEventos(pacienteId),
  });

  const invalidateChecklists = () => qc.invalidateQueries({ queryKey: ['procedimiento-checklists', pacienteId] });
  const invalidateEventos = () => qc.invalidateQueries({ queryKey: ['eventos-adversos', pacienteId] });

  const addChecklist = useMutation({
    mutationFn: (momento: 'pre' | 'post') =>
      procedimientosApi.createChecklist({ paciente_id: pacienteId, momento, items: defaultChecklistItems(momento) }),
    onSuccess: invalidateChecklists,
    onError: () => showToast('No se pudo crear el checklist.', 'error'),
  });
  const updateChecklist = useMutation({
    mutationFn: (v: { id: string; items: ChecklistItem[] }) =>
      procedimientosApi.updateChecklist(v.id, { items: v.items }),
    onSuccess: invalidateChecklists,
  });
  const removeChecklist = useMutation({
    mutationFn: (id: string) => procedimientosApi.removeChecklist(id),
    onSuccess: invalidateChecklists,
  });

  const addEvento = useMutation({
    mutationFn: () =>
      procedimientosApi.createEvento({ paciente_id: pacienteId, descripcion: evDesc.trim(), severidad: evSev }),
    onSuccess: () => { setEvDesc(''); setEvSev('leve'); invalidateEventos(); },
    onError: () => showToast('No se pudo registrar el evento.', 'error'),
  });
  const resolveEvento = useMutation({
    mutationFn: (e: { id: string; descripcion: string; severidad: 'leve' | 'moderado' | 'grave' }) =>
      procedimientosApi.updateEvento(e.id, { descripcion: e.descripcion, severidad: e.severidad, estado: 'resuelto' }),
    onSuccess: invalidateEventos,
  });

  const toggleItem = (c: ProcedimientoChecklist, idx: number) => {
    const items = c.items.map((it, i) => (i === idx ? { ...it, completado: !it.completado } : it));
    updateChecklist.mutate({ id: c.id, items });
  };

  return (
    <div className="fade-in" data-testid="procedimientos-panel">
      {/* Checklists */}
      <div className="glass-card" style={{ marginBottom: '1.25rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '1rem', flexWrap: 'wrap', marginBottom: '0.75rem' }}>
          <span className="overline" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem' }}>
            <ClipboardCheck size={15} /> Checklists de procedimiento
          </span>
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <button type="button" className="btn btn-outline" style={{ padding: '0.3rem 0.7rem', fontSize: '0.8rem' }} onClick={() => addChecklist.mutate('pre')}>
              <Plus size={13} /> Pre
            </button>
            <button type="button" className="btn btn-outline" style={{ padding: '0.3rem 0.7rem', fontSize: '0.8rem' }} onClick={() => addChecklist.mutate('post')}>
              <Plus size={13} /> Post
            </button>
          </div>
        </div>

        {checklists.length === 0 ? (
          <span className="text-muted" style={{ fontSize: '0.85rem' }}>Sin checklists. Añade uno pre o post procedimiento.</span>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            {checklists.map((c) => (
              <div key={c.id} style={{ border: '1px solid var(--color-border)', borderRadius: '8px', padding: '0.75rem 0.9rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                  <span className="badge badge-draft">{c.momento === 'pre' ? 'Pre-procedimiento' : 'Post-procedimiento'}</span>
                  <button type="button" className="btn-icon" aria-label="Eliminar checklist" onClick={() => removeChecklist.mutate(c.id)}>
                    <Trash2 size={14} />
                  </button>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
                  {c.items.map((it, idx) => (
                    <label key={idx} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.88rem', cursor: 'pointer' }}>
                      <input type="checkbox" checked={it.completado} onChange={() => toggleItem(c, idx)} />
                      <span style={{ textDecoration: it.completado ? 'line-through' : 'none', color: it.completado ? 'var(--color-muted)' : 'inherit' }}>{it.texto}</span>
                    </label>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Adverse events */}
      <div className="glass-card">
        <span className="overline" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem', marginBottom: '0.75rem' }}>
          <AlertTriangle size={15} /> Eventos adversos
        </span>

        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginBottom: '1rem' }}>
          <input
            type="text"
            className="form-input"
            placeholder="Describe el evento adverso…"
            value={evDesc}
            onChange={(e) => setEvDesc(e.target.value)}
            style={{ flex: '1 1 240px' }}
          />
          <select className="form-input" value={evSev} onChange={(e) => setEvSev(e.target.value as 'leve' | 'moderado' | 'grave')} style={{ flex: '0 0 130px' }}>
            <option value="leve">Leve</option>
            <option value="moderado">Moderado</option>
            <option value="grave">Grave</option>
          </select>
          <button type="button" className="btn btn-primary" disabled={!evDesc.trim() || addEvento.isPending} onClick={() => addEvento.mutate()}>
            <Plus size={14} /> Registrar
          </button>
        </div>

        {eventos.length === 0 ? (
          <span className="text-muted" style={{ fontSize: '0.85rem' }}>Sin eventos adversos registrados.</span>
        ) : (
          <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
            {eventos.map((e) => (
              <li key={e.id} style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', fontSize: '0.88rem' }}>
                <span className={e.severidad === 'grave' ? 'badge badge-danger' : 'badge badge-draft'}>{e.severidad}</span>
                <span style={{ flex: 1 }}>{e.descripcion}</span>
                {e.estado === 'resuelto' ? (
                  <span className="text-muted" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem' }}><Check size={14} /> Resuelto</span>
                ) : (
                  <button type="button" className="btn btn-outline" style={{ padding: '0.2rem 0.55rem', fontSize: '0.78rem' }} onClick={() => resolveEvento.mutate({ id: e.id, descripcion: e.descripcion, severidad: e.severidad })}>
                    Marcar resuelto
                  </button>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
