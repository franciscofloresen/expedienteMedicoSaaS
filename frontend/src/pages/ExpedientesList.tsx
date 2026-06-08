import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { FileText, Calendar, ExternalLink } from 'lucide-react';
import { expedientesApi } from '../services/api';

export default function ExpedientesList() {
  const navigate = useNavigate();

  const { data: expedientes = [], isLoading, isError } = useQuery({
    queryKey: ['expedientes'],
    queryFn: expedientesApi.getAll
  });

  return (
    <>
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }}>
        <h1 className="page-title animate-fade-in" style={{ marginBottom: 0 }}>
          Directorio de Expedientes
        </h1>
      </header>

      <div className="glass-card animate-fade-in" style={{ animationDelay: '0.1s', overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', minWidth: '800px' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--border-light)' }}>
              <th style={{ padding: '1rem', color: 'var(--text-muted)', fontWeight: 500 }}>Folio</th>
              <th style={{ padding: '1rem', color: 'var(--text-muted)', fontWeight: 500 }}>Paciente</th>
              <th style={{ padding: '1rem', color: 'var(--text-muted)', fontWeight: 500 }}>CURP</th>
              <th style={{ padding: '1rem', color: 'var(--text-muted)', fontWeight: 500 }}>Fecha de Apertura</th>
              <th style={{ padding: '1rem', color: 'var(--text-muted)', fontWeight: 500, textAlign: 'right' }}>Acciones</th>
            </tr>
          </thead>
          <tbody>
            {isError ? (
              <tr><td colSpan={5} style={{ padding: '3rem', textAlign: 'center', color: 'var(--error)' }}>
                <p>Error de conexión al cargar expedientes.</p>
              </td></tr>
            ) : isLoading ? (
              <tr><td colSpan={5} style={{ padding: '1rem', textAlign: 'center' }}>Cargando directorio...</td></tr>
            ) : expedientes.length === 0 ? (
              <tr><td colSpan={5} style={{ padding: '3rem', textAlign: 'center' }} className="text-muted">
                <FileText size={48} style={{ opacity: 0.5, margin: '0 auto 1rem auto' }} />
                No hay expedientes activos en la clínica.
              </td></tr>
            ) : (
              expedientes.map((exp: any) => (
                <tr key={exp.id} style={{ borderBottom: '1px solid var(--border-light)', transition: 'background-color 0.2s' }}>
                  <td style={{ padding: '1rem', fontFamily: 'monospace', fontSize: '0.9rem', fontWeight: 600, color: 'var(--primary)' }}>
                    {exp.folio}
                  </td>
                  <td style={{ padding: '1rem', fontWeight: 500 }}>
                    {exp.paciente_nombre}
                  </td>
                  <td style={{ padding: '1rem', fontFamily: 'monospace', fontSize: '0.9rem' }} className="text-muted">
                    {exp.paciente_curp || 'N/A'}
                  </td>
                  <td style={{ padding: '1rem', fontSize: '0.9rem' }} className="text-muted">
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <Calendar size={14} />
                      {new Date(exp.creado_en).toLocaleDateString()}
                    </div>
                  </td>
                  <td style={{ padding: '1rem', textAlign: 'right' }}>
                    <button 
                      className="btn btn-primary" 
                      style={{ padding: '0.4rem 0.75rem', fontSize: '0.85rem' }} 
                      onClick={() => navigate(`/pacientes/${exp.paciente_id}`)}
                    >
                      <ExternalLink size={16} /> Abrir
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
