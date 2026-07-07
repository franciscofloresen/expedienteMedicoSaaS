/* eslint-disable @typescript-eslint/no-explicit-any */
import { useState } from 'react';
import { useQuery, keepPreviousData } from '@tanstack/react-query';
import { ShieldCheck } from 'lucide-react';
import { auditApi, type AuditEntry } from '../services/api';

const PAGE_SIZE = 50;

function statusBadge(code: number | null) {
  if (code == null) return <span className="badge">—</span>;
  if (code < 400) return <span className="badge badge-gold">{code}</span>;
  return <span className="badge badge-draft">{code}</span>;
}

export default function Auditoria() {
  const [page, setPage] = useState(0);

  const { data: entries = [], isLoading, isError, error, isFetching } = useQuery({
    queryKey: ['auditLogs', page],
    queryFn: () => auditApi.list(PAGE_SIZE, page * PAGE_SIZE),
    placeholderData: keepPreviousData,
  });

  const isForbidden = (error as any)?.status === 403;

  return (
    <>
      <header className="page-header" style={{ marginBottom: '1.5rem' }}>
        <h1 className="page-title">Auditoría</h1>
        <p className="page-subtitle">
          Bitácora inmutable de accesos y cambios (NOM-024-SSA3-2012)
        </p>
      </header>

      <div className="table-card fade-in">
        {isError && isForbidden ? (
          <div className="empty-state">
            <div className="empty-state-title">Función Pro</div>
            <p className="empty-state-hint">
              El registro de auditoría está disponible en el plan Pro.
            </p>
          </div>
        ) : isError ? (
          <div className="empty-state">
            <div className="empty-state-title" style={{ color: 'var(--color-danger)' }}>
              Error de conexión
            </div>
            <p className="empty-state-hint">No fue posible cargar la bitácora.</p>
          </div>
        ) : isLoading ? (
          <div style={{ display: 'flex', justifyContent: 'center', padding: '3rem 0' }}>
            <div className="spinner" />
          </div>
        ) : entries.length === 0 && page === 0 ? (
          <div className="empty-state">
            <ShieldCheck size={40} style={{ color: 'var(--color-muted)' }} />
            <div className="empty-state-title">Sin registros aún</div>
            <p className="empty-state-hint">
              Aquí aparecerán los accesos y cambios a los expedientes.
            </p>
          </div>
        ) : (
          <>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Fecha y hora</th>
                  <th>Acción</th>
                  <th>Estado</th>
                  <th>IP</th>
                </tr>
              </thead>
              <tbody>
                {entries.map((e: AuditEntry, i: number) => (
                  <tr key={`${e.timestamp}-${i}`}>
                    <td data-label="Fecha y hora" style={{ color: 'var(--color-muted)' }}>
                      {new Date(e.timestamp).toLocaleString()}
                    </td>
                    <td data-label="Acción" className="mono">{e.action}</td>
                    <td data-label="Estado">{statusBadge(e.status_code)}</td>
                    <td data-label="IP" className="mono" style={{ color: 'var(--color-muted)' }}>
                      {e.ip_address || '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            <div
              style={{
                display: 'flex',
                justifyContent: 'flex-end',
                alignItems: 'center',
                gap: '1rem',
                padding: '1rem',
              }}
            >
              <span style={{ color: 'var(--color-muted)', fontSize: '0.85rem' }}>
                Página {page + 1}
              </span>
              <button
                className="btn btn-outline"
                disabled={page === 0 || isFetching}
                onClick={() => setPage((p) => Math.max(0, p - 1))}
              >
                Anterior
              </button>
              <button
                className="btn btn-outline"
                disabled={entries.length < PAGE_SIZE || isFetching}
                onClick={() => setPage((p) => p + 1)}
              >
                Siguiente
              </button>
            </div>
          </>
        )}
      </div>
    </>
  );
}
