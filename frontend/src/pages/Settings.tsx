import { useQuery } from '@tanstack/react-query';
import { User, Shield, Key, CreditCard, Lock, CheckCircle2 } from 'lucide-react';
import { authApi } from '../services/api';
import { useToast } from '../hooks/useToast';

export default function Settings() {
  const { showToast } = useToast();

  const { data: profile, isLoading, isError } = useQuery({
    queryKey: ['profile'],
    queryFn: authApi.getProfile,
    retry: 1
  });

  const handlePasswordChange = () => {
    showToast("Funcionalidad deshabilitada en la versión de demostración.", "info");
  };

  return (
    <div style={{ maxWidth: '800px', margin: '0 auto' }}>
      <header style={{ marginBottom: '2rem' }}>
        <h1 className="page-title animate-fade-in" style={{ marginBottom: 0 }}>Configuración de la Clínica</h1>
        <p className="text-muted" style={{ marginTop: '0.5rem' }}>Gestiona tu perfil profesional y la seguridad de tus datos.</p>
      </header>

      {isLoading ? (
        <div style={{ textAlign: 'center', padding: '3rem' }}>Cargando perfil...</div>
      ) : isError ? (
        <div className="glass-card" style={{ textAlign: 'center', color: 'var(--error)' }}>
          No se pudo cargar la configuración. Verifica tu conexión.
        </div>
      ) : profile ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
          
          {/* Tarjeta de Perfil */}
          <div className="glass-card animate-fade-in" style={{ animationDelay: '0.1s' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1.5rem' }}>
              <div style={{ backgroundColor: 'var(--primary-light)', padding: '0.5rem', borderRadius: 'var(--radius-md)', color: 'var(--primary)' }}>
                <User size={24} />
              </div>
              <h2 style={{ fontSize: '1.25rem', margin: 0 }}>Perfil Profesional</h2>
            </div>
            
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '1.5rem', marginBottom: '2rem' }}>
              <div>
                <label className="text-muted" style={{ fontSize: '0.85rem', display: 'block', marginBottom: '0.25rem' }}>Nombre Completo</label>
                <div style={{ fontWeight: 500 }}>{profile.nombre_medico}</div>
              </div>
              <div>
                <label className="text-muted" style={{ fontSize: '0.85rem', display: 'block', marginBottom: '0.25rem' }}>Cédula Profesional</label>
                <div style={{ fontFamily: 'monospace', fontWeight: 600 }}>{profile.cedula}</div>
              </div>
              <div>
                <label className="text-muted" style={{ fontSize: '0.85rem', display: 'block', marginBottom: '0.25rem' }}>Especialidad</label>
                <div>{profile.especialidad || 'No especificada'}</div>
              </div>
              <div>
                <label className="text-muted" style={{ fontSize: '0.85rem', display: 'block', marginBottom: '0.25rem' }}>Correo Electrónico</label>
                <div>{profile.email}</div>
              </div>
            </div>

            <div style={{ borderTop: '1px solid var(--border-light)', paddingTop: '1.5rem', display: 'flex', justifyContent: 'flex-end' }}>
              <button className="btn btn-outline" onClick={handlePasswordChange}>
                <Lock size={18} />
                Cambiar Contraseña
              </button>
            </div>
          </div>

          {/* Tarjeta de Seguridad y Facturación */}
          <div className="glass-card animate-fade-in" style={{ animationDelay: '0.2s' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1.5rem' }}>
              <div style={{ backgroundColor: 'var(--success)', padding: '0.5rem', borderRadius: 'var(--radius-md)', color: 'white' }}>
                <Shield size={24} />
              </div>
              <h2 style={{ fontSize: '1.25rem', margin: 0 }}>Seguridad y Cumplimiento (NOM-004)</h2>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
              <div style={{ display: 'flex', alignItems: 'flex-start', gap: '1rem', padding: '1rem', backgroundColor: 'var(--bg-main)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-light)' }}>
                <Key size={24} color="var(--primary)" style={{ flexShrink: 0, marginTop: '0.25rem' }} />
                <div>
                  <h3 style={{ fontSize: '1rem', margin: '0 0 0.25rem 0', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    Cifrado de Base de Datos
                    <span className="badge badge-success" style={{ display: 'inline-flex', gap: '0.25rem', alignItems: 'center' }}>
                      <CheckCircle2 size={12} /> Activo
                    </span>
                  </h3>
                  <p className="text-muted" style={{ margin: '0 0 0.5rem 0', fontSize: '0.9rem' }}>
                    Todos los antecedentes y notas médicas de tus pacientes están encriptados con AES-256 (Envelope Encryption) asegurando el cumplimiento de privacidad.
                  </p>
                  <div style={{ fontFamily: 'monospace', fontSize: '0.85rem', color: 'var(--text-muted)', backgroundColor: 'var(--bg-card)', padding: '0.25rem 0.5rem', borderRadius: 'var(--radius-sm)', display: 'inline-block' }}>
                    KMS Key ID: {profile.seguridad.kms_key_id}
                  </div>
                </div>
              </div>

              <div style={{ display: 'flex', alignItems: 'flex-start', gap: '1rem', padding: '1rem', backgroundColor: 'var(--bg-main)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-light)' }}>
                <CreditCard size={24} color="var(--text-main)" style={{ flexShrink: 0, marginTop: '0.25rem' }} />
                <div>
                  <h3 style={{ fontSize: '1rem', margin: '0 0 0.25rem 0' }}>Suscripción Actual</h3>
                  <p className="text-muted" style={{ margin: 0, fontSize: '0.9rem' }}>
                    Plan <strong style={{ textTransform: 'capitalize' }}>{profile.plan}</strong>. Las opciones de facturación no están disponibles en este demo.
                  </p>
                </div>
              </div>
            </div>
          </div>

        </div>
      ) : null}
    </div>
  );
}
