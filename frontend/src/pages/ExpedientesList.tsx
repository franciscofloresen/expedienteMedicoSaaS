/* eslint-disable @typescript-eslint/no-explicit-any */
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { ExternalLink } from 'lucide-react';
import { expedientesApi } from '../services/api';

function EmptyExpedientes() {
  return (
    <div className="empty-state">
      <svg className="empty-illustration" width="120" height="90" viewBox="0 0 120 90" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
        <path d="M28 24a6 6 0 0 1 6-6h18l8 8h26a6 6 0 0 1 6 6v34a6 6 0 0 1-6 6H34a6 6 0 0 1-6-6V24Z" stroke="var(--color-border)" strokeWidth="2" fill="var(--color-surface-2)" />
        <path d="M42 46h36M42 56h24" stroke="var(--color-muted)" strokeWidth="2" strokeLinecap="round" opacity="0.5" />
        <circle cx="88" cy="26" r="3" fill="var(--color-primary)" />
      </svg>
      <div className="empty-state-title">No hay expedientes activos</div>
      <p className="empty-state-hint">Los expedientes se crean desde la ficha de cada paciente, después de registrar su consentimiento.</p>
    </div>
  );
}

export default function ExpedientesList() {
  const navigate = useNavigate();

  const { data: expedientes = [], isLoading, isError } = useQuery({
    queryKey: ['expedientes'],
    queryFn: expedientesApi.getAll
  });

  return (
    <>
      <header className="page-header" style={{ marginBottom: '1.5rem' }}>
        <h1 className="page-title">Expedientes</h1>
        <p className="page-subtitle">Directorio de expedientes clínicos activos</p>
      </header>

      <div className="table-card fade-in">
        {isError ? (
          <div className="empty-state">
            <div className="empty-state-title" style={{ color: 'var(--color-danger)' }}>Error de conexión</div>
            <p className="empty-state-hint">No pudimos cargar los expedientes. Revisa tu conexión e inténtalo de nuevo.</p>
          </div>
        ) : isLoading ? (
          <div className="loading-state">
            <div className="spinner" />
            <span>Cargando expedientes clínicos…</span>
          </div>
        ) : expedientes.length === 0 ? (
          <EmptyExpedientes />
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Folio</th>
                <th>Paciente</th>
                <th>CURP</th>
                <th>Apertura</th>
                <th style={{ textAlign: 'right' }}>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {expedientes.map((exp: any) => (
                <tr
                  key={exp.id}
                  className="row-link"
                  onClick={() => navigate(`/app/pacientes/${exp.paciente_id}`)}
                >
                  <td data-label="Folio" className="mono" style={{ color: 'var(--color-primary)', fontWeight: 600 }}>
                    {exp.folio}
                  </td>
                  <td data-label="Paciente" style={{ fontWeight: 500 }}>
                    {exp.paciente_nombre}
                  </td>
                  <td data-label="CURP" className="mono" style={{ color: 'var(--color-muted)' }}>
                    {exp.paciente_curp || 'N/A'}
                  </td>
                  <td data-label="Apertura" style={{ color: 'var(--color-muted)' }}>
                    {new Date(exp.creado_en).toLocaleDateString()}
                  </td>
                  <td data-label="Acciones">
                    <div className="cell-actions">
                      <button
                        className="btn btn-outline"
                        style={{ padding: '0.3rem 0.7rem', fontSize: '0.8rem' }}
                        onClick={(e) => { e.stopPropagation(); navigate(`/app/pacientes/${exp.paciente_id}`); }}
                      >
                        <ExternalLink size={14} /> Abrir
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
