/* eslint-disable @typescript-eslint/no-explicit-any */
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { ShieldCheck, Edit3 } from 'lucide-react';
import { notasApi } from '../services/api';

function EmptyNotas() {
  return (
    <div className="empty-state">
      <svg className="empty-illustration" width="120" height="90" viewBox="0 0 120 90" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
        <rect x="36" y="12" width="48" height="64" rx="6" stroke="var(--color-border)" strokeWidth="2" fill="var(--color-surface-2)" />
        <path d="M46 30h28M46 42h28M46 54h16" stroke="var(--color-muted)" strokeWidth="2" strokeLinecap="round" opacity="0.5" />
        <path d="M78 62l6 6 10-12" stroke="var(--color-gold)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" fill="none" />
      </svg>
      <div className="empty-state-title">Sin notas médicas</div>
      <p className="empty-state-hint">No hay notas que coincidan con el filtro actual. Las notas se crean desde el expediente de cada paciente.</p>
    </div>
  );
}

export default function NotasList() {
  const navigate = useNavigate();
  const [filter, setFilter] = useState<'todas' | 'borradores' | 'firmadas'>('todas');

  const { data: notas = [], isLoading, isError } = useQuery({
    queryKey: ['notas'],
    queryFn: notasApi.getAll
  });

  const filteredNotas = notas.filter(nota => {
    if (filter === 'borradores') return !nota.firmada;
    if (filter === 'firmadas') return nota.firmada;
    return true;
  });

  return (
    <>
      <header className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', gap: '1rem', marginBottom: '1.5rem' }}>
        <div>
          <h1 className="page-title">Notas médicas</h1>
          <p className="page-subtitle">Directorio global de notas y borradores</p>
        </div>

        <div className="segmented" role="tablist" aria-label="Filtrar notas">
          <button className={filter === 'todas' ? 'active' : undefined} onClick={() => setFilter('todas')}>
            Todas
          </button>
          <button className={filter === 'borradores' ? 'active' : undefined} onClick={() => setFilter('borradores')}>
            Borradores
          </button>
          <button className={filter === 'firmadas' ? 'active' : undefined} onClick={() => setFilter('firmadas')}>
            Firmadas
          </button>
        </div>
      </header>

      <div className="table-card fade-in">
        {isError ? (
          <div className="empty-state">
            <div className="empty-state-title" style={{ color: 'var(--color-danger)' }}>Error de conexión</div>
            <p className="empty-state-hint">No fue posible cargar las notas.</p>
          </div>
        ) : isLoading ? (
          <div style={{ display: 'flex', justifyContent: 'center', padding: '3rem 0' }}>
            <div className="spinner" />
          </div>
        ) : filteredNotas.length === 0 ? (
          <EmptyNotas />
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Estado</th>
                <th>Tipo</th>
                <th>Paciente</th>
                <th>Expediente</th>
                <th>Fecha</th>
                <th style={{ textAlign: 'right' }}>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {filteredNotas.map((nota: any) => (
                <tr
                  key={nota.id}
                  className="row-link"
                  onClick={() => navigate(`/app/pacientes/${nota.paciente_id}#nota-${nota.id}`)}
                >
                  <td data-label="Estado">
                    {nota.firmada ? (
                      <span className="badge badge-gold">
                        <ShieldCheck size={11} /> Firmada
                      </span>
                    ) : (
                      <span className="badge badge-draft">
                        <Edit3 size={11} /> Borrador
                      </span>
                    )}
                  </td>
                  <td data-label="Tipo" style={{ fontWeight: 500, textTransform: 'capitalize' }}>
                    {nota.tipo_nota}
                  </td>
                  <td data-label="Paciente" style={{ fontWeight: 500 }}>
                    {nota.paciente_nombre}
                  </td>
                  <td data-label="Expediente" className="mono" style={{ color: 'var(--color-muted)' }}>
                    {nota.expediente_folio}
                  </td>
                  <td data-label="Fecha" style={{ color: 'var(--color-muted)' }}>
                    {new Date(nota.creado_en).toLocaleDateString()}
                  </td>
                  <td data-label="Acciones">
                    <div className="cell-actions">
                      <button
                        className="btn btn-outline"
                        style={{ padding: '0.3rem 0.7rem', fontSize: '0.8rem' }}
                        onClick={(e) => { e.stopPropagation(); navigate(`/app/pacientes/${nota.paciente_id}#nota-${nota.id}`); }}
                      >
                        Ver nota
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}
