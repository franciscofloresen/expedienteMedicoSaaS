/* eslint-disable @typescript-eslint/no-explicit-any */
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { Activity, ShieldCheck, Edit3, Calendar, ExternalLink } from 'lucide-react';
import { notasApi } from '../services/api';

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
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: '2rem' }}>
        <div>
          <h1 className="page-title animate-fade-in" style={{ marginBottom: 0 }}>Notas Médicas</h1>
          <p className="text-muted" style={{ marginTop: '0.5rem' }}>Directorio global de notas y borradores.</p>
        </div>
        
        <div style={{ display: 'flex', gap: '0.5rem', backgroundColor: 'var(--bg-card)', padding: '0.25rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-light)' }}>
          <button 
            className={`btn ${filter === 'todas' ? 'btn-primary' : 'btn-outline'}`}
            style={{ padding: '0.4rem 1rem', border: filter === 'todas' ? 'none' : '1px solid transparent' }}
            onClick={() => setFilter('todas')}
          >
            Todas
          </button>
          <button 
            className={`btn ${filter === 'borradores' ? 'btn-primary' : 'btn-outline'}`}
            style={{ padding: '0.4rem 1rem', border: filter === 'borradores' ? 'none' : '1px solid transparent' }}
            onClick={() => setFilter('borradores')}
          >
            Solo Borradores
          </button>
          <button 
            className={`btn ${filter === 'firmadas' ? 'btn-primary' : 'btn-outline'}`}
            style={{ padding: '0.4rem 1rem', border: filter === 'firmadas' ? 'none' : '1px solid transparent' }}
            onClick={() => setFilter('firmadas')}
          >
            Firmadas
          </button>
        </div>
      </header>

      <div className="glass-card animate-fade-in" style={{ animationDelay: '0.1s', overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--border-light)' }}>
              <th style={{ padding: '1rem', color: 'var(--text-muted)', fontWeight: 500 }}>Estado</th>
              <th style={{ padding: '1rem', color: 'var(--text-muted)', fontWeight: 500 }}>Tipo de Nota</th>
              <th style={{ padding: '1rem', color: 'var(--text-muted)', fontWeight: 500 }}>Paciente</th>
              <th style={{ padding: '1rem', color: 'var(--text-muted)', fontWeight: 500 }}>Expediente</th>
              <th style={{ padding: '1rem', color: 'var(--text-muted)', fontWeight: 500 }}>Fecha</th>
              <th style={{ padding: '1rem', color: 'var(--text-muted)', fontWeight: 500, textAlign: 'right' }}>Acciones</th>
            </tr>
          </thead>
          <tbody>
            {isError ? (
              <tr><td colSpan={6} style={{ padding: '3rem', textAlign: 'center', color: 'var(--error)' }}>
                <p>Error de conexión al cargar las notas.</p>
              </td></tr>
            ) : isLoading ? (
              <tr><td colSpan={6} style={{ padding: '1rem', textAlign: 'center' }}>Cargando notas...</td></tr>
            ) : filteredNotas.length === 0 ? (
              <tr><td colSpan={6} style={{ padding: '3rem', textAlign: 'center' }} className="text-muted">
                <Activity size={48} style={{ opacity: 0.5, margin: '0 auto 1rem auto' }} />
                No hay notas médicas que coincidan con el filtro actual.
              </td></tr>
            ) : (
              filteredNotas.map((nota: any) => (
                <tr key={nota.id} style={{ borderBottom: '1px solid var(--border-light)', transition: 'background-color 0.2s', cursor: 'pointer' }}
                    onMouseEnter={(e: React.MouseEvent<HTMLTableRowElement>) => e.currentTarget.style.backgroundColor = 'var(--primary-light)'}
                    onMouseLeave={(e: React.MouseEvent<HTMLTableRowElement>) => e.currentTarget.style.backgroundColor = 'transparent'}
                    onClick={() => navigate(`/app/pacientes/${nota.paciente_id}#nota-${nota.id}`)}>
                  <td data-label="Estado" style={{ padding: '1rem' }}>
                    {nota.firmada ? (
                      <span className="badge badge-success" style={{ display: 'inline-flex', gap: '0.25rem' }}>
                        <ShieldCheck size={12} /> Firmada
                      </span>
                    ) : (
                      <span className="badge" style={{ backgroundColor: 'var(--primary-light)', color: 'var(--primary)', display: 'inline-flex', gap: '0.25rem' }}>
                        <Edit3 size={12} /> Borrador
                      </span>
                    )}
                  </td>
                  <td data-label="Tipo de Nota" style={{ padding: '1rem', fontWeight: 500, textTransform: 'uppercase', fontSize: '0.9rem' }}>
                    {nota.tipo_nota}
                  </td>
                  <td data-label="Paciente" style={{ padding: '1rem', fontWeight: 500 }}>
                    {nota.paciente_nombre}
                  </td>
                  <td data-label="Expediente" style={{ padding: '1rem', fontFamily: 'monospace', fontSize: '0.9rem' }} className="text-muted">
                    {nota.expediente_folio}
                  </td>
                  <td data-label="Fecha" style={{ padding: '1rem', fontSize: '0.9rem' }} className="text-muted">
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', justifyContent: 'flex-end' }}>
                      <Calendar size={14} />
                      {new Date(nota.creado_en).toLocaleDateString()}
                    </div>
                  </td>
                  <td data-label="Acciones" style={{ padding: '1rem', textAlign: 'right' }}>
                    <button 
                      className="btn btn-primary" 
                      style={{ padding: '0.4rem 0.75rem', fontSize: '0.85rem' }} 
                      onClick={(e) => { e.stopPropagation(); navigate(`/app/pacientes/${nota.paciente_id}#nota-${nota.id}`); }}
                    >
                      Ver Nota
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </>
  );
}
