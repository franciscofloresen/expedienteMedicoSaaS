import React, { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { ArrowLeft, Plus, X, Stethoscope, CheckCircle, FileSignature } from 'lucide-react';
import { expedientesApi, notasApi } from '../services/api';

export default function Expediente() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const client = useQueryClient();
  const [isSidePanelOpen, setIsSidePanelOpen] = useState(false);

  // Fetch Expediente (this endpoint doesn't exist natively by ID returning full data in the backend yet,
  // wait, the backend endpoint is GET /api/v1/expedientes/paciente/{paciente_id}.
  // We passed `p.id` (Paciente ID) in the URL! So we fetch the expediente BY paciente_id.
  const { data: expediente, isLoading } = useQuery({
    queryKey: ['expediente', id],
    queryFn: () => expedientesApi.getByPacienteId(id as string)
  });

  const { data: notas = [], isLoading: isLoadingNotas } = useQuery({
    queryKey: ['notas', expediente?.id],
    queryFn: () => notasApi.getByExpedienteId(expediente?.id as string),
    enabled: !!expediente?.id
  });

  const createNotaMutation = useMutation({
    mutationFn: notasApi.create,
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ['notas', expediente?.id] });
      setIsSidePanelOpen(false);
      alert("Nota médica creada y firmada en KMS.");
    }
  });

  const handleSubmitNota = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!expediente) return;

    const formData = new FormData(e.currentTarget);
    
    // Contenido estructurado según NOM-004
    const contenido = {
      evolucion_y_actualizacion_cuadro: formData.get('evolucion') as string,
    };
    
    const signos_vitales = {
      frecuencia_cardiaca: Number(formData.get('fc')),
      frecuencia_respiratoria: Number(formData.get('fr')),
      temperatura: Number(formData.get('temp')),
      tension_arterial: formData.get('ta') as string
    };

    createNotaMutation.mutate({
      expediente_id: expediente.id,
      tipo_nota: 'evolucion',
      contenido,
      signos_vitales,
      diagnosticos: [formData.get('diagnostico') as string],
      tratamiento: formData.get('tratamiento') as string
    });
  };

  if (isLoading) return <div>Cargando expediente...</div>;

  // Si no hay expediente, podríamos mostrar un botón para crearlo
  if (!expediente) {
    return (
      <div className="glass-card" style={{ textAlign: 'center', padding: '3rem' }}>
        <h2>El paciente no tiene un expediente activo.</h2>
        <button className="btn btn-primary" style={{ marginTop: '1rem' }} onClick={async () => {
          await expedientesApi.create({ paciente_id: id });
          client.invalidateQueries({ queryKey: ['expediente', id] });
        }}>
          Crear Expediente Clínico (NOM-004)
        </button>
      </div>
    );
  }

  return (
    <div style={{ position: 'relative', height: '100%', overflow: 'hidden' }}>
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <button className="btn btn-outline" style={{ padding: '0.5rem' }} onClick={() => navigate('/')}>
            <ArrowLeft size={20} />
          </button>
          <h1 className="page-title animate-fade-in" style={{ marginBottom: 0 }}>Expediente: {expediente.numero_expediente}</h1>
        </div>
        <button className="btn btn-primary" onClick={() => setIsSidePanelOpen(true)}>
          <Plus size={20} /> Nueva Nota Médica
        </button>
      </header>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '2rem' }}>
        {/* Columna Izquierda: Datos del Paciente */}
        <div className="glass-card animate-fade-in" style={{ alignSelf: 'start' }}>
          <h3 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem' }}>
            <Stethoscope size={20} color="var(--primary)"/> Información Clínica
          </h3>
          <div style={{ marginBottom: '1.5rem' }}>
            <span className="text-muted">ID Expediente</span>
            <p style={{ fontWeight: 500 }}>{expediente.id}</p>
          </div>
          <div style={{ marginBottom: '1.5rem' }}>
            <span className="text-muted">Fecha de Creación</span>
            <p style={{ fontWeight: 500 }}>{new Date(expediente.creado_en).toLocaleDateString()}</p>
          </div>
          <div>
            <span className="text-muted">Antecedentes (Desencriptados vía KMS)</span>
            <div style={{ padding: '1rem', backgroundColor: 'var(--bg-app)', borderRadius: 'var(--radius-md)', marginTop: '0.5rem' }}>
              {expediente.antecedentes ? (
                <p>{expediente.antecedentes}</p>
              ) : (
                <p className="text-muted" style={{ fontStyle: 'italic' }}>Sin antecedentes registrados.</p>
              )}
            </div>
          </div>
        </div>

        {/* Columna Derecha: Historial de Notas */}
        <div className="glass-card animate-fade-in" style={{ animationDelay: '0.1s' }}>
          <h3 style={{ marginBottom: '1rem' }}>Historial de Notas Médicas</h3>
          
          {isLoadingNotas ? (
            <div style={{ textAlign: 'center', padding: '2rem' }} className="text-muted">Cargando notas...</div>
          ) : notas.length === 0 ? (
            <div style={{ padding: '3rem', textAlign: 'center', border: '2px dashed var(--border-light)', borderRadius: 'var(--radius-md)' }}>
              <p className="text-muted">No hay notas registradas para este expediente.</p>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              {notas.map((nota: any) => (
                <div key={nota.id} style={{ border: '1px solid var(--border-light)', padding: '1.5rem', borderRadius: 'var(--radius-md)', backgroundColor: 'var(--bg-app)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '1rem' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <CheckCircle size={18} color={nota.firmada ? "var(--success)" : "var(--text-muted)"} />
                      <strong>Nota de {nota.tipo_nota}</strong>
                    </div>
                    <span className="text-muted" style={{ fontSize: '0.85rem' }}>
                      {new Date(nota.creado_en).toLocaleString()}
                    </span>
                  </div>
                  
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1rem', fontSize: '0.9rem' }}>
                    <div>
                      <strong className="text-muted">Diagnóstico:</strong>
                      <p>{nota.contenido.diagnosticos?.[0] || 'N/A'}</p>
                    </div>
                    <div>
                      <strong className="text-muted">Signos Vitales:</strong>
                      <p>FC: {nota.signos_vitales?.frecuencia_cardiaca} | FR: {nota.signos_vitales?.frecuencia_respiratoria} | Temp: {nota.signos_vitales?.temperatura}°C</p>
                    </div>
                  </div>
                  
                  <div>
                    <strong className="text-muted">Evolución:</strong>
                    <p style={{ marginTop: '0.25rem', whiteSpace: 'pre-wrap', fontSize: '0.95rem' }}>
                      {nota.contenido.evolucion_y_actualizacion_cuadro || nota.contenido.contenido || JSON.stringify(nota.contenido)}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Side Panel para Notas Médicas */}
      <div style={{
        position: 'fixed',
        top: 0,
        right: isSidePanelOpen ? 0 : '-600px',
        width: '500px',
        height: '100vh',
        backgroundColor: 'var(--bg-card)',
        boxShadow: '-10px 0 30px rgba(0,0,0,0.1)',
        transition: 'right var(--transition-smooth)',
        zIndex: 1000,
        padding: '2rem',
        overflowY: 'auto'
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }}>
          <h2 style={{ margin: 0, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <FileSignature size={24} color="var(--primary)"/>
            Nota de Evolución
          </h2>
          <button className="btn btn-outline" style={{ padding: '0.5rem', border: 'none' }} onClick={() => setIsSidePanelOpen(false)}>
            <X size={24} />
          </button>
        </div>

        <div style={{ backgroundColor: 'var(--primary-light)', padding: '1rem', borderRadius: 'var(--radius-md)', marginBottom: '1.5rem', fontSize: '0.875rem' }}>
          <strong>Regla NOM-004:</strong> Las notas de evolución requieren obligatoriamente el registro de signos vitales, cuadro clínico, diagnósticos y tratamientos.
        </div>

        <form onSubmit={handleSubmitNota}>
          <h4 style={{ marginBottom: '1rem', color: 'var(--text-muted)' }}>Signos Vitales</h4>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1.5rem' }}>
            <div className="form-group">
              <label className="form-label">FC (lpm)</label>
              <input type="number" name="fc" className="form-input" required />
            </div>
            <div className="form-group">
              <label className="form-label">FR (rpm)</label>
              <input type="number" name="fr" className="form-input" required />
            </div>
            <div className="form-group">
              <label className="form-label">Temp (°C)</label>
              <input type="number" step="0.1" name="temp" className="form-input" required />
            </div>
            <div className="form-group">
              <label className="form-label">TA (ej. 120/80)</label>
              <input type="text" name="ta" className="form-input" placeholder="120/80" required />
            </div>
          </div>

          <h4 style={{ marginBottom: '1rem', color: 'var(--text-muted)' }}>Contenido Clínico</h4>
          <div className="form-group">
            <label className="form-label">Evolución y Actualización del Cuadro</label>
            <textarea name="evolucion" className="form-input" rows={4} required minLength={10} placeholder="Describa la evolución..."></textarea>
          </div>
          
          <div className="form-group">
            <label className="form-label">Diagnóstico Principal</label>
            <input type="text" name="diagnostico" className="form-input" required minLength={5} />
          </div>

          <div className="form-group">
            <label className="form-label">Plan / Tratamiento</label>
            <textarea name="tratamiento" className="form-input" rows={3} required minLength={5}></textarea>
          </div>

          <div style={{ marginTop: '3rem', display: 'flex', gap: '1rem' }}>
            <button type="button" className="btn btn-outline" style={{ flex: 1 }} onClick={() => setIsSidePanelOpen(false)}>Cancelar</button>
            <button type="submit" className="btn btn-primary" style={{ flex: 2 }} disabled={createNotaMutation.isPending}>
              {createNotaMutation.isPending ? 'Firmando...' : 'Firmar con KMS y Guardar'}
            </button>
          </div>
        </form>
      </div>
      
      {/* Backdrop for Side Panel */}
      {isSidePanelOpen && (
        <div 
          style={{ position: 'fixed', top: 0, left: 0, width: '100vw', height: '100vh', backgroundColor: 'rgba(0,0,0,0.2)', zIndex: 999 }}
          onClick={() => setIsSidePanelOpen(false)}
        />
      )}
    </div>
  );
}
