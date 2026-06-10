import { useQuery } from '@tanstack/react-query';
import { auditApi } from '../services/api';
import { ShieldCheck, Calendar, Activity, Globe, Server, Printer } from 'lucide-react';

// Helper function to translate technical logs into clinical language
const translateAction = (method: string, path: string) => {
  // Authentication
  if (path.includes('/auth/register')) return { text: 'Registro en Sistema', color: 'var(--primary)', bg: 'rgba(0,150,255,0.1)' };
  if (path.includes('/auth/login') || path.includes('/auth/me')) return { text: 'Inicio de Sesión', color: 'var(--success)', bg: 'rgba(0,200,80,0.1)' };
  
  // Notas
  if (path.includes('/firmar')) return { text: 'Firma Digital de Nota', color: 'var(--success)', bg: 'rgba(0,200,80,0.1)' };
  if (method === 'POST' && path.includes('/notas')) return { text: 'Creación de Nota Médica', color: 'var(--primary)', bg: 'rgba(0,150,255,0.1)' };
  if (method === 'GET' && path.includes('/notas')) return { text: 'Lectura de Nota Médica', color: 'var(--text-main)', bg: 'var(--bg-light)' };
  
  // Expedientes y Pacientes
  if (method === 'POST' && path.includes('/pacientes')) return { text: 'Registro de Paciente', color: 'var(--primary)', bg: 'rgba(0,150,255,0.1)' };
  if (method === 'GET' && path.includes('/expedientes')) return { text: 'Consulta de Expediente', color: 'var(--text-main)', bg: 'var(--bg-light)' };
  if (method === 'GET' && path.includes('/pacientes')) return { text: 'Búsqueda de Pacientes', color: 'var(--text-main)', bg: 'var(--bg-light)' };
  
  // Audit & System
  if (path.includes('/audit')) return { text: 'Revisión de Auditoría', color: 'var(--text-muted)', bg: 'var(--bg-light)' };
  
  // Generales
  if (method === 'PUT' || method === 'PATCH') return { text: 'Actualización de Datos', color: 'orange', bg: 'rgba(255,165,0,0.1)' };
  if (method === 'DELETE') return { text: 'Eliminación Lógica', color: 'var(--error)', bg: 'rgba(255,0,0,0.1)' };
  
  return { text: 'Actividad del Sistema', color: 'var(--text-muted)', bg: 'var(--bg-light)' };
};

export default function Auditoria() {
  const { data: auditLogs = [], isLoading, error } = useQuery({
    queryKey: ['auditLogs'],
    queryFn: () => auditApi.getRecent(1000),
    refetchInterval: 30000, // auto-refresh every 30s
  });

  return (
    <div className="animate-fade-in" style={{ maxWidth: '1200px', margin: '0 auto' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginBottom: '2rem' }}>
        <div style={{ 
          background: 'linear-gradient(135deg, var(--primary-light), var(--primary))', 
          padding: '1rem', 
          borderRadius: '12px',
          color: 'white',
          boxShadow: '0 4px 15px rgba(0, 0, 0, 0.1)'
        }}>
          <ShieldCheck size={32} />
        </div>
        <div>
          <h1 className="page-title" style={{ margin: 0, fontSize: '2rem' }}>Auditoría y Seguridad</h1>
          <p className="text-muted" style={{ margin: '0.25rem 0 0 0' }}>Registro inmutable de actividades y accesos del sistema</p>
        </div>
        <div style={{ marginLeft: 'auto' }}>
          <button className="btn btn-outline no-print" onClick={() => window.print()}>
            <Printer size={20} />
            Imprimir Reporte Técnico
          </button>
        </div>
      </div>

      <div className="glass-card" style={{ padding: 0, overflow: 'hidden' }}>
        <div style={{ padding: '1.5rem', borderBottom: '1px solid var(--border-light)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h2 style={{ fontSize: '1.2rem', margin: 0 }}>Eventos Recientes</h2>
          <div style={{ display: 'flex', gap: '1rem', fontSize: '0.85rem' }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
              <span style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--success)' }}></span> Exitoso
            </span>
            <span style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
              <span style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--error)' }}></span> Error / Denegado
            </span>
          </div>
        </div>

        <div className="table-responsive">
          <table className="table">
            <thead>
              <tr style={{ backgroundColor: 'rgba(0,0,0,0.02)', borderBottom: '1px solid var(--border-light)' }}>
                <th style={{ padding: '1.25rem 1.5rem', color: 'var(--text-muted)', fontWeight: 600, fontSize: '0.85rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}><div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}><Calendar size={16} /> Fecha / Hora</div></th>
                <th style={{ padding: '1.25rem 1.5rem', color: 'var(--text-muted)', fontWeight: 600, fontSize: '0.85rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}><div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}><Activity size={16} /> Acción Realizada</div></th>
                <th style={{ padding: '1.25rem 1.5rem', color: 'var(--text-muted)', fontWeight: 600, fontSize: '0.85rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}><div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}><Server size={16} /> Detalle Técnico</div></th>
                <th style={{ padding: '1.25rem 1.5rem', color: 'var(--text-muted)', fontWeight: 600, fontSize: '0.85rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Estado</th>
                <th style={{ padding: '1.25rem 1.5rem', color: 'var(--text-muted)', fontWeight: 600, fontSize: '0.85rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}><div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}><Globe size={16} /> Origen IP</div></th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr><td colSpan={5} style={{ padding: '3rem', textAlign: 'center' }}>Cargando bitácora de seguridad...</td></tr>
              ) : error ? (
                <tr><td colSpan={5} style={{ padding: '3rem', textAlign: 'center', color: 'var(--error)' }}>Error al cargar los registros de auditoría.</td></tr>
              ) : auditLogs.length === 0 ? (
                <tr><td colSpan={5} style={{ padding: '3rem', textAlign: 'center' }} className="text-muted">No hay eventos registrados recientemente.</td></tr>
              ) : (
                auditLogs.map((log: any, index: number) => {
                  const translation = translateAction(log.metodo, log.ruta);
                  const isHiddenInWeb = index >= 50;
                  return (
                  <tr 
                    key={log.id} 
                    className={isHiddenInWeb ? "print-only" : ""} 
                    style={{ 
                      borderBottom: '1px solid var(--border-light)', 
                      transition: 'background-color 0.2s', 
                      display: isHiddenInWeb ? 'none' : undefined,
                      cursor: 'default'
                    }}
                    onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--primary-light)'}
                    onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
                  >
                    <td style={{ padding: '1.25rem 1.5rem', fontFamily: 'monospace', fontSize: '0.9rem' }}>
                      {new Date(log.timestamp).toLocaleString()}
                    </td>
                    <td style={{ padding: '1.25rem 1.5rem' }}>
                      <span style={{ 
                        padding: '0.4rem 0.8rem', 
                        borderRadius: '20px', 
                        backgroundColor: translation.bg,
                        color: translation.color,
                        fontWeight: 600,
                        fontSize: '0.85rem',
                        border: `1px solid ${translation.color.replace('var(', '').replace(')', '') === 'orange' ? 'rgba(255,165,0,0.3)' : translation.color.includes('var') ? `var(--${translation.color.split('--')[1].split(')')[0]}-light)` : 'rgba(0,0,0,0.1)'}`
                      }}>{translation.text}</span>
                    </td>
                    <td style={{ padding: '1.25rem 1.5rem', fontFamily: 'monospace', fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                      <div className="tech-detail-web" style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: '250px' }} title={`${log.metodo} ${log.ruta}`}>
                        {log.metodo} {log.ruta.split('?')[0]}
                      </div>
                      <div className="print-only" style={{ display: 'none', fontSize: '0.75rem', marginTop: '0.5rem', lineHeight: '1.4' }}>
                        <div><strong>ID:</strong> {log.request_id || log.id}</div>
                        <div><strong>Ruta:</strong> {log.metodo} {log.ruta}</div>
                      </div>
                    </td>
                    <td style={{ padding: '1.25rem 1.5rem' }}>
                      <span style={{ 
                        color: log.status >= 400 ? 'var(--error)' : 'var(--success)',
                        fontWeight: 600,
                        display: 'flex',
                        alignItems: 'center',
                        gap: '0.5rem'
                      }}>
                        <span style={{ 
                          display: 'inline-block', 
                          width: 8, 
                          height: 8, 
                          borderRadius: '50%', 
                          background: log.status >= 400 ? 'var(--error)' : 'var(--success)',
                          boxShadow: log.status >= 400 ? '0 0 8px rgba(255, 59, 48, 0.4)' : '0 0 8px rgba(52, 199, 89, 0.4)'
                        }}></span>
                        {log.status}
                      </span>
                    </td>
                    <td style={{ padding: '1.25rem 1.5rem', fontFamily: 'monospace', color: 'var(--text-muted)', fontSize: '0.9rem' }}>
                      {log.ip_origen}
                    </td>
                  </tr>
                );
              })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
